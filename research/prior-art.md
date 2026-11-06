# Prior-art search: "outcome transactions"

Date of search: 2026-11-06. Searched: arXiv, ACM DL, USENIX, GitHub, product and vendor sites, and Google Patents (full-text queries through the patents.google.com query endpoint, plus fetches of individual patents).

**This is not legal advice.** It is an engineering survey of what has been published. It is not a freedom-to-operate opinion or a patentability opinion. Patent coverage is weakest here, for two reasons:
- US and EP applications are published about 18 months after filing, so anything that AI labs filed after roughly May 2025 on agent sandboxes or forks is probably still invisible.
- Keyword search on Google Patents produced a lot of noise.

A patent attorney should run a professional search (CPC G06F9/455, G06F11/14, G06F21/53, G06N3/006) before any filing decision.

Verdict scale:
- **anticipated**: the core idea has already been published or built.
- **partially anticipated**: the main idea exists, but our specifics differ.
- **no close prior art found**: nothing close turned up in this search.

---

## Summary table

| Claim | Verdict | Closest prior art |
|---|---|---|
| C1 Fork live desktop, run CUA in forks, commit only the winner | **Anticipated** (core idea) | TClone (arXiv 2605.17320, May 2026); Gensee transactional runtime; Microsoft US8677355B2; BranchFS "Fork, Explore, Commit" (arXiv 2602.08199) |
| C2 Effect firewall (hold writes, serve recorded reads, release winner's effects) | **Partially anticipated** | Speculator / Rethink the Sync (output buffering until commit); Remus; TClone §4.4/4.6 ("delayed release of external actions"); Gensee GUI/network blog; Mahimahi record-replay; ACRFence; transactional-outbox agent papers |
| C3 World read-set validation (OCC on the external world), volatile-value rebinding | **Partially anticipated** | "Authority at Commit Time" (arXiv 2609.31490); "Tracking State Footprints" (arXiv 2610.03140); CoAgent (arXiv 2606.15376); LoadRunner/JMeter "correlation" for token rebinding |
| C4 Virtual-time warp for GUI workloads (advance clock when all threads are blocked on timers; I/O as an event) | **Anticipated** (mechanism); applying it to CUA search forks is new | QEMU `-icount sleep=off`; Chrome DevTools `Emulation.setVirtualTimePolicy` (`advance`, `pauseIfNetworkFetchesPending`); Antithesis fast-forward; Meta Hermit; Palo Alto US11036859B2/US9542554B1; IAI WO2014147618A1; Gupta et al. NSDI'06; TimeKeeper |
| C5 Sub-page compressed deltas, content-addressed sibling sharing, discarding guest-freed pages | **Anticipated** (each part); the combination for fork trees has only thin specific prior art | Difference Engine (OSDI'08: sub-page patching against reference pages, compression, whole-page sharing); KSM; Potemkin delta virtualization; virtio-balloon free page reporting/hinting; SnowFlock |
| C6 Commit by semantic action replay plus outcome verification; fall back to result transplant | **Partially anticipated** | Speculative Actions (arXiv 2510.04371, commit-when-match); ReTrace / "Lost in Recovery" (arXiv 2610.27954); TClone commit/merge; BranchFS commit; Codex cloud "apply diff"; "Tracking State Footprints" (semantic, not deterministic, re-execution); RPA replay |
| C7 Verification: before/after diff + footprint (frame condition), frozen spec, mutation-tested spec in forks, cross-fork agreement, user disambiguation | **Partially anticipated** (each element); **no close prior art found** for the integrated combination, especially mutation-testing the spec in disposable forks of a live machine | Agent-Diff (state-diff contracts); SABench "collateral damage" (arXiv 2610.34167); LegacyWorld atomicity; VeriEvolve (frozen evaluator, counterfactual test states); "Fuzzing RLVR Verifiers" (arXiv 2606.01066); IRA; Agent S3/BJudge best-of-N; Codex best-of-N picker |
| C8 Speculative pre-solving of likely next requests in forks during idle time | **Partially anticipated** | Letta sleep-time compute (arXiv 2504.13171); ProAct "Anticipate and Learn" (arXiv 2605.25971); Speculative Actions; browser prerender; Menlo Security US12107867B1 |

---

## C1. Forked live desktop/VM for end-user computer-use tasks, committing only the verified result

**Closest prior art**
1. **TClone: Low-Latency Forking of Live GUI Environments for Computer-Use Agents** (Huang, Srivatsa, Asch, ..., Yiying Zhang; arXiv 2605.17320, 17 May 2026). https://arxiv.org/abs/2605.17320 . A "forkable personal workspace" for CUAs. A live GUI workspace (processes, memory, filesystem, compositor/GUI, network namespace) is snapshotted, forked into isolated branches, rolled back, and "selectively committed or merged". Commit "makes selected speculative state visible to the human workspace, either by promoting one chosen container or by merging selected state". The paper explicitly targets "speculative execution and parallel search" and best-of-N or beam selection, and it can "require approval before sensitive state is committed".
2. **Gensee transactional runtime** (same group; product plus blog series, 2026). https://www.gensee.ai/blogs/forking-live-agent-workspaces-choosing-system-boundary.html . "Fork a live agent workspace into isolated branches, inspect the outcomes, promote selected work, discard or roll back the rest." The blog explicitly mentions computer-use agents "exploring multiple action paths".
3. **Microsoft US8677355B2, "Virtual machine branching and parallel execution"** (priority 2010-12-17; also EP2652600A2, WO2012082811A2, KR101957533B1). https://patents.google.com/patent/US8677355B2/en . The hypervisor clones a running VM at a branch with an unknown outcome. Clones explore the paths in parallel, and a coordinator decides which copies continue, "discarding unneeded branches or merging branch results". Claim 4 covers "determining whether the cloned virtual machine will affect any resources outside of the original virtual machine". It does not involve AI agents or end-user tasks.
4. **Fork, Explore, Commit: OS Primitives for Agentic Exploration** (Wang and Zheng; arXiv 2602.08199, Feb 2026; BranchFS open source). https://arxiv.org/abs/2602.08199 . Copy-on-write branch contexts for agents, with fork, explore, and commit/abort, "first-commit-wins", and sibling invalidation. It covers the filesystem and processes, not GUI.
5. Commodity fork-of-a-running-sandbox products: E2B `sandbox.fork()` (https://docs.e2b.dev/sandbox/fork), Freestyle/Morph "best-of-N, keep the winner" (https://www.morphllm.com/fork-vm-for-ai-agents), CreateOS fork (https://createos.sh/blogs/createos-sandbox-fork-agent-state), Mitos (https://mitos.run/), forkd/sandstorm (https://github.com/deeplethe/forkd). These are cloud sandboxes and do not commit back to a user's real machine.
6. Parallel CUA rollouts in VMs, with a judge selecting among them: Agent S3 / Behavior Judge (arXiv 2510.02250); RAG-PJ parallel warm rollouts from a restored checkpoint (arXiv 2611.04073).
7. Context: SnowFlock VM fork (EuroSys'09); Qubes disposable VMs; Windows Agent Workspace (a separate desktop, not a fork); Claude Cowork (a local VM with mounted folders, not a fork).

**Same:** TClone covers the full core idea: fork a live personal GUI workspace, run CUA branches, discard the losers, and promote or commit the selected branch to the user's workspace, with an approval gate.

**Different:** TClone is container-based on Linux (sibling containers, CRIU-like reconstruction), not a VM or whole-OS fork; Windows/macOS desktops are not covered. The "outcome specification" that gates the commit, and the claim that only a *verified* result is committed, are not TClone's focus: selection is left to policy, the user, or best-of-N. The user-stated outcome as the transaction's contract (the "outcome transaction" framing) is not the paper's framing.

**Verdict: anticipated** for the generic claim. Novelty would have to come from the dependent features (C2, C3, C7). TClone and Gensee are the single most threatening prior art. Note that TClone's authors have a company and may have filed patents that are not yet published.

---

## C2. Effect firewall: hold back external side effects, serve recorded reads, release only the winner's effects at commit

**Closest prior art**
1. **Speculator** (Nightingale, Chen, Flinn; SOSP'05) and **Rethink the Sync / external synchrony** (OSDI'06). https://www.usenix.org/legacy/event/osdi06/tech/nightingale/nightingale.pdf . "Any external output from a process that is uncommitted is buffered within the kernel until the modifications on which the output depends have been committed." This is the classic form of "hold output until commit". It also covers dependency tracking across processes.
2. **Remus** (NSDI'08). Buffers VM network output until the checkpoint commits. https://www.usenix.org/legacyurl/remus-high-availability-asynchronous-virtual-machine-replication
3. **Potemkin honeyfarm** (SOSP'05). Containment of outbound traffic from flash-cloned VMs, including reflection of outbound traffic to other honeypot VMs. https://cseweb.ucsd.edu/~mvrable/papers/2005-sosp-potemkin.pdf
4. **TClone** §2.2, §4.4, §4.6: "each branch may attempt external actions such as sending messages, submitting forms ... safe parallel search requires isolation, rollback, external side-effect mediation ... and explicit commit"; "speculative branches can run with restricted networking, **delayed release of external actions**, or explicit approval before effects are committed." TClone closes external connections at fork time. It names delayed release as a policy option but does not appear to describe a full mechanism for it.
5. **Gensee "Forking GUI and Network State"** blog: external effects (email, payment, deployment, push) are "Block, allowlist, defer, or require approval". https://www.gensee.ai/blogs/forking-live-agent-workspaces-gui-network-boundaries.html
6. Recorded reads served to replicas: **Mahimahi** record-and-replay for HTTP (USENIX ATC'15) https://www.usenix.org/conference/atc15/technical-session/presentation/netravali ; VCR-style HTTP cassettes in testing; "Replay with egress blocked" (https://dev.to/dekita/replay-with-egress-blocked-or-it-is-not-a-replay-5edn).
7. Agent effect logs and outboxes: **ACRFence** (arXiv 2603.20625) records irreversible tool effects and enforces "replay-or-fork" semantics on restore; **forked** (https://github.com/clibequilibrium/forked) keeps an effect log for "effectively-once" emails and payments across forks and rewinds; "Authority at Commit Time" (transactional outbox, arXiv 2609.31490); agent shadow or dry-run modes.
8. Microsoft US8677355B2 claim 4 (checks whether a clone will affect external resources).

**Same:** Buffering external output until commit is decades old in OS work (Speculator, Remus). Applying the idea to forked CUA branches is stated in TClone. Record-and-replay of HTTP reads is standard.

**Different, and possibly novel:** We could not find a system that does all of the following together:
- (a) intercepts all external writes from *each of N sibling forks* of a desktop at the VM or network boundary, including payments, email, and printing;
- (b) serves the forks a shared recorded read cache, so that the forks observe a consistent external world;
- (c) at commit, releases only the winning fork's effect log, in order, against the live world.

TClone mentions "delayed release" in a single sentence. Speculator handles one speculative process tree, not competing siblings, and does not record reads for replay.

**Verdict: partially anticipated.** A claim limited to the specific mechanism (recorded reads plus per-fork effect queues plus winner-only release plus dependency on C3 validation) appears to be the defensible part. Expect examiners to combine Speculator or Remus with TClone.

---

## C3. Validating the fork's world read-set before commit (OCC on the external world); rebinding volatile values at commit

**Closest prior art**
1. **Authority at Commit Time: Reject-and-Rerun Semantics for Governed Agentic Systems** (Salas; arXiv 2609.31490, Sep 2026). https://arxiv.org/html/2609.31490v1 . Agents compute "from a snapshot of policy, facts, task state ..."; at admission the service "compares a proposal's declared dependencies ... with current state, applies the current verifier", and then either reserves an idempotent effect for outbox dispatch or rejects for rerun. The paper explicitly composes "optimistic concurrency control, semantic verification, and transactional outbox dispatch". This is very close to C3's core.
2. **Tracking State Footprints: How Agents Can Transact** (Mraz et al., TU Delft; arXiv 2610.03140, Oct 2026). https://arxiv.org/abs/2610.03140 . Footprints of state that agents read and write "across ... the orchestrator and external systems"; notes that agents "cannot be replayed deterministically" but "can resolve conflicts semantically". This is a vision paper.
3. **CoAgent / MTPO** (arXiv 2606.15376). OCC and read-set ideas for multi-agent tools; footprint-declared tools.
4. Agent-interface GitHub project issue "automatic read-set reconstruction and optimistic validation" (https://github.com/Unjuno/agent-interface/issues/1713). Informal prior art.
5. Kung and Robinson OCC (1981) in general.
6. Rebinding volatile values: **LoadRunner / JMeter "correlation"** re-extracts session IDs, CSRF tokens, and OAuth tokens at replay time instead of reusing the recorded values (https://perf-test.com/tutorials/loadrunner/correlation-techniques/). Test-automation OTP handling is similar. ACRFence discusses re-synthesized requests after restore.

**Same:** "Validate the external facts the work depended on, at commit time, then commit or rerun" is published for agent proposals (2609.31490). Rebinding volatile tokens during replay is standard practice in load testing.

**Different:** The prior art validates *declared* dependencies on a governed authority service (policy, facts, models). Our version would *automatically derive* the read-set from a fork's recorded network reads and GUI observations (through the C2 recorded-read cache) and re-validate it against the live web or desktop. Rebinding OTPs and CSRF tokens inside a semantic replay of GUI actions at commit was not found as such.

**Verdict: partially anticipated.** Automatically deriving the world read-set from the fork's network/GUI recording, then validating it, may be novel, but this is a thin margin.

---

## C4. Virtual-time warping for GUI workloads

**Closest prior art**
1. **QEMU `-icount shift=...,sleep=off`**. When all vCPUs are idle, the virtual clock warps to the next timer deadline instead of sleeping in real time (patch "icount: implement a new icount_sleep mode", Victor Clément, 2015; https://qemu-devel.nongnu.narkive.com/3EpJ9i2W/ ; QEMU manpage https://www.qemu.org/docs/master/system/qemu-manpage.html). This is whole-machine discrete-event time advance when the guest is idle, which is what C4 describes.
2. **Chrome DevTools `Emulation.setVirtualTimePolicy`** (https://chromedevtools.github.io/devtools-protocol/tot/Emulation/). With `advance`, "if the scheduler runs out of immediate work, the virtual time base may fast forward to allow the next delayed task to run". With `pauseIfNetworkFetchesPending`, virtual time does not advance while fetches are in flight. This is the same idea applied to a GUI (browser) workload, and it treats in-flight network I/O as a blocking event.
3. **Antithesis**: "The Antithesis simulation can 'fast-forward' through periods of time when the system is idle" (https://antithesis.com/docs/configuration/the_antithesis_environment/), on a deterministic hypervisor.
4. **Meta Hermit / Detcore**: deterministic virtual clock in which timers and sleeps count down on virtual time (https://github.com/rrnewton/hermit).
5. Malware sandboxes: **Palo Alto US11036859B2 / US9542554B1** (guest time advanced faster than host time to trigger time-delayed behaviour); **Israel Aerospace Industries WO2014147618A1** ("Accelerating a clock system to identify malware").
6. Time dilation: Gupta et al. "To Infinity and Beyond: Time-Warped Network Emulation" (NSDI'06); TimeKeeper (PADS'14); libfaketime; fake timers in JS test frameworks.

**Same:** "Advance the clock to the next timer when everything is blocked" is anticipated at the hypervisor level (QEMU icount), in browsers (Chrome virtual time), and in testing (Antithesis). Chrome's policy already treats in-flight fetches as something that gates time advance.

**Different:** We found no system that applies virtual-time warp to full desktop *GUI* apps inside *CUA search forks* in order to run outcome searches faster than real time, with I/O completion modelled explicitly as a discrete event (as opposed to "pause time while I/O is pending").

**Verdict: anticipated** for the mechanism. At best, the narrow claim "I/O completion as a scheduled event in a desktop VM used for agent search" is partially anticipated. Do not rely on C4 for novelty.

---

## C5. Copy-on-write forks with sub-page compressed deltas, content-addressed sibling sharing, discarding guest-freed pages

**Closest prior art**
1. **Difference Engine** (Gupta et al., OSDI'08). https://www.usenix.org/legacy/event/osdi08/tech/full_papers/gupta/gupta.pdf . Combines whole-page sharing (content hashing), **sub-page sharing via patching** (storing a page as a compressed delta against a similar reference page), and compression of infrequently used pages. This directly anticipates "byte-level compressed deltas against a base page".
2. **KSM** (Linux) and VMware transparent page sharing: content-based (hash) merging of identical pages across VMs, which means across sibling forks.
3. **Potemkin** delta virtualization (SOSP'05): CoW flash clones of a reference image. **SnowFlock** (EuroSys'09): VM fork with lazy state propagation.
4. Free-page handling: virtio-balloon **free page reporting** and **free page hinting** (used by QEMU live migration to skip free pages); Firecracker ballooning docs (https://github.com/firecracker-microvm/firecracker/blob/main/docs/ballooning.md); flexvm issue on holding free page reports during CoW checkpoints (https://github.com/kevmo314/flexvm/issues/53).
5. Delta compression for VM migration and snapshots (e.g., "Evaluation of Delta Compression Techniques for Efficient Live Migration", VEE'11 era; XBZRLE in QEMU, which XOR-encodes pages against the previous version of the same page). XBZRLE is close to "delta against the base page".
6. TClone's CoW-aware page cache for file-backed pages across branches.

**Same:** Each element exists. Difference Engine plus XBZRLE plus KSM plus free page reporting covers essentially all of C5.

**Different:** Combining them as the storage format for a *tree of short-lived forks* (each fork stores per-page XOR/compressed deltas against its parent's base page, siblings share identical post-write pages by content address, and guest-freed pages are dropped from fork deltas) was not found as a single published design. That combination would be weak as a patent ground because the combination is obvious.

**Verdict: anticipated** (elementwise). At most an engineering contribution.

---

## C6. Commit by semantic action replay with outcome verification; fall back to result transplant

**Closest prior art**
1. **Speculative Actions** (Ye et al.; arXiv 2510.04371). Speculatively executes predicted agent actions and commits "only when predictions match". This is verification-gated commit of speculative agent work, but it operates on API calls, not on replay onto a different machine state.
2. **Lost in Recovery / ReTrace** (arXiv 2610.27954). "Replaying downstream actions to test whether recovered states preserve outcomes": replay of CUA actions on a different state, checked against the outcome.
3. **Tracking State Footprints** (arXiv 2610.03140): agents cannot be replayed deterministically but can resolve conflicts semantically.
4. **Agentic Transaction: Towards ACID-Compliant Agent Systems** (arXiv 2608.13900): "semantics constrain committed effects rather than requiring deterministic execution traces"; exploration-execution-validation cycles.
5. Simular "Neuro-Symbolic Computer Use" (arXiv 2609.36927): reusable symbolic policies replayed on new starting states, with fallback to the neural agent. RPA replay of recorded scripts (e.g., Microsoft US12014192B2, Accenture EP4206903A1).
6. Result transplant: TClone commit by promoting a container or by "file-level merge mechanisms"; BranchFS atomic commit of the CoW delta to the parent; Codex cloud and similar coding agents producing a diff the user applies locally; Gensee "promote selected work".

**Same:** Both halves exist separately. Re-executing agent actions against a new state and checking the outcome exists (ReTrace, Speculative Actions). Committing by copying changed state (promote or merge) exists (TClone, BranchFS).

**Different:** We found no system that, at commit time, (i) replays the winning fork's GUI action trace semantically against the *live, possibly changed* real desktop, (ii) re-verifies the frozen outcome spec on the real machine, and (iii) falls back to transplanting changed result objects (files, app documents) when replay fails verification.

**Verdict: partially anticipated.** The specific two-tier commit protocol is the novel part, if anything is.

---

## C7. Outcome verification: diffs plus footprint (frame condition), frozen spec, mutation-tested spec, cross-fork agreement, user disambiguation

**Closest prior art, by element**
- *Before/after state diffs:* **Agent-Diff** (arXiv 2602.11224), with state-diff contracts for evaluation; OSWorld checkers; **Interactive Reward Agent** (arXiv 2607.25904), which inspects post-execution environment state; OpenComputer app-state verifiers (arXiv 2605.19769); Microsoft Universal Verifier (arXiv 2604.06240).
- *Footprint / frame condition (nothing outside the allowed footprint changed):* **SABench "collateral damage"** (arXiv 2610.34167), with trace-based oracles for unauthorized writes; **LegacyWorld** atomicity-aware evaluation (arXiv 2608.14131), where an independent validator checks for persistent unintended changes; OS-Harm and OSGuard; frame conditions are classic in formal methods (JML `assignable`, Dafny `modifies`). TClone records per-app syscall and file footprints for security profiles.
- *Spec frozen before search:* **VeriEvolve** (arXiv 2610.29005): "During each round ... the evaluator is frozen and serves as the fitness signal". It synthesizes challenge states and converts strong and weak end states into counterfactual test cases.
- *Mutation-testing the spec:* specification mutation (NIST thesis); **"Before the Model Learns the Bug: Fuzzing RLVR Verifiers"** (arXiv 2606.01066) probes verifiers for false positives; LLM mutation testing (Meta ACH). VeriEvolve's counterfactual states are closely related.
- *Agreement across independent forks:* best-of-N with a judge (Agent S3 / BJudge, arXiv 2510.02250); self-consistency voting.
- *Disambiguation by showing competing results:* Codex and Cursor best-of-N UIs where the user picks among versions; "Interactive Agents to Overcome Ambiguity" (arXiv 2502.13069).

**Different:** We found no work that, *before search*, freezes an outcome spec with an explicit desktop footprint, and then validates the spec by *driving disposable forks of the real machine into deliberately wrong outcomes* to confirm that the spec rejects them. Combining this with cross-fork agreement and outcome-level disambiguation (showing the user competing end states rather than trajectories) was not found either.

**Verdict: partially anticipated** for each element. **No close prior art found** for mutation-testing an outcome spec by executing wrong outcomes in forks of a live machine, and for the integrated pipeline. This is probably the strongest novelty candidate, together with C2 and C3 combined.

---

## C8. Speculative pre-solving of likely next user requests in forks during idle time

**Closest prior art**
1. **Sleep-time Compute** (Letta / UC Berkeley; arXiv 2504.13171): pre-compute answers to anticipated queries during idle time.
2. **ProAct, "Anticipate and Learn: Unleashing Idle-Time Compute in Proactive Agents"** (arXiv 2605.25971).
3. **Speculative Actions** (arXiv 2510.04371): predict and pre-execute likely next actions. PASTE (arXiv 2603.18897); cost-aware speculative agent workflows (arXiv 2606.07846).
4. Browser prefetch and prerender; **Menlo Security US12107867B1** "Speculative rendering" (predictive rendering in an isolated browser in response to user input); Autodesk US9009734B2 "Application level speculative processing" (speculatively executing likely event responses).
5. Speculator-style speculation in general.

**Different:** We found nothing that pre-solves predicted *whole user tasks* in *forks of the user's live desktop* during idle time and keeps the forks ready, so that commit (with C3 validation) happens instantly when the user actually asks.

**Verdict: partially anticipated.** The idea of idle-time anticipation is well covered; the fork-of-live-desktop vehicle is the only new part.

---

## Relevant patents (numbers checked on Google Patents unless noted)

| Number | Title | Assignee | Priority | Relevance |
|---|---|---|---|---|
| US8677355B2 (EP2652600A2, WO2012082811A2, KR101957533B1) | Virtual machine branching and parallel execution | Microsoft | 2010-12-17 | C1 (clone running VM at branch, explore in parallel, coordinate/discard/merge results); claim 4 touches C2 (external resource effects). Active per Google Patents. |
| US8151263B1 | Real time cloning of a virtual machine | VMware | 2007 | C1/C5 (live clone while the source runs) |
| US9619268B2 | Rapid suspend/resume for virtual machines via resource sharing | VMware | 2014 | C5 (forked VM virtual desktops sharing memory state) |
| US9626212B2 | Live migration of virtual machines with memory state sharing | VMware | 2014 | C5 |
| US8464250B1 | On-demand cloning of virtual machines | (not checked) | — | C1 background |
| US11036859B2 | Collecting algorithmically generated domains (accelerated guest clock) | Palo Alto Networks | 2014-12-18 | C4 |
| US9542554B1 | Deduplicating malware (guest clock manipulation in VM instances) | Palo Alto Networks | 2014-12-18 | C4 |
| WO2014147618A1 | Accelerating a clock system to identify malware | Israel Aerospace Industries | 2013-03-20 | C4 |
| US12107867B1 | Speculative rendering | Menlo Security | 2020 | C8 (and C2-like isolation) |
| US9009734B2 | Application level speculative processing | Autodesk | 2012 | C8 (speculatively executing likely event responses) |
| US12014192B2 | Crawler of web automation scripts | Microsoft | 2020 | C6 (learned UI action scripts) |
| EP4206903A1 | Intelligent automation of UI interactions | Accenture | 2021 | C6 (RPA replay) |
| US12405822B1 | Multi-agent interactions using a shared workspace | OpenAI | 2024 | Tangential (agent workspaces) |
| EP4657314A1 | Dynamic agents with real-time alignment | Microsoft | 2024 | Tangential; found in agent searches, not about forks |
| FireEye US8689333B2 / US9912684B1 | VM-based malware analysis replaying network traffic in VMs | FireEye | 2004 | C2 (replaying captured traffic into isolated VMs) |

**Patent gaps:** We found no published patent or application that claims C1 with AI agents on the user's desktop, nor any for C2, C3, or C7 in the agent context. This is weak evidence of absence, because of the 18-month publication lag and because Google Patents full-text search was noisy. Filings by TClone/Gensee (UCSD, Yiying Zhang), E2B, Antithesis, Simular, Microsoft (Windows Agent Workspace / Copilot Actions), OpenAI (Operator/Codex), and Anthropic (Cowork, computer use) may exist but not yet be public. Re-search in 6 to 12 months.

---

## Uncertainty and caveats

- Many of the 2026 arXiv items (TClone, Authority at Commit Time, Tracking State Footprints, VeriEvolve, SABench, LegacyWorld, ReTrace) were read only at the abstract level plus key passages. Their full texts may contain more (or less) overlap.
- TClone's text about delayed release of external effects is a sentence-level policy statement. Whether it is implemented was not confirmed.
- XBZRLE, the VEE delta-compression paper, and US8464250B1's assignee are cited from domain knowledge and were not fetched in this session.
- Combination claims (e.g., C1 + C2 + C3 + C7 together) are where novelty most plausibly lies. Obviousness over TClone + Speculator + Authority-at-Commit-Time is the main risk.
