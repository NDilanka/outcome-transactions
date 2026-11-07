## Forced-busy commit per run

| case | rep | commit | gate | rejections | read-back after each rejection | disk after commit | disk after user save | verdict |
|---|---|---|---|---|---|---|---|---|
| control | 1 | committed | ok | 0 | - | unchanged | agent edit, user note kept | CORRECT |
| control | 2 | committed | ok | 0 | - | unchanged | agent edit, user note kept | CORRECT |
| control | 3 | committed | ok | 0 | - | unchanged | agent edit, user note kept | CORRECT |
| gate-busy | 1 | refused (Excel busy) | Excel busy after 18 tries | 0 | - | unchanged | prior value, user note kept | CORRECT |
| gate-busy | 2 | refused (Excel busy) | Excel busy after 17 tries | 0 | - | unchanged | prior value, user note kept | CORRECT |
| gate-busy | 3 | refused (Excel busy) | Excel busy after 17 tries | 0 | - | unchanged | prior value, user note kept | CORRECT |
| guard-no-prompt | 1 | committed | ok | 0 | - | unchanged | agent edit, user note kept | CORRECT |
| guard-no-prompt | 2 | committed | ok | 0 | - | unchanged | agent edit, user note kept | CORRECT |
| guard-no-prompt | 3 | committed | ok | 0 | - | unchanged | agent edit, user note kept | CORRECT |
| hang-late-yes | 1 | refused (the B2 value write returned after the timeout, and its value landed) | ok | 0 | - | unchanged | prior value, user note kept | CORRECT |
| hang-late-yes | 2 | refused (the B2 value write returned after the timeout, and its value landed) | ok | 0 | - | unchanged | prior value, user note kept | CORRECT |
| hang-late-yes | 3 | refused (the B2 value write returned after the timeout, and its value landed) | ok | 0 | - | unchanged | prior value, user note kept | CORRECT |
| hang-no-answer | 1 | unknown (Excel did not return from the B2 value write (the call had not returned by the end of the reconcile window; last read unreadable (Excel turned the call away))) | ok | 0 | - | unchanged | prior value, user note kept | CORRECT |
| hang-no-answer | 2 | unknown (Excel did not return from the B2 value write (the call had not returned by the end of the reconcile window; last read unreadable (Excel turned the call away))) | ok | 0 | - | unchanged | prior value, user note kept | CORRECT |
| hang-no-answer | 3 | unknown (Excel did not return from the B2 value write (the call had not returned by the end of the reconcile window; last read unreadable (Excel turned the call away))) | ok | 0 | - | unchanged | prior value, user note kept | CORRECT |
| write-exhausted | 1 | refused (busy: rejected (com_error 0x800AC472), and no read-back of the target was possible within the write budget (Excel turned the call away); the value is unconfirmed) | ok | 1 | unreadable (Excel turned the call away) | unchanged | prior value, user note kept | CORRECT |
| write-exhausted | 2 | unknown (Excel did not return from the B2 value write (the call returned, but the target could not be read back: Excel turned the call away)) | ok | 0 | - | unchanged | prior value, user note kept | WRONG |
| write-exhausted | 3 | refused (busy: rejected (com_error 0x800AC472), and no read-back of the target was possible within the write budget (Excel turned the call away); the value is unconfirmed) | ok | 1 | unreadable (Excel turned the call away) | unchanged | prior value, user note kept | CORRECT |
| write-retry-ok | 1 | committed | ok | 1 | 1000.0 | unchanged | agent edit, user note kept | CORRECT |
| write-retry-ok | 2 | committed | ok | 1 | 1000.0 | unchanged | agent edit, user note kept | CORRECT |
| write-retry-ok | 3 | committed | ok | 1 | 1000.0 | unchanged | agent edit, user note kept | CORRECT |
