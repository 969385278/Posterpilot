"""Local release governance bound to code and server-generated regression evidence."""

import hashlib
import importlib.metadata
import json
import os
import re
import sqlite3
import subprocess
import sys
import xml.etree.ElementTree as ET
from contextlib import contextmanager
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from uuid import UUID, uuid4

from app.agent.tools.catalog import BASE_TOOLS, DESCRIPTIONS, tool_definition
from app.core.exceptions import PosterPilotError
from app.core.paths import PROJECT_ROOT
from app.schemas.tool_release import GapTriageRequest, ToolReviewRequest

GATE_PATHS = (
    "apps/api/tests/poster",
    "apps/api/tests/evaluation",
    "apps/api/tests/agent/test_react_tools.py",
    "apps/api/tests/agent/test_rendering_nodes.py",
    "apps/api/tests/agent/test_initial_text_colors.py",
    "apps/api/tests/agent/test_controlled_design.py",
    "apps/api/tests/harness/test_tool_contracts.py",
)


def now() -> str:
    return datetime.now(UTC).isoformat()


@lru_cache(maxsize=4096)
def _file_digest(path: str, modified: int, changed: int, size: int) -> bytes:
    return hashlib.sha256(Path(path).read_bytes()).digest()


class ToolHarness:
    def __init__(self, root: Path, hub):
        self.root = root
        self.hub = hub
        root.mkdir(parents=True, exist_ok=True)
        self.path = root / "harness.sqlite3"
        self.loaded_fingerprint = self.fingerprint()
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS tool_releases (
                    name TEXT PRIMARY KEY, revision INTEGER NOT NULL, payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS validation_reports (
                    id TEXT PRIMARY KEY, state TEXT NOT NULL, payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS capability_gaps (
                    id TEXT PRIMARY KEY, revision INTEGER NOT NULL, payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS gap_observations (
                    id TEXT PRIMARY KEY, gap_id TEXT NOT NULL, payload TEXT NOT NULL);
            """)

    @contextmanager
    def connect(self, *, write=False):
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        try:
            with db:
                db.execute("BEGIN IMMEDIATE" if write else "BEGIN")
                yield db
        finally:
            db.close()

    @staticmethod
    def fingerprint() -> str:
        digest = hashlib.sha256()
        paths = set((PROJECT_ROOT / "apps/api/app").rglob("*.py"))
        paths.update((PROJECT_ROOT / "apps/api/tests").rglob("*.py"))
        paths.update((PROJECT_ROOT / "data/templates").rglob("*.json"))
        paths.update((PROJECT_ROOT / "data/templates").rglob("*.yaml"))
        paths.update((PROJECT_ROOT / "data/templates").rglob("*.yml"))
        paths.update(
            path
            for path in (PROJECT_ROOT / "data/fonts/open-source").rglob("*")
            if path.suffix.lower() in {".ttf", ".otf"}
        )
        paths.add(PROJECT_ROOT / "apps/api/pyproject.toml")
        for path in sorted(paths):
            digest.update(path.relative_to(PROJECT_ROOT).as_posix().encode())
            stat = path.stat()
            digest.update(_file_digest(str(path), stat.st_mtime_ns, stat.st_ctime_ns, stat.st_size))
        digest.update(json.dumps(GATE_PATHS).encode())
        for package in ("pillow", "pydantic", "langgraph", "pytest", "sqlalchemy"):
            digest.update(f"{package}={importlib.metadata.version(package)}".encode())
        digest.update(sys.version.encode())
        return digest.hexdigest()

    def catalog(self) -> list[dict]:
        fingerprint = self.fingerprint()
        with self.connect() as db:
            rows = {
                row["name"]: json.loads(row["payload"])
                for row in db.execute("SELECT * FROM tool_releases")
            }
        result = []
        for name in sorted(DESCRIPTIONS):
            release = rows.get(name)
            status = (
                release["status"] if release else "bundled" if name in BASE_TOOLS else "candidate"
            )
            if status == "published" and (
                release["fingerprint"] != fingerprint or fingerprint != self.loaded_fingerprint
            ):
                status = "stale"
            result.append(
                {
                    **tool_definition(name),
                    "status": status,
                    "enabled": status in {"published", "bundled"},
                    "revision": release["revision"] if release else 0,
                    "fingerprint": fingerprint,
                    "release": release,
                }
            )
        return result

    def public_catalog(self) -> list[dict]:
        return [
            {
                key: item[key]
                for key in ("name", "description", "parameters", "revision", "fingerprint")
            }
            for item in self.catalog()
            if item["enabled"]
        ]

    def authorization(self, name: str) -> dict:
        item = next((item for item in self.catalog() if item["name"] == name), None)
        if not item or not item["enabled"]:
            raise PosterPilotError(
                "工具未发布、已撤回或代码已变化，需重新验证发布",
                code="tool_not_published",
                status_code=409,
            )
        return {key: item[key] for key in ("name", "revision", "fingerprint", "status")}

    def start_validation(self, name: str) -> dict:
        if name not in DESCRIPTIONS:
            raise PosterPilotError("未注册的工具", code="unknown_tool", status_code=404)
        report = {
            "id": str(uuid4()),
            "tool": name,
            "state": "queued",
            "fingerprint": self.fingerprint(),
            "created_at": now(),
            "gate_paths": list(GATE_PATHS),
            "schema": tool_definition(name)["parameters"],
        }
        with self.connect(write=True) as db:
            running = db.execute(
                "SELECT id FROM validation_reports WHERE state IN ('queued','running')"
            ).fetchone()
            if running:
                raise PosterPilotError(
                    "已有回归任务，请等待完成；进程中断后可取消旧任务再重试",
                    code="validation_busy",
                    status_code=409,
                )
            db.execute(
                "INSERT INTO validation_reports VALUES(?,?,?)",
                (report["id"], report["state"], json.dumps(report, ensure_ascii=False)),
            )
        return report

    def report(self, report_id: UUID | str) -> dict:
        with self.connect() as db:
            row = db.execute(
                "SELECT payload FROM validation_reports WHERE id=?", (str(report_id),)
            ).fetchone()
        if row is None:
            raise PosterPilotError("测试报告不存在", code="report_not_found", status_code=404)
        return json.loads(row[0])

    def reports(self) -> list[dict]:
        with self.connect() as db:
            rows = db.execute("SELECT payload FROM validation_reports ORDER BY rowid DESC LIMIT 50")
            return [json.loads(row[0]) for row in rows]

    def cancel_validation(self, report_id: UUID) -> dict:
        report = self.report(report_id)
        if report["state"] not in {"queued", "running"}:
            raise PosterPilotError("该任务已结束", code="validation_finished", status_code=409)
        report.update(state="cancelled", completed_at=now())
        self._save_report(report, expected={"queued", "running"})
        return report

    def _save_report(self, report: dict, *, expected: set[str]) -> bool:
        with self.connect(write=True) as db:
            row = db.execute(
                "SELECT state FROM validation_reports WHERE id=?", (report["id"],)
            ).fetchone()
            if row is None or row["state"] not in expected:
                return False
            db.execute(
                "UPDATE validation_reports SET state=?,payload=? WHERE id=?",
                (report["state"], json.dumps(report, ensure_ascii=False), report["id"]),
            )
        return True

    def run_validation(self, report_id: str) -> None:
        report = self.report(report_id)
        report.update(state="running", started_at=now())
        if not self._save_report(report, expected={"queued"}):
            return
        directory = self.root / report_id
        directory.mkdir(parents=True, exist_ok=True)
        xml_path = directory / "junit.xml"
        command = [
            sys.executable,
            "-m",
            "pytest",
            *GATE_PATHS,
            "-q",
            "-o",
            "addopts=",
            f"--junitxml={xml_path}",
        ]
        environment = {**os.environ, "POSTERPILOT_ENV": "test", "PYTHONIOENCODING": "utf-8"}
        environment.pop("PYTEST_ADDOPTS", None)
        try:
            result = subprocess.run(
                command,
                cwd=PROJECT_ROOT,
                env=environment,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=180,
            )
            log = result.stdout + result.stderr
            (directory / "test.log").write_text(log, encoding="utf-8")
            suite = ET.parse(xml_path).getroot()
            cases = list(suite.iter("testcase"))
            failures = sum(
                len(case.findall("failure")) + len(case.findall("error")) for case in cases
            )
            skipped = sum(len(case.findall("skipped")) for case in cases)
            tests = len(cases)
            unchanged = report["fingerprint"] == self.fingerprint()
            passed = (
                result.returncode == 0
                and tests > 0
                and failures == 0
                and skipped == 0
                and unchanged
            )
            report.update(
                state="passed" if passed else "failed",
                tests=tests,
                failures=failures,
                skipped=skipped,
                returncode=result.returncode,
                code_unchanged=unchanged,
                test_cases=[f"{case.get('classname')}.{case.get('name')}" for case in cases],
                log_tail=log[-12000:],
            )
        except Exception as error:
            report.update(state="failed", error=f"{type(error).__name__}: {error}")
        report["completed_at"] = now()
        self._save_report(report, expected={"running"})

    def review(self, name: str, request: ToolReviewRequest) -> dict:
        if name not in DESCRIPTIONS:
            raise PosterPilotError("未注册的工具", code="unknown_tool", status_code=404)
        fingerprint = self.fingerprint()
        report = None
        if request.action == "publish":
            if fingerprint != self.loaded_fingerprint:
                raise PosterPilotError(
                    "运行进程加载的是旧代码，请重启 API 后再发布",
                    code="runtime_code_stale",
                    status_code=409,
                )
            if not request.implementation_reviewed or not request.report_id:
                raise PosterPilotError(
                    "需确认实现审查并选择回归报告", code="review_required", status_code=422
                )
            report = self.report(request.report_id)
            if (
                report["tool"] != name
                or report["state"] != "passed"
                or report["fingerprint"] != fingerprint
            ):
                raise PosterPilotError(
                    "报告未通过或与当前实现不匹配", code="release_gate_failed", status_code=422
                )
        with self.connect(write=True) as db:
            row = db.execute("SELECT * FROM tool_releases WHERE name=?", (name,)).fetchone()
            revision = row["revision"] if row else 0
            if revision != request.expected_revision:
                raise PosterPilotError(
                    "发布记录已变化，请刷新", code="stale_release", status_code=409
                )
            old = json.loads(row["payload"]) if row else {}
            release = {
                "name": name,
                "revision": revision + 1,
                "status": "published" if request.action == "publish" else "withdrawn",
                "fingerprint": fingerprint,
                "report_id": str(request.report_id) if report else None,
                "reviewer": request.reviewer,
                "note": request.note,
                "audit": [
                    *old.get("audit", []),
                    {
                        "action": request.action,
                        "revision": revision + 1,
                        "at": now(),
                        "reviewer": request.reviewer,
                        "note": request.note,
                        "fingerprint": fingerprint,
                        "report_id": report["id"] if report else None,
                    },
                ],
            }
            db.execute(
                "INSERT INTO tool_releases VALUES(?,?,?) ON CONFLICT(name) DO UPDATE "
                "SET revision=excluded.revision,payload=excluded.payload",
                (name, release["revision"], json.dumps(release, ensure_ascii=False)),
            )
        return release

    def collect(self) -> dict:
        added = 0
        for case in self.hub.repository.list():
            after = case.evidence["after"]
            observations = []
            for index, trace in enumerate(after.get("tool_traces", [])):
                if not trace.get("success"):
                    detail = trace.get("observation", "工具执行失败")
                    signature = hashlib.sha256(
                        re.sub(r"\d+(?:\.\d+)?", "#", detail).encode()
                    ).hexdigest()[:12]
                    observations.append(
                        (
                            f"tool:{index}",
                            f"tool:{trace['tool_name']}#{signature}",
                            detail,
                        )
                    )
            for check in (after.get("goal_verification") or {}).get("checks", []):
                if check.get("status") in {"failed", "unavailable"}:
                    observations.append(
                        (
                            f"check:{check['key']}#{check['status']}",
                            f"check:{check['key']}#{check['status']}",
                            check.get("detail", "目标未确认达成"),
                        )
                    )
            if case.feedback.verdict == "rejected":
                feedback_key = hashlib.sha256(case.feedback.comment.encode()).hexdigest()
                observations.append(
                    (f"feedback:{feedback_key}", "user_rejected", case.feedback.comment)
                )
            for key, signature, detail in observations:
                origin = case.origin
                gap_id = hashlib.sha256(f"{origin}:{signature}".encode()).hexdigest()[:24]
                occurrence = hashlib.sha256(
                    f"{case.id}:{case.evidence_hash}:{key}".encode()
                ).hexdigest()
                observation = {
                    "id": occurrence,
                    "case_id": str(case.id),
                    "run_id": str(case.run_id),
                    "source_revision": case.revision,
                    "evidence_hash": case.evidence_hash,
                    "origin": origin,
                    "detail": detail,
                    "signature": signature,
                }
                with self.connect(write=True) as db:
                    if db.execute(
                        "SELECT id FROM gap_observations WHERE id=?", (occurrence,)
                    ).fetchone():
                        continue
                    gap_row = db.execute(
                        "SELECT payload FROM capability_gaps WHERE id=?", (gap_id,)
                    ).fetchone()
                    gap = (
                        json.loads(gap_row[0])
                        if gap_row
                        else {
                            "id": gap_id,
                            "revision": 0,
                            "category": "unclassified",
                            "status": "open",
                            "signature": signature,
                            "origin": origin,
                            "audit": [],
                            "occurrences": 0,
                        }
                    )
                    gap.update(
                        revision=gap["revision"] + 1,
                        occurrences=gap["occurrences"] + 1,
                        status="open",
                        last_observed_at=now(),
                    )
                    db.execute(
                        "INSERT INTO capability_gaps VALUES(?,?,?) ON CONFLICT(id) DO UPDATE "
                        "SET revision=excluded.revision,payload=excluded.payload",
                        (gap_id, gap["revision"], json.dumps(gap, ensure_ascii=False)),
                    )
                    db.execute(
                        "INSERT INTO gap_observations VALUES(?,?,?)",
                        (occurrence, gap_id, json.dumps(observation, ensure_ascii=False)),
                    )
                    added += 1
        return {"new_observations": added, "gaps": self.gaps()}

    def gaps(self) -> list[dict]:
        with self.connect() as db:
            values = [
                json.loads(row[0]) for row in db.execute("SELECT payload FROM capability_gaps")
            ]
            for gap in values:
                gap["observations"] = [
                    json.loads(row[0])
                    for row in db.execute(
                        "SELECT payload FROM gap_observations WHERE gap_id=?", (gap["id"],)
                    )
                ]
        for gap in values:
            if gap["status"] != "resolved":
                continue
            evidence = gap["audit"][-1]
            try:
                references = evidence.get("resolution_sources") or [{
                    "case_id": evidence["resolution_case_id"],
                    "revision": evidence["resolution_revision"],
                }]
                sources = []
                for reference in references:
                    source = self.hub.repository.get(UUID(reference["case_id"]))
                    sources.append(source)
                    if (
                        source.status != "approved"
                        or source.revision != reference["revision"]
                        or self.hub.quality_issues(source)
                    ):
                        gap["status"] = "resolution_stale"
                # Old single-source approvals must satisfy the same coverage rule.
                if gap["signature"].startswith("run:") and not all(
                    any(
                        item.get("brief") is not None
                        and item["brief"] == source.evidence["after"].get("brief")
                        for source in sources
                    )
                    for item in gap["observations"]
                ):
                    gap["status"] = "resolution_stale"
            except PosterPilotError:
                gap["status"] = "resolution_stale"
        return sorted(values, key=lambda item: (-item["occurrences"], item["id"]))

    def record_run_failure(self, run, *, origin: str) -> bool:
        if run.status != "failed":
            return False
        detail = run.error_message or "任务执行失败，没有更多诊断"
        normalized = re.sub(r"\d+(?:\.\d+)?", "#", detail)
        signature = f"run:{run.error_code}#" + hashlib.sha256(normalized.encode()).hexdigest()[:12]
        gap_id = hashlib.sha256(f"{origin}:{signature}".encode()).hexdigest()[:24]
        key = hashlib.sha256(f"{run.id}:{signature}".encode()).hexdigest()
        observation = {
            "id": key,
            "run_id": str(run.id),
            "case_id": None,
            "origin": origin,
            "detail": detail,
            "signature": signature,
            "brief": run.brief.model_dump(mode="json"),
        }
        with self.connect(write=True) as db:
            if db.execute("SELECT id FROM gap_observations WHERE id=?", (key,)).fetchone():
                return False
            row = db.execute("SELECT payload FROM capability_gaps WHERE id=?", (gap_id,)).fetchone()
            gap = (
                json.loads(row[0])
                if row
                else {
                    "id": gap_id,
                    "revision": 0,
                    "occurrences": 0,
                    "category": "unclassified",
                    "signature": signature,
                    "origin": origin,
                    "audit": [],
                }
            )
            gap.update(
                revision=gap["revision"] + 1,
                occurrences=gap["occurrences"] + 1,
                status="open",
                last_observed_at=now(),
            )
            db.execute(
                "INSERT INTO capability_gaps VALUES(?,?,?) ON CONFLICT(id) DO UPDATE "
                "SET revision=excluded.revision,payload=excluded.payload",
                (gap_id, gap["revision"], json.dumps(gap, ensure_ascii=False)),
            )
            db.execute(
                "INSERT INTO gap_observations VALUES(?,?,?)",
                (key, gap_id, json.dumps(observation, ensure_ascii=False)),
            )
        return True

    def triage(self, gap_id: str, request: GapTriageRequest) -> dict:
        source_ids = request.resolution_case_ids + (
            [request.resolution_case_id] if request.resolution_case_id else []
        )
        resolutions = []
        for source_id in source_ids:
            resolution = self.hub.repository.get(source_id)
            if resolution.status != "approved" or self.hub.quality_issues(resolution):
                raise PosterPilotError(
                    "解决证据需要通过案例审核", code="resolution_not_approved", status_code=422
                )
            if (resolution.evidence["after"].get("goal_verification") or {}).get(
                "outcome"
            ) != "met":
                raise PosterPilotError(
                    "解决证据尚未通过目标验收", code="resolution_unverified", status_code=422
                )
            resolutions.append(resolution)
        with self.connect(write=True) as db:
            row = db.execute("SELECT payload FROM capability_gaps WHERE id=?", (gap_id,)).fetchone()
            if not row:
                raise PosterPilotError("缺口记录不存在", code="gap_not_found", status_code=404)
            gap = json.loads(row[0])
            if gap["revision"] != request.expected_revision:
                raise PosterPilotError("缺口记录已变化，请刷新", code="stale_gap", status_code=409)
            if any(resolution.origin != gap["origin"] for resolution in resolutions):
                raise PosterPilotError(
                    "不能混用离线和真实运行证据", code="resolution_origin_mismatch", status_code=422
                )
            originals = [
                json.loads(item[0])
                for item in db.execute(
                    "SELECT payload FROM gap_observations WHERE gap_id=?", (gap_id,)
                )
            ]
            coverage = {}
            for resolution in resolutions:
                subject = gap["signature"].split("#")[0]
                after = resolution.evidence["after"]
                if subject.startswith("check:"):
                    key = subject.removeprefix("check:")
                    matched = any(
                        check.get("key") == key and check.get("status") == "passed"
                        for check in after["goal_verification"].get("checks", [])
                    )
                elif subject.startswith("tool:"):
                    tool = request.resolution_tool or subject.removeprefix("tool:")
                    self.authorization(tool)
                    matched = any(
                        trace.get("tool_name") == tool and trace.get("success")
                        for trace in after.get("tool_traces", [])
                    )
                elif subject.startswith("run:"):
                    covered = [
                        item["id"] for item in originals
                        if item.get("brief") is not None and item["brief"] == after.get("brief")
                    ]
                    coverage[str(resolution.id)] = covered
                    matched = bool(covered)
                else:
                    matched = resolution.feedback.verdict == "accepted"
                if not matched:
                    raise PosterPilotError(
                        "解决证据未覆盖该失败项或工具",
                        code="resolution_not_matched",
                        status_code=422,
                    )
            if resolutions and gap["signature"].startswith("run:"):
                covered_ids = {item for group in coverage.values() for item in group}
                if covered_ids != {item["id"] for item in originals}:
                    raise PosterPilotError(
                        "解决证据仅覆盖部分原始需求，请补充其余需求的验收案例",
                        code="resolution_incomplete",
                        status_code=422,
                    )
            first_resolution = resolutions[0] if resolutions else None
            gap.update(
                category=request.category,
                revision=gap["revision"] + 1,
                status="resolved" if resolutions else "triaged",
            )
            gap["audit"].append(
                {
                    "at": now(),
                    "note": request.note,
                    "category": request.category,
                    "resolution_case_id": str(first_resolution.id) if first_resolution else None,
                    "resolution_revision": first_resolution.revision if first_resolution else None,
                    "resolution_sources": [
                        {"case_id": str(item.id), "revision": item.revision}
                        for item in resolutions
                    ],
                    "observation_coverage": coverage,
                    "resolution_tool": request.resolution_tool,
                    "revision": gap["revision"],
                }
            )
            db.execute(
                "UPDATE capability_gaps SET revision=?,payload=? WHERE id=?",
                (gap["revision"], json.dumps(gap, ensure_ascii=False), gap_id),
            )
        return gap
