"""Fixed contexts with persistent smoothed outcomes and hard eligibility."""
from __future__ import annotations

import json
from pathlib import Path

from contracts import Action, Case, Citation, Result
from domain import eligibility, facts

COUNTS_FILE = Path(__file__).resolve().parents[1] / "runtime" / "learning_counts.json"
CONTEXTS = ("timely_nonreceipt", "nonreceipt_review", "conflict_review", "refund_overdue",
            "refund_pending", "refund_completed", "refund_review", "tracking", "tracking_review")


def context(case: Case) -> str:
    evidence = facts(case)
    if evidence["issues"]:
        return "conflict_review"
    if case.claims.intent == "non_receipt" or case.claims.denies_receipt:
        age = evidence["dnr_age"]
        return "timely_nonreceipt" if age is not None and 0 <= age <= case.policy.dnr_window_days else "nonreceipt_review"
    if case.claims.intent == "refund_status":
        if not evidence["refund_verified"]:
            return "refund_review"
        if case.refund_status == "completed":
            return "refund_completed"
        return "refund_overdue" if evidence["overdue"] else "refund_pending"
    if case.claims.intent == "tracking":
        return "tracking" if case.order_status in {"shipped", "in_transit"} and case.expected_date is not None and case.today <= case.expected_date else "tracking_review"
    return "unknown"


def seed_counts() -> dict[str, dict[str, int]]:
    counts = {f"{label}|{action.value}": {"success": 0, "failure": 0}
              for label in CONTEXTS for action in Action}
    counts[f"timely_nonreceipt|{Action.INVESTIGATE.value}"] = {"success": 6, "failure": 3}
    counts[f"timely_nonreceipt|{Action.REVIEW.value}"] = {"success": 5, "failure": 4}
    return counts


def load_counts(path: Path = COUNTS_FILE) -> dict[str, dict[str, int]]:
    path = Path(path)
    if not path.exists():
        return seed_counts()
    counts = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(counts, dict):
        raise ValueError("Counts must be a JSON object")
    for key, stats in counts.items():
        if not isinstance(key, str) or key.count("|") != 1 or not key.split("|")[0]:
            raise ValueError("Invalid context/action key")
        Action(key.split("|")[1])
        if not isinstance(stats, dict) or set(stats) != {"success", "failure"}:
            raise ValueError("Each entry requires success and failure counts")
        if any(type(value) is not int or value < 0 for value in stats.values()):
            raise ValueError("Counts must be nonnegative integers")
    return counts


def feedback(path: Path, context: str, action: Action | str, success: bool) -> dict[str, int]:
    if not isinstance(context, str) or not context or "|" in context:
        raise ValueError("Invalid context")
    if type(success) is not bool:
        raise ValueError("Success must be a boolean")
    action = Action(action)
    counts = load_counts(path)
    entry = counts.setdefault(f"{context}|{action.value}", {"success": 0, "failure": 0})
    entry["success" if success else "failure"] += 1
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(counts, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return dict(entry)


def reset(path: Path = COUNTS_FILE) -> dict[str, dict[str, int]]:
    counts = seed_counts()
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(counts, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return counts


def run(case: Case, counts: dict | None = None) -> Result:
    history = load_counts() if counts is None else counts
    context_label = context(case)
    eligible_actions = eligibility(case)
    candidates, excluded = {}, {}
    for action in Action:
        stats = history.get(f"{context_label}|{action.value}", {"success": 0, "failure": 0})
        if not isinstance(stats, dict) or set(stats) != {"success", "failure"} or any(type(value) is not int or value < 0 for value in stats.values()):
            raise ValueError("Counts must contain nonnegative integer success/failure entries")
        estimated_success = (stats["success"] + 1) / (stats["success"] + stats["failure"] + 2)
        info = {**stats, "estimate": estimated_success}
        if action in eligible_actions:
            candidates[action.value] = {**info, "eligibility": eligible_actions[action]}
        else:
            excluded[action.value] = {**info, "reason": "Hard prerequisites are unmet; learned success cannot override eligibility."}
    tie_preference = (Action.INVESTIGATE, Action.ESCALATE, Action.COMPLETED, Action.PENDING,
                      Action.TRACKING, Action.STATUS, Action.CLARIFY, Action.REVIEW)
    # Earlier entries win when estimated success is equal.
    chosen = max(eligible_actions, key=lambda action: (
        candidates[action.value]["estimate"], -tie_preference.index(action)))
    supported = context_label in CONTEXTS
    if not supported:
        chosen = Action.REVIEW
    if supported:
        explanation = "Rank eligible actions by smoothed outcomes; use the declared preference to break ties."
    else:
        explanation = "No experience for this context; seek human review."
    return Result(agent="Learning", case_id=case.case_id, action=chosen,
                  rationale=f"Context {context_label}: {explanation} Initial nonzero counts are synthetic demo data.",
                  issues=facts(case)["issues"], trace=[{"context": context_label, "supported_context": supported,
                      "mechanism": "contextual_outcome_counts", "candidates": candidates, "excluded": excluded,
                       "formula": "(success+1)/(success+failure+2)", "tie_preference": [a.value for a in tie_preference]}],
                  citations=(Citation(tool="lookup_case_records", field="claims"),
                             Citation(tool="lookup_support_policy", field="SAFE")))
