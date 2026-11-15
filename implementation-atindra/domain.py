"""Shared evidence checks and eligibility, never shared answer selection."""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from contracts import Action, Case, Result, Status


def add_business_days(start: date, count: int) -> date:
    if count < 0:
        raise ValueError("Business-day count must be nonnegative")
    current = start
    added = 0
    while added < count:
        current += timedelta(days=1)
        if current.weekday() < 5:
            added += 1
    return current


def facts(case: Case) -> dict[str, Any]:
    issues: list[str] = []
    if not case.found:
        issues.append("Order record not found; verify identity.")
    if case.claims.found is not None and case.claims.found != case.found:
        issues.append("Customer found claim conflicts with the order record.")
    if case.claims.item is not None and case.claims.item.casefold() != case.item.casefold():
        issues.append("Customer item conflicts with the recorded item.")
    if case.claims.returned_date is not None:
        if case.return_date is None:
            issues.append("Customer return claim has no return evidence.")
        elif case.claims.returned_date != case.return_date:
            issues.append("Customer return date conflicts with the recorded return date.")
        if case.claims.returned_date > case.today:
            issues.append("Customer return date is in the future.")

    for field in ("delivery_date", "return_date", "inspection_date"):
        value = getattr(case, field)
        if value is not None and value > case.today:
            issues.append(f"{field} is in the future.")
    if case.order_status == "delivered" and case.delivery_date is None:
        issues.append("Delivered status has no delivery date.")
    if case.order_status in {"in_transit", "shipped"} and case.delivery_date is not None:
        issues.append("Order status conflicts with the recorded delivery date.")
    if case.order_status in {"in_transit", "shipped"} and (case.return_date or case.inspection_date):
        issues.append("Outbound shipment status conflicts with return/inspection evidence.")
    if case.order_status == "returned" and case.return_date is None:
        issues.append("Returned status has no return evidence.")
    if case.claims.intent == "tracking" and case.expected_date is None:
        issues.append("Expected delivery date is missing.")
    if case.claims.denies_receipt or case.claims.intent == "non_receipt":
        if case.order_status != "delivered":
            issues.append("Non-receipt report is not supported by delivered status.")
        if case.delivery_date is None and case.order_status != "delivered":
            issues.append("Non-receipt report has no delivery date.")
    if case.inspection != "unknown":
        if case.return_date is None:
            issues.append("Inspection requires return evidence.")
        if case.inspection_date is None:
            issues.append("Inspection date is missing.")
    if case.inspection_date is not None and case.inspection == "unknown":
        issues.append("Inspection outcome is unknown.")
    if case.return_date is not None and case.delivery_date is not None:
        if case.return_date < case.delivery_date:
            issues.append("Return date precedes delivery.")
    if case.inspection_date is not None and case.return_date is not None:
        if case.inspection_date < case.return_date:
            issues.append("Inspection date precedes return.")
    if case.claims.intent == "refund_status" or case.refund_status != "unknown":
        if case.return_date is None:
            issues.append("Refund verification requires return evidence.")
        if case.inspection != "passed":
            issues.append("Refund verification requires a passed inspection.")
        if case.refund_status == "unknown":
            issues.append("Refund status is unknown.")

    # Replay in date order without replacing current records or hiding conflicts.
    latest: dict[str, Any] = {}
    terminal_order = None
    refund_completed = False
    observed_fields = {"order_status", "delivery_date", "return_date", "inspection", "inspection_date", "refund_status", "tracking"}
    for observation in sorted(case.observations, key=lambda entry: entry.date):
        if observation.field not in observed_fields:
            issues.append(f"Unsupported observation field: {observation.field}.")
        else:
            try:
                candidate = {**case.model_dump(), observation.field: observation.value}
                Case.model_validate(candidate)
                if observation.field == "order_status" and observation.value not in {"unknown", "shipped", "in_transit", "delivered", "returned"}:
                    raise ValueError("Unknown order status")
            except ValueError:
                issues.append(f"Invalid observation value for {observation.field}.")
        if observation.field == "order_status":
            if terminal_order in {"delivered", "returned"} and observation.value in {"shipped", "in_transit"}:
                issues.append("Order status history regresses after delivery/return.")
            if terminal_order == "returned" and observation.value == "delivered":
                issues.append("Order status history regresses after return.")
            if observation.value in {"delivered", "returned"}:
                terminal_order = observation.value
        if observation.field == "refund_status":
            if refund_completed and observation.value != "completed":
                issues.append("Refund history contradicts a completed refund.")
            refund_completed = refund_completed or observation.value == "completed"
        if observation.date > case.today:
            issues.append(f"Observation {observation.field} from {observation.source} is in the future.")
        previous = latest.get(observation.field)
        if previous is not None:
            if previous.date == observation.date and previous.value != observation.value:
                issues.append(f"Conflicting observations for {observation.field} on {observation.date}.")
            if observation.field == "refund_status" and previous.value == "completed" and observation.value != "completed":
                issues.append("Refund history contradicts a completed refund.")
            if observation.field == "order_status" and previous.value in {"delivered", "returned"} and observation.value in {"shipped", "in_transit"}:
                issues.append("Order status history regresses after delivery/return.")
            if observation.field == "order_status" and previous.value == "returned" and observation.value == "delivered":
                issues.append("Order status history regresses after return.")
        latest[observation.field] = observation
    for field, observation in latest.items():
        if field in Case.model_fields and field not in {"observations", "claims", "policy"}:
            current = getattr(case, field)
            if isinstance(current, date):
                current = current.isoformat()
            elif isinstance(current, bool):
                current = str(current).lower()
            if current is None or str(current) != observation.value:
                issues.append(f"Current {field} conflicts with observation from {observation.source}.")

    dnr_age = None
    if case.delivery_date is not None and case.delivery_date <= case.today:
        dnr_age = (case.today - case.delivery_date).days
    refund_verified = (
        case.found and not issues and case.return_date is not None
        and case.inspection == "passed" and case.inspection_date is not None
        and case.refund_status in {"pending", "completed"}
    )
    deadline = None
    if refund_verified:
        deadline = add_business_days(case.inspection_date, case.policy.refund_sla_business_days)
    return {
        "issues": tuple(dict.fromkeys(issues)),
        "dnr_age": dnr_age,
        "refund_deadline": deadline,
        "refund_verified": refund_verified,
        "overdue": bool(refund_verified and case.refund_status == "pending" and case.today > deadline),
    }


