# VM Test Log - Group 21 combined repository

Agentic AI (PCAM ZG519), Mini Project 1. Group 21: G.Chandramouli (2025paml525),
Atindra R K Ranjana Singh (2025paml584).

This log records runs of both original implementations on the course lab VMs (Prayogshala).
Both implementation folders are kept unchanged as the record of the independent work; findings
that qualify statements in their READMEs are recorded here instead of editing them.

Raw output files from the second VM are in [`vm-runs/2026-11-17/`](vm-runs/2026-11-17/).
Results from the first VM come from terminal screenshots shared during the session; that run
was not saved to log files.

## Environments

| Item | Laptop (Chandramouli) | Atindra's machine (from his README) | VM 1 (15 Nov) | VM 2 (17 Nov) |
|---|---|---|---|---|
| Host | Windows (build 10.0.26300.9711) | not recorded | `ip-10-3-19-183` | `ip-10-3-19-165` |
| OS | Windows | not recorded | Ubuntu 24.04, kernel 7.0.0-1014-aws, x86_64 | not checked (same lab image assumed, not verified) |
| CPU / memory | not recorded | not recorded | 8 cores, 31 GiB RAM, no swap | 31 GiB RAM, no swap |
| Python | 3.14.3 | 3.13.5 | 3.12.3 | 3.12.3 |
| Ollama | 0.40.13 | 0.40.16 | 0.40.2 | 0.40.2 |
| `qwen3:1.7b` | layer `3d0b790534fe` | - | layer `3d0b790534fe` | layer `3d0b790534fe`, ID `8f68893c685c` |
| `qwen3:4b` | - | "original `qwen3:4b` tag" (ID not recorded) | layer `3e4cb1417446` | layer `3e4cb1417446`, ID `359d7dd4bcda` |
| Inference | not recorded | not recorded | not recorded | 100% CPU (no GPU), per `ollama ps` |
| Repository location | local disk | - | home folder (lost when VM was replaced) | `~/workspace/...` on AWS EFS network storage (persists across VMs) |

The `qwen3:1.7b` layer ID is identical on the laptop and both VMs, so all runs of
Chandramouli's implementation used the same model build. The `qwen3:4b` build on Atindra's
machine could not be compared because its ID is not recorded.

## Summary of runs

| # | VM | Implementation | Command | Result |
|---|---|---|---|---|
| V1 | 1 | Chandramouli | `pytest -v` | 64 passed in 4.21 s |
| V2 | 1 | Chandramouli | `python run_classical.py` | Identical to laptop (Run 5 in implementation-chandramouli/docs/TEST_LOG.md) |
| V3 | 1 | Atindra | `python -m pytest -m "not live" -q` | 275 passed, 4 deselected in 7.47 s |
| V4 | 1 | Atindra | `python run_classical.py` | 20 results identical to his README |
| V5 | 1 | Chandramouli | `python run_llm.py` (`qwen3:1.7b`) | 2 of 4 match policy (A, D differ) |
| V6 | 1 | Atindra | live tests, all four cases in one batch (`qwen3:4b`) | **Did not complete: the VM crashed** |
| V7 | 2 | Atindra | `python -m pytest -m "not live" -q` | 275 passed, 4 deselected in 20.77 s |
| V8 | 2 | Atindra | live tests, one case at a time (`qwen3:4b`) | 3 of 4 match his expected actions (C differs); same as his recorded run |
| V9 | 2 | Chandramouli | `python run_llm.py` (`qwen3:1.7b`) | 2 of 4; identical output to V5 |

## Offline tests and classical agents (V1-V4, V7)

