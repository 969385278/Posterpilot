"""Render three reviewed-source walkthroughs; publishing requires hash-matched visual review."""

import argparse
import hashlib
import json
from pathlib import Path
from uuid import UUID

from app.core.paths import PROJECT_ROOT
from app.showcase import create_app, reviewed_media
from fastapi.testclient import TestClient


def save(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def prepare(root: Path, *, regenerate=False):
    target = root / "showcase-report.json"
    if target.is_file() and not regenerate:
        print(f"Existing showcase retained: {target}. Use --regenerate for new runs.")
        return json.loads(target.read_text(encoding="utf-8"))
    scenarios = json.loads(
        (PROJECT_ROOT / "data/showcase/scenarios.json").read_text(encoding="utf-8")
    )
    assets = reviewed_media()
    public = PROJECT_ROOT / "apps/web/public/showcase"
    public.mkdir(parents=True, exist_ok=True)
    entries = []
    app = create_app(root)
    with TestClient(app) as client:

        def request(method, url, data=None):
            response = client.request(method, url, json=data)
            if response.status_code >= 300:
                raise RuntimeError(response.text)
            return response.json()

        for scenario in scenarios:
            asset = assets[scenario["id"]]
            source = {key: value for key, value in asset.items() if key != "path"}
            run = request("POST", "/api/v1/runs", scenario["brief"])
            run_id = run["id"]
            pending = request("GET", f"/api/v1/runs/{run_id}/pending")
            assert pending["round_number"] == 0
            request(
                "POST",
                f"/api/v1/runs/{run_id}/decisions",
                {
                    "action": "instruct",
                    "expected_round_number": 0,
                    "instruction": scenario["instruction"],
                },
            )
            pending = request("GET", f"/api/v1/runs/{run_id}/pending")
            assert pending["round_number"] == 1
            request(
                "POST",
                f"/api/v1/runs/{run_id}/decisions",
                {"action": "finish", "expected_round_number": 1},
            )
            service = app.state.run_service
            uid = UUID(run_id)
            record = service.artifacts.write_json(uid, "media_source.json", source)
            service.repository.add_artifact(uid, record)
            evidence = request(
                "GET", f"/api/v1/runs/{run_id}/artifacts/experience_round_1.json"
            )
            images = {}
            hashes = {}
            for label, name in (
                ("initial", "poster_initial.png"),
                ("optimized", "poster_round_1.png"),
            ):
                raw = service.artifact_path(uid, name).read_bytes()
                filename = f"{scenario['id']}-{label}.png"
                (public / filename).write_bytes(raw)
                images[label] = f"/showcase/{filename}"
                hashes[label] = hashlib.sha256(raw).hexdigest()
            cases = request("GET", f"/api/v1/datahub/cases?run_id={run_id}")
            case = next(value for value in cases if value["round_number"] == 1)
            notes = {
                **case["notes"],
                "title": scenario["title"] + " · 授权素材排版演示",
                "problem": "时间地点字号较小",
                "lesson": scenario["lesson"],
                "applicable_when": scenario["applicable_when"],
                "avoid_when": scenario["avoid_when"],
                "rights": "own_or_authorized",
                "rights_note": f"公共领域背景：{source['source_url']}；中文使用随项目 OFL 字体，活动事实为自拟虚构示例。",
            }
            case = request(
                "PUT",
                f"/api/v1/datahub/cases/{case['id']}",
                {
                    "expected_revision": case["revision"],
                    "notes": notes,
                    "feedback": {
                        "verdict": "unknown",
                        "source": "not_collected",
                        "comment": "",
                    },
                },
            )
            entry = {
                **scenario,
                "run_id": run_id,
                "case_id": case["id"],
                "source": source,
                "images": images,
                "image_hashes": hashes,
                "case_status": case["status"],
                "comparison": case["evidence"]["comparison"],
                "quality_issues": request(
                    "GET", f"/api/v1/datahub/cases/{case['id']}/quality"
                )["issues"],
                "tool_traces": evidence["tool_traces"],
                "goal_verification": evidence["goal_verification"],
                "evaluation": evidence["evaluation"],
            }
            entries.append(entry)
    report = {
        "kind": "reviewed_source_render_walkthrough",
        "paid_model_calls": 0,
        "real_user_feedback": False,
        "quality_improvement_claim": False,
        "notice": "公共领域背景 + 本项目中文排版与实际工具调整；规划固定，非生图大模型输出，活动为虚构示例。",
        "entries": entries,
    }
    save(target, report)
    save(public / "index.json", report)
    # The frontend imports this generated manifest; the scenarios remain the sole authored source.
    save(PROJECT_ROOT / "apps/web/src/data/showcase.json", report)
    print(
        f"Rendered {len(entries)} scenarios / {len(entries) * 2} posters; feedback remains unknown."
    )
    return report


def publish_reviewed(root: Path):
    report_path = root / "showcase-report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    reviews = json.loads(
        (PROJECT_ROOT / "data/showcase/reviewed-results.json").read_text(
            encoding="utf-8"
        )
    )
    with TestClient(create_app(root)) as client:
        for entry in report["entries"]:
            review = next((r for r in reviews if r["id"] == entry["id"]), None)
            if (
                not review
                or review["image_sha256"] != entry["image_hashes"]["optimized"]
            ):
                raise ValueError(f"Missing matching visual review: {entry['id']}")
            case = client.get(f"/api/v1/datahub/cases/{entry['case_id']}").json()
            if review["decision"] == "approve" and case["status"] != "approved":
                response = client.post(
                    f"/api/v1/datahub/cases/{case['id']}/review",
                    json={
                        "expected_revision": case["revision"],
                        "action": "approve",
                        "note": review["note"],
                    },
                )
                if response.status_code != 200:
                    raise ValueError(response.text)
                case = response.json()
            entry["case_status"] = case["status"]
            entry["visual_review"] = review
    save(report_path, report)
    save(PROJECT_ROOT / "apps/web/public/showcase/index.json", report)
    save(PROJECT_ROOT / "apps/web/src/data/showcase.json", report)
    print("Hash-matched visual reviews applied; no user acceptance fabricated.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-dir", type=Path, default=PROJECT_ROOT / "data/reviewed-showcase"
    )
    parser.add_argument("--regenerate", action="store_true")
    parser.add_argument("--publish-reviewed", action="store_true")
    args = parser.parse_args()
    if args.publish_reviewed:
        publish_reviewed(args.data_dir)
    else:
        prepare(args.data_dir, regenerate=args.regenerate)
