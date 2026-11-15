from collections import deque
from copy import deepcopy
from datetime import date
import json

import pytest

from agents import goal_based, learning, model_based, simple_reflex, utility_based
from contracts import Action, Case, Claims, Observation, Result, Status, load_cases
from domain import eligibility, validate_result

AGENTS = (simple_reflex, model_based, goal_based, utility_based, learning)
INFORMED = (model_based, goal_based, utility_based, learning)


@pytest.fixture
def cases():
    return load_cases()


def variant(case, **updates):
    return Case.model_validate({**case.model_dump(), **updates})


def run(agent, case):
    return agent.run(case, counts=learning.seed_counts()) if agent is learning else agent.run(case)


@pytest.mark.parametrize("agent", AGENTS)
@pytest.mark.parametrize("case_id", ("A", "B", "C", "D"))
def test_a_to_d_same_immutable_schema(cases, agent, case_id):
    case = cases[case_id]
    before = case.model_dump_json()
    expected = {"A": Action.INVESTIGATE, "B": Action.ESCALATE, "C": Action.CLARIFY, "D": Action.TRACKING}
    if agent is simple_reflex:
        expected["B"] = Action.PENDING
    result = run(agent, case)
    assert isinstance(result, Result)
    assert result.case_id == case_id
    assert result.action == expected[case_id]
    assert result.status == Status.OK
    assert result.rationale and result.citations
    assert result.trace and all(isinstance(entry, dict) for entry in result.trace)
    result.trace[0]["mutated"] = True
    assert "mutated" not in run(agent, case).trace[0]
    assert case.model_dump_json() == before
    assert run(agent, variant(case, case_id="RENAMED")).action == expected[case_id]


def test_reflex_limitation_is_evaluated_without_replacing_raw_action(cases):
    raw = simple_reflex.run(cases["B"])
    evaluated = validate_result(cases["B"], raw)
    assert raw.action == evaluated.action == Action.PENDING
    assert raw.status == Status.OK and evaluated.status == Status.WARNING
    assert evaluated.issues
    assert not raw.trace[0]["uses_history"] and not raw.trace[0]["uses_dates"]
    assert model_based.run(cases["B"]).action == Action.ESCALATE


@pytest.mark.parametrize("agent", INFORMED)
@pytest.mark.parametrize("today,expected", [("2026-11-06", Action.PENDING), ("2026-11-07", Action.ESCALATE), ("2026-11-09", Action.ESCALATE)])
def test_business_day_friday_saturday_monday(cases, agent, today, expected):
    case = variant(cases["B"], today=date.fromisoformat(today))
    result = run(agent, case)
    assert result.action == expected
    if agent is model_based:
        assert result.trace[0]["derived"]["refund_deadline"] == date(2026, 11, 6)


@pytest.mark.parametrize("agent", INFORMED)
@pytest.mark.parametrize("today,expected", [("2026-11-10", Action.INVESTIGATE), ("2026-11-17", Action.INVESTIGATE), ("2026-11-18", Action.REVIEW), ("2026-11-09", Action.CLARIFY)])
def test_nonreceipt_inclusive_window_and_future(cases, agent, today, expected):
    assert run(agent, variant(cases["A"], today=date.fromisoformat(today))).action == expected


@pytest.mark.parametrize("agent", INFORMED)
def test_proof_and_intent_only_nonreceipt(cases, agent):
    case = variant(cases["A"], proof="Photo and signature", claims=Claims(intent="non_receipt", denies_receipt=False))
    assert run(agent, case).action == Action.INVESTIGATE


@pytest.mark.parametrize("agent", INFORMED)
@pytest.mark.parametrize("updates", [
    {"found": False}, {"claims": Claims(intent="refund_status", item="wrong item")},
    {"claims": Claims(intent="refund_status", found=False)},
    {"claims": Claims(intent="refund_status", returned_date=date(2026, 10, 28))},
    {"inspection": "failed"}, {"inspection_date": None},
    {"inspection_date": date(2026, 11, 14)}, {"inspection_date": date(2026, 10, 28)},
    {"return_date": None}, {"refund_status": "unknown"},
])
def test_refund_missing_conflicting_and_chronology(cases, agent, updates):
    result = run(agent, variant(cases["B"], **updates))
    assert result.action == Action.CLARIFY
    assert result.issues


