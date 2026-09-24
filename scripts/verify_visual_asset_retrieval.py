"""Real local Ollama smoke check. Not a held-out benchmark or a business metric."""

import argparse
import base64
import hashlib
import json
from pathlib import Path
from uuid import uuid4

from app.core.paths import PROJECT_ROOT
from app.providers.embedding.asset_ollama import AssetOllamaEmbeddings
from app.rag.case_repository import CaseRepository
from app.schemas.visual_asset import (
    AssetMetadata,
    AssetReview,
    AssetSearch,
    AssetSource,
)
from app.services.visual_assets import VisualAssetService


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:11434")
    parser.add_argument("--model", default="bge-m3")
    parser.add_argument("--output-root", type=Path, default=PROJECT_ROOT / "work")
    args = parser.parse_args()
    root = args.output_root / f"visual-asset-smoke-{uuid4().hex[:12]}"
    provider = AssetOllamaEmbeddings(
        model=args.model, base_url=args.base_url, timeout_seconds=120
    )
    assets = VisualAssetService(root / "assets", embeddings=provider)
    catalog = CaseRepository()
    inputs = []
    for case_id in ("commons-128994779", "commons-31912550", "commons-31824857"):
        case = catalog.get(case_id)
        image = catalog.image_path(case_id).read_bytes()
        if hashlib.sha256(image).hexdigest() != case.source.image_sha256:
            raise ValueError(f"Source image changed: {case_id}")
        item = assets.upload(
            base64.b64encode(image).decode(),
            AssetMetadata(
                title=case.title,
                description="；".join(case.features.values()),
                composition=case.features["composition"],
                styles=case.styles,
                scenarios=["cultural_event"],
                cautions="；".join(case.cautions),
            ),
            AssetSource(
                origin="external",
                creator=case.source.creator,
                source_url=case.source.source_url,
                rights=case.source.rights,
            ),
        )["asset"]
        item = assets.review(
            item["id"],
            AssetReview(
                expected_revision=item["revision"],
                action="approve",
                rights_confirmed=True,
                reviewer="自动化检索验证，非人工业务审批",
                note="独立测试目录复用仓库已有授权参考；不改变正式数据",
            ),
        )
        inputs.append({"catalog_id": case_id, "asset": item})
    index = assets.index()
    queries = ["太空探险爱好者的聚会", "在水中锻炼身体的课程", "开学后一起阅读文学作品"]
    results = [
        assets.search(AssetSearch(query=query, scenario="cultural_event"))
        for query in queries
    ]
    report = {
        "kind": "real-ollama-smoke-not-benchmark",
        "inputs": inputs,
        "index": index,
        "results": results,
        "limitations": "Three curated smoke queries, not independently labelled or held out. No recall/accuracy claim.",
    }
    path = root / "report.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "report": str(path),
                "index": index,
                "queries": [
                    {
                        "query": result["query"]["query"],
                        "mode": result["mode"],
                        "fallback": result["fallback_reason"],
                        "matches": [
                            {"title": item["title"], "reason": item["reason"]}
                            for item in result["matches"]
                        ],
                    }
                    for result in results
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    if any(result["mode"] != "hybrid" for result in results):
        raise RuntimeError("Real semantic provider check did not succeed; see report")


if __name__ == "__main__":
    main()
