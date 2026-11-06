# Automatic Outcome Checking: Design v0.1

Date: 2026-11-06
Status: paper design, not yet validated

## 1. Why this is the critical piece

The engine commits a fork's result to the real machine only when an outcome check passes. If the check is wrong, the engine commits the wrong result with full confidence. Experiment 3 showed that OSWorld needs 121 hand-written checker functions for 368 tasks. Generating checks automatically from a plain-language request is the problem this document addresses.

## 2. Prior work

| Work | Approach | Limitation for our setting |
|---|---|---|
| Universal Verifier (Microsoft, arXiv 2604.06240) | Rubrics, separate process and outcome rewards, judges all screenshots | Web only; judges a trajectory after the fact |
| VeriCUA (arXiv 2610.40578) | Verification as agentic exploration; picks GUI or code checks per requirement | Works on one finished environment; no baseline to compare against |
| Interactive Reward Agent (arXiv 2607.25904) | Proposes completion conditions, then verifies them with system, app, and GUI tools; 86.9% on GUI-RewardBench | Same: one end state, no before state |
| VAGEN (arXiv 2602.00575) | Progressive verification, cheap evidence first, then probing state | Same |
| OpenComputer (arXiv 2605.19769) | Hand-built app state verifiers for 33 apps; beat LLM judges on fine-grained state | Verifiers written per app by people |
| VeriEvolve (arXiv 2610.29005) | Writes an executable evaluator from the instruction before running the agent; refines it with counterfactual end states | Filesystem and API tasks; needs an external verifier for calibration |
| OSReward (arXiv 2607.28609) | Benchmark of VLM judges | Finds a systematic leniency bias: judges label failed runs as successes |

Shared limitation: every verifier above inspects **one end state of one run in the real environment**, without the starting state and without alternatives. The leniency bias reported by OSReward follows directly from that: with one state and no comparison, a judge has no reference point.

## 3. What our engine has that no verifier has had

1. **The exact starting state.** Every fork begins from a snapshot, so the engine can compute the precise difference between before and after.
2. **Many independent end states.** Several forks attempt the same outcome in different ways.
3. **Free, disposable copies.** The engine can create states on purpose, including deliberately wrong ones, at almost no cost.

The design below is built on these three properties.

## 4. Design

### 4.1 Check the difference, not the whole state

The engine computes a **state diff** for each fork: files created, changed, or deleted; settings changed; app state changed (read through the bridge layers: accessibility, scripting, browser state).

The outcome check runs over the diff. This has two effects:

- Checks are smaller and easier to get right, because they only look at what changed.
- The engine can check **what must not change**: "B2 is 5000 and nothing else in the workbook changed." Existing verifiers cannot check this without a baseline. It catches collateral damage, such as an agent that deletes a sheet while editing a cell.

### 4.2 Outcome specifications

A request is compiled, before any search starts, into an outcome specification with three parts:

```yaml
request: "Q3 budget exported as PDF, with B2 = 5000"
must:                       # required changes
  - cell(file: "Budget.xlsx", sheet: "Q3", ref: "B2") == 5000
  - file("D:/out/q3.pdf").exists
  - pdf("D:/out/q3.pdf").text contains cell_text(file: "Budget.xlsx", sheet: "Q3", ref: "B2")
footprint:                  # everything allowed to change
  - file("Budget.xlsx")
  - file("D:/out/q3.pdf")
  - app_state("excel")       # windows, recent files
fuzzy: []                   # criteria that need judgment
```

- **must**: typed predicates over state readers. Readers address state the same way the protocol does (files, cells, slides, settings, browser tabs, accessibility values).
- **footprint**: the set of state the task may touch. Any change outside it fails the check. This is the frame condition from formal verification, applied to desktops.
- **fuzzy**: criteria that code cannot decide, such as "make the slide look professional". These go to comparative judging (4.5).

The spec is written by a model and then **frozen** before the search starts. Forks cannot edit it. This separates the solver from the grader, the evaluator-first principle shown in VeriEvolve.

### 4.3 Test the checker inside forks before trusting it

Because forks are cheap, the engine tests the spec before using it:

1. **Negative tests.** Create forks with deliberately wrong outcomes: B2 = 500 instead of 5000, PDF saved to the wrong folder, an extra sheet deleted. The spec must reject every one. A spec that accepts a wrong state is rewritten.
2. **Starting-state test.** The untouched starting state must fail the spec. A spec that already passes before any work is done checks nothing.
3. **Positive test, when possible.** For simple outcomes, the engine produces the outcome directly through a known channel and confirms the spec accepts it.

This is mutation testing applied to outcome checks. It directly targets the leniency bias found in OSReward.

### 4.4 Agreement between forks

When several forks pass the spec, the engine compares their diffs:

- **Same diff from different methods**: high confidence. Independent paths agreeing is strong evidence, as in N-version programming.
- **Different diffs that all pass**: the spec is under-specified, or the request is ambiguous. Example from ActionEngine's failure analysis: "5 pants arrived, update the stock" can mean add 5 or set to 5.

### 4.5 Ask with results, not questions

When forks disagree, the engine shows the user the competing results ("Stock set to 5" vs "Stock increased from 12 to 17") and the user picks one. People decide faster between outcomes than they answer abstract questions, and the request never has to be rephrased.

For fuzzy criteria, judging is **comparative**: a model ranks fork results against each other instead of scoring one result on its own, and the top result is shown to the user when stakes are high.

### 4.6 Confidence levels at commit

| Level | Condition | Action |
|---|---|---|
| Verified | All `must` predicates pass, footprint respected, spec passed its negative tests, forks agree | Commit automatically |
| Ambiguous | Passing forks disagree | Show competing results; user picks |
| Fuzzy | Outcome depends on `fuzzy` criteria | Comparative judgment; confirm with user if the action is irreversible |
| Unverifiable | No reader can observe the outcome | Never commit automatically |

## 5. How this connects to the open-document problem

Experiment 3 found that in about 132 of 230 OSWorld document tasks, the result lives only in app memory until saved. The state diff therefore needs app memory readers (through scripting or accessibility) as well as file readers. At commit, the transplant step includes a reload of the changed document in the real app, and the spec is checked again on the real machine after commit.

## 6. New problem: the user keeps working during the search

The engine forks the live machine, but the user does not stop working while forks search. By commit time, the real machine has moved on. This is a merge problem, like a git merge:

- If the user's changes and the fork's diff touch disjoint state, both apply cleanly.
- If they overlap, the engine re-runs the winning plan from the current real state (replay instead of transplant) and re-checks the spec.

The footprint makes this check cheap: a conflict exists only if the user changed something inside the task's footprint.

## 7. Novelty claim (to be confirmed by a full literature search)

Prior verifiers judge one end state after the fact. This design checks outcomes with:

1. before/after diffs and footprint conditions,
2. specs frozen before search and mutation-tested in disposable forks,
3. agreement between independent forks as evidence,
4. disambiguation by showing results.

All four depend on cheap forks, so they are specific to this engine.

## 8. Validation plan

- **Experiment 4a (no hardware):** for each of OSWorld's 121 evaluator functions, check whether it can be expressed as `must` predicates over a small library of state readers plus a footprint. Measure the size of the reader library needed.
- **Experiment 4b (no special hardware):** have a model write specs from OSWorld instructions alone, then compare them with the official evaluator configurations. Measure agreement and the share of tasks where the generated spec is stricter or looser.
- **Experiment 4c (needs the VM host):** run the negative tests from 4.3 on real forks and measure how often generated specs accept wrong states before and after mutation testing.
