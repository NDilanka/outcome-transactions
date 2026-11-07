# Unit 2 results (excel)

Isolation: in-process socket guard only; OS-level network isolation not applied on Windows. Snapshot method: copy (NTFS has no block clone).

| Scenario | Outcome | Winner | Replays | Notes kept | User cell kept | Committed | Snapshot s | Search s | Verify s | Commit s | Total s | Divergence bytes direct / wrong / null | Mutation correct | Network guard | Second method verified | Round-trip losses |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| normal | committed | f1_direct | 0 | True | None | yes | 2.31 | 5.94 | 0.04 | 0.02 | 10.9 | 11666 / 9341 / 0 | 6/6 | installed; office COM allowed | yes | none |
| conflict | committed | replay1 | 1 | True | True | yes | 1.26 | 4.27 | 0.03 | 0.01 | 12.17 | 11668 / 9348 / 0 | 6/6 | installed; office COM allowed | yes | none |
| same_cell | true_conflict | f1_direct | 0 | True | True | no | 1.26 | 15.22 | 0.09 | - | 18.99 | 11668 / 9346 / 0 | 6/6 | installed; office COM allowed | yes | none |
| features | agreement_refused | - | 0 | True | None | no | 11.54 | 16.95 | 0.07 | - | 44.74 | 12220 / 9872 / 0 | 6/6 | installed; office COM allowed | no | value |
