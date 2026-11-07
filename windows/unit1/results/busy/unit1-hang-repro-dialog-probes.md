## Hang probe: one COM call with the Open dialog up (no timeout)

| call | outcome | seconds | busy probe before the call |
|---|---|---|---|
| ready | raised: com_error: com_error(-2147418111, 'Call was rejected by callee.', None, None) | 0.34 | busy |
| hwnd | raised: com_error: com_error(-2147418111, 'Call was rejected by callee.', None, None) | 0.04 | busy |
| read-b2 | raised: com_error: com_error(-2147418111, 'Call was rejected by callee.', None, None) | 0.03 | busy |
| saved | raised: com_error: com_error(-2147418111, 'Call was rejected by callee.', None, None) | 0.03 | busy |
| write-b2 | raised: com_error: com_error(-2147418111, 'Call was rejected by callee.', None, None) | 0.01 | busy |
| close-doc | raised: com_error: com_error(-2147418111, 'Call was rejected by callee.', None, None) | 0.01 | busy |
| quit | raised: com_error: com_error(-2147418111, 'Call was rejected by callee.', None, None) | 0.01 | busy |
| gate | returned: {'ok': False, 'reason': 'Excel busy', 'tries': 21, 'seconds': 5.07, 'last_error': 'com_error 0x80010001'} | 5.07 | busy |
| live-commit | returned: {'status': 'refused', 'reason': 'Excel busy', 'done': [], 'rollback': [], 'rejections': 0, 'gate': {'ok': False, 'reason': 'Excel busy', 'tries': 21, 'seconds': | 5.1 | busy |