def eligibility(case: Case) -> dict[Action, str]:
    evidence = facts(case)
    actions = {Action.REVIEW: "Human review is available; no operational remedy is executed."}
    if evidence["issues"]:
        actions[Action.CLARIFY] = "Resolve missing or conflicting evidence: " + "; ".join(evidence["issues"])
        return actions
    if case.claims.intent == "non_receipt" or case.claims.denies_receipt:
        age = evidence["dnr_age"]
        if age is not None and 0 <= age <= case.policy.dnr_window_days:
            actions[Action.INVESTIGATE] = "Delivered-not-received report is within the reporting window; proof is not a prerequisite."
        else:
            actions[Action.REVIEW] = "Delivery report is outside the reporting window or its chronology is unknown."
    elif case.claims.intent == "refund_status":
        if evidence["refund_verified"]:
            if case.refund_status == "completed":
                actions[Action.COMPLETED] = "Verified refund record is completed."
            elif evidence["overdue"]:
                actions[Action.ESCALATE] = f"Pending refund exceeded the deadline {evidence['refund_deadline']}."
            else:
                actions[Action.PENDING] = f"Pending refund is within SLA through {evidence['refund_deadline']}."
    elif case.claims.intent == "tracking":
        if case.order_status in {"shipped", "in_transit"}:
            if case.expected_date is None:
                actions[Action.CLARIFY] = "Expected delivery date is missing."
            elif case.today > case.expected_date:
                actions[Action.REVIEW] = "Expected delivery date has passed; review before proposing a resolution."
            else:
                actions[Action.STATUS] = f"Order is {case.order_status}; expected {case.expected_date}."
                if case.tracking and case.tracking.strip():
                    actions[Action.TRACKING] = "Share the recorded tracking information without inventing a delay."
                else:
                    actions[Action.CLARIFY] = "Tracking evidence is missing."
        else:
            actions[Action.CLARIFY] = "Tracking prerequisites are unavailable."
    else:
        actions[Action.CLARIFY] = "Clarify the customer intent before selecting a support workflow."
    return actions


def policy_records(case: Case) -> dict[str, str]:
    return {
        "case_id": case.case_id,
        "version": case.policy.version,
        "SAFE": "Recommend next steps only. Do not issue refunds, replacements, order changes, or carrier contact.",
        "VERIFY": "Missing prerequisites, future events, or conflicting claims/records/history require clarification or human review. Passed inspection requires return evidence.",
        "DNR": f"For delivered-not-received reports within {case.policy.dnr_window_days} calendar days (inclusive), recommend delivery investigation. Photo/signature proof is not required. Outside the window, seek human review.",
        "REFUND": f"Verify return evidence, passed inspection and its date, and refund status. Pending refunds are within SLA through {case.policy.refund_sla_business_days} business days after inspection (Monday-Friday, exclude inspection day, no holidays). Escalate when today is after the deadline, including weekends. Explain completed refunds rather than escalating them.",
        "TRACK": "For in-transit/shipped orders with usable tracking and an expected date not yet passed, share tracking or explain status. Missing dates require clarification; passed expected dates require review. Never fabricate delay or resolution.",
    }


def validate_result(case: Case, result: Result) -> Result:
    issues = list(result.issues)
    if result.case_id != case.case_id:
        issues.append("Result case_id does not match the selected case.")
    if result.action is not None and result.action not in eligibility(case):
        issues.append(f"Raw action {result.action.value} is ineligible for the supplied evidence.")
    status = result.status
    if len(issues) > len(result.issues) and status in {Status.OK, Status.WARNING}:
        status = Status.WARNING
    return result.model_copy(update={"status": status, "issues": tuple(dict.fromkeys(issues))})
