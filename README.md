# E-commerce Order and Refund Support Assistant - Group 21

Agentic AI (PCAM ZG519), Mini Project 1.

| Member | Student ID | Implementation |
|---|---|---|
| G.Chandramouli | 2025paml525 | [`implementation-chandramouli/`](implementation-chandramouli/) |
| Atindra R K Ranjana Singh | 2025paml584 | [`implementation-atindra/`](implementation-atindra/) |

This repository contains **two complete, independent implementations** of the mini project, a
comparison of the two, execution results from both (including runs on the course lab VMs), and
what we learned from them.

## Our approach

As a team, we each started the implementation independently, so that both of us contributed
substantial work from the first stages. We then critically evaluated our own implementations,
intending to either merge them or keep them separate.

In this mini project, each implementation turned out to be complete and independently
verifiable. They also took different directions: typed data models and a shared eligibility
layer in one, free-text message reading and output claim checks in the other, along with
different model and context-size choices, different edge-case scenarios and different learning
agent demonstrations. Each turned out to be unique in its own way.

After evaluating both internally, we decided to submit both, together with the comparison,
the execution results and our learnings, rather than reduce them to one.

Both implementations are kept exactly as they were developed, each with its full original
commit history (Chandramouli's 7 commits on 8 November, Atindra's 8 commits on 14 November),
joined into this repository on 15 November without rewriting any commit.

## Quick review path

