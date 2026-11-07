## Forced-busy commit per run

| case | rep | commit | gate | rejections | read-back after each rejection | disk after commit | disk after user save | verdict |
|---|---|---|---|---|---|---|---|---|
| control | 1 | committed | ok | 0 | - | unchanged | agent edit, user note kept | CORRECT |
| control | 2 | committed | ok | 0 | - | unchanged | agent edit, user note kept | CORRECT |
| control | 3 | committed | ok | 0 | - | unchanged | agent edit, user note kept | CORRECT |
| gate-busy | 1 | refused (Excel busy) | Excel busy after 20 tries | 0 | - | unchanged | prior value, user note kept | CORRECT |
| gate-busy | 2 | refused (Excel busy) | Excel busy after 16 tries | 0 | - | unchanged | prior value, user note kept | CORRECT |
| gate-busy | 3 | refused (Excel busy) | Excel busy after 20 tries | 0 | - | unchanged | prior value, user note kept | CORRECT |
| guard-no-prompt | 1 | committed | ok | 0 | - | unchanged | agent edit, user note kept | CORRECT |
| guard-no-prompt | 2 | committed | ok | 0 | - | unchanged | agent edit, user note kept | CORRECT |
| guard-no-prompt | 3 | committed | ok | 0 | - | unchanged | agent edit, user note kept | CORRECT |
| hang-late-yes | 1 | refused (the B2 value write returned after the timeout, and its value landed) | ok | 0 | - | unchanged | prior value, user note kept | CORRECT |
| hang-late-yes | 2 | refused (the B2 value write returned after the timeout, and its value landed) | ok | 0 | - | unchanged | prior value, user note kept | CORRECT |
| hang-late-yes | 3 | refused (the B2 value write returned after the timeout, and its value landed) | ok | 0 | - | unchanged | prior value, user note kept | CORRECT |
| hang-no-answer | 1 | unknown (Excel did not return from the B2 value write (the call had not returned after 20 s; last read unreadable (AttributeError (member lookup turned away)))) | ok | 0 | - | unchanged | prior value, user note kept | CORRECT |
| hang-no-answer | 2 | unknown (Excel did not return from the B2 value write (the call had not returned after 20 s; last read unreadable (AttributeError (member lookup turned away)))) | ok | 0 | - | unchanged | prior value, user note kept | CORRECT |
| hang-no-answer | 3 | unknown (Excel did not return from the B2 value write (the call had not returned after 20 s; last read unreadable (AttributeError (member lookup turned away)))) | ok | 0 | - | unchanged | prior value, user note kept | CORRECT |
| write-exhausted | 1 | refused_partial (write error: RuntimeError; rollback of Application.DisplayAlerts set refused: target unreadable before the write: AttributeError (member lookup turned away)) | ok | 0 | - | unchanged | prior value, user note kept | WRONG |
| write-exhausted | 2 | refused_partial (write error: RuntimeError; rollback of Application.DisplayAlerts set refused: target unreadable before the write: AttributeError (member lookup turned away)) | ok | 0 | - | unchanged | prior value, user note kept | WRONG |
| write-exhausted | 3 | unknown (Excel did not return from the B2 value write (the call returned, but the target could not be read back: AttributeError (member lookup turned away))) | ok | 0 | - | unchanged | prior value, user note kept | WRONG |
| write-retry-ok | 1 | refused_partial (write error: RuntimeError; rollback of Application.DisplayAlerts set refused: target unreadable before the write: AttributeError (member lookup turned away)) | ok | 0 | - | unchanged | prior value, user note kept | WRONG |
| write-retry-ok | 2 | refused_partial (write error: RuntimeError; rollback of Application.DisplayAlerts set refused: target unreadable before the write: AttributeError (member lookup turned away)) | ok | 0 | - | unchanged | prior value, user note kept | WRONG |
| write-retry-ok | 3 | refused_partial (write error: RuntimeError; rollback of Application.DisplayAlerts set refused: target unreadable before the write: AttributeError (member lookup turned away)) | ok | 0 | - | unchanged | prior value, user note kept | WRONG |
