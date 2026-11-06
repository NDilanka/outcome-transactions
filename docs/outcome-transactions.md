# Outcome Transactions: Design v0.2

Date: 2026-11-06
Status: design + partial evidence. A file-level prototype runs end to end (`prototype/`). Whole-machine forking is measured (Experiment 1) but not built.
Supersedes: `docs/research-design.md` (interface compiler). Extends: `docs/outcome-checking.md` (v0.1).

## 1. The idea in one paragraph

Today a computer-use agent acts on the live machine one step at a time, and every step is visible and irreversible. In an outcome transaction, the user states an **outcome**, not steps. The engine forks the live machine cheaply, searches for that outcome in many disposable forks at once, checks each fork's end state against a **frozen, mutation-tested outcome spec**, and commits only a verified winner to the real machine. The user keeps working during the search. Every external effect (email, HTTP POST, payment) made inside a fork is held, and only the winner's held effects are released, after commit. From the user's side, the task happens in one step, and a wrong attempt never touches the real machine.

## 2. What is new, honestly

Forking a desktop for an agent and committing the winner is **already published** (TClone, arXiv 2605.17320; Microsoft US8677355B2). So is warping virtual time (QEMU icount, Chrome virtual time) and sharing sub-page memory (Difference Engine, OSDI'08). See `research/prior-art.md`. This design does not claim those.

The contribution we claim is the **commit discipline around the fork**, which no prior work we found combines:

1. **Spec before search, and the spec is tested.** The outcome spec is frozen (hashed) before any fork runs. Then it is mutation-tested: deliberately wrong end states built in throwaway copies must be rejected, and a correct one must pass. A spec that cannot tell right from wrong is never used. (VeriEvolve refines evaluators with counterfactuals but has no frozen before-state or fork controls.)
2. **Differential verification against controls.** Each fork is judged against the starting snapshot, against a **null control fork** (same app, no task), and against other forks that used independent methods. Agreement between independent methods raises confidence; disagreement is shown to the user as competing results.
3. **Automatically derived world read-set, validated at commit.** The engine records what the winning fork read from the live world (files, cells, remote responses). At commit, it checks those reads are still valid. If the user or the world moved, it runs a semantic overlap test, then replays on a fresh fork, under optimistic concurrency. ("Authority at Commit Time", arXiv 2609.31490, validates **declared** dependencies; ours are observed.)
4. **Per-fork held-effect queues** with a shared cache of recorded reads, released for the winner only and only after the commit is verified on the real machine.

## 3. Architecture

```
 user request ──► spec writer ──► frozen spec ──► mutation tests (in throwaway forks)
                      ▲  read-only view of snapshot           │ pass
                      │                                        ▼
 live machine ──snapshot──► fork 0 (null control)   fork 1..N (methods: GUI, API, script, ...)
     │  user keeps working       │                      │  no network; outbox holds writes
     │                           ▼                      ▼
     │                    noise set            end states + read-sets + held effects
     │                                 ▼
     │                    verify (spec − noise) ► agreement ► confidence level
     │                                 ▼
     └──────────────► merge check (read-set still valid?) ─ no ─► overlap test ─► replay on fresh fork
                                       │ yes                         │ overlap
                                       ▼                             ▼
                      commit (transplant or replay) ► re-verify on real ► release winner's effects
                                                                     or: show both versions to user
```

Confidence levels reported to the user: **verified** (≥2 independent methods agree), **single** (one method passed), **ambiguous** (passing forks disagree; user picks from results), **none** (nothing passed; report what was tried).

## 4. Evidence so far

| Experiment | Question | Result |
|---|---|---|
| 3 (`research/exp3-outcome-location.md`) | Where do task outcomes live? | 86.5% of 342 feasible OSWorld tasks have outcomes that can be transplanted as state; ~132 of 230 document tasks need a save. |
| 4a (`research/exp4a-results.md`) | Can real checkers be expressed as state readers + predicates? | All 120 OSWorld checkers expressible (77.5% directly, 20% with a new reader, 2.5% partly). 57 readers in 12 families, ~7 operators. 50.3% of tasks rely on gold files. |
| 4b (`research/exp4b/results.md`) | Can a model write specs blind, from the request alone? | 66 tasks: 30.3% equivalent to OSWorld's checker, 36.4% reasonably stricter, 9.1% over-strict, 10.6% looser, 9.1% different (blind spec more faithful to the request in 5 of 6), 4.5% unverifiable. Footprint added value in 84.8%. |
| 5 (`research/exp5-grounded/results.md`) | Does seeing a read-only copy of the starting state fix bad specs? | Wrong specs fell from 36.4% to 7.6% (66 tasks, blind paired judge from another lab); on gold-file tasks from 58.3% to 4.2%. Grounded spec judged better in 51 tasks, worse in 5. About half the gain came from better writer instructions (control group without files also improved). |
| 1 (`research/exp1-exp2-results.md`) | What does a live-app fork cost in RAM? | 8–57 MB naive CoW per task on a 74–124 MB app; 0.7–6.5 MB compressed. |
| 2 (same file) | How much time is waiting? | All threads asleep in 60–96% of samples; settle times 0.16–4.8 s vs fixed 2–10 s sleeps in agent harnesses. |
| Prototype (`prototype/README.md`) | Does the whole loop work on a real app? | Yes, on 3 scenarios: normal commit with "verified" agreement; disjoint concurrent edit merged by replay; same-cell edit correctly refused. Search ~12 s, total 15–17 s. |

## 5. Problems found, and the fix for each

Each problem below was found by an experiment or by the prototype. "Built" means the prototype implements and tests it. "Designed" means not yet built.

### 5.1 Half of real checkers compare against gold files we will not have (Exp 4a: 50.3%)
OSWorld checkers compare the result to a file the benchmark author made by hand. A real user has no such file.
**Fix: before-relative specs.** Replace "equals gold" with "the starting snapshot, plus exactly the requested change, and nothing else". The engine has the before-state, so "nothing else" becomes checkable (`preserve` and `footprint` in the prototype). For outputs that cannot be described exactly (an edited image, a rewritten paragraph), use **independent-method agreement**: two unrelated methods that both pass the must-checks and produce the same semantic diff are strong evidence, even with no gold file. *Built for cells; agreement built.*

### 5.2 The spec writer could not see file contents (Exp 4b failure pattern)
Blind specs failed when the request said "the column with prices" and the writer could not know it was column D.
**Fix: snapshot-grounded spec writing.** The spec writer gets a read-only view of the fork snapshot (the same overlay the forks use), so it can open files and resolve references before freezing the spec. This adds no risk: it reads a copy, never the live machine. *Tested in Experiment 5: with a generic inspector, wrong specs fell from 43.2% to 9.1% on tasks with starting files. Remaining misses: an inspector gap (fixed), and hidden app defaults that no file shows, which need 5.15.*

### 5.3 Thresholds too tight or too loose (Exp 4b: 9.1% over-strict, 10.6% looser)
**Fix: calibrate with both kinds of controls.** Negative mutations must fail (catches loose specs); positive variants must pass (catches strict specs). Positive variants come from forks that reach the outcome by different methods. If a GUI-made result and a script-made result differ only in, say, float formatting, the spec must accept both. A spec that rejects a positive variant is reported as "over-strict at predicate X" and relaxed only at that predicate. *Negative mutations and one positive control built; positive variants from forks designed.*

### 5.4 Apps leave noise: lock files, caches, recent-file lists (prototype)
The correct GUI result was first rejected because the killed app left `.~lock.budget.ods#`.
**Fix: null control fork.** Run the same app in one extra fork with no task, and subtract what it changes. The noise set is found on every run, with no per-app list to maintain. *Built; it found exactly the lock file, and the GUI fork then passed and agreed with the direct method.*

### 5.5 Hidden couplings: one setting changes another file (Exp 4b failure pattern)
**Fix: differential footprint.** Changes that every passing method makes, minus noise, are part of the outcome. A change that only one method makes is a side effect of that method. It is flagged, and that fork loses ties. *Designed.*

### 5.6 Agents sleep a fixed 2–10 s per step (Exp 2)
**Fix: UI-settled event.** Inside a fork, the engine sees all threads, timers, pending I/O, and screen damage. "All threads blocked, no pending I/O, no new frames for one frame interval" is a precise settle signal. Inside a fork with no human watching, the remaining timer waits can also be warped forward (only sleep-only waits are skipped; I/O waits become events). *Measured; not built.*

### 5.7 The user edits the same file during the search (prototype; RealCUA's multi-user cloud apps)
**Fix: semantic overlap test + replay + optimistic commit.** If the user's changes and the agent's changes touch disjoint semantic units (cells, paragraphs, records), replay the winning method on a fresh fork of the current state, re-verify with the same frozen spec, and commit only if nothing moved again (at most 3 tries). If they overlap, nothing is committed, and the user sees both versions. Replay matters because derived artifacts (the PDF) must be regenerated from the merged state; a byte-level merge would leave them stale. *Built and tested both ways.*

### 5.8 The target document is open in the user's app with unsaved edits
If the engine writes `budget.ods` on disk, the user's open app may later overwrite it, or the user's unsaved edits may be lost.
**Fix: commit through the owner.** Before transplanting, check the open-file table. If no process has the file open, transplant. If an app has it open and clean, transplant and then ask the app to reload (most office apps detect external changes). If it is open and dirty, do not transplant. Replay the winning method in the user's live app instead: it is the only path into the in-memory document, and the method is already known to work. Then verify the live result with the same spec. *Designed.*

### 5.9 Checking can change the state being checked (Exp 4a: OSWorld's evaluator presses Ctrl+S in 200 of 342 tasks)
**Fix: observation forks.** Verification reads through its own read-only overlay of the fork's end state (prototype `view_of`), so a reader that saves, reloads, or touches files cannot alter the result it is judging or leak into the commit. *Built (file level).*

### 5.10 External effects and external reads
**Fix: per-fork outbox + recorded reads.** Forks have no network. Writes are held in a per-fork outbox and released for the winner after commit. Reads are fetched once through a shared, recorded cache so all forks see the same world, and the read-set (5.7) records them for commit validation. Tasks that depend on real time or live web data (11 in OSWorld) run in a **real-time island**: one fork with the real clock and a live read path, writes still held. *Outbox built; read cache designed.*

### 5.11 No fork succeeds, or the task is impossible
**Fix: refusal as an outcome.** If the spec passed its mutation tests and no fork passes, the engine reports "not done" with the closest results and why each failed (the prototype already returns per-predicate reasons). If the must-predicates contradict the preserve conditions (for example, "change B2 but keep every cell the same"), the spec is infeasible and the engine says so before searching. *Reasons built; contradiction check designed.*

### 5.12 Leftovers from one fork break the next (prototype)
A killed X server left a lock in shared `/tmp`. Its PID came from another namespace, so the next X server refused to start.
**Fix: full per-fork isolation.** Each fork gets its own mount, network, and PID namespace and a private `/tmp`. Every process in the fork dies with it. *Built.*

### 5.13 Memory for many forks on an 8 GB laptop (Exp 1)
**Fix: compressed divergence + adaptive width.** Store fork divergence compressed (0.7–6.5 MB per task measured). Choose how many forks run in parallel from free memory, and run the rest one after another. Discard freed pages instead of copying them. *Measured; not built.*

### 5.15 Settings that are app defaults, and vague amounts (Experiment 5)
Some outcomes depend on an app default that appears in no file (Thunderbird only filters IMAP subfolders if an unlisted default is changed). Some requests give no amount ("make the text bigger").
**Fix 1: behavioral probes.** Check what the setting does, not the key: in a throwaway copy of the winning fork, deliver a test message and see whether the filter fires. A probe needs no knowledge of the app's internals.
**Fix 2: confirm vague amounts.** When the request has no number, the spec states one ("text at least 1.2× larger") and shows it to the user with the frozen spec, before the search starts. *Both designed.*

### 5.14 Windows and macOS
The prototype forks files on Linux. On Windows, the same loop maps to Windows Sandbox or Hyper-V checkpoints for whole-machine forks, and to ProjFS or a filter driver for file-level forks. The effect firewall maps to a per-sandbox proxy, and the open-file check to the Restart Manager API. *Not built; the mapping is a plan, not evidence.*

## 6. What to build next, in order

1. ~~Snapshot-grounded spec writer (5.2), then rerun Experiment 4b.~~ Done (Experiment 5): 7.6% wrong.
2. Behavioral probes and confirmed amounts (5.15), then positive variants from forks (5.3) and differential footprint (5.5).
3. Commit through the owner for open documents (5.8).
4. Process-level forks (CRIU or VM snapshots) so the GUI method can start from the user's already-open app, plus the UI-settled event (5.6).
5. Run 20–30 OSWorld tasks through the full loop and report: commit rate, wrong-commit rate (target 0), and time to outcome versus a step-by-step agent.

## 7. What would prove this wrong

- Wrong commits: any passing spec that commits an outcome the user rejects. One per 100 is too many.
- Specs that need a gold file even after 5.1 and 5.2, in more than 20% of tasks.
- Replay failing after disjoint edits in more than 10% of cases, which would mean methods are not replayable in practice.
- Fork cost on whole-machine snapshots far above Experiment 1's process-level numbers.
