## Revert per run

| case | rep | expected | revert calls | revert results | footprint | confirm reasons | in memory after revert | on disk after save | residue left by revert | foreground changes in revert | dialogs | verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| after-other-cell | 1 | reverted | 1 | reverted | B2 | none | prior | prior | none | 0 | 0 | CORRECT |
| after-other-cell | 2 | reverted | 1 | reverted | B2 | none | prior | prior | none | 0 | 0 | CORRECT |
| after-other-cell | 3 | reverted | 1 | reverted | B2 | none | prior | prior | none | 0 | 0 | CORRECT |
| after-same-cell | 1 | refused | 1 | refused | B2 | none | user value (77) | user value (77) | none | 0 | 0 | CORRECT |
| after-same-cell | 2 | refused | 1 | refused | B2 | none | user value (77) | user value (77) | none | 0 | 0 | CORRECT |
| after-same-cell | 3 | refused | 1 | refused | B2 | none | user value (77) | user value (77) | none | 0 | 0 | CORRECT |
| clean-format | 1 | reverted | 1 | reverted | B2 | none | prior | prior | none | 0 | 0 | CORRECT |
| clean-format | 2 | reverted | 1 | reverted | B2 | none | prior | prior | none | 0 | 0 | CORRECT |
| clean-format | 3 | reverted | 1 | reverted | B2 | none | prior | prior | none | 0 | 0 | CORRECT |
| clean-value | 1 | reverted | 1 | reverted | B2 | none | prior | prior | none | 0 | 0 | CORRECT |
| clean-value | 2 | reverted | 1 | reverted | B2 | none | prior | prior | none | 0 | 0 | CORRECT |
| clean-value | 3 | reverted | 1 | reverted | B2 | none | prior | prior | none | 0 | 0 | CORRECT |
| comment | 1 | confirm | 2 | confirm_required then reverted (confirm) | B2 | comment added or removed, which the record does not capture | prior | prior | comment on B2 | 0 | 0 | CORRECT |
| comment | 2 | confirm | 2 | confirm_required then reverted (confirm) | B2 | comment added or removed, which the record does not capture | prior | prior | comment on B2 | 0 | 0 | CORRECT |
| comment | 3 | confirm | 2 | confirm_required then reverted (confirm) | B2 | comment added or removed, which the record does not capture | prior | prior | comment on B2 | 0 | 0 | CORRECT |
| dirty-user-elsewhere | 1 | reverted | 1 | reverted | B2 | none | prior | prior | none | 0 | 0 | CORRECT |
| dirty-user-elsewhere | 2 | reverted | 1 | reverted | B2 | none | prior | prior | none | 0 | 0 | CORRECT |
| dirty-user-elsewhere | 3 | reverted | 1 | reverted | B2 | none | prior | prior | none | 0 | 0 | CORRECT |
| formula | 1 | confirm | 2 | confirm_required then reverted (confirm) | E2 | E2: formula cell | prior | prior | none | 0 | 0 | CORRECT |
| formula | 2 | confirm | 2 | confirm_required then reverted (confirm) | E2 | E2: formula cell | prior | prior | none | 0 | 0 | CORRECT |
| formula | 3 | confirm | 2 | confirm_required then reverted (confirm) | E2 | E2: formula cell | prior | prior | none | 0 | 0 | CORRECT |
| merged | 1 | confirm | 2 | confirm_required then reverted (confirm) | E5 | E5: merged range | prior | prior | none | 0 | 0 | CORRECT |
| merged | 2 | confirm | 2 | confirm_required then reverted (confirm) | E5 | E5: merged range | prior | prior | none | 0 | 0 | CORRECT |
| merged | 3 | confirm | 2 | confirm_required then reverted (confirm) | E5 | E5: merged range | prior | prior | none | 0 | 0 | CORRECT |
