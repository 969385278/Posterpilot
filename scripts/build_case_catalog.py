"""Combine manually reviewed features with downloaded immutable provenance."""
import hashlib
import html
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/api"))
from app.schemas.poster_case import PosterCase

ALLOWED_LICENSES = {"Public domain", "CC0", "CC BY 4.0", "CC BY-SA 4.0", "CC BY 3.0", "CC BY-SA 3.0"}


def build(root: Path) -> list[dict]:
    features = json.loads((root / "reviewed_features.json").read_text(encoding="utf-8"))
    catalog = []
    for feature in features:
        item = dict(feature)
        page_id = item.pop("page_id")
        case_id = f"commons-{page_id}"
        record = json.loads((root / "sources" / f"{case_id}.json").read_text(encoding="utf-8"))
        page = record["response"]
        info = page["imageinfo"][0]
        metadata = info["extmetadata"]
        license_name = metadata["LicenseShortName"]["value"]
        if license_name not in ALLOWED_LICENSES:
            raise ValueError(f"Unexpected rights for {case_id}")
        image_asset = record.get("image_asset", f"{case_id}.jpg")
        digest = hashlib.sha256((root / "images" / image_asset).read_bytes()).hexdigest()
        if digest != record["image_sha256"]:
            raise ValueError(f"Image hash mismatch: {case_id}")
        creator = html.unescape(re.sub(r"<[^>]*>", "", metadata.get("Artist", {}).get("value", "作者未确认"))).strip()
        item.update(id=case_id, original_title=page["title"].removeprefix("File:"),
                    image_asset=image_asset, status="curated",
                    analysis_basis="assistant_visual_review", user_acceptance="pending",
                    source={"creator": creator, "institution": "Wikimedia Commons（原始机构见来源页）",
                            "source_url": info["descriptionurl"], "image_url": record["image_url"],
                            "rights": ("来源页标注 Public domain；保留原作者、原机构与条目权利说明，商用需核对适用地区。"
                                       if license_name == "Public domain" else
                                       f"{license_name}；署名见 creator，原图按原许可提供，未修改图像内容。改编需遵守原许可；机构标志不表示背书。"),
                            "rights_url": metadata.get("LicenseUrl", {}).get("value") or info["descriptionurl"] + "#Licensing",
                            "retrieved_at": record["retrieved_at"], "image_sha256": digest})
        catalog.append(PosterCase.model_validate(item).model_dump(mode="json"))
    if len({item["id"] for item in catalog}) != len(catalog):
        raise ValueError("Duplicate reviewed case")
    return catalog


if __name__ == "__main__":
    root = ROOT / "data/knowledge/cases"
    catalog = build(root)
    (root / "catalog.json").write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Built {len(catalog)} visually reviewed cases; user acceptance remains pending.")
