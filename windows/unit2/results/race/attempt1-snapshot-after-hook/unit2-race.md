## Preflight-to-replace race

| run | Excel held the file at replace | holders at replace | outcome | replace error | file changed | real B2 | notes kept | verdict |
|---|---|---|---|---|---|---|---|---|
| race-1 | yes | 1 | error | - | no | 1000.0 | True | CHECK: outcome error |
| race-2 | yes | 1 | error | - | no | 1000.0 | True | CHECK: outcome error |
| race-3 | yes | 1 | error | - | no | 1000.0 | True | CHECK: outcome error |
| control | no | 0 | committed | - | yes | 5000.0 | True | CONTROL: committed with no holder |
