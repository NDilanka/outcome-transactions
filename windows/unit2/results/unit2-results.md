# Unit 2 results (offline)

Isolation: in-process socket guard only; OS-level network isolation not applied on Windows. Snapshot method: copy (NTFS has no block clone).

| Scenario | Outcome | Winner | Replays | Notes kept | User cell kept | Committed | Snapshot s | Search s | Verify s | Commit s | Total s | Divergence bytes direct / wrong / null | Mutation correct | Network guard |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| normal | committed | f1_direct | 0 | True | None | yes | 0.11 | 5.91 | 0.1 | 0.85 | 7.83 | 7867 / 7867 / 0 | 6/6 | installed; office COM refused |
| conflict | committed | replay1 | 1 | True | True | yes | 0.33 | 15.83 | 0.16 | 0.4 | 29.61 | 7867 / 7867 / 0 | 6/6 | installed; office COM refused |
| same_cell | true_conflict | f1_direct | 0 | True | True | no | 0.29 | 9.48 | 0.08 | - | 13.81 | 7867 / 7867 / 0 | 6/6 | installed; office COM refused |
