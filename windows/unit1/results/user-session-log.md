# User Office session log (Windows unit 1)

Entries are dated by the machine clock. Process IDs are recorded; no account name or document name is written here.

- Before 22:44: the user had Word open in a session that the harness did not start. Harness work at that time was Excel only.
- 22:44:30 to 22:48:28: two user Word instances (PIDs 25440 and 1888) ended. No harness action touched Word. Cause unconfirmed at the time.
- 22:49:19: the user reopened the same document in a new Word instance (PID 23508). It was alive at the end of busy matrix attempt 4 (about 22:5x).
- Between attempt 4 and 23:01:32: PID 23508 stopped running. No WINWORD or EXCEL process was running at 23:01:32.
- Orchestrator answer (after the checkpoint): the user closed Word themselves and is not using Word now. The closures are explained. No document check is needed.
- Harness rule in force: the harness starts its own Office instances with DispatchEx, quits only instances it started, kills only by the PID of its own instance, and never kills by image name. Before and after each Word run, the foreign Office processes are compared and named. Any process the harness did not start is left alone.
