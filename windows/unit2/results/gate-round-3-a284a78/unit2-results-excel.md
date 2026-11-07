# Unit 2 results (excel)

Isolation: in-process socket guard only; OS-level network isolation not applied on Windows. Snapshot method: copy (NTFS has no block clone).

| Scenario | Outcome | Winner | Replays | Notes kept | User cell kept | Committed | Snapshot s | Search s | Verify s | Commit s | Total s | Divergence bytes direct / wrong / null | Mutation correct | Network guard | Second method verified | Round-trip losses |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| normal | committed | f1_direct | 0 | True | None | yes | 3.19 | 9.27 | 0.04 | 0.03 | 16.74 | 11667 / 9341 / 0 | 6/6 | installed; office COM allowed | yes | none |
| conflict | committed | replay1 | 1 | True | True | yes | 2.51 | 12.51 | 0.1 | 0.02 | 33.39 | 11669 / 9346 / 0 | 6/6 | installed; office COM allowed | yes | none |
| same_cell | true_conflict | f1_direct | 0 | True | True | no | 2.27 | 8.9 | 0.19 | - | 15.89 | 11665 / 9347 / 0 | 6/6 | installed; office COM allowed | yes | none |
| features | agreement_refused | - | 0 | True | None | no | 5.71 | 26.39 | 0.09 | - | 42.68 | 12218 / 9869 / 0 | 6/6 | installed; office COM allowed | no | value |
