# Unit 2 results (excel)

Isolation: in-process socket guard only; OS-level network isolation not applied on Windows. Snapshot method: copy (NTFS has no block clone).

| Scenario | Outcome | Winner | Replays | Notes kept | User cell kept | Committed | Snapshot s | Search s | Verify s | Commit s | Total s | Divergence bytes direct / wrong / null | Mutation correct | Network guard |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| normal | committed | f1_direct | 0 | True | None | yes | 0.02 | 8.09 | 0.04 | 0.06 | 12.56 | 11663 / 9342 / 0 | 6/6 | installed; office COM allowed |
| conflict | committed | replay1 | 1 | True | True | yes | 0.02 | 7.64 | 0.05 | 0.01 | 15.34 | 11666 / 9342 / 0 | 6/6 | installed; office COM allowed |
| same_cell | true_conflict | f1_direct | 0 | True | True | no | 0.02 | 8.82 | 0.04 | - | 14.8 | 11667 / 9346 / 0 | 6/6 | installed; office COM allowed |
