# Unit 2 results (excel)

Isolation: in-process socket guard only; OS-level network isolation not applied on Windows. Snapshot method: copy (NTFS has no block clone).

| Scenario | Outcome | Winner | Replays | Notes kept | User cell kept | Committed | Snapshot s | Search s | Verify s | Commit s | Total s | Divergence bytes direct / wrong / null | Mutation correct | Network guard |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| normal | committed | f1_direct | 0 | True | None | yes | 0.02 | 5.77 | 0.04 | 0.03 | 9.69 | 11665 / 9338 / 0 | 6/6 | installed; office COM allowed |
| conflict | committed | replay1 | 1 | True | True | yes | 0.01 | 5.69 | 0.04 | 0.02 | 12.1 | 11662 / 9343 / 0 | 6/6 | installed; office COM allowed |
| same_cell | true_conflict | f1_direct | 0 | True | True | no | 0.02 | 11.76 | 0.06 | - | 15.19 | 11666 / 9344 / 0 | 6/6 | installed; office COM allowed |
