"""Independent assertions against the B plan, not agent-selected answers."""
from datetime import date

import pytest
from pydantic import ValidationError

from contracts import Action, Case, Citation, Claims, FinalAnswer, Observation, Policy, Result, Status, load_cases
from domain import add_business_days, eligibility, facts, policy_records, validate_result


@pytest.fixture
def cases():
    return load_cases()


def changed(case, **updates):
    payload = case.model_dump()
    payload.update(updates)
    return Case.model_validate(payload)


def test_fixture_identities_dates_and_evidence(cases):
    assert set(cases) == {"A", "B", "C", "D"}
    assert [case.order_id for case in cases.values()] == ["ORD-3001", "ORD-3002", "ORD-3003", "ORD-3004"]
    assert [case.item for case in cases.values()] == ["e-reader", "raincoat", "kettle", "keyboard"]
    assert all(case.today == date(2026, 11, 13) for case in cases.values())
    assert cases["A"].delivery_date == date(2026, 11, 10)
    assert cases["A"].proof is None and cases["A"].claims.denies_receipt
    assert cases["B"].return_date == date(2026, 10, 29)
    assert cases["B"].inspection_date == date(2026, 10, 30)
    assert cases["B"].inspection == "passed" and cases["B"].refund_status == "pending"
    assert cases["C"].delivery_date == date(2026, 10, 20)
    assert cases["C"].claims.returned_date == date(2026, 10, 30)
    assert cases["C"].return_date is None and cases["C"].refund_status == "unknown"
    assert cases["D"].expected_date == date(2026, 11, 16)
    assert [event.date for event in cases["D"].observations] == [date(2026, 11, 10), date(2026, 11, 12), date(2026, 11, 12)]
    assert all("expected_action" not in case.model_dump() for case in cases.values())


def test_nested_inputs_are_frozen_and_dump_is_isolated(cases):
    case = cases["A"]
    for obj, field, value in [(case, "item", "wrong"), (case.claims, "denies_receipt", False),
                              (case.policy, "dnr_window_days", 99), (case.observations[0], "value", "wrong")]:
        with pytest.raises(ValidationError):
            setattr(obj, field, value)
    assert isinstance(case.observations, tuple)
    dump = case.model_dump()
    dump["claims"]["denies_receipt"] = False
    dump["policy"]["dnr_window_days"] = 99
    assert case.claims.denies_receipt and case.policy.dnr_window_days == 7
    assert load_cases()["A"] == case


@pytest.mark.parametrize("model,payload", [
    (Claims, {}), (Policy, {}),
    (Observation, {"date": "2026-11-10", "field": "order_status", "value": "delivered", "source": "carrier"}),
    (Citation, {"tool": "lookup_case_records", "field": "case_id"}),
    (Result, {"agent": "test", "case_id": "A"}),
])
def test_contracts_forbid_extra_fields(model, payload):
    with pytest.raises(ValidationError):
        model.model_validate({**payload, "unexpected": 1})


def test_case_and_final_answer_schema(cases):
    with pytest.raises(ValidationError):
        changed(cases["A"], unexpected=1)
    citations = [{"tool": "lookup_case_records", "field": "delivery_date"},
                 {"tool": "lookup_support_policy", "field": "DNR"}]
    payload = {"action": "delivery_investigation", "rationale": "Timely report.", "policy_id": "DNR", "citations": citations}
    assert FinalAnswer.model_validate(payload).action is Action.INVESTIGATE
    for updates in [{"citations": citations[:1]}, {"action": "refund_now"}, {"extra": True},
                    {"citations": [{"tool": "unknown", "field": "date"}] * 2}]:
        with pytest.raises(ValidationError):
            FinalAnswer.model_validate({**payload, **updates})
    assert {status.value for status in Status} == {"ok", "warning", "error", "invalid_output", "incomplete_evidence", "not_run"}
    assert {action.value for action in Action} == {"explain_status", "share_tracking", "request_clarification", "delivery_investigation", "explain_refund_pending", "explain_refund_completed", "payments_escalation", "human_review"}