@pytest.mark.parametrize("agent", AGENTS)
def test_completed_refund_is_not_escalated(cases, agent):
    observation = Observation(date=date(2026, 11, 12), field="refund_status", value="completed", source="payments")
    case = variant(cases["B"], refund_status="completed", observations=cases["B"].observations + (observation,))
    assert run(agent, case).action == Action.COMPLETED


@pytest.mark.parametrize("agent", INFORMED)
@pytest.mark.parametrize("updates,expected", [
    ({"today": date(2026, 11, 16)}, Action.TRACKING),
    ({"today": date(2026, 11, 17)}, Action.REVIEW),
    ({"expected_date": None}, Action.CLARIFY),
    ({"tracking": None, "observations": ()}, Action.STATUS),
    ({"order_status": "unknown", "observations": ()}, Action.CLARIFY),
])
def test_tracking_boundaries(cases, agent, updates, expected):
    assert run(agent, variant(cases["D"], **updates)).action == expected


def test_model_replay_real_transitions_snapshot_phase_and_case_reset(cases):
    result = model_based.run(variant(cases["B"], observations=tuple(reversed(cases["B"].observations))))
    trace = result.trace[0]
    transitions = trace["transitions"]
    historical = [step for step in transitions if step["phase"] == "history"]
    assert historical[0]["before"] == {}
    assert historical[0]["after"]["order_status"] == "delivered"
    status_transitions = [step for step in historical if step["field"] == "order_status"]
    assert status_transitions[1]["after"]["order_status"] == "returned"
    assert [step["date"] for step in historical] == sorted(step["date"] for step in historical)
    assert all(left["after"] == right["before"] for left, right in zip(transitions, transitions[1:]))
    assert all(step["phase"] == "current_snapshot" for step in transitions[len(historical):])
    assert trace["belief"]["order_status"] == "returned"
    assert trace["model_copy"]["case_id"] == "B"
    fresh = model_based.run(cases["D"]).trace[0]
    assert fresh["belief"]["return_date"] is None
    assert fresh["derived"]["refund_deadline"] is None
    assert not fresh["conflicts"]


@pytest.mark.parametrize("observations", [
    (Observation(date=date(2026, 11, 12), field="order_status", value="in_transit", source="carrier"),),
    (Observation(date=date(2026, 11, 10), field="order_status", value="returned", source="warehouse"),),
    (Observation(date=date(2026, 11, 14), field="order_status", value="delivered", source="carrier"),),
    (Observation(date=date(2026, 11, 12), field="delivery_date", value="not-a-date", source="carrier"),),
    (Observation(date=date(2026, 11, 12), field="unrecognized", value="anything", source="carrier"),),
])
def test_model_same_current_snapshot_history_changes_decision(cases, observations):
    case = variant(cases["A"], observations=cases["A"].observations + observations)
    assert simple_reflex.run(case).action == Action.INVESTIGATE
    result = model_based.run(case)
    assert result.action == Action.CLARIFY and result.issues
    assert result.trace[0]["belief"]["order_status"] == "delivered"
    assert model_based.run(cases["A"]).action == Action.INVESTIGATE


def test_model_refund_completion_regression_preserved(cases):
    observations = cases["B"].observations + (
        Observation(date=date(2026, 11, 10), field="refund_status", value="completed", source="payments"),
        Observation(date=date(2026, 11, 12), field="refund_status", value="pending", source="payments"),
    )
    result = model_based.run(variant(cases["B"], observations=observations))
    assert result.action == Action.CLARIFY
    assert any("completion" in issue or "completed" in issue for issue in result.issues)


def test_goal_missing_return_blocks_requested_goal_then_supported_reaches_it(cases):
    original = goal_based.run(cases["C"]).trace[0]
    assert not original["requested_reachable"]
    assert "return_record" in original["blocked"]["verify_return"]
    assert original["plan"] == ["request_clarification", "communicate_review_addressed"]
    supported = variant(cases["C"], return_date=date(2026, 10, 30), inspection="passed",
                        inspection_date=date(2026, 10, 30), refund_status="pending")
    result = goal_based.run(supported)
    assert result.action == Action.ESCALATE
    assert result.trace[0]["requested_reachable"]
    assert "verify_return" in result.trace[0]["plan"]


