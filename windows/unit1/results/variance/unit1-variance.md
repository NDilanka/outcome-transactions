## Variance: 90 runs, 3 reps per cell

| app | state | method | main verdict | rep 1 | rep 2 | rep 3 | stable | foreground changes in commit (reps 1, 2, 3) | dialogs (reps 1, 2, 3) |
|---|---|---|---|---|---|---|---|---|---|
| excel | clean | close-replace-reopen | PASS | PASS | PASS | PASS | yes | 1, 1, 0 | 0, 0, 0 |
| excel | clean | live-com-quiet-focused | PASS | PASS | PASS | PASS | yes | 1, 0, 0 | 0, 0, 0 |
| excel | clean | live-com-quiet | PASS | PASS | PASS | PASS | yes | 0, 0, 0 | 0, 0, 0 |
| excel | clean | live-com | PASS | PASS | PASS | PASS | yes | 0, 0, 0 | 0, 0, 0 |
| excel | dirty | live-com-focused | PASS | status error | PASS | PASS | no | 0, 0, 1 | 0, 0, 0 |
| excel | dirty | live-com-quiet-focused | PASS | PASS | PASS | PASS | yes | 0, 0, 1 | 0, 0, 0 |
| excel | dirty | live-com-quiet | PASS | PASS | PASS | PASS | yes | 0, 0, 0 | 0, 0, 0 |
| excel | dirty | live-com | PASS | PASS | PASS | PASS | yes | 0, 0, 0 | 0, 0, 0 |
| word | clean | close-replace-reopen | PASS | PASS | PASS | PASS | yes | 0, 0, 0 | 0, 0, 0 |
| word | clean | live-com-quiet-focused | PASS | PASS | PASS | PASS | yes | 0, 0, 0 | 0, 0, 0 |
| word | clean | live-com-quiet | PASS | PASS | PASS | PASS | yes | 0, 0, 0 | 0, 0, 0 |
| word | clean | live-com | PASS | PASS | PASS | PASS | yes | 0, 0, 0 | 0, 0, 0 |
| word | dirty | live-com-focused | PASS | PASS | PASS | PASS | yes | 1, 0, 1 | 0, 0, 0 |
| word | dirty | live-com-quiet-focused | PASS | PASS | PASS | PASS | yes | 1, 0, 0 | 0, 0, 0 |
| word | dirty | live-com-quiet | PASS | PASS | PASS | PASS | yes | 0, 0, 0 | 0, 0, 0 |
| word | dirty | live-com | PASS | PASS | PASS | PASS | yes | 0, 0, 0 | 0, 0, 0 |
| excel | clean | inplace | REFUSED | REFUSED | REFUSED | REFUSED | yes | 0, 0, 0 | 0, 0, 0 |
| excel | clean | reload-after-replace | REFUSED | REFUSED | REFUSED | REFUSED | yes | 0, 0, 0 | 0, 0, 0 |
| excel | clean | replace | REFUSED | REFUSED | REFUSED | REFUSED | yes | 1, 0, 0 | 0, 0, 0 |
| excel | clean | sibling-rename | REFUSED | REFUSED | REFUSED | REFUSED | yes | 0, 0, 0 | 0, 0, 0 |
| excel | dirty | inplace | REFUSED | REFUSED | REFUSED | REFUSED | yes | 0, 0, 0 | 0, 0, 0 |
| excel | dirty | replace | REFUSED | REFUSED | REFUSED | REFUSED | yes | 0, 0, 0 | 0, 0, 0 |
| excel | dirty | sibling-rename | REFUSED | REFUSED | REFUSED | REFUSED | yes | 0, 0, 0 | 0, 0, 0 |
| word | clean | inplace | REFUSED | REFUSED | REFUSED | REFUSED | yes | 0, 0, 0 | 0, 0, 0 |
| word | clean | reload-after-replace | REFUSED | REFUSED | REFUSED | REFUSED | yes | 0, 0, 0 | 0, 0, 0 |
| word | clean | replace | REFUSED | REFUSED | REFUSED | REFUSED | yes | 0, 0, 0 | 0, 0, 0 |
| word | clean | sibling-rename | REFUSED | REFUSED | REFUSED | REFUSED | yes | 0, 0, 0 | 0, 0, 0 |
| word | dirty | inplace | REFUSED | REFUSED | REFUSED | REFUSED | yes | 0, 0, 0 | 0, 0, 0 |
| word | dirty | replace | REFUSED | REFUSED | REFUSED | REFUSED | yes | 0, 0, 0 | 0, 0, 0 |
| word | dirty | sibling-rename | REFUSED | REFUSED | REFUSED | REFUSED | yes | 0, 0, 0 | 0, 0, 0 |

Cells that changed verdict across reps: ['excel-dirty-live-com-focused'].

Foreground changes during commit, runs with at least one: ['excel-clean-close-replace-reopen rep 1: 1', 'excel-clean-close-replace-reopen rep 2: 1', 'excel-clean-live-com-quiet-focused rep 1: 1', 'excel-dirty-live-com-focused rep 3: 1', 'excel-dirty-live-com-quiet-focused rep 3: 1', 'word-dirty-live-com-focused rep 1: 1', 'word-dirty-live-com-focused rep 3: 1', 'word-dirty-live-com-quiet-focused rep 1: 1', 'excel-clean-replace rep 1: 1'].
