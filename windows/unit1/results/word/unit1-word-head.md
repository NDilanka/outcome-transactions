## Word cases: head

Git HEAD 57165d5; working tree open_doc_experiment.py differs from HEAD: True; live_agent sha eb98e94d63c8.

| case | commit outcome | status | reason | seconds | DisplayAlerts after | paragraph 2 after | late outcome | expected | verdict |
|---|---|---|---|---|---|---|---|---|---|
| modal-dialog | raised | None |  | 0.63 | -1 | Total: 1000 | None | refused by the gate as Word busy, nothing written, within 6.5 s | WRONG: the commit raised an unclassified error |
| prompt-no-answer | HUNG: stage 'injected' did not finish within 45 s | None |  | None | None | None | None | unknown outcome, returned within 40 s, the cell left for the user to check | HUNG |
| prompt-answer-8s | raised | None |  | 8.05 | -1 | Total: 1000 | None | refused: the call returned later with nothing landed, within 40 s | WRONG: the commit raised an unclassified error |
| delay-landed-late | returned | None |  | 8.02 | -1 | Total: 5000 | None | refused, the late write rolled back, within 40 s | WRONG |
