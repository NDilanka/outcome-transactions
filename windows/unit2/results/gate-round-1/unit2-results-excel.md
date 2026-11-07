# Unit 2 results (excel)

Isolation: in-process socket guard only; OS-level network isolation not applied on Windows. Snapshot method: copy (NTFS has no block clone).

| Scenario | Outcome | Winner | Replays | Notes kept | User cell kept | Committed | Snapshot s | Search s | Verify s | Commit s | Total s | Divergence bytes direct / wrong / null | Mutation correct | Network guard | Second method verified | Round-trip losses |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| normal | committed | f1_direct | 0 | True | None | yes | 3.37 | 11.12 | 0.07 | 0.03 | 21.83 | 11664 / 9342 / 0 | 6/6 | installed; office COM allowed | yes | none |
| conflict | committed | replay1 | 1 | True | True | yes | 1.76 | 3.65 | 0.03 | 0.01 | 11.51 | 11666 / 9343 / 0 | 6/6 | installed; office COM allowed | yes | none |
| same_cell | true_conflict | f1_direct | 0 | True | True | no | 1.01 | 4.83 | 0.04 | - | 7.63 | 11667 / 9345 / 0 | 6/6 | installed; office COM allowed | yes | none |
| features | agreement_refused | - | 0 | True | None | no | 1.72 | 6.84 | 0.04 | - | 11.64 | 12220 / 9871 / 0 | 6/6 | installed; office COM allowed | no | value |
