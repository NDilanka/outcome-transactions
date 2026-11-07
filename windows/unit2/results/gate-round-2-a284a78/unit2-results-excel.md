# Unit 2 results (excel)

Isolation: in-process socket guard only; OS-level network isolation not applied on Windows. Snapshot method: copy (NTFS has no block clone).

| Scenario | Outcome | Winner | Replays | Notes kept | User cell kept | Committed | Snapshot s | Search s | Verify s | Commit s | Total s | Divergence bytes direct / wrong / null | Mutation correct | Network guard | Second method verified | Round-trip losses |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| normal | committed | f1_direct | 0 | True | None | yes | 3.3 | 10.03 | 0.06 | 0.07 | 19.23 | 11662 / 9342 / 0 | 6/6 | installed; office COM allowed | yes | none |
| conflict | committed | replay1 | 1 | True | True | yes | 3.0 | 12.06 | 0.05 | 0.02 | 32.22 | 11663 / 9346 / 0 | 6/6 | installed; office COM allowed | yes | none |
| same_cell | true_conflict | f1_direct | 0 | True | True | no | 3.35 | 8.76 | 0.05 | - | 18.81 | 11668 / 9345 / 0 | 6/6 | installed; office COM allowed | yes | none |
| features | agreement_refused | - | 0 | True | None | no | 2.74 | 9.64 | 0.07 | - | 17.12 | 12221 / 9868 / 0 | 6/6 | installed; office COM allowed | no | value |