Both implementations' offline tests passed on the VMs with the same counts as on their
original machines (Chandramouli 64; Atindra 275 passed, 4 deselected). Both classical
comparisons gave exactly the same decisions, reasons and scores as on the original machines.
Test times were longer on VM 2 (20.77 s vs 7.47 s on VM 1 for Atindra's suite), consistent with
the repository being on network storage; this was not measured further.

## Chandramouli's LLM agent on the VMs (V5, V9)

| Scenario | Policy-expected | Laptop (Runs 11, 13) | VM 1 (V5) | VM 2 (V9) | Time VM 1 | Time VM 2 |
|---|---|---|---|---|---|---|
| A | open_carrier_investigation | ✘ request_clarification_and_flag | ✘ same | ✘ same | 89.3 s | 134.7 s |
| B | escalate_to_payments | ✔ | ✔ | ✔ | 139.9 s | 129.8 s |
| C | request_clarification_and_flag | ✔ | ✔ | ✔ | 116.9 s | 109.8 s |
| D | share_tracking | ✔ share_tracking | **✘ request_clarification_and_flag** | **✘ same** | 123.8 s | 117.3 s |
| Total | | 3 of 4 | 2 of 4 | 2 of 4 | 469.9 s | 491.6 s |

Observations:

1. **VM 1 and VM 2 gave identical output**: the same actions, the same policy-search queries and
   word-for-word the same explanations in all four scenarios.
2. **D differs between the laptop and the VMs.** On both VMs the model asked for clarification on an
   order that is in transit within its expected date, explaining that the order "does not have a
   return or refund record". On the laptop it shared tracking (Runs 11 and 13).
3. **Wording differs between laptop and VM where the action is the same.** In B the VM runs used the
   short policy query "returned running shoes passed inspection but refund pending"; the laptop runs
   used the full customer message. In C the VM explanation says the issue "matches the 'Delivered but
   not received' policy".
4. **The checks behaved the same on both VMs.** The action check flagged A and D ("record is consistent;
   clarification may be unnecessary"); the claim check flagged C's explanation ("Treats the order as
   delivered, but the record status is 'shipped'") although C's action was correct.
5. **Speed:** 89-140 s per scenario on the VMs, against 24-70 s on the laptop.
6. **Context size:** `ollama ps` showed a context of 4096 tokens for this model (Ollama's default; the
   code does not set it). Whether any prompt exceeded it could not be checked: the lab account cannot
   read the Ollama service log.

## Atindra's LLM agent on the VMs (V6, V8)

**VM 1 (V6):** all four live cases were started as one batch
(`python -m pytest tests/test_llm.py -m live -v -s`). The VM crashed before the batch completed. No
result was recorded. The cause was not determined.

**VM 2 (V8):** each case was run separately with output saved to a log
(`python -m pytest "tests/test_llm.py::test_live_qwen3_four_cases[X]" -m live -v -s`), while a second
terminal showed `free -h` and `ollama ps` every 5 seconds.

| Case | Expected action | VM 2 result | Status | His recorded result | Time |
|---|---|---|---|---|---|
| A | delivery_investigation | delivery_investigation | ok | same | 501.8 s |
| B | payments_escalation | payments_escalation | ok | same | 784.6 s |
| C | request_clarification | **explain_refund_pending** | **warning** | same | 483.8 s |
| D | share_tracking | share_tracking | ok | same | 617.8 s |
| Total | | 3 of 4 | | 3 of 4 | 2,387.9 s |

All four tests report `PASSED`, because these live tests accept status `ok` or `warning`; a pass
means the agent completed with valid tool evidence, not that the action was correct (as his README
states). The `warning` in C is his eligibility check flagging that the action is not allowed by the
evidence; the run record gives the issue as "Raw action explain_refund_pending is ineligible for
the supplied evidence."

From the run records (`live_A.json` ... `live_D.json`): in every case both tools
(`lookup_case_records`, `lookup_support_policy`) succeeded, the agent used 2 model rounds, and no
JSON repair attempt was needed.

Observations:

1. **Same decisions as his recorded run** in all four cases, including the wrong action in C.
2. **About 10 times slower:** 2,387.9 s in total against 243.14 s for his recorded batch.
3. **Memory was not exhausted.** During the run `qwen3:4b` used 3.9 GB, total memory use stayed at
   about 6 GiB, and 24-25 GiB remained available. Context size was 8192 (set in his code).
4. **Model reload during B.** For a short time `ollama ps` showed "Stopping..." for `qwen3:4b`, then the
   model was listed again with a normal keep-alive time. B completed normally; it was the slowest case.
   The reason for the reload was not determined.
5. **No crash when run one case at a time.** Combined with observation 3, this suggests the VM 1 crash
   was not caused by running out of memory, but the cause remains unknown.

## Repeatability

This qualifies the statement in implementation-chandramouli/README.md ("Outputs were identical
across repeated runs at temperature 0, but variation over many runs was not measured"), which was
based on laptop runs only.

| Implementation | Same environment, repeated | Different environments |
|---|---|---|
| Chandramouli (`qwen3:1.7b`, temperature 0) | Identical: laptop Runs 11, 13, 14 (A); VM 1 and VM 2 | **Differs in D:** laptop 3 of 4, VMs 2 of 4 |
| Atindra (`qwen3:4b`, temperature 0) | One run per environment | Identical: his machine and VM 2 (3 of 4, same actions) |

Findings:

1. **Within one environment, both implementations gave repeatable output** at temperature 0 in the
   runs recorded.
2. **Across environments, the same model build can give a different answer.** Chandramouli's agent,
   with the identical `qwen3:1.7b` build, chose a different action for D on the laptop than on the VMs,
   consistently on each side. The visible differences between the two environments are the Ollama
   version (0.40.13 vs 0.40.2), the operating system and the hardware. These runs do not show which of
   them causes the difference.
3. **Atindra's agent gave the same decisions on two machines.** These runs do not show why; his
   stricter output format (typed JSON with required citations) is one possible reason, not tested here.
4. **Sample sizes are small:** one to three runs per scenario per environment.

## Raw files

In [`vm-runs/2026-11-17/`](vm-runs/2026-11-17/) (VM 2):

| File | Contents |
|---|---|
| `live_A.log` ... `live_D.log` | pytest output of Atindra's live test for each case |
| `live_A.json` ... `live_D.json` | His agent's full run record for each case (tool calls, model answer, checks), copied from `implementation-atindra/evidence/` after each run |
| `run_llm_vm2.log` | Output of Chandramouli's `python run_llm.py` on VM 2 |

His live tests overwrite `implementation-atindra/evidence/llm_qwen3-4b_*.json`; those files were
restored with `git restore` before committing, so his original recorded evidence is unchanged.
