## Word probes: which calls hang

Each case: a child process, stage limit 25 s, Word dialogs listed while a call is stuck, Word PIDs killed by PID only.

| case | condition | call | outcome | seconds | Word dialogs while stuck |
|---|---|---|---|---|---|
| baseline | write, file as copied | write Paragraphs(2).Range.Text | returned | 0.54 | - |
| readonly-file | write, file read-only on disk when opened | write Paragraphs(2).Range.Text | returned | 0.58 | - |
| changed-on-disk | write, file replaced on disk after it was opened (mtime moved) | write Paragraphs(2).Range.Text | returned | 0.37 | - |
| protected | write, document protected for reading only | write Paragraphs(2).Range.Text | raised com_error(-2147352567, 'Exception occurred.', (0, 'Microsoft Word', 'You are not allowed to edit this selection because it is protected.', 'wdmain11.chm', 25604 | 0.69 | - |
| save-readonly-target | SaveAs2 onto a read-only file, alerts on (save prompt) | SaveAs2 onto readonly-target.docx | HUNG: no result within 25 s (last stage: call-start) | - | Microsoft Word (#32770): Static: We can’t save this file because it’s read-only.
To keep your changes, you'll need to save the document with a new name or in a different location. (D:\dev\ic-win\...\readonly-target.docx) |
| save-file-in-use | SaveAs2 onto a file a second instance holds open (File In Use) | SaveAs2 onto budget.docx | HUNG: no result within 25 s (last stage: call-start) | - | Microsoft Word (#32770): Static: Word cannot save this file because it is already open elsewhere. (D:\dev\ic-win\windows\...\budget.docx) |
| open-file-in-use | Documents.Open of a file a second instance holds open (File In Use) | Documents.Open of a file another instance holds | HUNG: no result within 25 s (last stage: call-start) | - | File In Use (bosa_sdm_msword):  |
| modal-open-dialog | Word Open dialog up in the instance: readiness reads, then the write | write Paragraphs(2).Range.Text | raised com_error(-2147418111, 'Call was rejected by callee.', None, None) | 0.0 | - |
