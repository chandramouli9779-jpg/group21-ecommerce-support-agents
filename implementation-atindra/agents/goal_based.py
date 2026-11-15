"""Search a fixed equal-cost workflow graph, not a preselected action chain."""
from collections import deque

from contracts import Action, Case, Citation, Result
from domain import eligibility, facts


def run(case: Case) -> Result:
    available, evidence = eligibility(case), facts(case)
    intent = "non_receipt" if case.claims.denies_receipt else case.claims.intent
    initial = {"case_available"}
    if case.found:
        initial.add("order_record")
    if not evidence["issues"]:
        initial.add("consistent")
    if case.return_date is not None:
        initial.add("return_record")
    if case.inspection == "passed" and case.inspection_date is not None:
        initial.add("passed_inspection_record")
    if case.refund_status in {"pending", "completed"}:
        initial.add("refund_record")
    if case.tracking:
        initial.add("tracking_record")
    initial.update(f"eligible:{action.value}" for action in available)
    operators = [
        ("verify_order", {"order_record", "consistent"}, {"order_verified"}, None),
        ("verify_return", {"order_verified", "return_record", "passed_inspection_record"}, {"return_verified"}, None),
        ("verify_refund", {"return_verified", "refund_record"}, {"refund_verified"}, None),
        ("verify_tracking", {"order_verified", "tracking_record"}, {"tracking_verified"}, None),
        ("recommend_investigation", {"order_verified", f"eligible:{Action.INVESTIGATE.value}"}, {"nonreceipt_addressed"}, Action.INVESTIGATE),
        ("recommend_escalation", {"refund_verified", f"eligible:{Action.ESCALATE.value}"}, {"refund_addressed"}, Action.ESCALATE),
        ("explain_pending", {"refund_verified", f"eligible:{Action.PENDING.value}"}, {"refund_addressed"}, Action.PENDING),
        ("explain_completed", {"refund_verified", f"eligible:{Action.COMPLETED.value}"}, {"refund_addressed"}, Action.COMPLETED),
        ("share_tracking", {"tracking_verified", f"eligible:{Action.TRACKING.value}"}, {"tracking_addressed"}, Action.TRACKING),
        ("explain_status", {"order_verified", f"eligible:{Action.STATUS.value}"}, {"status_addressed"}, Action.STATUS),
        ("request_clarification", {"case_available", f"eligible:{Action.CLARIFY.value}"}, {"review_addressed"}, Action.CLARIFY),
        ("recommend_review", {"case_available", f"eligible:{Action.REVIEW.value}"}, {"review_addressed"}, Action.REVIEW),
    ]
    for goal in ("nonreceipt_addressed", "refund_addressed", "tracking_addressed", "status_addressed", "review_addressed"):
        operators.append((f"communicate_{goal}", {goal}, {"communicated"}, None))
    requested = {"non_receipt": "nonreceipt_addressed", "refund_status": "refund_addressed",
                 "tracking": "tracking_addressed" if case.tracking else "status_addressed"}.get(intent, "review_addressed")

    def search(target):
        state = frozenset(initial)
        queue = deque([(state, None, [])])
        # A node includes its recommendation as well as its workflow facts.
        visited = {(state, None)}
        explored, blocked = [], {}
        while queue:
            state, recommendation, path = queue.popleft()
            explored.append({"facts": sorted(state), "action": recommendation, "depth": len(path)})
            if {target, "communicated"} <= state:
                return path, recommendation, explored, blocked
            for name, preconditions, effects, action in operators:
                if action is not None and recommendation is not None:
                    # A workflow recommends one next step, not multiple remedies.
                    continue
                missing = preconditions - state
                if missing:
                    blocked.setdefault(name, set()).update(missing)
                    continue
                successor = state | effects
                next_recommendation = action if action is not None else recommendation
                visited_key = (successor, next_recommendation)
                if visited_key not in visited:
                    visited.add(visited_key)
                    queue.append((successor, next_recommendation, path + [name]))
        return [], None, explored, blocked

    plan, action, explored, blocked = search(requested)
    reachable = action is not None
    target = requested
    fallback_count = 0
    if not reachable:
        target = "review_addressed"
        plan, action, fallback_explored, fallback_blocked = search(target)
        fallback_count = len(fallback_explored)
        explored += fallback_explored
        for name, missing in fallback_blocked.items():
            blocked.setdefault(name, set()).update(missing)
    summary = {"mechanism": "breadth_first_search", "intent": intent,
               "requested_goal": [requested, "communicated"], "goal": [target, "communicated"],
               "requested_reachable": reachable, "initial_facts": sorted(initial),
               "plan": plan, "plan_length": len(plan), "search_count": len(explored),
               "fallback_search_count": fallback_count, "explored": explored,
               "blocked": {name: sorted(missing) for name, missing in blocked.items()},
                "operators": [{"name": name, "prerequisites": sorted(preconditions),
                               "effects": sorted(effects), "action": action}
                              for name, preconditions, effects, action in operators],
                "effects_are_hypothetical": True}
    return Result(agent="Goal-Based", case_id=case.case_id, action=action,
                  rationale=f"Shortest equal-cost plan for {intent}: {' -> '.join(plan)}. Plan effects identify recommendations and customer communication, not completed operations.",
                  issues=evidence["issues"], trace=[summary],
                  citations=(Citation(tool="lookup_case_records", field="claims"),
                             Citation(tool="lookup_support_policy", field="VERIFY" if not reachable else {"non_receipt": "DNR", "refund_status": "REFUND", "tracking": "TRACK"}.get(intent, "VERIFY"))))