| To check | Go to |
|---|---|
| Full submission document and step-by-step evaluator guide (Word) | [`Group21_MiniProject1_Submission.docx`](Group21_MiniProject1_Submission.docx) |
| Requirements met by each implementation | [Rubric checklist](#rubric-checklist) below |
| How the two differ | [Comparison](#how-the-two-implementations-differ) |
| Results side by side | [Results](#results) |
| Runs on the lab VMs, and repeatability | [`docs/VM_TEST_LOG.md`](docs/VM_TEST_LOG.md) |
| Chandramouli's full documentation and test log | [`implementation-chandramouli/README.md`](implementation-chandramouli/README.md), [`docs/TEST_LOG.md`](implementation-chandramouli/docs/TEST_LOG.md) |
| Atindra's full documentation and saved evidence | [`implementation-atindra/README.md`](implementation-atindra/README.md), [`evidence/RESULTS.md`](implementation-atindra/evidence/RESULTS.md) |

## Repository layout

```
group21-ecommerce-support-agents/
├── README.md                        This file
├── Group21_MiniProject1_Submission.docx   Submission document and evaluator guide
├── docs/
│   ├── VM_TEST_LOG.md               Both implementations on the lab VMs; repeatability findings
│   └── vm-runs/2026-11-17/          Raw VM output (logs and run records)
├── implementation-chandramouli/     Complete implementation, own README, tests, test log, screenshots
└── implementation-atindra/          Complete implementation, own README, tests, evidence, screenshots
```

Each implementation folder is self-contained: its own `requirements.txt`, `app.py` (Streamlit
UI), agents, tests and documentation. Run each from inside its own folder, in its own virtual
environment, because their pinned package versions differ.

## How to run

Both need [Ollama](https://ollama.com) running for the LLM agent; everything else works without it.

**Chandramouli's implementation** (model `qwen3:1.7b`):

```
cd implementation-chandramouli
python -m venv .venv
.venv\Scripts\activate            # Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
ollama pull qwen3:1.7b
pytest -v                         # 64 tests, no Ollama needed
python run_classical.py           # five classical agents, all scenarios
python run_llm.py                 # LLM agent, all scenarios
streamlit run app.py              # UI at http://localhost:8501
```

**Atindra's implementation** (model `qwen3:4b`):

```
cd implementation-atindra
python -m venv .venv
.venv\Scripts\activate            # Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
ollama pull qwen3:4b
python -m pytest -m "not live" -q # 275 offline tests, no Ollama needed
python run_classical.py           # five classical agents, all cases
python -m streamlit run app.py    # UI at http://localhost:8501
```

Atindra's live LLM tests (`python -m pytest tests/test_llm.py -m live -v -s`) overwrite his saved
evidence files; see his README.

Python versions tested: Chandramouli's on 3.14.3 (Windows laptop) and 3.12.3 (lab VMs); Atindra's
on 3.13.5 (his machine) and 3.12.3 (lab VMs).

## Rubric checklist

| Criterion | Chandramouli | Atindra |
|---|---|---|
| Five classical agents | [`agents/`](implementation-chandramouli/agents/): rules, internal state, uniform-cost plan search, weighted utility, success counts | [`agents/`](implementation-atindra/agents/): rules, belief state, breadth-first plan search, weighted utility over eligible actions, success counts |
| LLM agent and tool calling | [`agents/llm_agent.py`](implementation-chandramouli/agents/llm_agent.py): Ollama via LangChain, 4 read-only tools, at least 2 required, claim and action checks | [`agents/llm.py`](implementation-atindra/agents/llm.py): Ollama via LangChain, 2 case-bound tools, both required, every citation checked against tool results |
| Shared scenarios and testing | 4 scenarios (A-D), one shared case file for all six agents; 64 tests | 4 cases (A-D), one shared case for all six agents; 275 offline and 4 live tests |
| Streamlit UI and comparison | [`app.py`](implementation-chandramouli/app.py): comparison table, per-agent reasoning, all-scenarios grid, LLM check results | [`app.py`](implementation-atindra/app.py): comparison, expandable agent details, downloadable comparison |
| Learning and evaluation | Feedback buttons update success/failure counts; output checks; limitations section | Recorded failures switch the decision (screenshots); citation and eligibility checks; limitations section |
| Documentation and demonstration | README, setup, 9 screenshots, test log of 14 runs, changelog | README, setup, screenshots, results index with exports |

## How the two implementations differ

| Area | Chandramouli | Atindra |
|---|---|---|
| Data structure | Plain dictionaries, shared action list | Typed data models (Pydantic) with action and status lists |
| Policy rules | Each agent applies the shared policy limits itself | Goal based, utility based and learning choose from eligible actions. Simple reflex and the LLM can give an ineligible action, which is then flagged |
| Customer message | Classical agents read the free-text message | Customer claims are structured in the case data |
| LLM tools | 4, named as suggested in the instructions | 2 grouped tools, restricted to the selected case |
| LLM output checks | Claim check on the explanation text; action and safety checks | Strict JSON; citations verified against tool results; one repair attempt; eligibility |
| Model and context | `qwen3:1.7b`, Ollama default context (4096) | `qwen3:4b`, context set to 8192 |
| Edge case (C) | Item, status and tracking conflict with the record | Customer claims a return the records do not show |
| Learning demo | One recorded success updates the counts (14/3 to 15/3) | Two recorded failures switch the decision to human review |
| Evidence | Versioned test log, including a fix cycle and its regression | Results index, JSONL exports, live and offline screenshots |
| Prompt injection (not in the project instructions; course Module 7 topic) | Not handled | Tool data treated as untrusted; tool calls accepted only for the selected case |

## Results

**Classical agents** (same on every machine tested):

| Implementation | Matches expected action | Differences |
|---|---|---|
| Chandramouli | 18 of 20 | Simple Reflex in B (no deadline check) and C (no record consistency check) |
| Atindra | 19 of 20 | Simple Reflex in B (no deadline calculation) |

**LLM agent:**

| Implementation | Original machine | Lab VM | Wrong action(s) |
|---|---|---|---|
| Chandramouli (`qwen3:1.7b`) | 3 of 4 (laptop) | 2 of 4 (VM 1 and VM 2, identical output) | A; D on the VMs only |
| Atindra (`qwen3:4b`) | 3 of 4 (his machine) | 3 of 4 (VM 2, same decisions) | C |

In every wrong case, the implementation's own checks flagged the problem (Chandramouli: action
or claim check; Atindra: `warning` status), and the original answer stays visible.

Details: [`implementation-chandramouli/docs/TEST_LOG.md`](implementation-chandramouli/docs/TEST_LOG.md),
[`implementation-atindra/evidence/RESULTS.md`](implementation-atindra/evidence/RESULTS.md),
[`docs/VM_TEST_LOG.md`](docs/VM_TEST_LOG.md).

## What we learned

These are observations from our runs, with small samples (one to three runs per scenario per
environment).

1. **Prompt wording decided whether the small model called tools at all.** With the raw customer
   message, `qwen3:1.7b` wrote "Let me look that up" without calling a tool; a short, structured task
   fixed it (Chandramouli's test log, Runs 1-3).
2. **Giving the model more policy text fixed one case and broke another.** Returning all policies fixed
   Scenario C but led to a wrong answer in A (Chandramouli's test log, Runs 9-11).
3. **The same model build can answer differently on another machine.** Chandramouli's agent, with the
   identical `qwen3:1.7b` build, chose a different action for D on the laptop than on the VMs,
   consistently on each side. Each environment on its own gave repeatable output.
4. **Atindra's stricter design gave the same decisions on two machines.** Typed JSON answers with
   required citations are one possible reason; we did not test this.
5. **Checks that report rather than override keep the model's real behavior visible.** Both
   implementations flag a wrong or ungrounded answer instead of replacing it, so the comparison shows
   what the model actually did.
6. **A shared eligibility layer reduces duplicated rules.** In Chandramouli's implementation each agent
   applies the same hand-coded limits; in Atindra's, Goal based, utility based and learning choose from
   eligible actions. Simple reflex and the LLM can give an ineligible action, which is then flagged
7. **CPU-only inference is slow.** On the lab VMs, `qwen3:4b` took 8-13 minutes per case (about 10 times
   slower than on Atindra's machine) and `qwen3:1.7b` about 2 minutes per scenario.

## Limitations

The limitations of each implementation are listed in its own README. Across both: all data is
simulated; each LLM's accuracy comes from four scenarios and is not a general measure; the
checks catch many but not all errors (for example, a wrong date in an explanation was not
detected); and LLM runs are slow on CPU-only machines.

## Version history

- Chandramouli's versions are tagged `chandramouli/v0.4` to `chandramouli/v0.7`; earlier versions
  are described in [`implementation-chandramouli/CHANGELOG.md`](implementation-chandramouli/CHANGELOG.md).
- Atindra's history is his 8 commits of 14 November.
- On GitHub, a file's history inside an implementation folder starts at the 15 November merge; the
  earlier commits are in the repository's main commit list with their original dates.
