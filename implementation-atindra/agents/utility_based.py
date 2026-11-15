"""Score only permissible actions using illustrative normalized features."""
from math import isfinite

from contracts import Action, Case, Citation, Result
from domain import eligibility, facts

WEIGHTS = {"customer_impact": 0.40, "delay": 0.25, "effort": 0.10, "error_risk": 0.25}
# Impact is a benefit; delay, effort, and error risk are costs, not probabilities.
# Feature order: customer impact, delay, effort, error risk.
FEATURES = {
    Action.STATUS: (0.65, 0.05, 0.05, 0.05),
    Action.TRACKING: (0.85, 0.10, 0.10, 0.05),
    Action.CLARIFY: (0.60, 0.40, 0.25, 0.05),
    Action.INVESTIGATE: (0.90, 0.10, 0.45, 0.15),
    Action.PENDING: (0.65, 0.45, 0.10, 0.05),
    Action.COMPLETED: (0.80, 0.15, 0.05, 0.02),
    Action.ESCALATE: (0.90, 0.05, 0.45, 0.10),
    Action.REVIEW: (0.55, 0.65, 0.65, 0.02),
}


def run(case: Case, weights: dict[str, float] | None = None) -> Result:
    effective = dict(WEIGHTS)
    if weights is not None:
        if set(weights) - set(effective):
            raise ValueError("Unknown utility weight")
        effective.update(weights)
    if any(type(value) not in {int, float} or not isfinite(value) or value < 0 for value in effective.values()):
        raise ValueError("Weights must be finite nonnegative numbers")
    available = eligibility(case)
    candidates = {}
    for action, reason in available.items():
        features = dict(zip(WEIGHTS, FEATURES[action]))
        contributions = {}
        for feature_name, feature_value in features.items():
            sign = 1 if feature_name == "customer_impact" else -1
            contributions[feature_name] = sign * effective[feature_name] * feature_value
        candidates[action.value] = {"features": features, "contributions": contributions,
                                    "score": sum(contributions.values()), "eligibility": reason}
    # Highest score first; ties prefer a non-review action, then alphabetical order.
    ranked = sorted(available, key=lambda action: (
        -candidates[action.value]["score"], action == Action.REVIEW, action.value))
    chosen = ranked[0]
    excluded = {action.value: "Ineligible under the supplied evidence and policy, regardless of utility."
                for action in Action if action not in available}
    return Result(agent="Utility-Based", case_id=case.case_id, action=chosen,
                  rationale=f"Maximum permissible weighted utility: {candidates[chosen.value]['score']:.4f}. {available[chosen]} Features and weights are synthetic teaching assumptions.",
                  issues=facts(case)["issues"], trace=[{"mechanism": "weighted_utility", "weights": effective,
                      "candidates": candidates, "ranking": [a.value for a in ranked], "excluded": excluded,
                      "formula": "impact*weight - delay*weight - effort*weight - error_risk*weight"}],
                  citations=(Citation(tool="lookup_case_records", field="claims"),
                             Citation(tool="lookup_support_policy", field="SAFE")))
