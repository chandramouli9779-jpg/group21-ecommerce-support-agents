"""Typed comparison inputs and raw agent results."""
from __future__ import annotations

import json
from datetime import date
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class Action(StrEnum):
    STATUS = "explain_status"
    TRACKING = "share_tracking"
    CLARIFY = "request_clarification"
    INVESTIGATE = "delivery_investigation"
    PENDING = "explain_refund_pending"
    COMPLETED = "explain_refund_completed"
    ESCALATE = "payments_escalation"
    REVIEW = "human_review"


class Status(StrEnum):
    OK = "ok"
    WARNING = "warning"
    ERROR = "error"
    INVALID = "invalid_output"
    INCOMPLETE = "incomplete_evidence"
    NOT_RUN = "not_run"


class Claims(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    found: bool | None = None
    intent: Literal["non_receipt", "refund_status", "tracking", "unknown"] = "unknown"
    denies_receipt: bool = False
    returned_date: date | None = None
    item: str | None = None


class Observation(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    date: date
    field: str
    value: str
    source: str


class Policy(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    version: str = "sim-v1"
    dnr_window_days: int = Field(default=7, ge=0)
    refund_sla_business_days: int = Field(default=5, ge=0)


class Case(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    case_id: str
    order_id: str
    item: str
    today: date
    message: str
    claims: Claims
    found: bool = True
    order_status: str = "unknown"
    delivery_date: date | None = None
    proof: str | None = None
    tracking: str | None = None
    expected_date: date | None = None
    return_date: date | None = None
    inspection: Literal["passed", "failed", "unknown"] = "unknown"
    inspection_date: date | None = None
    refund_status: Literal["pending", "completed", "unknown"] = "unknown"
    observations: tuple[Observation, ...] = ()
    policy: Policy = Field(default_factory=Policy)


class Citation(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    tool: Literal["lookup_case_records", "lookup_support_policy"]
    field: str = Field(min_length=1)


class FinalAnswer(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    action: Action
    rationale: str = Field(min_length=1, max_length=1500)
    policy_id: str = Field(min_length=1)
    citations: tuple[Citation, ...] = Field(min_length=2, max_length=8)


class Result(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent: str
    case_id: str
    action: Action | None = None
    rationale: str = ""
    status: Status = Status.OK
    citations: tuple[Citation, ...] = ()
    issues: tuple[str, ...] = ()
    trace: list[dict[str, Any]] = Field(default_factory=list)
    model: str | None = None
    latency_seconds: float | None = Field(default=None, ge=0)


def load_cases() -> dict[str, Case]:
    records = json.loads(Path(__file__).with_name("fixtures.json").read_text(encoding="utf-8"))
    cases = {record["case_id"]: Case.model_validate(record) for record in records}
    if len(cases) != len(records):
        raise ValueError("Duplicate fixture case_id")
    return cases
