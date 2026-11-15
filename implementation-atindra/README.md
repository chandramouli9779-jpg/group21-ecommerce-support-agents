# E-commerce Order and Refund Support Assistant

BITS Pilani WILP | Agentic AI (S2-25_PCAMZG519) | Assignment 1, Set 6 | Group 21

| Member                    | Student ID    |
| ------------------------- | ------------- |
| G.Chandramouli            | `2025paml525` |
| Atindra R K Ranjana Singh | `2025paml584` |

## Overview

This Streamlit app compares five classical agents and one local LLM agent on order, delivery, return, and refund cases. Each agent recommends a next step and explains its choice. The app uses simulated records and does not issue refunds, change orders, or contact customers or carriers.

The classical agents use Python decision logic. The LLM uses LangChain to call tools through Qwen running locally in Ollama. All six agents work from the same selected case. Expected actions are used for comparison, not supplied to the agents.

For a quick review, read the [comparison](#six-agent-results), [learning example](#learning-example), and [saved evidence](evidence/RESULTS.md). No installation is needed to inspect them.

## Setup And Run

Use Python 3.13 and run commands from the project directory containing `app.py`. Dependencies are pinned in [requirements.txt](requirements.txt).

For bash or zsh:

```bash
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

On Windows PowerShell:

```powershell
py -3.13 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

If PowerShell blocks activation, use `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` and activate again.

### Start Ollama And Streamlit

Install [Ollama](https://ollama.com/download) for the LLM. Start its desktop app or run `ollama serve` in a separate terminal if its server is not already running. The app connects to `http://127.0.0.1:11434`.

```bash
ollama pull qwen3:4b
python -m streamlit run app.py
```

1. Open the URL printed by Streamlit, normally `http://localhost:8501`. Select a case and inspect its records and policies.
2. Uncheck **Run real local LLM** for an offline comparison. It defaults to enabled. When disabled, the LLM row shows `not_run`.
3. Click **Run Comparison**. Real model calls can take minutes.
4. Expand agent details to see explanations, belief updates, plans, scores, and tool calls. **Download this comparison** saves JSONL.

Recorded runs used Python 3.13.5, Ollama 0.40.16, and the original `qwen3:4b` tag. Other model tags have not been verified.

### Run Tests

Run these separately. Neither command below needs Ollama:

```bash
python -m pytest -m "not live" -q
python run_classical.py
```

The script prints 20 classical A-D results using starting learning counts, not your saved feedback. Offline LLM tests use substitute model messages rather than real inference.

Optional live tests, with Ollama running:

```bash
python -m pytest tests/test_llm.py -m live -v -s
python -m pytest "tests/test_llm.py::test_live_qwen3_four_cases[C]" -m live -v -s
```

Replace `C` with A, B, or D for another single case. A busy server can make a batch take over 600 seconds. Live tests overwrite `evidence/llm_qwen3-4b_<case>.json`, so use a separate project copy to preserve the saved results.

## Agents

<a id="five-mechanisms"></a>

| Agent              | How it decides                                                                                                                                      | Source                                      |
| ------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------- |
| Simple Reflex      | Chooses the first matching rule from current fields. It does not replay history or calculate deadlines.                                             | [simple_reflex.py](agents/simple_reflex.py) |
| Model-Based Reflex | Rebuilds a belief state from dated observations, checks it against current records, then applies rules.                                             | [model_based.py](agents/model_based.py)     |
| Goal-Based         | Uses breadth-first search (BFS) with prerequisites and effects to find a workflow toward the goal. Falls back to clarification or review if needed. | [goal_based.py](agents/goal_based.py)       |
| Utility-Based      | Scores eligible actions by impact, delay, effort, and error risk, then chooses the highest score.                                                   | [utility_based.py](agents/utility_based.py) |
| Learning           | Uses saved success and failure counts to rank eligible actions within fixed case contexts.                                                          | [learning.py](agents/learning.py)           |
| LLM                | Calls two LangChain tools, reads their results, and returns an action with an explanation and citations.                                            | [llm.py](agents/llm.py)                     |

Utility uses `0.40*impact - 0.25*delay - 0.10*effort - 0.25*error_risk`. The UI also shows a risk-heavy weight example that changes A's choice to review. Shared policy checks limit actions but do not choose one common answer for all agents. BFS steps are proposed steps, not completed operations.

The main files are [app.py](app.py) for the UI, [contracts.py](contracts.py) for case/result types, [fixtures.json](fixtures.json) for cases, and [domain.py](domain.py) for facts and policy checks.

## Scenarios And Results

All cases use the fixed evaluation date **2026-11-13**. A-C are required by the assignment. D adds a normal tracking example.

| Case               | Prepared records                                                                                   | Expected action          |
| ------------------ | -------------------------------------------------------------------------------------------------- | ------------------------ |
| A: critical        | Delivered Nov 10, but customer denies receipt. No photo or signature.                              | `delivery_investigation` |
| B: service failure | Return inspected and passed Oct 30. Refund still pending after the Nov 6 deadline.                 | `payments_escalation`    |
| C: ambiguous       | Customer claims a return, but records do not confirm it. Inspection and refund status are unknown. | `request_clarification`  |
| D: normal          | Order is in transit and has tracking. Expected delivery is Nov 16.                                 | `share_tracking`         |

These are simulation policies, not real store policies. For example, refunds have a five-business-day deadline after inspection, excluding inspection day and ignoring holidays. Missing or conflicting prerequisites call for clarification or review. Full rules are in [domain.py](domain.py) and visible in the UI.

### Six-Agent Results

The table shows saved classical results with starting counts and the final real `qwen3:4b` batch. Labels shorten the action names above.

| Agent                     | A             | B                            | C                            | D        |
| ------------------------- | ------------- | ---------------------------- | ---------------------------- | -------- |
| Simple Reflex             | Investigation | Explain pending (ineligible) | Clarification                | Tracking |
| Model-Based Reflex        | Investigation | Payments escalation          | Clarification                | Tracking |
| Goal-Based                | Investigation | Payments escalation          | Clarification                | Tracking |
| Utility-Based             | Investigation | Payments escalation          | Clarification                | Tracking |
| Learning, starting counts | Investigation | Payments escalation          | Clarification                | Tracking |
| LLM, real run             | Investigation | Payments escalation          | Explain pending (ineligible) | Tracking |

Simple Reflex misses B because it reads the pending status without calculating the refund deadline. The LLM's C recommendation is incorrect because an unknown refund status does not establish a pending refund. Both receive `warning`, and the app keeps their original answers visible.

The other agents often agree, but reach their choices through different mechanisms. **Policy Eligible** checks the simulation rules. **Fixture Match** checks the prepared target. The LLM matched 3/4 targets, which is not a general accuracy measure. Live integration tests accept `ok` or `warning`, so passing does not mean every recommendation was correct.

## Learning

<a id="learning-example"></a>

The agent estimates success as `(success+1)/(success+failure+2)` and chooses the eligible action with the highest unrounded estimate. Starting counts are simulated experience. All context/action counts start at 0/0 except A's investigation at 6/3 and review at 5/4. Ties use a fixed order.

To reproduce the change, disable the LLM, select A, reset learning, and run a comparison. Record a failure, rerun, record another failure, and rerun again.

| State          | Investigation success/failure | Investigation estimate | Review estimate | Choice        |
| -------------- | ----------------------------- | ---------------------- | --------------- | ------------- |
| Start          | 6/3                           | `7/11`                 | `6/11`          | Investigation |
| First failure  | 6/4                           | `7/12`                 | `6/11`          | Investigation |
| Second failure | 6/5                           | `7/13`                 | `6/11`          | Human review  |

Feedback and reset save counts in `runtime/learning_counts.json`, which survives restarts. Missing history uses starting counts without creating a file. Each feedback click clears the comparison, so rerun before giving more feedback. Ordinary comparisons do not add outcomes. Reset restores the starting counts.

Screenshots: [start](evidence/learning_A_stage_0.png), [first failure](evidence/learning_A_stage_1.png), [switch to review](evidence/learning_A_stage_2.png). Matching exports are in the [learning evidence](evidence/RESULTS.md#learning-demonstration).

## LLM Tools And Checks

<a id="llm-output-and-limits"></a>

| LangChain tool                   | What it returns                                                                          |
| -------------------------------- | ---------------------------------------------------------------------------------------- |
| `lookup_case_records(case_id)`   | Selected order, delivery events, return, inspection, refund status, and customer claims. |
| `lookup_support_policy(case_id)` | Applicable safety, verification, delivery, refund, and tracking rules.                   |

These two tools group the order/status/event and policy lookups suggested in the PDF. They are restricted to the selected case. The model requests them, and the adapter sends their actual results back as tool messages.

The app checks that both tools succeeded and that the final answer has valid citations from both tools. It separately checks action eligibility, the cited policy, and relevant record fields. These checks do not prove every claim in the explanation. A valid citation can still be misinterpreted.

The adapter allows six model rounds, including at most one answer-format/citation repair. Unsupported actions stay as `warning` without a policy-based repair. Invalid answers show `invalid_output`, missing tool evidence or tool-loop exhaustion shows `incomplete_evidence`, and connection failures show `error`. There is no automatic model or classical-answer fallback.

## Evidence

Saved results from November 14 are indexed in [evidence/RESULTS.md](evidence/RESULTS.md):

- Offline tests: **275 passed, 4 deselected in 2.45s**. A fresh environment from the recorded package also passed 275 tests on the same machine.
- Real Ollama batch: **4 integration tests passed in 243.14s**. Both tools ran in every case.
- Separate real Streamlit runs: A-D screenshots and six-agent downloads. Offline screenshots show desktop comparisons and expanded mechanisms.
- Learning: three screenshots and matching downloads show the two-failure decision change. Persistence and reset are also tested.

## Rubric Checklist

| Requirement                     | Marks | Implementation and evidence                                                                                                         |
| ------------------------------- | ----- | ----------------------------------------------------------------------------------------------------------------------------------- |
| Five classical agents           | 5     | [Mechanisms and source](#agents), [agent tests](tests/test_agents.py), [saved traces](evidence/RESULTS.md#classical-a-d-comparison) |
| Local LLM and two tools         | 4     | [LangChain/Ollama adapter](agents/llm.py), [actual A-D tool calls](evidence/RESULTS.md#real-llm-evaluation)                         |
| Shared scenarios and testing    | 3     | [A-D fixtures](fixtures.json), [policy tests](tests/test_domain.py), [comparison](#six-agent-results)                               |
| Streamlit UI and comparison     | 3     | [app.py](app.py), [UI tests](tests/test_app.py), [screenshots and downloads](evidence/RESULTS.md#separate-live-ui-runs)             |
| Learning and evaluation         | 3     | [Feedback and decision change](#learning), [LLM checks](#llm-tools-and-checks), [limitations](#limitations)                         |
| Documentation and demonstration | 2     | [Setup](#setup-and-run), [requirements](requirements.txt), [test results and screenshots](evidence/RESULTS.md)                      |

## Limitations

The known incorrect recommendations are shown in the comparison above. Classical agents use structured records rather than general language understanding. Policies, utility scores, and learning counts are teaching assumptions. Learning adjusts preferences in fixed contexts and does not explore new actions or assess outcomes automatically.

Feedback storage is for one user and is not safe for concurrent writes. Model results can vary with model contents, versions, hardware, and server load.
