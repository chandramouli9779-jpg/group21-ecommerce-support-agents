"""Session-only comparison of one frozen case across six support agents."""
from copy import deepcopy
import streamlit as st

from agents import goal_based, learning, llm, model_based, simple_reflex, utility_based
from contracts import Action, Result, Status, load_cases
from domain import eligibility, policy_records, validate_result

st.set_page_config(page_title="Support Lab", layout="wide")
COUNTS_PATH = learning.COUNTS_FILE
EXPECTED = {"A": Action.INVESTIGATE, "B": Action.ESCALATE,
            "C": Action.CLARIFY, "D": Action.TRACKING}
CLASSICAL = (simple_reflex, model_based, goal_based, utility_based)
MECHANISMS = {
    "Simple Reflex": "First matching current-field rule; no history replay or SLA arithmetic.",
    "Model-Based Reflex": "Replay dated observations, reconcile beliefs, then apply belief rules.",
    "Goal-Based": "Breadth-first search for a shortest eligible recommendation workflow.",
    "Utility-Based": "Maximize weighted benefit minus costs among policy-eligible actions.",
    "Learning": "Rank eligible actions using persistent, smoothed success/failure counts.",
}


def clear_results():
    st.session_state.pop("comparison", None)


def main():
    cases = load_cases()
    with st.sidebar:
        st.header("Support Lab")
        case_id = st.selectbox("Scenario", list(cases), key="scenario", on_change=clear_results)
        model = st.text_input("Local Ollama model", "qwen3:4b", key="model", on_change=clear_results)
        include_llm = st.checkbox("Run real local LLM", value=True, key="include_llm", on_change=clear_results)
        st.caption("No automatic model fallback. All records are simulated and read-only.")
        if st.button("Reset learning history"):
            try:
                learning.reset(COUNTS_PATH)
                clear_results()
                st.session_state.pop("last_feedback", None)
                st.rerun()
            except (OSError, ValueError) as exc:
                st.error(f"Learning reset failed: {exc}")

    case = cases[case_id]
    st.title("Evidence Before Action")
    st.caption("E-commerce support | Five classical mechanisms and one local tool-calling model")
    st.subheader(f"{case.case_id} / {case.order_id} / {case.item}")
    st.write(case.message)
    st.caption(f"Fixed evaluation date: {case.today} | Structured intent: {case.claims.intent}")
    if st.session_state.get("last_feedback"):
        feedback = st.session_state.last_feedback
        before, after = feedback["before"], feedback["after"]
        old_rate = (before["success"] + 1) / (sum(before.values()) + 2)
        new_rate = (after["success"] + 1) / (sum(after.values()) + 2)
        st.success(f"Feedback saved for {feedback['context']} / {feedback['action']}: "
                   f"estimated success {old_rate:.4f} -> {new_rate:.4f}. Run Comparison again.")
        st.caption(f"Persistent history: {COUNTS_PATH}")
        with st.expander("Last explicit feedback"):
            st.json(feedback)
    with st.expander("Try the learning demonstration"):
        st.write("Select A, disable the LLM for a quick demo, reset learning history, and run a comparison. "
                 "Record a failure under Learning, then compare again. Repeat once: investigation's "
                 "estimate falls from 7/11 to 7/13, below review's 6/11, so Learning chooses human review. "
                 "Both actions remain policy-eligible; feedback cannot authorize an unsafe action.")
    with st.expander("Shared case and simulation policies"):
        st.json(case.model_dump(mode="json"))
        st.json(policy_records(case))
    history_error = None
    try:
        counts = learning.load_counts(COUNTS_PATH)
    except (OSError, ValueError) as exc:
        counts = None
        history_error = str(exc)
        st.error(f"Cannot read learning history: {exc}. Reset it to restore the demo.")

    if st.button("Run Comparison", type="primary"):
        results = []
        for module in CLASSICAL:
            try:
                results.append(validate_result(case, module.run(case)))
            except Exception as exc:
                results.append(Result(agent=module.__name__.split(".")[-1], case_id=case_id,
                                      status=Status.ERROR, rationale=f"Agent failed: {type(exc).__name__}"))
        try:
            if history_error:
                raise ValueError(history_error)
            results.append(validate_result(case, learning.run(case, deepcopy(counts))))
        except (OSError, ValueError) as exc:
            results.append(Result(agent="Learning", case_id=case_id, status=Status.ERROR,
                                  rationale=f"History unavailable: {exc}"))
        if include_llm:
            with st.spinner(f"Retrieving evidence with {model}..."):
                results.append(llm.run(case, model=model))
        else:
            results.append(Result(agent="LLM", case_id=case_id, model=model,
                                  status=Status.NOT_RUN, rationale="Real local LLM was not run."))
        st.session_state.comparison = {"case": case, "model": model, "include_llm": include_llm,
                                       "counts": deepcopy(counts), "results": results}

    comparison = st.session_state.get("comparison")
    if comparison and (comparison["case"] != case or comparison["model"] != model
                       or comparison["include_llm"] != include_llm or comparison["counts"] != counts):
        clear_results()
        comparison = None
    if not comparison:
        st.info("Run Comparison to inspect six outcomes. Results remain frozen until inputs or feedback change.")
        return
    allowed = eligibility(case)
    st.subheader("Comparison")
    comparison_rows = []
    for result in comparison["results"]:
        comparison_rows.append({
            "Agent": result.agent,
            "Action": result.action.value if result.action else "-",
            "Status": result.status.value,
            "Policy Eligible": result.action in allowed if result.action else None,
            "Fixture Match": result.action == EXPECTED[case_id] if result.action else None,
            "Rationale": result.rationale,
        })
    st.dataframe(comparison_rows, hide_index=True, width="stretch")
    st.caption(f"Fixture target: {EXPECTED[case_id].value}. Exact agreement is not a general accuracy metric. Raw decisions are never replaced by the evaluator.")
    st.subheader("Why decisions differ")
    for result in comparison["results"]:
        st.write(f"**{result.agent}:** {MECHANISMS.get(result.agent, 'Local model selects tools and synthesizes retrieved evidence; validation does not replace its answer.')} "
                 f"Result: {result.action.value if result.action else result.status.value}.")
    if case_id == "B":
        st.info("Simple Reflex reads the current pending-refund label without calculating its age. "
                "The informed mechanisms check the inspection date and business-day deadline. "
                "The reflex's raw answer is retained and flagged, not silently corrected.")
    else:
        st.caption("Agreement does not imply identical algorithms. Inspect belief replay, search plans, "
                   "utility scores, and learning estimates below to see how each decision was reached.")
    for result in comparison["results"]:
        with st.expander(f"{result.agent}: {result.action.value if result.action else result.status.value}"):
            st.write(result.rationale)
            st.caption(MECHANISMS.get(result.agent, "Actual selected-case tool calls and grounding checks."))
            if result.issues:
                st.warning("; ".join(result.issues))
            if result.model:
                st.caption(f"Model {result.model} | {result.latency_seconds}s | {result.status.value}")
            st.json([citation.model_dump() for citation in result.citations])
            if result.trace and result.agent in {"Model-Based Reflex", "Goal-Based", "Utility-Based", "Learning"}:
                details = result.trace[0]
                if result.agent == "Model-Based Reflex":
                    st.dataframe([{k: row[k] for k in ("phase", "date", "field", "value", "source", "accepted")}
                                  for row in details["transitions"]], hide_index=True)
                elif result.agent == "Goal-Based":
                    st.write("Hypothetical recommendation plan: " + " -> ".join(details["plan"]))
                    st.caption(f"Explored {details['search_count']} states; requested goal reachable: {details['requested_reachable']}.")
                else:
                    st.dataframe([{"Action": action, **info} for action, info in details["candidates"].items()], hide_index=True)
                    if result.agent == "Utility-Based":
                        cautious = utility_based.run(case, weights={"customer_impact": 0.1, "delay": 0, "effort": 0, "error_risk": 1})
                        st.caption(f"Weight sensitivity, not a second comparison result: risk-heavy weights "
                                   f"(impact=0.1, delay=0, effort=0, risk=1) choose {cautious.action.value}; "
                                   "the eligible action set is unchanged.")
                        st.dataframe([{"Action": action, "Default score": info["score"],
                                       "Risk-heavy score": cautious.trace[0]["candidates"][action]["score"]}
                                      for action, info in details["candidates"].items()], hide_index=True)
            for entry in result.trace:
                st.json(entry)
            if result.agent == "Learning" and result.action and result.trace:
                saved_context = result.trace[0]["context"]
                left, right = st.columns(2)
                for column, success, label in ((left, True, "Record success"), (right, False, "Record failure")):
                    if column.button(label, key=f"feedback-{success}"):
                        try:
                            history_key = f"{saved_context}|{result.action.value}"
                            before = deepcopy(comparison["counts"].get(
                                history_key, {"success": 0, "failure": 0}))
                            after = learning.feedback(COUNTS_PATH, saved_context, result.action, success)
                            st.session_state.last_feedback = {"context": saved_context, "action": result.action.value,
                                                              "before": before, "after": after}
                            clear_results()
                            st.rerun()
                        except (OSError, ValueError) as exc:
                            st.error(f"Feedback failed: {exc}")
    st.download_button("Download this comparison", data="\n".join(r.model_dump_json() for r in comparison["results"]),
                       file_name=f"comparison_{case_id}_{model.replace(':', '-')}.jsonl", mime="application/jsonl")


if __name__ == "__main__":
    main()
