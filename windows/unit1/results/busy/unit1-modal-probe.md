## Excel answers with its Open dialog up (measured)

Dialog windows seen: ['#32770']. Closed by the harness: ['#32770']. Helper: exit 0.

| state | call | outcome | seconds |
|---|---|---|---|
| dialog not open | pre-bound Application.Ready | ok True | 0.001 |
| dialog not open | pre-bound Application.Name | ok 'Microsoft Excel' | 0.0 |
| dialog not open | pre-bound Range(B2).Value read | ok 1000.0 | 0.17 |
| dialog not open | pre-bound Range(B2).Value write 1000 (unchanged value) | ok None | 0.026 |
| dialog not open | excel_ready_probe on pre-bound view | ok True | 0.02 |
| dialog not open | wait_busy on pre-bound Application | ok {'busy': False, 'tries': 20, 'last_error': None} | 2.066 |
| dialog not open | fresh GetObject(path).Application | ok <win32com.gen_py.None.Application> | 0.012 |
| Open dialog up | pre-bound Application.Ready | ok False | 0.378 |
| Open dialog up | pre-bound Application.Name | ok 'Microsoft Excel' | 0.503 |
| Open dialog up | pre-bound Range(B2).Value read | ok 1000.0 | 0.159 |
| Open dialog up | pre-bound Range(B2).Value write 1000 (unchanged value) | error com_error 0x800AC472 | 0.018 |
| Open dialog up | excel_ready_probe on pre-bound view | ok False | 0.015 |
| Open dialog up | wait_busy on pre-bound Application | ok {'busy': True, 'tries': 1, 'last_error': 'Application.Rea | 0.002 |
| Open dialog up | fresh GetObject(path).Application | error Excel turned the call away | 0.036 |
| Open dialog up (second round) | pre-bound Application.Ready | ok False | 0.001 |
| Open dialog up (second round) | pre-bound Application.Name | ok 'Microsoft Excel' | 0.004 |
| Open dialog up (second round) | pre-bound Range(B2).Value read | ok 1000.0 | 0.098 |
| Open dialog up (second round) | pre-bound Range(B2).Value write 1000 (unchanged value) | error com_error 0x800AC472 | 0.008 |
| Open dialog up (second round) | excel_ready_probe on pre-bound view | ok False | 0.006 |
| Open dialog up (second round) | wait_busy on pre-bound Application | ok {'busy': True, 'tries': 1, 'last_error': 'Application.Rea | 0.0 |
| Open dialog up (second round) | fresh GetObject(path).Application | error Excel turned the call away | 0.003 |
| dialog closed | pre-bound Application.Ready | ok True | 0.001 |
| dialog closed | pre-bound Application.Name | ok 'Microsoft Excel' | 0.0 |
| dialog closed | pre-bound Range(B2).Value read | ok 1000.0 | 0.005 |
| dialog closed | pre-bound Range(B2).Value write 1000 (unchanged value) | ok None | 0.006 |
| dialog closed | excel_ready_probe on pre-bound view | ok True | 0.005 |
| dialog closed | wait_busy on pre-bound Application | ok {'busy': False, 'tries': 20, 'last_error': None} | 2.027 |
| dialog closed | fresh GetObject(path).Application | ok <win32com.gen_py.None.Application> | 0.002 |
