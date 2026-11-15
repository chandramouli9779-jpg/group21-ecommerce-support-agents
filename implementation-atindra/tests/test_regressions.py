from datetime import date

from contracts import Action, Observation, load_cases
from domain import eligibility, facts
from agents import model_based


def test_invalid_superseded_history_stays_a_conflict():
    case = load_cases()["B"]
    bad = Observation(date=date(2026, 10, 29), field="refund_status", value="garbage", source="payments")
    changed = case.model_copy(update={"observations": (bad,) + case.observations})
    assert any("Invalid observation" in issue for issue in facts(changed)["issues"])
    assert Action.ESCALATE not in eligibility(changed)


def test_intermediate_unknown_cannot_erase_delivery():
    case = load_cases()["D"]
    observations = tuple(Observation(date=date(2026, 11, day), field="order_status", value=value, source="carrier")
                         for day, value in ((10, "delivered"), (11, "unknown"), (12, "in_transit")))
    changed = case.model_copy(update={"observations": observations})
    assert Action.TRACKING not in eligibility(changed)
    assert model_based.run(changed).action in {Action.CLARIFY, Action.REVIEW}


def test_outbound_status_and_return_conflict():
    case = load_cases()["B"].model_copy(update={"order_status": "in_transit", "observations": ()})
    assert Action.ESCALATE not in eligibility(case)


def test_whitespace_is_not_tracking():
    case = load_cases()["D"].model_copy(update={"tracking": "   ", "observations": ()})
    assert Action.TRACKING not in eligibility(case)
    assert model_based.run(case).action != Action.TRACKING
