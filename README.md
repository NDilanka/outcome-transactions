# Outcome Transactions

Research and a working prototype for a new way for AI agents to use computers. The user states an outcome. The engine forks the machine, searches for that outcome in disposable forks while the user keeps working, checks each fork against a frozen, mutation-tested outcome spec, and commits only a verified winner. External effects (emails, HTTP posts) are held and released for the winner only.

Start here:
- `docs/outcome-transactions.md`: the design, what is new versus prior work, the evidence, and each problem found with its fix.
- `prototype/README.md`: a runnable end-to-end prototype on LibreOffice (WSL/Linux), with three scenarios: a normal commit, a concurrent user edit merged by replay, and a true conflict refused.
- `research/`: the experiments behind the design (outcome location, checker expressibility, blind and grounded spec writing on OSWorld tasks, memory divergence and time-warp headroom, prior-art survey).

Not included: the OSWorld clone (`git clone https://github.com/xlang-ai/OSWorld research/OSWorld`) and the downloaded task starting files (`python3 research/exp5-grounded/fetch.py`).
