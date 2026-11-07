# T6 joined table: spec and judge decisions per request

Sources and labels:
- Spec decisions (measured): frozen executor at c909d02, primary field empty_all_undecided_decision, and a sensitivity run with __eq__ added in memory to CellObj and RunP. Each cell is frozen / sensitivity.
- Judge verdicts (measured): Sol judge, branch t6-judge-verdicts at 88ef4e1, joined to end states through the blind map. All 80 present, no duplicates.
- Writer's followed reading (inferred): mapped by me from each writer's flag text against reading_A and reading_B. Writers never saw A or B.
- No-op flags (measured): end state is byte-identical to start.
- amb16: both readings are identical (A = B = start). Excluded from the ambiguity rate and reported separately.

Summary (measured):
- Judge accepts A on 37 of 40 and B on 14 of 40 (51 accept verdicts of 80).
- Judge accepts both A and B: 12 requests (includes amb16).
- Spec accepts both A and B: frozen 7 requests, sensitivity 12 requests (includes amb16).
- Spec and judge both accept both readings, excluding amb16: frozen 1, sensitivity 3.
  - Frozen: amb30
  - Sensitivity: amb30, amb31, amb35

| request | spec on A (frozen / sensitivity) | spec on B (frozen / sensitivity) | judge on A (verdict, confidence) | judge on B (verdict, confidence) | writer's followed reading | no-op flags |
|---|---|---|---|---|---|---|
| amb01 | ACCEPT / ACCEPT | ACCEPT / ACCEPT | accept (high) | reject (medium) | A | - |
| amb02 | UNDECIDED / UNDECIDED | REJECT / REJECT | accept (high) | reject (high) | A | - |
| amb03 | UNDECIDED / UNDECIDED | UNDECIDED / UNDECIDED | accept (medium) | accept (medium) | B | A is byte-identical to start |
| amb04 | ACCEPT / ACCEPT | UNDECIDED / UNDECIDED | accept (high) | reject (high) | A | - |
| amb05 | UNDECIDED / UNDECIDED | UNDECIDED / UNDECIDED | accept (high) | accept (high) | A | - |
| amb06 | ACCEPT / ACCEPT | REJECT / REJECT | accept (high) | reject (high) | A | - |
| amb07 | REJECT / REJECT | ACCEPT / ACCEPT | reject (medium) | accept (medium) | B | - |
| amb08 | ACCEPT / ACCEPT | ACCEPT / ACCEPT | accept (low) | reject (low) | A | - |
| amb09 | ACCEPT / ACCEPT | REJECT / REJECT | accept (high) | reject (high) | A | - |
| amb10 | UNDECIDED / UNDECIDED | REJECT / REJECT | accept (high) | accept (high) | A | - |
| amb11 | ACCEPT / ACCEPT | REJECT / REJECT | accept (high) | reject (high) | A | - |
| amb12 | ACCEPT / ACCEPT | ACCEPT / ACCEPT | accept (high) | reject (high) | A | - |
| amb13 | ACCEPT / ACCEPT | REJECT / REJECT | accept (high) | reject (high) | A | - |
| amb14 | ACCEPT / ACCEPT | REJECT / REJECT | accept (high) | reject (high) | A | B is byte-identical to start |
| amb15 | UNDECIDED / UNDECIDED | REJECT / REJECT | accept (high) | reject (high) | A | - |
| amb16 | ACCEPT / ACCEPT | ACCEPT / ACCEPT | accept (high) | accept (high) | A | A and B both byte-identical to start (A = B); excluded from rate, reported separately |
| amb17 | REJECT / REJECT | REJECT / REJECT | reject (low) | accept (low) | neither (note 1) | - |
| amb18 | ACCEPT / ACCEPT | ACCEPT / ACCEPT | accept (high) | reject (medium) | A | - |
| amb19 | ACCEPT / ACCEPT | REJECT / REJECT | accept (high) | reject (high) | A | - |
| amb20 | UNDECIDED / UNDECIDED | REJECT / REJECT | accept (low) | accept (low) | A | - |
| amb21 | REJECT / UNDECIDED | REJECT / UNDECIDED | accept (low) | reject (medium) | A | - |
| amb22 | REJECT / REJECT | REJECT / REJECT | accept (medium) | reject (medium) | neither (note 2) | - |
| amb23 | REJECT / UNDECIDED | REJECT / UNDECIDED | accept (high) | accept (high) | A | - |
| amb24 | REJECT / REJECT | REJECT / REJECT | accept (high) | reject (high) | A | A is byte-identical to start |
| amb25 | REJECT / ACCEPT | REJECT / ACCEPT | accept (medium) | reject (medium) | A | A is byte-identical to start |
| amb26 | UNDECIDED / UNDECIDED | REJECT / REJECT | accept (high) | accept (medium) | A | A is byte-identical to start |
| amb27 | REJECT / ACCEPT | REJECT / ACCEPT | accept (low) | reject (high) | A | - |
| amb28 | REJECT / ACCEPT | REJECT / ACCEPT | accept (low) | reject (medium) | A | - |
| amb29 | ACCEPT / ACCEPT | ACCEPT / ACCEPT | accept (high) | reject (high) | A | - |
| amb30 | ACCEPT / ACCEPT | ACCEPT / ACCEPT | accept (low) | accept (low) | neither (note 3) | - |
| amb31 | REJECT / ACCEPT | REJECT / ACCEPT | accept (low) | accept (low) | A | - |
| amb32 | UNDECIDED / UNDECIDED | REJECT / REJECT | accept (low) | reject (high) | A | - |
| amb33 | UNDECIDED / UNDECIDED | UNDECIDED / UNDECIDED | accept (high) | accept (high) | A | - |
| amb34 | ACCEPT / ACCEPT | REJECT / REJECT | accept (high) | reject (high) | A | - |
| amb35 | REJECT / ACCEPT | REJECT / ACCEPT | accept (low) | accept (low) | A | A is byte-identical to start |
| amb36 | ACCEPT / ACCEPT | REJECT / REJECT | accept (high) | reject (medium) | A | - |
| amb37 | REJECT / REJECT | REJECT / REJECT | accept (low) | accept (medium) | A | - |
| amb38 | ACCEPT / ACCEPT | REJECT / REJECT | accept (high) | reject (high) | A | - |
| amb39 | REJECT / REJECT | REJECT / REJECT | reject (medium) | reject (high) | neither (note 4) | - |
| amb40 | ACCEPT / ACCEPT | REJECT / REJECT | accept (low) | reject (high) | A | - |

Notes on the followed-reading column:
1. amb17: writer followed "magnitude of each Amount grows" (values scaled); neither A nor B.
2. amb22: writer followed "table already sums to 10, leave it"; neither A nor B.
3. amb30: writer followed italics on both conditional lines and bracketed instructions; union of A and B.
4. amb39: writer followed "remove bullet markers, keep text"; neither A nor B.
