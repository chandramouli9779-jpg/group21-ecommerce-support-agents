"""Print reproducible A-D classical comparisons without writing experience."""
import json
from agents import simple_reflex, model_based, goal_based, utility_based, learning
from contracts import load_cases
from domain import validate_result


if __name__ == "__main__":
    for case in load_cases().values():
        for module in (simple_reflex, model_based, goal_based, utility_based, learning):
            result = module.run(case, counts=learning.seed_counts()) if module is learning else module.run(case)
            print(json.dumps(validate_result(case, result).model_dump(mode="json")))
