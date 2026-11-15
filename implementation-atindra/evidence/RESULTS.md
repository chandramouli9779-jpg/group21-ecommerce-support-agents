# Results And Evidence

## Current Results (2026-11-14)

This page points to the saved final results. Start with the test logs, one live comparison, and the learning screenshots. The [README](../README.md) explains the agents, setup, policies, and comparison.

| Check                                   | Saved result                                         | File                                                 |
| --------------------------------------- | ---------------------------------------------------- | ---------------------------------------------------- |
| Offline tests                           | 275 passed, 4 live tests deselected in 2.45s         | [Test log](verification-offline-test-results.txt)    |
| Recorded package in a fresh environment | 275 passed, 4 deselected in 15.54s                   | [Package test log](package-offline-test-results.txt) |
| Real Ollama A-D batch                   | 4 integration tests passed, 64 deselected in 243.14s | [Live test log](final-live-test-results.txt)         |
| Classical comparison                    | 20 results using starting learning counts            | [Decisions and traces](classical-results.jsonl)      |
| Learning feedback                       | Two failures changed A from investigation to review  | [Screenshots and exports](#learning-demonstration)   |

These are recorded runs, not new tests of the documentation edits.

## Classical A-D Comparison

The [six-agent table](../README.md#six-agent-results) gives the outcomes. [classical-results.jsonl](classical-results.jsonl) saves each classical agent's decision, explanation, citations, and trace. Simple Reflex's B answer is ineligible and has `warning`.

For the different mechanisms, see the [source links](../README.md#agents) and the saved belief updates, BFS plans, utility scores, and learning estimates. [mechanisms_A_offline.png](mechanisms_A_offline.png) shows expanded UI details.

## Real LLM Evaluation

Each final trace records both successful model-requested tools, their returned records and policies, and final citations. All four used two model rounds with no format repair.

| Case                  | Actual recommendation    | Status    | Tool trace               |
| --------------------- | ------------------------ | --------- | ------------------------ |
| A: non-receipt        | `delivery_investigation` | `ok`      | [A](llm_qwen3-4b_A.json) |
| B: overdue refund     | `payments_escalation`    | `ok`      | [B](llm_qwen3-4b_B.json) |
| C: incomplete records | `explain_refund_pending` | `warning` | [C](llm_qwen3-4b_C.json) |
| D: normal tracking    | `share_tracking`         | `ok`      | [D](llm_qwen3-4b_D.json) |

C is incorrect. Its cited refund status is `unknown`, and the return and inspection are unverified. The model's answer remains visible rather than being replaced. See the [README comparison](../README.md#six-agent-results) for expected actions and the distinction between passing integration and a correct recommendation.

### Separate Live UI Runs

These screenshots came from separate real Streamlit calls, not replays of the pytest batch. The downloads contain all six decisions, explanations, and traces. Their outcomes agree with the batch, including C's warning.

| Case | Screenshot                            | Six-agent download                     |
| ---- | ------------------------------------- | -------------------------------------- |
| A    | [Live A](scenario_A_live.png)         | [A JSONL](final-ui-A-comparison.jsonl) |
| B    | [Live B](scenario_B_live.png)         | [B JSONL](final-ui-B-comparison.jsonl) |
| C    | [Live C warning](scenario_C_live.png) | [C JSONL](final-ui-C-comparison.jsonl) |
| D    | [Live D](scenario_D_live.png)         | [D JSONL](final-ui-D-comparison.jsonl) |

## Learning Demonstration

The saved sequence used actual feedback buttons with a new comparison between clicks. The LLM was disabled. The [README learning example](../README.md#learning) explains the counts and how to reproduce the switch.

| Stage           | Choice        | Screenshot                                | Download                                 |
| --------------- | ------------- | ----------------------------------------- | ---------------------------------------- |
| Starting counts | Investigation | [Start](learning_A_stage_0.png)           | [Start JSONL](learning_A_stage_0.jsonl)  |
| First failure   | Investigation | [First failure](learning_A_stage_1.png)   | [First JSONL](learning_A_stage_1.jsonl)  |
| Second failure  | Human review  | [Decision change](learning_A_stage_2.png) | [Second JSONL](learning_A_stage_2.jsonl) |

[Agent tests](../tests/test_agents.py) and [UI tests](../tests/test_app.py) also check adaptation, reload, reset, and the feedback sequence. History was restored after capture. Blank screenshot space was cropped and a personal-path caption was masked. Decisions and scores were not changed.

## Screenshot Scope

Offline desktop comparisons are saved for [A](scenario_A_offline.png), [B](scenario_B_offline.png), [C](scenario_C_offline.png), and [D](scenario_D_offline.png). The LLM row is `not_run` in these images.

[Expanded mechanisms](mechanisms_A_offline.png) show utility scoring details. The learning screenshots above show feedback counts and the change in recommendation.

Screenshots can be recreated using [capture_screenshots.py](../capture_screenshots.py). Run `python capture_screenshots.py --help` for instructions. Playwright and Chrome are required.

## Clean Package Verification

The recorded package was installed in a fresh Python 3.13.5 environment. The [package log](package-offline-test-results.txt) records 275 passing offline tests. The classical runner also succeeded.

## Runtime Settings

**Local test environment:** Python 3.13.5, Ollama 0.40.16, and `qwen3:4b` (Qwen3 4B Thinking 2507). Python dependencies are listed in [requirements.txt](../requirements.txt).

The [adapter](../agents/llm.py) and final traces record the settings: localhost port 11434, temperature 0, `reasoning=None`, a generation limit of 2400 tokens, context 8192, and a 180-second timeout per request. Timings include server loading and waiting, not just generation.

## Limitations

The [README limitations](../README.md#limitations) cover scope, learning storage, and variation in model results. B's Simple Reflex warning and C's LLM warning are preserved above. Tool use and citation checks are separate from policy support. They do not prove every explanation claim. No real order changes or refunds occurred.
