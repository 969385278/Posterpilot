"""Paired profile-update ablation; extraction input is shared between conditions."""

import json
from pathlib import Path
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.memory import (
    MemoryEventInput,
    MemoryKey,
    MemoryScope,
    MemorySuggestion,
    SourceMessageInput,
)
from app.services.user_memory import UserMemoryService


class CheckProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user: str = Field(default="local", pattern=r"^[A-Za-z0-9_-]{1,80}$")
    scope: MemoryScope = "all"
    values: dict[MemoryKey, str]


class ConfirmPreference(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: MemoryKey
    value: str
    scope: MemoryScope = "all"
    quote: str


class MemoryStep(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1)
    user: str = Field(default="local", pattern=r"^[A-Za-z0-9_-]{1,80}$")
    conversation: str = Field(default="session-1", min_length=1)
    action: Literal["message", "retract"] = "message"
    text: str = Field(min_length=1, max_length=6000)
    suggestions: list[MemorySuggestion] = Field(default_factory=list)
    confirmations: list[ConfirmPreference] = Field(default_factory=list)
    retract_step: str | None = None
    retract_key: MemoryKey | None = None
    retract_scope: MemoryScope = "all"
    checks: list[CheckProfile] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_action(self):
        if self.action == "retract" and (not self.retract_step or not self.retract_key):
            raise ValueError("retraction needs source step and preference key")
        if self.action == "message" and self.retract_step:
            raise ValueError("message cannot retract an event")
        if any(item.quote not in self.text for item in self.confirmations):
            raise ValueError("confirmation quote must occur in user message")
        return self


class MemorySequence(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1, pattern=r"^[a-zA-Z0-9_-]+$")
    description: str
    steps: list[MemoryStep] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_steps(self):
        seen = set()
        for step in self.steps:
            if step.id in seen:
                raise ValueError("duplicate step")
            if step.action == "retract" and step.retract_step not in seen:
                raise ValueError("retraction must refer to an earlier step")
            seen.add(step.id)
        return self


class CaptureProvider:
    def __init__(self, provider, fixture, records):
        self.provider = provider
        self.fixture = fixture
        self.records = records

    async def complete_json(self, messages):
        row = {
            "messages": messages,
            "response": None,
            "error": None,
            "mode": "live_model" if self.provider else "frozen_candidate_replay",
        }
        self.records.append(row)
        try:
            row["response"] = (
                await self.provider.complete_json(messages)
                if self.provider
                else {
                    "suggestions": [item.model_dump(mode="json") for item in self.fixture],
                }
            )
            return row["response"]
        except Exception as error:
            row["error"] = type(error).__name__
            raise


def errors_for_profile(expected, actual):
    return {
        key: {"expected": expected.get(key), "actual": actual.get(key)}
        for key in sorted(expected.keys() | actual.keys())
        if expected.get(key) != actual.get(key)
    }


async def compare_memory(sequences: list[MemorySequence], root: Path, *, provider=None):
    if not sequences or len({case.id for case in sequences}) != len(sequences):
        raise ValueError("empty dataset or duplicate sequence IDs")
    root.mkdir(parents=True, exist_ok=False)
    rows = []
    with (root / "rows.jsonl").open("x", encoding="utf-8") as output:
        for case in sequences:
            service = UserMemoryService(root / case.id / "memory.sqlite3")
            slots = {}
            event_refs = {}
            conversations = {}
            for step in case.steps:
                row = {
                    "case_id": case.id,
                    "step_id": step.id,
                    "action": step.action,
                    "input": step.model_dump(mode="json", exclude={"checks"}),
                    "provider_records": [],
                    "error": None,
                    "actions": [],
                    "unmatched_confirmations": [],
                    "checks": [],
                }
                conversation_id = conversations.setdefault((step.user, step.conversation), uuid4())
                source = SourceMessageInput(
                    id=uuid4(), text=step.text, conversation_id=conversation_id
                )
                try:
                    if step.action == "message":
                        extracted = await service.extract(
                            step.user,
                            source,
                            CaptureProvider(
                                provider,
                                step.suggestions,
                                row["provider_records"],
                            ),
                        )
                        row["extraction"] = extracted
                        slots_in_response = [
                            (item["scope"], item["key"]) for item in extracted["suggestions"]
                        ]
                        if len(slots_in_response) != len(set(slots_in_response)):
                            raise ValueError("ambiguous duplicate candidates in one source")
                        row["unmatched_confirmations"] = [
                            confirmation.model_dump(mode="json")
                            for confirmation in step.confirmations
                            if not any(
                                raw["kind"] == "explicit" and all(
                                    getattr(confirmation, key) == raw[key]
                                    for key in ("key", "value", "scope", "quote")
                                )
                                for raw in extracted["suggestions"]
                            )
                        ]
                        for raw in extracted["suggestions"]:
                            item = MemorySuggestion.model_validate(raw)
                            slot = (step.user, item.scope, item.key)
                            ref = (step.user, step.id, item.scope, item.key)
                            # Baseline retains user/scope partitioning and supports retraction.
                            # Only confirmation and kind gating are removed in this baseline.
                            slots[slot] = {"value": item.value, "ref": ref}
                            confirmed = any(
                                all(
                                    getattr(confirmation, key) == getattr(item, key)
                                    for key in ("key", "value", "scope", "quote")
                                )
                                for confirmation in step.confirmations
                            )
                            action = {"candidate": raw, "confirmed": confirmed, "committed": False}
                            if item.kind != "explicit" or confirmed:
                                event = service.record(
                                    step.user,
                                    MemoryEventInput(
                                        **item.model_dump(),
                                        source_id=source.id,
                                        confirmed=confirmed and item.kind == "explicit",
                                        expected_revision=service.profile(step.user)["revision"],
                                    ),
                                )
                                event_refs[ref] = event["id"]
                                action.update(committed=event["state"] == "active", event=event)
                            row["actions"].append(action)
                    else:
                        service.save_source(step.user, source)
                        ref = (step.user, step.retract_step, step.retract_scope, step.retract_key)
                        slot = (step.user, step.retract_scope, step.retract_key)
                        if slots.get(slot, {}).get("ref") == ref:
                            del slots[slot]
                        event_id = event_refs.get(ref)
                        if event_id:
                            service.retract(
                                step.user,
                                UUID(event_id),
                                expected_revision=service.profile(step.user)["revision"],
                                reason=step.text,
                            )
                        row["actions"].append(
                            {"retracted_event": event_id, "no_event": event_id is None}
                        )
                except Exception as error:
                    row["error"] = getattr(error, "code", type(error).__name__)
                for check in step.checks:
                    baseline = {
                        key: value["value"]
                        for (user, scope, key), value in slots.items()
                        if user == check.user and scope == "all"
                    }
                    baseline.update(
                        {
                            key: value["value"]
                            for (user, scope, key), value in slots.items()
                            if user == check.user and scope == check.scope
                        }
                    )
                    profile = service.profile(check.user, scope=check.scope)
                    governed = {
                        key: value["value"] for key, value in profile["preferences"].items()
                    }
                    row["checks"].append(
                        {
                            "expected": check.model_dump(),
                            "direct_overwrite": baseline,
                            "governed": governed,
                            "profile_snapshot": profile,
                            "errors": {
                                "direct_overwrite": errors_for_profile(check.values, baseline),
                                "governed": errors_for_profile(check.values, governed),
                            },
                        }
                    )
                row["source"] = service.source(step.user, source.id)
                rows.append(row)
                output.write(json.dumps(row, ensure_ascii=False) + "\n")
                output.flush()
    summary = {
        "sequences": len(sequences),
        "steps": len(rows),
        "runtime_errors": sum(row["error"] is not None for row in rows),
        "mode": "live_shared_extraction" if provider else "frozen_candidate_replay",
        "conditions": {},
    }
    for condition in ("direct_overwrite", "governed"):
        failed = [
            row
            for row in rows
            if row["error"] or any(check["errors"][condition] for check in row["checks"])
        ]
        summary["conditions"][condition] = {
            "incorrect_steps": len(failed),
            "incorrect_sequences": len({row["case_id"] for row in failed}),
            "failures": [f"{row['case_id']}:{row['step_id']}" for row in failed],
        }
    summary["unmatched_confirmation_steps"] = sum(
        bool(row["unmatched_confirmations"]) for row in rows
    )
    summary["valid_governance_comparison"] = (
        summary["runtime_errors"] == 0 and summary["unmatched_confirmation_steps"] == 0
    )
    summary["extraction_quality_validated"] = False
    return summary, rows
