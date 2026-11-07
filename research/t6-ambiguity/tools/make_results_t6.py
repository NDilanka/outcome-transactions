#!/usr/bin/env python3
"""Generates t6-ambiguity-results.md from the measured T6 outputs (executor, verdicts, flags, scoring).

Gate numbers come from the orchestrator's scoring (t6-scoring); this script recomputes them from the joined data
and states where it agrees or differs.
"""
import glob, json, os, sys, yaml
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from stats_t6 import cp_interval, wilson

T6 = '/home/factory-user/t6-work'
REPO = '/home/factory-user/repos/outcome-transactions'
bm = json.load(open(os.path.join(T6, 'private/judge_blind_map.json')))
by = {(v['amb'], v['state']): k for k, v in bm.items()}
ver = {}
for f in sorted(glob.glob('/tmp/t6_verdicts/research/t6-ambiguity/judge_verdicts/verdicts_*.json')):
    ver.update(json.load(open(f)))
F = {r['id']: r for r in json.load(open(os.path.join(T6, 'executor_results.json')))}
S = {r['id']: r for r in json.load(open(os.path.join(T6, 'executor_results_eqfix.json')))}
amb = {a['id']: a for a in json.load(open(os.path.join(T6, 'private/ambiguity-set.json')))}
SPECS = os.path.join(REPO, 'research/t6-ambiguity/specs')
flags = {a: json.load(open(os.path.join(SPECS, f'{a}.flag.json'))) for a in amb}
conf = {a: yaml.safe_load(open(os.path.join(SPECS, f'{a}.yaml')))[0]['confidence'] for a in amb}

INTENDED_B = {'amb03', 'amb05', 'amb07', 'amb17'}   # sealed intent (orchestrator scoring)
NOOP = {'amb03': 'A', 'amb14': 'B', 'amb24': 'A', 'amb25': 'A', 'amb26': 'A', 'amb35': 'A', 'amb16': 'A and B'}
FOLLOW = {'amb17': 'neither', 'amb22': 'neither', 'amb30': 'neither (union of A and B)', 'amb39': 'neither',
          'amb03': 'B', 'amb07': 'B'}
ids = [a for a in sorted(amb) if a != 'amb16']
assert len(ids) == 39

def intended(a): return 'B' if a in INTENDED_B else 'A'
def unint(a): return 'A' if a in INTENDED_B else 'B'
def spec(R, a, s): return R[a]['runs'][s]['empty_all_undecided_decision']
def jv(a, s): return ver[by[(a, s)]]
def jdesc(a, s):
    v = jv(a, s); return f"{v['verdict']} ({v['confidence']})"

# Recomputed gate numbers (must match the scoring)
calc = {}
for tag, R in (('frozen', F), ('sens', S)):
    both = [a for a in ids if spec(R, a, unint(a)) == 'ACCEPT' and jv(a, unint(a))['verdict'] == 'accept']
    both_hi = [a for a in both if jv(a, unint(a))['confidence'] == 'high']
    spec_alone = [a for a in ids if spec(R, a, unint(a)) == 'ACCEPT']
    judge_alone = [a for a in ids if jv(a, unint(a))['verdict'] == 'accept']
    judge_hi_alone = [a for a in ids if jv(a, unint(a))['verdict'] == 'accept' and jv(a, unint(a))['confidence'] == 'high']
    commit = [a for a in ids if spec(R, a, intended(a)) == 'ACCEPT' and jv(a, intended(a))['verdict'] == 'accept']
    commit_hi = [a for a in commit if jv(a, intended(a))['confidence'] == 'high']
    judge_commit_hi = [a for a in ids if jv(a, intended(a))['verdict'] == 'accept' and jv(a, intended(a))['confidence'] == 'high']
    calc[tag] = dict(both=both, both_hi=both_hi, spec_alone=spec_alone, judge_alone=judge_alone,
                     judge_hi_alone=judge_hi_alone, commit=commit, commit_hi=commit_hi, judge_commit_hi=judge_commit_hi)

