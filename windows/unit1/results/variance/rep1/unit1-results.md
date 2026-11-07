## Commit and verdict per run

| app | state | method | write ok | app shows commit before save | disk after commit | disk after user save | user edit kept | copy after commit correct | focus changes in commit | window changes in commit | undo first reverts | dialogs | verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| excel | clean | close-replace-reopen | yes | yes | new | new | n/a | yes | 1 | 0 | probe error | none | PASS: disk correct after the user's save |
| excel | clean | inplace | no: PermissionError winerror=None: Permission denied | no | old | old | n/a | no | 0 | 0 | nothing | none | REFUSED: write failed, nothing committed |
| excel | clean | live-com-quiet-focused | yes | yes | old | new | n/a | yes | 1 | 0 | nothing | none | PASS: disk correct after the user's save |
| excel | clean | live-com-quiet | yes | yes | old | new | n/a | yes | 0 | 0 | nothing | none | PASS: disk correct after the user's save |
| excel | clean | live-com | yes | yes | old | new | n/a | yes | 0 | 0 | nothing | none | PASS: disk correct after the user's save |
| excel | clean | reload-after-replace | no: PermissionError winerror=5: Access is denied | no | old | old | n/a | no | 0 | 0 | nothing | none | REFUSED: write failed, nothing committed |
| excel | clean | replace | no: PermissionError winerror=5: Access is denied | no | old | old | n/a | no | 1 | 0 | probe error | none | REFUSED: write failed, nothing committed |
| excel | clean | sibling-rename | no: PermissionError winerror=32: The process cannot access the file because it is being used by another process | no | old | old | n/a | no | 0 | 0 | nothing | none | REFUSED: write failed, nothing committed |
| excel | dirty | inplace | no: PermissionError winerror=None: Permission denied | no | old | old | yes | no | 0 | 0 | nothing | none | REFUSED: write failed, nothing committed |
| excel | dirty | live-com-focused | - | - | - | - | - | - | - | - | - | - | error |
| excel | dirty | live-com-quiet-focused | yes | yes | old | new | yes | yes | 0 | 0 | probe error | none | PASS: disk correct after the user's save |
| excel | dirty | live-com-quiet | yes | yes | old | new | yes | yes | 0 | 0 | nothing | none | PASS: disk correct after the user's save |
| excel | dirty | live-com | yes | yes | old | new | yes | yes | 0 | 0 | undo error | none | PASS: disk correct after the user's save |
| excel | dirty | replace | no: PermissionError winerror=5: Access is denied | no | old | old | yes | no | 0 | 0 | probe error | none | REFUSED: write failed, nothing committed |
| excel | dirty | sibling-rename | no: PermissionError winerror=32: The process cannot access the file because it is being used by another process | no | old | old | yes | no | 0 | 0 | nothing | none | REFUSED: write failed, nothing committed |
| word | clean | close-replace-reopen | yes | yes | new | new | n/a | yes | 0 | 1 | nothing | none | PASS: disk correct after the user's save |
| word | clean | inplace | no: PermissionError winerror=None: Permission denied | no | old | old | n/a | no | 0 | 0 | nothing | none | REFUSED: write failed, nothing committed |
| word | clean | live-com-quiet-focused | yes | yes | old | new | n/a | yes | 0 | 0 | others_ok | none | PASS: disk correct after the user's save |
| word | clean | live-com-quiet | yes | yes | old | new | n/a | yes | 0 | 0 | agent | none | PASS: disk correct after the user's save |
| word | clean | live-com | yes | yes | old | new | n/a | yes | 0 | 0 | agent | none | PASS: disk correct after the user's save |
| word | clean | reload-after-replace | no: PermissionError winerror=5: Access is denied | no | old | old | n/a | no | 0 | 1 | nothing | none | REFUSED: write failed, nothing committed |
| word | clean | replace | no: PermissionError winerror=5: Access is denied | no | old | old | n/a | no | 0 | 0 | nothing | none | REFUSED: write failed, nothing committed |
| word | clean | sibling-rename | no: PermissionError winerror=32: The process cannot access the file because it is being used by another process | no | old | old | n/a | no | 0 | 0 | nothing | none | REFUSED: write failed, nothing committed |
| word | dirty | inplace | no: PermissionError winerror=None: Permission denied | no | old | old | yes | no | 0 | 0 | user | none | REFUSED: write failed, nothing committed |
| word | dirty | live-com-focused | yes | yes | old | new | yes | yes | 1 | 0 | agent | none | PASS: disk correct after the user's save |
| word | dirty | live-com-quiet-focused | yes | yes | old | new | yes | yes | 1 | 0 | agent | none | PASS: disk correct after the user's save |
| word | dirty | live-com-quiet | yes | yes | old | new | yes | yes | 0 | 0 | agent | none | PASS: disk correct after the user's save |
| word | dirty | live-com | yes | yes | old | new | yes | yes | 0 | 0 | agent | none | PASS: disk correct after the user's save |
| word | dirty | replace | no: PermissionError winerror=5: Access is denied | no | old | old | yes | no | 0 | 0 | user | none | REFUSED: write failed, nothing committed |
| word | dirty | sibling-rename | no: PermissionError winerror=32: The process cannot access the file because it is being used by another process | no | old | old | yes | no | 0 | 0 | user | none | REFUSED: write failed, nothing committed |

## Snapshot through the owner (before the commit)

| app | state | snapshot ok | user edit in snapshot | dirty flag unchanged | name unchanged | snapshot state correct | undo probe restored after redo |
|---|---|---|---|---|---|---|---|
| excel | clean | yes | n/a | yes | yes | yes | no |
| excel | clean | yes | n/a | yes | yes | yes | yes |
| excel | clean | yes | n/a | yes | yes | yes | yes |
| excel | clean | yes | n/a | yes | yes | yes | yes |
| excel | clean | yes | n/a | yes | yes | yes | yes |
| excel | clean | yes | n/a | yes | yes | yes | yes |
| excel | clean | yes | n/a | yes | yes | yes | no |
| excel | clean | yes | n/a | yes | yes | yes | yes |
| excel | dirty | yes | yes | yes | yes | yes | yes |
| excel | dirty | yes | yes | yes | yes | yes | no |
| excel | dirty | yes | yes | yes | yes | yes | yes |
| excel | dirty | yes | yes | yes | yes | yes | no |
| excel | dirty | yes | yes | yes | yes | yes | no |
| excel | dirty | yes | yes | yes | yes | yes | yes |
| word | clean | yes | n/a | yes | yes | yes | yes |
| word | clean | yes | n/a | yes | yes | yes | yes |
| word | clean | yes | n/a | yes | yes | yes | yes |
| word | clean | yes | n/a | yes | yes | yes | yes |
| word | clean | yes | n/a | yes | yes | yes | yes |
| word | clean | yes | n/a | yes | yes | yes | yes |
| word | clean | yes | n/a | yes | yes | yes | yes |
| word | clean | yes | n/a | yes | yes | yes | yes |
| word | dirty | yes | yes | yes | yes | yes | yes |
| word | dirty | yes | yes | yes | yes | yes | yes |
| word | dirty | yes | yes | yes | yes | yes | yes |
| word | dirty | yes | yes | yes | yes | yes | yes |
| word | dirty | yes | yes | yes | yes | yes | yes |
| word | dirty | yes | yes | yes | yes | yes | yes |
| word | dirty | yes | yes | yes | yes | yes | yes |
