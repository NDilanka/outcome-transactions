# Unit 2 results (excel)

Isolation: in-process socket guard only; OS-level network isolation not applied on Windows. Snapshot method: copy (NTFS has no block clone).

| Scenario | Outcome | Winner | Replays | Notes kept | User cell kept | Committed | Snapshot s | Search s | Verify s | Commit s | Total s | Divergence bytes direct / wrong / null | Mutation correct | Network guard | Second method verified | Round-trip losses |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| normal | committed | f1_direct | 0 | True | None | yes | 3.01 | 11.24 | 0.14 | 0.05 | 21.33 | 11665 / 9342 / 0 | 6/6 | installed; office COM allowed | yes | none |
| conflict | committed | replay1 | 1 | True | True | yes | 3.11 | 6.98 | 0.04 | 0.03 | 23.37 | 11670 / 9344 / 0 | 6/6 | installed; office COM allowed | yes | none |
| same_cell | true_conflict | f1_direct | 0 | True | True | no | 3.93 | 7.17 | 0.04 | - | 15.51 | 11666 / 9344 / 0 | 6/6 | installed; office COM allowed | yes | none |
| features | agreement_refused | - | 0 | True | None | no | 1.52 | 6.44 | 0.13 | - | 10.97 | 12220 / 9870 / 0 | 6/6 | installed; office COM allowed | no | value |
