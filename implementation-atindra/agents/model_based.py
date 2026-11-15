"""Replay observations, reconcile the current snapshot, then apply belief rules."""
from copy import deepcopy
from datetime import date

from pydantic import ValidationError

from contracts import Action, Case, Citation, Result
from domain import facts

BELIEF_FIELDS = ("found", "item", "order_status", "delivery_date", "proof", "tracking",
                 "expected_date", "return_date", "inspection", "inspection_date", "refund_status")
DATE_FIELDS = {"delivery_date", "expected_date", "return_date", "inspection_date"}


def run(case: Case) -> Result:
    # These objects are local: no belief can leak into the next case or invocation.
    belief = {}
    sources = {}
    latest_observation_by_field = {}
    transitions = []
    issues = []
    for observation in sorted(case.observations, key=lambda entry: entry.date):
        before = deepcopy(belief)
        field, value = observation.field, observation.value
        previous = latest_observation_by_field.get(field)
        accepted = True
        if field not in BELIEF_FIELDS:
            issues.append(f"Unsupported history field {field} from {observation.source}.")
            accepted = False
        if observation.date > case.today:
            issues.append(f"Future observation {field} from {observation.source}.")
            accepted = False
        if previous:
            if previous.date == observation.date and previous.value != value:
                issues.append(f"Conflicting observations for {field} on {observation.date}.")
            if field == "refund_status" and previous.value == "completed" and value != "completed":
                issues.append("Refund history regresses after completion.")
            if field == "order_status" and (
                (previous.value in {"delivered", "returned"} and value in {"shipped", "in_transit"})
                or (previous.value == "returned" and value == "delivered")
            ):
                issues.append("Order history regresses after delivery/return.")
        parsed = value
        if accepted:
            try:
                if field in DATE_FIELDS:
                    parsed = date.fromisoformat(value)
                elif field == "found":
                    if value not in {"true", "false"}:
                        raise ValueError("found must be true or false")
                    parsed = value == "true"
                # Validate the history value without allowing identity/intent edits.
                Case.model_validate({**case.model_dump(), field: parsed})
            except (ValueError, ValidationError):
                issues.append(f"Invalid observation value {value!r} for {field}.")
                accepted = False
        latest_observation_by_field[field] = observation
        if accepted:
            belief[field] = parsed
            sources[field] = observation.source
        transitions.append({"phase": "history", "date": observation.date.isoformat(),
                            "field": field, "value": value, "source": observation.source,
                            "accepted": accepted, "before": before, "after": deepcopy(belief)})
    for field in BELIEF_FIELDS:
        current = getattr(case, field)
        before = deepcopy(belief)
        if field in belief and belief[field] != current:
            issues.append(f"Current {field} conflicts with replayed evidence from {sources[field]}.")
        # The snapshot is observed now, not retroactively at the first event date.
        belief[field] = current
        sources[field] = "current_snapshot"
        transitions.append({"phase": "current_snapshot", "date": case.today.isoformat(),
                            "field": field, "value": current, "source": "current_snapshot",
                            "accepted": True, "before": before, "after": deepcopy(belief)})
    reconstructed = Case.model_validate({**case.model_dump(), **belief})
    evidence = facts(reconstructed)
    issues = list(dict.fromkeys([*issues, *evidence["issues"]]))
    policy_id = "VERIFY"
    if issues:
        action, reason = Action.CLARIFY, "Reconstructed belief contains unresolved evidence: " + "; ".join(issues)
    elif reconstructed.claims.intent == "non_receipt" or reconstructed.claims.denies_receipt:
        policy_id = "DNR"
        age = evidence["dnr_age"]
        if age is not None and 0 <= age <= reconstructed.policy.dnr_window_days:
            action, reason = Action.INVESTIGATE, f"Delivered non-receipt report is {age} days old and within the inclusive reporting window; proof does not establish receipt."
        else:
            action, reason = Action.REVIEW, "Delivery report falls outside the reporting window or chronology is unknown."
    elif reconstructed.claims.intent == "refund_status":
        policy_id = "REFUND"
        if evidence["refund_verified"] and reconstructed.refund_status == "completed":
            action, reason = Action.COMPLETED, "Reconciled refund evidence shows completion, not pending escalation."
        elif evidence["overdue"]:
            action, reason = Action.ESCALATE, f"Passed inspection and pending refund exceed the business-day deadline {evidence['refund_deadline']}; recommend payments escalation only."
        elif evidence["refund_verified"]:
            action, reason = Action.PENDING, f"Verified pending refund remains within SLA through {evidence['refund_deadline']}."
        else:
            action, reason = Action.CLARIFY, "Refund prerequisites are unresolved."
    elif reconstructed.claims.intent == "tracking":
        policy_id = "TRACK"
        if reconstructed.order_status not in {"shipped", "in_transit"}:
            action, reason = Action.CLARIFY, "Shipment status cannot support tracking."
        elif reconstructed.expected_date is not None and reconstructed.today > reconstructed.expected_date:
            action, reason = Action.REVIEW, "Expected date has passed; history does not establish a physical resolution."
        elif reconstructed.tracking and reconstructed.tracking.strip():
            action, reason = Action.TRACKING, "Reconciled shipment history supports sharing recorded tracking."
        else:
            action, reason = Action.STATUS, "Share known shipment status and expected date; tracking text is unavailable."
    else:
        action, reason = Action.CLARIFY, "Clarify intent before selecting a support workflow."
    return Result(agent="Model-Based Reflex", case_id=case.case_id, action=action, rationale=reason,
                  issues=tuple(issues), citations=(Citation(tool="lookup_case_records", field="observations"),
                                                Citation(tool="lookup_support_policy", field=policy_id)),
                  trace=[{"mechanism": "observation_replay", "transitions": transitions, "belief": belief,
                          "sources": sources, "conflicts": issues,
                          "derived": evidence, "model_copy": reconstructed.model_dump(mode="json")}])
