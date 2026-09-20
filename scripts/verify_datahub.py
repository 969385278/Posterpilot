"""Paid-service-free integration proof. This is NOT an aesthetics benchmark.

PYTHONPATH=apps/api python scripts/verify_datahub.py --data-dir data/datahub-demo
The directory must be separate from production data; existing records are preserved.
"""

import argparse
import json
from pathlib import Path
from time import perf_counter

from fastapi.testclient import TestClient

from app.datahub_demo import create_app as create_demo_app


def verify(root: Path) -> dict:
    started = perf_counter()
    checks = {}
    app = create_demo_app(root)
    with TestClient(app) as client:

        def post(path, payload):
            response = client.post(path, json=payload)
            assert response.status_code < 300, response.text
            return response.json()

        def generate(title, memory):
            created = post(
                "/api/v1/runs",
                {
                    "title": title,
                    "poster_type": "cultural_event",
                    "notes": "标题不醒目，保持克制",
                    "use_case_memory": memory,
                    "attention_layout": False,
                },
            )
            run_id = created["id"]
            pending = client.get(f"/api/v1/runs/{run_id}/pending")
            assert pending.status_code == 200, client.get(f"/api/v1/runs/{run_id}").text
            return run_id

        source_run = generate("春日诗会", False)
        post(
            f"/api/v1/runs/{source_run}/decisions",
            {
                "action": "instruct",
                "expected_round_number": 0,
                "instruction": "标题不醒目，增强标题",
                "controls": {
                    "adjustments": [
                        {
                            "trait": "title_emphasis",
                            "direction": "strengthen",
                            "strength": 0.1,
                        }
                    ]
                },
            },
        )
        pending = client.get(f"/api/v1/runs/{source_run}/pending").json()
        assert pending["round_number"] == 1
        post(
            f"/api/v1/runs/{source_run}/decisions",
            {"action": "finish", "expected_round_number": 1},
        )
        candidates = client.get(f"/api/v1/datahub/cases?run_id={source_run}").json()
        assert len(candidates) == 2
        checks["round_evidence_auto_captured"] = True
        assert all(item["feedback"]["verdict"] == "unknown" for item in candidates)
        checks["finish_does_not_infer_acceptance"] = True
        case = next(item for item in candidates if item["round_number"] == 1)
        assert case["evidence"]["after"]["tool_traces"]
        checks["actions_and_before_after_preserved"] = True
        case["notes"].update(
            {
                "title": "短标题层级调整 · 离线演示",
                "styles": ["克制"],
                "problem": "标题不醒目",
                "lesson": "先检查标题实际渲染字号与对比度，在当前文字框可容纳时适度提高字号。保留活动事实。",
                "applicable_when": "文化活动竖版海报，四至六字短标题，标题排版未锁定。",
                "avoid_when": "长标题或狭窄文字框可能溢出；文字锁定时不修改。不是固定增加百分比。",
                "rights": "own_or_authorized",
                "rights_note": "程序绘制测试素材与虚构活动，仅用于验证软件流程。",
            }
        )
        response = client.put(
            f"/api/v1/datahub/cases/{case['id']}",
            json={
                "expected_revision": case["revision"],
                "notes": case["notes"],
                "feedback": {
                    "verdict": "accepted",
                    "source": "demo_fixture",
                    "comment": "模拟验收接受，只验证数据流；不是实际用户反馈。",
                },
            },
        )
        assert response.status_code == 200, response.text
        case = response.json()
        quality = client.get(f"/api/v1/datahub/cases/{case['id']}/quality").json()
        assert quality["issues"] == [], quality
        case = post(
            f"/api/v1/datahub/cases/{case['id']}/review",
            {
                "expected_revision": case["revision"],
                "action": "approve",
                "note": "离线测试审核，只确认数据与适用条件完整。",
            },
        )
        checks["explicit_review_required"] = case["status"] == "approved"
        probe = {
            "query": "标题不醒目",
            "poster_type": "cultural_event",
            "include_demo": True,
        }
        matches = post("/api/v1/datahub/retrieve", probe)["matches"]
        assert matches
        assert all(
            item["case_id"] != case["id"]
            for item in post(
                "/api/v1/datahub/retrieve", {**probe, "exclude_run_id": source_run}
            )["matches"]
        )
        checks["exclude_current_run"] = True
        assert all(
            item["origin"] != "offline_demo"
            for item in post(
                "/api/v1/datahub/retrieve", {**probe, "include_demo": False}
            )["matches"]
        )
        checks["demo_not_used_in_normal_retrieval"] = True
        baseline_run = generate("秋日读诗", False)
        enabled_run = generate("秋日读诗", True)
        references = {}
        for label, run_id in (("disabled", baseline_run), ("enabled", enabled_run)):
            evidence = client.get(
                f"/api/v1/runs/{run_id}/artifacts/experience_round_0.json"
            ).json()
            references[label] = evidence["experience_references"]
        assert not references["disabled"] and references["enabled"]
        checks["generation_reference_on_off"] = True
        post(
            f"/api/v1/runs/{enabled_run}/decisions",
            {
                "action": "instruct",
                "expected_round_number": 0,
                "instruction": "标题不醒目，保持所有文字内容",
            },
        )
        optimized = client.get(
            f"/api/v1/runs/{enabled_run}/artifacts/experience_round_1.json"
        ).json()
        assert optimized["experience_references"]
        assert optimized["brief"]["title"] == "秋日读诗"
        checks["optimization_receives_references_without_copying_source_title"] = True
        # Verify withdrawal using current case revision, then re-publish to leave a useful demo.
        withdrawn = post(
            f"/api/v1/datahub/cases/{case['id']}/review",
            {
                "expected_revision": case["revision"],
                "action": "withdraw",
                "note": "测试撤回即时生效。",
            },
        )
        assert not any(
            item["case_id"] == case["id"]
            for item in post("/api/v1/datahub/retrieve", probe)["matches"]
        )
        checks["withdrawal_removes_new_retrieval"] = True
        assert references["enabled"]  # saved reference evidence still exists
        post(
            f"/api/v1/datahub/cases/{case['id']}/review",
            {
                "expected_revision": withdrawn["revision"],
                "action": "approve",
                "note": "恢复离线展示样例。",
            },
        )
        repeated = post(f"/api/v1/datahub/capture/{source_run}", {})
        assert (
            len(repeated) == 2
            and next(item for item in repeated if item["id"] == case["id"])["status"]
            == "approved"
        )
        checks["recapture_keeps_review"] = True
        # Frozen held-out retrieval probes: different problem and different domain must not be forced to match.
        probes = []
        for text, kind, expected in [
            ("标题不醒目", "cultural_event", True),
            ("提高标题字号", "cultural_event", True),
            ("量子纠缠研究", "cultural_event", False),
            ("标题不醒目", "club_recruitment", False),
        ]:
            found = post(
                "/api/v1/datahub/retrieve",
                {**probe, "query": text, "poster_type": kind},
            )["matches"]
            passed = bool(found) == expected
            probes.append(
                {
                    "query": text,
                    "poster_type": kind,
                    "expected_match": expected,
                    "matches": len(found),
                    "passed": passed,
                }
            )
        checks["fixed_retrieval_probes"] = all(item["passed"] for item in probes)
        assert all(checks.values()), checks
    # Reopen the app/database and confirm persistence independently of the prior process objects.
    with TestClient(create_demo_app(root)) as restored:
        assert (
            restored.get(f"/api/v1/datahub/cases/{case['id']}").json()["status"]
            == "approved"
        )
        assert (
            restored.get(f"/api/v1/datahub/cases/{case['id']}/image").status_code == 200
        )
    checks["restart_persistence"] = True
    summary = {
        "kind": "offline_functional_verification",
        "paid_model_calls": 0,
        "quality_improvement_claim": False,
        "real_user_feedback_collected": False,
        "checks": checks,
        "retrieval_probes": probes,
        "elapsed_seconds": round(perf_counter() - started, 2),
        "source_run_id": source_run,
        "baseline_run_id": baseline_run,
        "enabled_run_id": enabled_run,
        "case_id": case["id"],
        "reference_counts": {key: len(value) for key, value in references.items()},
        "note": "固定模型决策与程序图片，只证明流程、审核和参考传递，不证明真实模型效果提升。",
    }
    root.mkdir(parents=True, exist_ok=True)
    (root / "verification.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-dir", type=Path, default=Path("data/datahub-verification")
    )
    args = parser.parse_args()
    print(json.dumps(verify(args.data_dir.resolve()), ensure_ascii=False, indent=2))