# Detector (writer flag two_readings_plausible; spec-text check: only amb16 has an explicit alternative, see text)
det_fail = calc['sens']['both']  # the three sensitivity failures
flagged = [a for a in ids if flags[a]['two_readings_plausible']]
nonfail = [a for a in ids if a not in det_fail]
hits = [a for a in det_fail if flags[a]['two_readings_plausible']]
false_alarms = [a for a in nonfail if flags[a]['two_readings_plausible']]
hit_ci = wilson(len(hits), len(det_fail)); fa_ci = wilson(len(false_alarms), len(nonfail))

def ci(x, n):
    cl, cu = cp_interval(x, n); return f"{cl*100:.1f}% to {cu*100:.1f}%"

rows = []
for a in ids:
    fu = unint(a)
    rows.append(
        f"| {a} | {amb[a]['request']} | {intended(a)} | {unint(a)} | "
        f"{spec(F,a,'A')} / {spec(S,a,'A')} | {spec(F,a,'B')} / {spec(S,a,'B')} | "
        f"{jdesc(a,'A')} | {jdesc(a,'B')} | {FOLLOW.get(a, 'A')} | "
        f"{NOOP.get(a, '-')} | {'yes' if a in calc['frozen']['both'] else 'no'} / {'yes' if a in calc['sens']['both'] else 'no'} |")

table_hdr = ("| request | request text | intended | unintended | spec on A (frozen / sensitivity) | spec on B (frozen / sensitivity) "
             "| judge on A | judge on B | writer's followed reading | no-op state | both keys accept unintended (frozen / sensitivity) |\n"
             "|---|---|---|---|---|---|---|---|---|---|---|")

f_ci = ci(len(calc['frozen']['both']), 39); s_ci = ci(len(calc['sens']['both']), 39)
j_ci = ci(len(calc['sens']['judge_hi_alone']), 39)
exp_frozen = round(len(calc['frozen']['spec_alone']) * len(calc['frozen']['judge_alone']) / 39, 2)
exp_sens = round(len(calc['sens']['spec_alone']) * len(calc['sens']['judge_alone']) / 39, 2)
fa_flagged_nonfail = len(false_alarms)