@pytest.mark.parametrize("case_id,length", [("A", 3), ("B", 5), ("C", 2), ("D", 4)])
def test_goal_explicit_prerequisites_effects_and_independent_shortest_path(cases, case_id, length):
    result = goal_based.run(cases[case_id])
    trace = result.trace[0]
    operators = {op["name"]: op for op in trace["operators"]}
    state = set(trace["initial_facts"])
    recommendation = None
    for name in trace["plan"]:
        operator = operators[name]
        assert set(operator["prerequisites"]) <= state
        state.update(operator["effects"])
        if operator["action"] is not None:
            assert recommendation is None
            recommendation = operator["action"]
    assert recommendation == result.action
    assert set(trace["goal"]) <= state
    queue = deque([(frozenset(trace["initial_facts"]), None, 0)])
    visited = set()
    while queue:
        state, chosen, depth = queue.popleft()
        if (state, chosen) in visited:
            continue
        visited.add((state, chosen))
        if set(trace["goal"]) <= state:
            assert depth == trace["plan_length"] == length
            break
        for op in operators.values():
            if set(op["prerequisites"]) <= state and not (op["action"] is not None and chosen is not None):
                queue.append((state | frozenset(op["effects"]), op["action"] or chosen, depth + 1))
    else:
        pytest.fail("Declared goal unreachable")
    assert trace["effects_are_hypothetical"] and trace["search_count"] > length


def test_utility_weight_sensitive_eligible_tradeoff_and_explicit_scores(cases):
    default = utility_based.run(cases["A"])
    cautious = utility_based.run(cases["A"], weights={"customer_impact": 0.1, "delay": 0, "effort": 0, "error_risk": 1})
    assert default.action == Action.INVESTIGATE and cautious.action == Action.REVIEW
    assert set(default.trace[0]["candidates"]) == set(cautious.trace[0]["candidates"])
    for info in default.trace[0]["candidates"].values():
        weights = default.trace[0]["weights"]
        parts = info["features"]
        expected = parts["customer_impact"] * weights["customer_impact"] - sum(parts[key] * weights[key] for key in ("delay", "effort", "error_risk"))
        assert info["score"] == pytest.approx(expected)
    assert Action.ESCALATE.value in default.trace[0]["excluded"]
    assert utility_based.WEIGHTS["customer_impact"] == 0.4


@pytest.mark.parametrize("weights", ({"bad": 1}, {"delay": -1}, {"effort": float("nan")}, {"delay": True}))
def test_utility_rejects_invalid_weights(cases, weights):
    with pytest.raises(ValueError):
        utility_based.run(cases["A"], weights=weights)


def test_learning_seed_all_known_contexts_and_neutral_ties(cases):
    counts = learning.seed_counts()
    assert len(counts) == len(learning.CONTEXTS) * len(Action)
    nonneutral = {key: stats for key, stats in counts.items() if stats != {"success": 0, "failure": 0}}
    assert nonneutral == {"timely_nonreceipt|delivery_investigation": {"success": 6, "failure": 3},
                          "timely_nonreceipt|human_review": {"success": 5, "failure": 4}}
    before = deepcopy(counts)
    for case_id in ("B", "C", "D"):
        result = learning.run(cases[case_id], counts)
        assert result.action != Action.REVIEW
        assert result.trace[0]["context"] == learning.context(cases[case_id])
    assert counts == before
    counts[next(iter(counts))]["success"] = 999
    assert learning.seed_counts() == before


def test_learning_persisted_two_failure_adaptation_reload_reset(cases, tmp_path):
    path = tmp_path / "runtime" / "counts.json"
    assert learning.load_counts(path) == learning.seed_counts()
    assert not path.exists()
    learning.reset(path)
    before_case = cases["A"].model_dump_json()
    initial = learning.run(cases["A"], learning.load_counts(path))
    assert initial.action == Action.INVESTIGATE
    assert initial.trace[0]["candidates"][Action.INVESTIGATE.value]["estimate"] == 7 / 11
    learning.feedback(path, initial.trace[0]["context"], initial.action, False)
    first = learning.run(cases["A"], learning.load_counts(path))
    assert first.action == Action.INVESTIGATE
    assert first.trace[0]["candidates"][Action.INVESTIGATE.value]["estimate"] == 7 / 12
    learning.feedback(path, first.trace[0]["context"], first.action.value, False)
    second = learning.run(cases["A"], learning.load_counts(path))
    assert second.action == Action.REVIEW
    assert second.trace[0]["candidates"][Action.INVESTIGATE.value]["estimate"] == 7 / 13
    assert initial.trace[0]["candidates"][Action.INVESTIGATE.value]["failure"] == 3
    assert json.loads(path.read_text()) == learning.load_counts(path)
    assert cases["A"].model_dump_json() == before_case
    learning.reset(path)
    assert learning.load_counts(path) == learning.seed_counts()


