"""Ordered current-observation rules, deliberately without temporal reasoning."""
from contracts import Action, Case, Citation, Result


def run(case: Case) -> Result:
    mismatch = (
        not case.found
        or (case.claims.found is not None and case.claims.found != case.found)
        or (case.claims.item is not None and case.claims.item.casefold() != case.item.casefold())
        or (case.claims.returned_date is not None and case.claims.returned_date != case.return_date)
    )
    refund_intent = case.claims.intent == "refund_status"
    rules = [
        (mismatch, Action.CLARIFY, "Current identity, item, or return claim lacks matching records.", "VERIFY"),
        ((case.claims.denies_receipt or case.claims.intent == "non_receipt") and case.order_status == "delivered",
         Action.INVESTIGATE, "Current delivered status and non-receipt claim trigger investigation; no history or age calculation.", "DNR"),
        (refund_intent and case.return_date is not None and case.inspection == "passed" and case.refund_status == "completed",
         Action.COMPLETED, "Current refund status is completed.", "REFUND"),
        (refund_intent and case.return_date is not None and case.inspection == "passed" and case.refund_status == "pending",
         Action.PENDING, "Current refund status is pending; this reflex does not calculate an historical SLA deadline.", "REFUND"),
        (case.claims.intent == "tracking" and case.order_status in {"shipped", "in_transit"} and bool(case.tracking),
         Action.TRACKING, "Current shipment status and tracking text are available; no date reasoning.", "TRACK"),
        (True, Action.CLARIFY, "No supported current-observation rule matched; clarify the request.", "VERIFY"),
    ]
    checked = []
    for index, (matches, action, reason, policy_id) in enumerate(rules, 1):
        checked.append({"rule": index, "matched": bool(matches)})
        if matches:
            return Result(agent="Simple Reflex", case_id=case.case_id, action=action, rationale=reason,
                          citations=(Citation(tool="lookup_case_records", field="claims"),
                                     Citation(tool="lookup_support_policy", field=policy_id)),
                          trace=[{"mechanism": "first_match", "uses_history": False, "uses_dates": False,
                                  "checked_rules": checked, "fired_rule": index}])
    raise AssertionError("The fallback rule always matches")