def test_independent_base_eligibility(cases):
    assert set(eligibility(cases["A"])) == {Action.INVESTIGATE, Action.REVIEW}
    assert set(eligibility(cases["B"])) == {Action.ESCALATE, Action.REVIEW}
    assert set(eligibility(cases["C"])) == {Action.CLARIFY, Action.REVIEW}
    assert set(eligibility(cases["D"])) == {Action.TRACKING, Action.STATUS, Action.REVIEW}
    assert facts(cases["A"])["dnr_age"] == 3
    assert facts(cases["B"])["refund_deadline"] == date(2026, 11, 6)
    assert facts(cases["B"])["overdue"] is True
    assert any("return evidence" in issue for issue in facts(cases["C"])["issues"])


@pytest.mark.parametrize("start,count,deadline", [
    (date(2026, 10, 30), 5, date(2026, 11, 6)),
    (date(2026, 11, 6), 1, date(2026, 11, 9)),
    (date(2026, 11, 7), 1, date(2026, 11, 9)),
    (date(2026, 11, 7), 0, date(2026, 11, 7)),
])
def test_business_day_arithmetic(start, count, deadline):
    assert add_business_days(start, count) == deadline
    with pytest.raises(ValueError):
        add_business_days(start, -1)


@pytest.mark.parametrize("today,overdue,action", [
    (date(2026, 11, 6), False, Action.PENDING),
    (date(2026, 11, 7), True, Action.ESCALATE),
    (date(2026, 11, 9), True, Action.ESCALATE),
])
def test_friday_deadline_and_weekend(cases, today, overdue, action):
    case = changed(cases["B"], today=today)
    assert facts(case)["refund_deadline"] == date(2026, 11, 6)
    assert facts(case)["overdue"] is overdue
    assert set(eligibility(case)) == {action, Action.REVIEW}


@pytest.mark.parametrize("today,eligible", [
    (date(2026, 11, 10), True), (date(2026, 11, 17), True), (date(2026, 11, 18), False),
])
def test_dnr_window_and_proof(cases, today, eligible):
    case = changed(cases["A"], today=today, proof="Photo and signature")
    assert (Action.INVESTIGATE in eligibility(case)) is eligible


@pytest.mark.parametrize("updates", [
    {"delivery_date": None}, {"delivery_date": date(2026, 11, 14)},
])
def test_dnr_missing_future_dates_are_unknown(cases, updates):
    case = changed(cases["A"], **updates)
    assert facts(case)["dnr_age"] is None
    assert facts(case)["issues"]
    assert Action.INVESTIGATE not in eligibility(case)


@pytest.mark.parametrize("updates", [
    {"return_date": None}, {"inspection_date": None}, {"inspection": "failed"},
    {"inspection": "unknown"}, {"inspection_date": date(2026, 11, 14)},
    {"return_date": date(2026, 11, 14)}, {"inspection_date": date(2026, 10, 28)},
    {"refund_status": "unknown"},
])
def test_refund_missing_failed_future_and_conflicting_prerequisites(cases, updates):
    case = changed(cases["B"], observations=(), **updates)
    assert facts(case)["issues"]
    assert facts(case)["refund_verified"] is False
    assert facts(case)["refund_deadline"] is None
    assert facts(case)["overdue"] is False
    assert set(eligibility(case)) == {Action.CLARIFY, Action.REVIEW}


def test_completed_refund_and_supported_return(cases):
    completed = changed(cases["B"], refund_status="completed", observations=())
    assert facts(completed)["refund_verified"] is True
    assert facts(completed)["overdue"] is False
    assert set(eligibility(completed)) == {Action.COMPLETED, Action.REVIEW}
    supported = changed(cases["C"], return_date=date(2026, 10, 30), inspection="passed",
                        inspection_date=date(2026, 11, 2), refund_status="pending")
    assert not facts(supported)["issues"]
    assert facts(supported)["refund_deadline"] == date(2026, 11, 9)
    assert Action.ESCALATE in eligibility(supported)


def test_history_conflicts_are_preserved(cases):
    before = cases["B"].model_dump()
    conflicting = changed(cases["B"], refund_status="completed")
    assert any("Current refund_status conflicts" in issue for issue in facts(conflicting)["issues"])
    assert conflicting.refund_status == "completed"
    assert conflicting.observations[-1].value == "pending"
    regression = changed(cases["B"], observations=[
        {"date": "2026-10-30", "field": "refund_status", "value": "completed", "source": "payments"},
        {"date": "2026-11-01", "field": "refund_status", "value": "pending", "source": "payments"},
    ])
    assert any("history contradicts" in issue for issue in facts(regression)["issues"])
    assert not facts(regression)["refund_verified"]
    assert cases["B"].model_dump() == before


