# Experiment 10 results: does a render judge catch what the text judge accepts?

Status: scored once, with the locked scorer. Verdicts are from branch `exp10-judge-verdicts` (commit f9fc8b7, on top of the packet root 433a0ec). The scorer is `exp10_score.py` (sha256 3a9cbe95..., unchanged since the lock at ff013bb). Its raw output is `exp10-results.json` in this folder. Rules: `exp10-preregistration.md`, sections 3 to 8, Amendment 1 (section 12) and Addendum A.

Attempt codes are the Exp 8 codes, as in the preregistration. Labels: **measured** (scorer or run output), **inferred**, **reported** (from the judge or from Exp 8 files).

## 1. Result

- **The gate fails.** Basis 18 passes. Basis 17 fails: A AND R still commits a wrong candidate on d53ff5ee (method 2). The render key does not earn a second-key place. **Measured.**
- **Renderable wrong accepts:** the render judge rejected 3 of 3 (ecc2413d, methods 1, 2 and 4), all with high confidence. **Measured.**
- **Other office wrong accepts:** the render judge rejected 1 of 3 (66399b0d method 4), and accepted d53ff5ee methods 2 and 4, both with high confidence. **Measured.**
- **Office wrong states (11):** Sol accepted 6 and rejected 5. The render judge rejected 8 and accepted 3. **Measured.**
- **Office correct states (69):** the render judge rejected 13, a rate of 18.8% (95% exact interval 10.4% to 30.1%). Sol rejected 13 too. The two sets share 5 states, and the rest split into 8 render-only and 8 Sol-only. **Measured.**
- **Interpretation (the two judges' errors differ):** on these real agent outputs, the render judge and Sol fail on different states. On wrong states, the render alone caught 4 and Sol alone caught 1. On correct states, 8 were rejected only by the render and 8 only by Sol. The render caught all 3 pagination cases (ecc2413d methods 1, 2 and 4), the class the predicate was written for. This is one run on 80 states, so it shows the errors differ here, not that they are independent in general.
- **Interpretation (request-reading class):** the gate fails on d53ff5ee method 2. The render and Sol both accepted it, and no second representation caught this shared misreading. Amendment 1 made no prediction for this pair, so this is a result, not a predicted outcome.
- **Interpretation (judge reliability):** the render judge applied the blank-page reason inconsistently across the 8 66399b0d states. All 8 go from 2 to 3 pages. It rejected 3 for a blank page (ui method 4, noui methods 2 and 4). It accepted 3 with the same page count (ui methods 1 and 2, noui method 1) without citing a blank page. This is a reliability limit of the judge's reading, not of the render's pages.

## 2. Verdicts checked before scoring

- 32 verdict files on `exp10-judge-verdicts`, one per batch. The batch ids equal the 80 packet folders, with one entry per id and no duplicates. **Measured.**
- Each entry has `verdict` (accept or reject), `confidence` (high, medium or low) and a non-empty `reason`. Totals: 59 accept (28 high, 25 low, 6 medium) and 21 reject (12 high, 9 medium). **Measured.**
- The four profile states have no packet. Their render verdict is undecided, which counts as reject (section 3 of the preregistration).
- Scorer checks: the salt matches the commitment `a3bdd873...`, and the scorer and prompt hashes match the lock. **Measured.**

## 3. Gate and policies

Policies are on the 18 primary requests. A is Sol's highest-confidence accept. R is the render judge's highest-confidence accept. A AND R is the highest Sol confidence among candidates both judges accept, then render confidence. Ties go to the lower method.

| Policy | Basis 17: correct, wrong, confirm (17 requests) | Basis 18: correct, wrong, confirm (18 requests) |
|---|---|---|
| A (Sol) | 13, 2, 2 | 13, 3, 2 |
| R (render) | 14, 2, 1 | 14, 2, 2 |
| A AND R | 13, 1, 3 | 13, 1, 4 |

Gate outcome (section 7 and Amendment 1, item 3):

| Basis | Test | Result |
|---|---|---|
| 18 | A AND R removes at least 2 of A's 3 wrong commits (removed: 2cd43775, ecc2413d) | Pass |
| 18 | A AND R keeps at least 12 of A's 13 correct commits (kept 13) | Pass |
| 17 | A AND R leaves no wrong commit on both of A's wrong requests (removed ecc2413d; d53ff5ee still wrong) | **Fail** |
| 17 | A AND R keeps at least 12 of A's 13 correct commits (kept 13) | Pass |

**The gate fails on basis 17.** The Amendment 1 expectation said the render had to reject both d53ff5ee candidates. It accepted both. **Measured.**

Basis 18 credits 2cd43775 by construction (the profile render is undecided, so it counts as reject). Basis 17 is the test of the render itself.

Sensitivity (2cd43775 scored under the all-C auto-save reading): A 14 correct, 2 wrong, 2 confirm. R 14, 2, 2. A AND R 13, 1, 4. **Measured.**

### Per request (strict GT, candidate committed by each policy)

| Request | A | R | A AND R |
|---|---|---|---|
| 0326d92d | correct, m1 | correct, m1 | correct, m1 |
| 1273e544 | correct, m1 | correct, m1 | correct, m1 |
| 21760ecb | correct, m2 | correct, m1 | correct, m2 |
| 2cd43775 (basis 18 only) | wrong, m1 | confirm | confirm |
| 42e0a640 | correct, m1 | correct, m1 | correct, m1 |
| 51719eea | correct, m3 | **wrong, m1** | correct, m3 |
| 550ce7e7 | correct, m1 | correct, m4 | correct, m4 |
| 57667013 | correct, m1 | correct, m1 | correct, m1 |
| 6054afcb | correct, m1 | correct, m1 | correct, m1 |
| 66399b0d | correct, m1 | correct, m1 | correct, m1 |
| 6a33f9b9 | correct, m1 | correct, m1 | correct, m1 |
| 7ae48c60 | confirm | correct, m2 | confirm |
| 88fe4b2d | correct, m1 | correct, m1 | correct, m1 |
| 936321ce | correct, m1 | correct, m1 | correct, m1 |
| a9f325aa | confirm | correct, m2 | confirm |
| d53ff5ee | **wrong, m2** | **wrong, m2** | **wrong, m2** |
| ecc2413d | **wrong, m1** | confirm | confirm |
| f23acfd2 | correct, m3 | correct, m3 | correct, m3 |

## 4. Joint table, office states (80 rendered, strict GT)

Each cell is a count of states. "Render only" means Sol accepted and the render rejected. "Sol only" means Sol rejected and the render accepted. **Measured.**

| GT v4 strict | Both reject | Render only | Sol only | Both accept | Total |
|---|---|---|---|---|---|
| Wrong (11) | 4 | 4 | 1 | 2 | 11 |
| Correct (69) | 5 | 8 | 8 | 48 | 69 |

- Render rejects of correct states: 13 of 69 (18.8%, exact 95% interval 10.4% to 30.1%). Sol rejects of correct states: 13 of 69, the same rate and interval.
- Profile states (not rendered, Sol's verdict only): 2cd43775 methods 1 (wrong, accept), 2 (wrong, reject), 3 (correct, accept) and 4 (wrong, reject). **Measured.**

## 5. Sol's first-pass wrong accepts (7)

Seven wrong accepts, from the strict GT. Six are office states with a render verdict. One is the profile state, which has no render. The renderability flags are from section 5 of the preregistration. The render verdict and its reason are quoted verbatim from the judge.

| Attempt | Renderable (section 5) | Sol first pass | Render verdict | Reason (verbatim) |
|---|---|---|---|---|
| 2cd43775 m1 (attempt 083c86e1), profile | No (profile folder) | accept, high | undecided (no packet, counts as reject) | none |
| 66399b0d m4, ui (attempt e6b4b156) | No (cursor) | accept, low | reject, high. **Tag: both** | "The empty seven-column, five-row table was inserted below the existing table, but an unrequested blank third page was also added." |
| d53ff5ee m2 (attempt de97694c) | No (request reading) | accept, high | **accept, high** | "The document text, including headings and table entries, is lowercase while its content and formatting are preserved." |
| d53ff5ee m4 (attempt b9d8b59c) | No (request reading) | accept, high | **accept, high** | "All visible text has been converted to lowercase while preserving the document's content and formatting." |
| ecc2413d m1, ui (attempt 476b080a) | Yes (page count) | accept, low | reject, high | "There is no blank page after page 1, and page 2 still contains the statutory declaration." |
| ecc2413d m2, ui (attempt eeb4b683) | Yes (page count) | accept, low | reject, high | "Page 2 still contains the statutory declaration rather than the requested blank page after page 1." |
| ecc2413d m4, ui (attempt 7b72ebd1) | Yes (page count) | accept, low | reject, high | "Page 2 still contains declaration text immediately after page 1, so the requested blank page was not inserted." |

**Tag for 66399b0d m4 (Amendment 1, item 2): both.** The reason uses an image fact, the unrequested blank third page. It also uses the position "below the existing table", which matches the wording of the Live UI block ("below the table"). The tag does not change the verdict. **Measured (tag rule), inferred (reading of the reason).**

What the render showed for 66399b0d: all eight states go from 2 to 3 pages. Page 3 is blank (no text, drawings or images) in the two correct states I checked (noui methods 2 and 4). So the blank page is real. The label for the correct states does not count it as a defect. **Measured.** The GT's wrong label for m4 rests on its cursor placement (Exp 8 results, cursor probe). The render judge's reason does not address that placement. **Reported.**

Result on the ecc2413d states: the page-count predicate matched (7 pages on each side for methods 1, 2 and 4). The render rejected all three. **Measured.** The GT ruling for ecc2413d (ruling 1c) was set by a LibreOffice render, so this agreement is not independent of the GT (preregistration, section 9). **Reported.**

Result on d53ff5ee: no predicate was registered for it (section 5). The render accepted both wrong candidates with high confidence, so the basis-17 expectation failed. **Measured.** Both reasons describe the lowercased text as correct. Whether that is wrong depends on the request reading (GT ruling d53ff5ee, option a). The render judge did not raise that reading. **Inferred.**

## 6. Render accepts of wrong office states not in Sol's list

One more wrong state was accepted by the render, and Sol rejected it. Its reason is quoted verbatim.

| Attempt | Sol first pass | Render verdict | Reason (verbatim) |
|---|---|---|---|
| 51719eea m1 (attempt 3ab6ba1b), xlsx | reject, high | accept, low | "The revenue values correctly reflect retail price, quantity and discount and the new page summarizes revenue by product, although the images cannot verify the Sheet2 name or actual Pivot Table structure." |

The judge said the images could not confirm the pivot table structure or the sheet name. This is a limit of the render for spreadsheets (preregistration, section 9). **Reported, inferred.** Under R this state is the wrong commit on 51719eea. A AND R commits the correct candidate there, because Sol rejects this candidate. **Measured.**

## 7. Render false rejects on correct office states (13)

Every render reject on a GT-correct office state, with the reason quoted verbatim. Sol rejected 13 correct states too, but on different states (section 4).

| Attempt | Sol first pass | Render verdict | Reason (verbatim) |
|---|---|---|---|
| 6054afcb m3 (4e3dd7f6), xlsx | accept, medium | reject, medium | "Entire records containing N/A disappear from the visible table, hiding populated dates and budgets as well as the requested N/A markers." |
| a9f325aa m1 (0184bad5), xlsx | reject, medium | reject, medium | "The hyphenated title leaves the word after the hyphen lowercase rather than capitalizing the first letter of every word." |
| 7ae48c60 m1 (055f763f), pptx | reject, high | reject, medium | "On slide 3 the decorative squiggles have been enlarged across the text while the main photograph remains unchanged, causing unrequested layout damage." |
| f23acfd2 m2, ui (a82ecaac), pptx | reject, medium | reject, medium | "The existing slide content remains unbulleted while an unrelated placeholder reading 'New bullet point' has been added." |
| f23acfd2 m4, ui (5d0f89a5), pptx | reject, high | reject, high | "The slide content remains unchanged with no bullet point added." |
| 66399b0d m3, ui (d0089f7d), docx | accept, low | reject, medium | "The empty seven-column, five-row table is present, but the existing work-effort table has also been shifted left without being requested." |
| 66399b0d m2, noui (b5b43c61), docx | accept, low | reject, medium | "An empty 7-column, 5-row table was inserted, but the existing table's formatting changed and an unrequested blank third page was added." |
| 66399b0d m3, noui (58c48620), docx | accept, low | reject, medium | "The empty 7-column, 5-row table is present, but the existing example table's outer borders and column widths were also changed." |
| 66399b0d m4, noui (49e0f4f8), docx | accept, low | reject, medium | "The empty seven-column, five-row table is present, but an unrequested blank third page has also been introduced." |
| 936321ce m3 (8275ea44), docx | accept, low | reject, high | "The comma-separated text became a table, but the meaningful underlining of graphemes in the example words was removed." |
| d53ff5ee m1 (699226e8), docx | accept, medium | reject, high | "Only one paragraph was lowercased, leaving uppercase letters in the title, other paragraphs, and table." |
| d53ff5ee m3 (a6cac88c), docx | reject, medium | reject, high | "The uppercase passages were lowercased, but the following paragraph's spacing and wrapping changed and the existing table shifted left without being requested." |
| ecc2413d m3, ui (02d030c7), docx | accept, low | reject, high | "A blank second page was added, but the original document's text wrapping, spacing and table positions were also altered." |

Notes on these 13 (measured from the reasons and the render):
- Two 66399b0d rejects (noui methods 2 and 4) cite the blank third page. So does the wrong state (ui method 4). The judge accepted ui methods 1 and 2 and noui method 1, which have the same 2-to-3-page layout. One of those accept reasons says "split across two pages". So the blank-page reason was not applied the same way to states with the same page count.
- Two rejects (d53ff5ee methods 1 and 3) are on the request-reading case. GT v4 labels both correct.
- The ecc2413d method 3 reject is the correct state with the added page. The judge wrote that the layout was also altered.

## 8. Costs (section 8)

Measured on the render run (`exp10_run.py`) and the scorer output:

- Render time per state (wall clock, cold start, conversion through PNG checks): median 2.35 s (the average of the two middle values; the scorer's nearest-rank median is 2.34 s), 90th percentile 10.88 s, maximum 15.21 s (a 6-page state with 12 PNGs). Total 337 s for 80 states.
- PNGs: 847 in all. Largest state 48 PNGs. Largest batch 48 PNGs. Largest PNG 4,108,801 bytes.
- Batches: 32 (groups of 4 by blind id, split by PNG count). Eight states over 40 PNGs, each alone in its batch.
- Pages re-encoded losslessly: 8 (in 4 states). Pages tiled: 0.
- MuPDF printed 64 warnings, "cannot create appearance stream for Screen annotations" (form-field annotations). No page was dropped.
- Judge tokens and per-batch timing were not measured.
- Render false-reject rate on correct office states: 13 of 69 (18.8%, 10.4% to 30.1%). Sol's rate on the same states: 13 of 69.

## 9. Salt

The salt was revealed after the scorer had run. The scorer checked it against the commitment `a3bdd873ee37ff981732b87d04d0a7fd04b6f2a18a04d705fc927744789ec07d` (sha256 of the salt text, no final newline) before it computed any result. **Measured.**

SALT: `e30c1083c913a25678bf006309855c2143c9fbf69b512f0568b01dd79f5495e0`

## 10. Limits

- Same judge (Sol) as the text judge, with pictures in place of text. One judge run, not repeated. Judge variance is measured only by Exp 8 (4 of 84 verdicts flipped on rerun).
- LibreOffice is the only renderer. Word was not checked.
- The ecc2413d GT was set by a LibreOffice render (ruling 1c), so that agreement is not independent of the GT.
- A cursor position (66399b0d) and a profile setting (2cd43775) cannot be seen in a render. The UI block was the only record for the cursor.
- Spreadsheets render as print output. A pivot table structure and sheet names may not show (section 6).
- 18 requests and 80 rendered states. The results describe these states.
- The alphanumeric row-check variant (Addendum A) is post hoc. It was not used for any number here.

## 11. Reproduce

```
exp10_score.py --salt-file <salt> --verdicts-dir <verdicts> --stats <run>/stats.json \
  --packets <run>/packets --batches <run>/batches --out exp10-results.json
```

Verdicts: branch `exp10-judge-verdicts`, commit f9fc8b7, files `verdicts/verdicts_01.json` to `verdicts_32.json`. Packets: branch `exp10-packets`, commit 433a0ec.

## Appendix: all 80 rendered office states

Sorted by request, method and condition. The 4 profile states are in section 4.

| Exp 8 code | Request | Method | Condition | Kind | GT v4 (strict) | Sol first pass | Render verdict |
|---|---|---|---|---|---|---|---|
| ff0d05a9 | 0326d92d | 1 | none | xlsx | C | accept, low | accept, high |
| f18f5859 | 0326d92d | 2 | none | xlsx | C | accept, low | accept, high |
| 5c34a92b | 0326d92d | 3 | none | xlsx | C | accept, low | accept, high |
| 861cce96 | 0326d92d | 4 | none | xlsx | C | accept, low | accept, high |
| fd317894 | 1273e544 | 1 | none | xlsx | C | accept, high | accept, low |
| a429f526 | 1273e544 | 2 | none | xlsx | C | accept, high | accept, low |
| 4628b3fe | 1273e544 | 3 | none | xlsx | C | accept, high | accept, low |
| 85834c78 | 1273e544 | 4 | none | xlsx | C | accept, high | accept, low |
| 2f1be108 | 21760ecb | 1 | noui | pptx | C | accept, low | accept, low |
| 27a4b457 | 21760ecb | 1 | ui | pptx | C | accept, low | accept, low |
| 02763f79 | 21760ecb | 2 | noui | pptx | C | accept, high | accept, low |
| 4bbc8949 | 21760ecb | 2 | ui | pptx | C | accept, high | accept, low |
| 2cd48d90 | 21760ecb | 3 | noui | pptx | W | reject, high | reject, high |
| f624e5ec | 21760ecb | 3 | ui | pptx | W | reject, high | reject, high |
| ca8f42eb | 21760ecb | 4 | noui | pptx | C | accept, high | accept, low |
| 3b5e7219 | 21760ecb | 4 | ui | pptx | C | accept, high | accept, low |
| 73fca539 | 42e0a640 | 1 | none | xlsx | C | accept, high | accept, low |
| cbd4feef | 42e0a640 | 2 | none | xlsx | C | accept, high | accept, low |
| 8e61376d | 42e0a640 | 3 | none | xlsx | C | accept, high | accept, low |
| e45c72f8 | 42e0a640 | 4 | none | xlsx | C | accept, high | accept, low |
| 3ab6ba1b | 51719eea | 1 | none | xlsx | W | reject, high | accept, low |
| 3f9e3de2 | 51719eea | 2 | none | xlsx | W | reject, high | reject, high |
| 74e4e825 | 51719eea | 3 | none | xlsx | C | accept, low | accept, low |
| b89fa873 | 51719eea | 4 | none | xlsx | C | accept, low | accept, low |
| b26824d0 | 550ce7e7 | 1 | noui | pptx | C | accept, medium | accept, high |
| 75dfcc33 | 550ce7e7 | 1 | ui | pptx | C | accept, high | accept, medium |
| 907c296d | 550ce7e7 | 2 | noui | pptx | C | accept, low | accept, high |
| 431c3aa6 | 550ce7e7 | 2 | ui | pptx | C | accept, high | accept, medium |
| 40e73df1 | 550ce7e7 | 3 | noui | pptx | C | accept, low | accept, high |
| 34e4ec4a | 550ce7e7 | 3 | ui | pptx | C | accept, medium | accept, medium |
| d71bee5a | 550ce7e7 | 4 | noui | pptx | C | accept, medium | accept, high |
| 3411f5b0 | 550ce7e7 | 4 | ui | pptx | C | accept, high | accept, high |
| 9e648579 | 57667013 | 1 | none | pptx | C | accept, high | accept, high |
| 629cb7af | 57667013 | 2 | none | pptx | C | accept, high | accept, high |
| 5eaa12a5 | 57667013 | 3 | none | pptx | C | accept, low | accept, high |
| 18c94eea | 57667013 | 4 | none | pptx | C | accept, high | accept, high |
| 5a2c5250 | 6054afcb | 1 | none | xlsx | C | accept, high | accept, low |
| d8fa1b66 | 6054afcb | 2 | none | xlsx | C | accept, medium | accept, low |
| 4e3dd7f6 | 6054afcb | 3 | none | xlsx | C | accept, medium | reject, medium |
| fbd38e91 | 6054afcb | 4 | none | xlsx | C | accept, high | accept, low |
| f0246e6d | 66399b0d | 1 | noui | docx | C | accept, low | accept, low |
| 799cff5f | 66399b0d | 1 | ui | docx | C | accept, low | accept, high |
| b5b43c61 | 66399b0d | 2 | noui | docx | C | accept, low | reject, medium |
| ef88f910 | 66399b0d | 2 | ui | docx | C | accept, low | accept, high |
| 58c48620 | 66399b0d | 3 | noui | docx | C | accept, low | reject, medium |
| d0089f7d | 66399b0d | 3 | ui | docx | C | accept, low | reject, medium |
| 49e0f4f8 | 66399b0d | 4 | noui | docx | C | accept, low | reject, medium |
| e6b4b156 | 66399b0d | 4 | ui | docx | W | accept, low | reject, high |
| 67e71203 | 6a33f9b9 | 1 | none | odt | C | accept, high | accept, high |
| e96b9f2e | 6a33f9b9 | 2 | none | odt | C | accept, high | accept, high |
| f3b9bec4 | 6a33f9b9 | 3 | none | odt | C | accept, high | accept, high |
| df133c60 | 6a33f9b9 | 4 | none | odt | C | accept, high | accept, high |
| 055f763f | 7ae48c60 | 1 | none | pptx | C | reject, high | reject, medium |
| 67903403 | 7ae48c60 | 2 | none | pptx | C | reject, high | accept, low |
| f06f57bc | 7ae48c60 | 3 | none | pptx | W | reject, high | reject, medium |
| ae6f6569 | 7ae48c60 | 4 | none | pptx | C | reject, high | accept, low |
| d759d99e | 88fe4b2d | 1 | none | docx | C | accept, high | accept, high |
| e86f5ecb | 88fe4b2d | 2 | none | docx | C | accept, high | accept, low |
| 84ce344f | 88fe4b2d | 3 | none | docx | C | reject, high | accept, high |
| 41f952df | 88fe4b2d | 4 | none | docx | C | accept, high | accept, high |
| 46b17a55 | 936321ce | 1 | none | docx | C | accept, high | accept, high |
| cf6bf3e3 | 936321ce | 2 | none | docx | C | accept, low | accept, high |
| 8275ea44 | 936321ce | 3 | none | docx | C | accept, low | reject, high |
| 886caffa | 936321ce | 4 | none | docx | C | reject, high | accept, high |
| 0184bad5 | a9f325aa | 1 | none | xlsx | C | reject, medium | reject, medium |
| a03e8257 | a9f325aa | 2 | none | xlsx | C | reject, medium | accept, medium |
| db47f2e7 | a9f325aa | 3 | none | xlsx | C | reject, medium | accept, medium |
| cdb9b450 | a9f325aa | 4 | none | xlsx | C | reject, medium | accept, medium |
| 699226e8 | d53ff5ee | 1 | none | docx | C | accept, medium | reject, high |
| de97694c | d53ff5ee | 2 | none | docx | W | accept, high | accept, high |
| a6cac88c | d53ff5ee | 3 | none | docx | C | reject, medium | reject, high |
| b9d8b59c | d53ff5ee | 4 | none | docx | W | accept, high | accept, high |
| 476b080a | ecc2413d | 1 | ui | docx | W | accept, low | reject, high |
| eeb4b683 | ecc2413d | 2 | ui | docx | W | accept, low | reject, high |
| 02d030c7 | ecc2413d | 3 | ui | docx | C | accept, low | reject, high |
| 7b72ebd1 | ecc2413d | 4 | ui | docx | W | accept, low | reject, high |
| 01fecf3e | f23acfd2 | 1 | ui | pptx | C | reject, high | accept, low |
| a82ecaac | f23acfd2 | 2 | ui | pptx | C | reject, medium | reject, medium |
| 8252b764 | f23acfd2 | 3 | ui | pptx | C | accept, high | accept, high |
| 5d0f89a5 | f23acfd2 | 4 | ui | pptx | C | reject, high | reject, high |
