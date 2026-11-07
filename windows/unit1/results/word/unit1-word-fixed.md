## Word cases: fixed

Git HEAD 57165d5; working tree open_doc_experiment.py differs from HEAD: True; live_agent sha 4c81817c4b74.

| case | commit outcome | status | reason | seconds | DisplayAlerts after | paragraph 2 after | late outcome | expected | verdict |
|---|---|---|---|---|---|---|---|---|---|
| modal-dialog | returned | refused | Word busy | 5.0 | -1 | Total: 1000 | None | refused by the gate as Word busy, nothing written, within 6.5 s | CORRECT |
| prompt-no-answer | returned | unknown | Word did not return from the total line value write (the call had not returned by the end of the reconcile window; last read unreadable (the application turned the call away)) | 25.08 | -1 | Total: 1000 | unchanged | unknown outcome, returned within 40 s, the cell left for the user to check | CORRECT |
| prompt-answer-8s | returned | refused | Word did not answer the total line value write within 5 s, and the call returned later with nothing landed | 8.28 | -1 | Total: 1000 | None | refused: the call returned later with nothing landed, within 40 s | CORRECT |
| delay-landed-late | returned | refused | the total line value write returned after the timeout, and its value landed | 8.37 | -1 | Total: 1000 | None | refused, the late write rolled back, within 40 s | CORRECT |
