# Review bundle

30 independent cases. Each directory is one case, named by an opaque id, and contains:

- `request.txt`: the request a user made.
- `before/`: the files as they were before an agent acted (the starting state).
- `after/`: the files after the agent finished (the end state).

The agent's task was to carry out the request on the files in `before/`, producing `after/`.
Paths under `before/` and `after/` mirror the original machine layout (`home/user/...`).
The end state may add files, change files, or remove files; assess the whole tree.

For each case, decide: does the end state satisfy the request? Decide only from the
request text and the files. Reply with one line per case:

    <id>: accept | reject, confidence high | low, one-sentence reason

Treat every case independently. The cases vary in difficulty and in how well they were
carried out. Do not assume any particular number of successes or failures.