md = f"""# T6 ambiguity gate: results

Status: final. The gate result is the orchestrator's scoring against the sealed intents. My recomputation from the joined data matches it, with two differences noted below. n = 39 requests. amb16 is excluded from the rate because its two readings are identical (A = B = start). It is reported separately.

Labels: measured = produced by a run or by a count I made; inferred = my reasoning from measured results; guess = not tested.

## Gate result

| Executor | Both keys accept the unintended reading | Rate | 95% interval (exact, two-sided) | Gate (<= 5%) |
|---|---|---|---|---|
| Frozen c909d02 (primary) | 1 (amb30) | 2.6% | {ci(1,39)} | Point estimate passes; interval does not show it |
| Sensitivity (__eq__ and __hash__ added in memory) | 3 (amb30, amb31, amb35) | 7.7% | {ci(3,39)} | Fails |
| Sensitivity, judge high confidence only | 0 | 0% | 0.0% to 9.0% | Point estimate passes |

All three sensitivity failures have a low-confidence judge accept. amb30's failure is the same under both executors.

## My check of the scoring (measured)

- Reproduced from the joined data: both-key failures (frozen 1, sensitivity 3), spec-alone unintended accepts (frozen {len(calc['frozen']['spec_alone'])}, sensitivity {len(calc['sens']['spec_alone'])}), judge-alone unintended accepts ({len(calc['sens']['judge_alone'])}), and intended commits with spec and judge both accepting (frozen {len(calc['frozen']['commit'])}, sensitivity {len(calc['sens']['commit'])}).
- Difference 1: intended commits with spec ACCEPT and judge high confidence. I count {len(calc['sens']['commit_hi'])} (amb16 excluded). The scoring says 15. The 15 is reproduced only if amb16 is counted. Its A state has spec ACCEPT and judge accept at high confidence, so the gap is most likely that. This is inferred, not confirmed with the scoring author; I use 14.
- Difference 2: expected joint count under independence. For frozen, 6 x 11 / 39 = {exp_frozen}. The scoring says about 1.6. For sensitivity, 11 x 11 / 39 = {exp_sens}, which matches the scoring's 3.1.
- Difference 3: the scoring's 0% judge-high figure is for the joint policy only. Judge high confidence alone accepts the unintended reading on {len(calc['sens']['judge_hi_alone'])} of 39 requests ({', '.join(calc['sens']['judge_hi_alone'])}). That is {len(calc['sens']['judge_hi_alone'])/39*100:.1f}%, above 5%. A judge-only gate fails.
- The 95% intervals I computed are exact (Clopper-Pearson). The scoring's approximate bounds are close, except for 0 of 39, where the scoring's 7.4% is a one-sided bound and mine is two-sided (9.0%).

## Independence (inferred)

Under independence, the expected joint counts are {exp_frozen} (frozen) and {exp_sens} (sensitivity). The observed counts are 1 and 3. Two observations cannot test independence, so the claim that the errors are independent is assumed, not shown.

## What the three sensitivity failures share (inferred)

- amb30: the writer followed the union of both readings (italics on conditional lines and bracketed instructions). Its spec accepts either reading, and the judge accepts both at low confidence. Writer flag: two readings plausible; writer confidence low.
- amb31 and amb35: both are title edits. The sensitivity spec accepts the wrong reading because its must predicates check text and structure, not the difference between the two readings (title size versus title plus body, or subtitle alignment). The judge accepts both at low confidence. Both writers flagged two readings, and both have low writer confidence. amb35's A state is a no-op, because the title is already centred.

## Writer detector: "two readings" flag (measured)

Signal: the writer's flag `two_readings_plausible`. I also searched each spec's text for explicit statements of an alternative reading. Among the seven requests the flag marks as not ambiguous, only amb16 has such a statement ("either outcome is acceptable" for the title cell). On n = 39, the flag alone and the flag or text give the same counts, because amb16 is excluded.

- Hit rate on the three sensitivity failures: {len(hits)} of {len(det_fail)} ({len(hits)/len(det_fail)*100:.0f}%; 95% interval {hit_ci[0]*100:.0f}% to {hit_ci[1]*100:.0f}%). Frozen failure amb30: 1 of 1.
- False-alarm rate on the other {len(nonfail)} requests: {len(false_alarms)} of {len(nonfail)} ({len(false_alarms)/len(nonfail)*100:.0f}%; 95% interval {fa_ci[0]*100:.0f}% to {fa_ci[1]*100:.0f}%).
- Flagged overall: {len(flagged)} of 39. Precision (failures among flagged): {len(hits)} of {len(flagged)} ({len(hits)/len(flagged)*100:.0f}%).
- Not flagged: amb01, amb02, amb32, amb34, amb37, amb40 (and amb16, excluded).

Reading (inferred): the flag misses no failure on this set, but it fires on {len(flagged)/39*100:.0f}% of requests. It cannot separate failures from the requests the keys handle correctly. Routing every flagged request to confirmation would confirm {len(flagged)} of 39 requests. The detector is not a usable gate on its own. Its hit rate on three failures has a wide interval, so this result is weak evidence either way.

## Recommendation (inferred)

- Do not auto-commit when spec and judge both accept, under the sensitivity executor. The gate fails at 7.7%.
- A judge confidence floor (accept only when high) removes the three failures in the joint policy. It also removes {len(calc['sens']['commit'])-len(calc['sens']['commit_hi'])} intended commits.
- Judge high confidence alone is unsafe ({len(calc['sens']['judge_hi_alone'])} unintended accepts).
- Fix the executor equality bug (CellObj and RunP) and add formatting coverage before the next run. Re-test on fresh requests. This is a guess until tested.

## Per-request table (measured, with intended readings revealed)

Intended reading per the sealed intents. The unintended reading is the other one. amb16 is excluded. Spec columns are the empty_all_undecided_decision values. Judge columns are verdict and confidence from the blinded Sol judge.

{table_hdr}
{chr(10).join(rows)}

## Method (steps 0 to 4)

- Environment: Ubuntu 24.04, 4 CPUs, 7.8 GiB RAM. LibreOffice 24.2.7.2 installed for PDF rendering and verified (measured).
- End states (step 1): built by five builder subagents with Python edits to the Exp 5 starting snapshots (fetched by `research/exp5-grounded/fetch.py`, not committed). An independent tree diff (`tools/verify_endstates.py`) checked each state against its start. Seven requests have a state byte-identical to the start (amb03 A, amb14 B, amb24 A, amb25 A, amb26 A, amb35 A, and amb16 A and B), kept per the orchestrator's ruling (measured).
- Specs (step 2): 40 grounded specs written by fresh subagents, each seeing only the request text and the inspector report. Writers never saw the readings, end states, or brief. Frozen with 80 SHA-256 hashes (commit 4d5d23d). Hashes were checked before each executor run (measured).
- Executor (step 3): frozen `specexec.py` at c909d02 run on all 80 end states, plus each spec against the untouched start (240 runs). The primary and vacuous-all decisions agree on every run (measured). Results: `results/executor_results.json`. Sensitivity run: `results/executor_results_eqfix.json`.
- Judge packets (step 4): 80 blinded packets built with `tools/judge_packets_t6.py` and `tools/inspect_snapshot_t6.py`. Clip asserts pass on all 80 (measured). A rebuild is byte-identical to the committed set (measured). Verdicts from the Sol judge, joined through the blind map: all 80 present, no duplicates (measured).

## Findings from steps 1 to 4

1. Executor bug (measured). `CellObj` (table cells) and `RunP` (text runs) in `specexec.py` have no `__eq__`. Table-row and text-run equality is therefore identity-based. It makes `table(n).rows == before(...)` and `text_runs == before(...)` False even on an identical file. The primary result keeps the frozen file. The sensitivity run adds `__eq__` and `__hash__` in memory and changes 22 decisions. No spec uses `!=` on these values, so the bug causes false REJECTs, not false ACCEPTs, in the primary result.
2. amb37 is still wrong after the patch. `text_runs subset_of ['FFC000']` compares run objects with colour strings. This is a spec error (measured).
3. Start-state gate (inferred). The gate rule in `exp6-gate.md` requires a spec to REJECT the start root. Applied to measured START decisions, it would reject 11 of 15 start-accepting specs. Ten of those 11 are formatting checks the executor cannot read. One (amb12) is a content gap: the spec never checks the total. It would wrongly reject 4 specs whose followed reading is a no-op or no change (amb16, 22, 25, 35). The gate itself was not run on these specs (guess that it behaves as described).
4. Spec coverage gaps (measured). Formatting readings (bold, font size, fill, number format, alignment, highlight, italic, hyperlink) are not checked by the executor. Specs for those requests check content only, so both readings can be accepted (amb01, 08, 18, 29, 30, and in the sensitivity run 27, 28, 31).
5. Spec errors (measured). Parse errors leave predicates UNSUPPORTED for amb02, 05, 10, 23, 26, 33. amb24 reads `rows[10]` (0-based), which is the "NOT to be funded" row; the Total row is index 9 (inferred: spec index error from measured row content).
6. Writers followed reading A on 34 of 40 requests (mapped by me from writer flag text; writers never saw A or B). The most likely explanation is that A is the natural reading (inferred, not tested).
7. Degenerate and PDF cases (measured). amb20 and amb32 PDFs were hand-built, text-only, because LibreOffice was not yet installed when they were built. They were not re-rendered. amb34's two readings both assume a false premise: slide 2 is not picture-only, since its grouped shapes hold instruction text. amb32 B deletes the original pptx by design of that reading.

## Deviations and limits

- The Exp 5 writer instruction text is not in the repo. `writer_conventions.txt` was used (measured: file used; inferred: the Exp 5 prompt differs).
- Writers received a reader reference and filtered grammar examples, not the Exp 5 examples (most Exp 5 calc examples came from this request set).
- Judge packets used an inspector copy with its row, slice, and entry caps lifted (`tools/inspect_snapshot_t6.py`). Spec writers used the original inspector. Clip asserts pass on all 80 packets (measured).
- Snapshots were downloaded from HuggingFace at build time and are not committed. They are reproducible with `research/exp5-grounded/fetch.py`.
- The judge ran on the orchestrator side (Sol). I did not judge any state.
- The "intended" letters come from the orchestrator's scoring. I could not read the sealed intent file.
"""
out = os.path.join(T6, 't6-ambiguity-results.md')
open(out, 'w').write(md)
print('wrote', out, len(md), 'chars')
print('frozen both', calc['frozen']['both'], '| sens both', calc['sens']['both'])
print('detector hits', hits, 'false alarms', len(false_alarms), 'of', len(nonfail), 'flagged', len(flagged))