def test_same_day_conflicting_and_future_observations(cases):
    observations = [
        {"date": "2026-11-10", "field": "order_status", "value": "shipped", "source": "store"},
        {"date": "2026-11-10", "field": "order_status", "value": "delivered", "source": "carrier"},
        {"date": "2026-11-14", "field": "tracking", "value": "At hub", "source": "carrier"},
    ]
    case = changed(cases["A"], observations=observations)
    assert any("Conflicting observations" in issue for issue in facts(case)["issues"])
    assert any("future" in issue for issue in facts(case)["issues"])
    assert Action.INVESTIGATE not in eligibility(case)


@pytest.mark.parametrize("earlier,later", [("delivered", "in_transit"), ("returned", "delivered")])
def test_order_history_regression_blocks_eligibility(cases, earlier, later):
    case = changed(cases["D"], order_status=later, observations=[
        {"date": "2026-11-10", "field": "order_status", "value": earlier, "source": "carrier"},
        {"date": "2026-11-12", "field": "order_status", "value": later, "source": "store"},
    ])
    assert any("history regresses" in issue for issue in facts(case)["issues"])
    assert set(eligibility(case)) == {Action.CLARIFY, Action.REVIEW}


def test_unknown_order_claim_mismatch_late_and_missing_tracking(cases):
    unknown = changed(cases["D"], found=False)
    assert set(eligibility(unknown)) == {Action.CLARIFY, Action.REVIEW}
    mismatch = changed(cases["A"], claims=Claims(intent="non_receipt", denies_receipt=True, item="kettle", found=False))
    assert any("item conflicts" in issue for issue in facts(mismatch)["issues"])
    assert any("found claim conflicts" in issue for issue in facts(mismatch)["issues"])
    assert set(eligibility(changed(cases["D"], today=date(2026, 11, 17)))) == {Action.REVIEW}
    assert Action.CLARIFY in eligibility(changed(cases["D"], expected_date=None))
    assert any("Expected delivery date is missing" in issue for issue in facts(changed(cases["D"], expected_date=None))["issues"])
    missing = changed(cases["D"], tracking=None, observations=())
    assert Action.TRACKING not in eligibility(missing)
    assert Action.CLARIFY in eligibility(missing)


def test_policy_records_are_snapshot_bound_and_not_expected_answers(cases):
    case = changed(cases["A"], case_id="A-custom", policy=Policy(version="test-policy", dnr_window_days=2, refund_sla_business_days=3))
    records = policy_records(case)
    assert set(records) == {"case_id", "version", "SAFE", "VERIFY", "DNR", "REFUND", "TRACK"}
    assert records["case_id"] == "A-custom" and records["version"] == "test-policy"
    assert "2 calendar days" in records["DNR"]
    assert "3 business days" in records["REFUND"]
    assert Action.INVESTIGATE not in eligibility(case)
    records["DNR"] = "tampered"
    assert "2 calendar days" in policy_records(case)["DNR"]


def test_validator_flags_raw_action_without_substitution(cases):
    raw = Result(agent="Simple Reflex", case_id="B", action=Action.PENDING, rationale="Refund pending.",
                 trace=[{"rule": "pending"}], issues=("Known limitation",))
    checked = validate_result(cases["B"], raw)
    assert checked.status is Status.WARNING
    assert checked.action is Action.PENDING and checked.rationale == raw.rationale
    assert checked.trace == raw.trace
    assert checked.issues[0] == "Known limitation"
    assert any("ineligible" in issue for issue in checked.issues)
    assert raw.status is Status.OK and raw.issues == ("Known limitation",)
    assert validate_result(cases["B"], checked) == checked
    assert validate_result(cases["A"], Result(agent="test", case_id="A", action=Action.INVESTIGATE)).status is Status.OK
    wrong_case = validate_result(cases["A"], Result(agent="test", case_id="D", action=Action.INVESTIGATE))
    assert wrong_case.status is Status.WARNING
    assert any("case_id" in issue for issue in wrong_case.issues)


@pytest.mark.parametrize("status", [Status.ERROR, Status.INVALID, Status.INCOMPLETE, Status.NOT_RUN])
def test_validation_preserves_execution_failures(cases, status):
    raw = Result(agent="LLM", case_id="B", status=status, action=Action.PENDING)
    assert validate_result(cases["B"], raw).status is status
