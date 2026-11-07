## Preflight-to-replace race

| run | Excel held the file at replace | holders at replace | outcome | replace error | file changed | real B2 | notes kept | verdict |
|---|---|---|---|---|---|---|---|---|
| race-1 | yes | 1 | refused | PermissionError winerror=5: Access is denied | no | 1000.0 | True | REFUSED loudly: replace failed, file unchanged |
| race-2 | yes | 1 | refused | PermissionError winerror=5: Access is denied | no | 1000.0 | True | REFUSED loudly: replace failed, file unchanged |
| race-3 | yes | 1 | refused | PermissionError winerror=5: Access is denied | no | 1000.0 | True | REFUSED loudly: replace failed, file unchanged |
| control | no | 0 | committed | - | yes | 5000.0 | True | CONTROL: committed with no holder |