def test_learning_default_path_loads_and_reruns_never_write(cases, tmp_path, monkeypatch):
    path = tmp_path / "counts.json"
    learning.reset(path)
    label = learning.context(cases["A"])
    learning.feedback(path, label, Action.INVESTIGATE, False)
    learning.feedback(path, label, Action.INVESTIGATE, False)
    loader = learning.load_counts
    monkeypatch.setattr(learning, "load_counts", lambda: loader(path))
    before = path.read_bytes()
    assert learning.run(cases["A"]).action == Action.REVIEW
    assert learning.run(cases["A"]).action == Action.REVIEW
    assert path.read_bytes() == before
    assert learning.COUNTS_FILE.parts[-2:] == ("runtime", "learning_counts.json")


def test_learning_full_precision_and_high_success_ineligible_exclusion(cases):
    counts = learning.seed_counts()
    label = learning.context(cases["A"])
    counts[f"{label}|{Action.INVESTIGATE.value}"] = {"success": 1000, "failure": 1000}
    counts[f"{label}|{Action.REVIEW.value}"] = {"success": 1001, "failure": 1000}
    counts[f"{label}|{Action.ESCALATE.value}"] = {"success": 999, "failure": 0}
    result = learning.run(cases["A"], counts)
    assert result.action == Action.REVIEW
    trace = result.trace[0]
    assert len({round(info["estimate"], 3) for info in trace["candidates"].values()}) == 1
    assert Action.ESCALATE.value not in trace["candidates"]
    assert trace["excluded"][Action.ESCALATE.value]["success"] == 999


def test_learning_unknown_context_explicit_review(cases):
    result = learning.run(variant(cases["D"], claims=Claims(intent="unknown")), {})
    assert result.action == Action.REVIEW
    assert result.trace[0]["context"] == "unknown"
    assert not result.trace[0]["supported_context"]


def test_learning_context_tracks_timing_and_conflicts_not_identity(cases):
    assert learning.context(cases["A"]) == "timely_nonreceipt"
    assert learning.context(variant(cases["A"], today=date(2026, 11, 18))) == "nonreceipt_review"
    assert learning.context(cases["B"]) == "refund_overdue"
    assert learning.context(variant(cases["B"], today=date(2026, 11, 6))) == "refund_pending"
    assert learning.context(cases["C"]) == "conflict_review"
    assert learning.context(cases["D"]) == "tracking"
    assert learning.context(variant(cases["D"], today=date(2026, 11, 17))) == "tracking_review"


@pytest.mark.parametrize("agent", INFORMED)
def test_custom_policy_window_and_sla(cases, agent):
    case = variant(cases["A"], policy={"dnr_window_days": 2, "refund_sla_business_days": 5})
    assert run(agent, case).action == Action.REVIEW
    case = variant(cases["B"], policy={"dnr_window_days": 7, "refund_sla_business_days": 20})
    assert run(agent, case).action == Action.PENDING


@pytest.mark.parametrize("stats", ({"success": -1, "failure": 0}, {"success": True, "failure": 0}, {"success": 1}))
def test_learning_invalid_counts_rejected(cases, tmp_path, stats):
    path = tmp_path / "bad.json"
    key = f"{learning.context(cases['A'])}|{Action.INVESTIGATE.value}"
    path.write_text(json.dumps({key: stats}))
    with pytest.raises(ValueError):
        learning.load_counts(path)
    with pytest.raises(ValueError):
        learning.run(cases["A"], {key: stats})


@pytest.mark.parametrize("context,action,success", [("bad|context", Action.REVIEW, True), ("valid", "not-an-action", True), ("valid", Action.REVIEW, 1)])
def test_feedback_validation_before_writes(tmp_path, context, action, success):
    path = tmp_path / "counts.json"
    with pytest.raises(ValueError):
        learning.feedback(path, context, action, success)
    assert not path.exists()


def test_no_old_api_aliases():
    assert not hasattr(learning, "reset_counts")
    assert not hasattr(learning, "record_feedback")
    assert not hasattr(learning, "DEMO_COUNTS")


@pytest.mark.parametrize("agent", INFORMED)
def test_informed_agents_obey_shared_eligibility(cases, agent):
    for case in cases.values():
        result = run(agent, case)
        assert result.action in eligibility(case)
