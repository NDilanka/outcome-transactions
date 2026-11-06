# Universal Interface Compiler: Research Design

Status: draft v0.1, 2026-11-06. **Superseded** by `docs/outcome-transactions.md` (the project moved from compiling interfaces to outcome transactions).

## 1. Thesis

Graphical interfaces are built for humans. An agent that drives them by looking at screens and clicking re-derives, on every run, knowledge that does not change between runs: where controls live, how screens connect, what each control does.

That knowledge can be extracted once per application and compiled into a typed, callable interface. After compilation, every action a user can perform in the application becomes one function call that executes with zero runtime reasoning and returns a verified result.

The goal is this property for any application on any operating system.

## 2. Definitions

These definitions are the contract. Every metric in section 8 is measured against them.

- **Action.** A user-level operation in an application, such as "set cell B2 to 5", "send message to X", or "export as PDF". Not a click.
- **Compiled action.** A typed function `f(args) -> Result` backed by a deterministic execution plan.
- **Zero-step.** Executing a compiled action makes zero model calls inside the system. No looking, no planning, no grounding by a neural model. The system may still send input events. The caller (a human or an agent) decides which function to call; that decision is outside the system.
- **Verified.** The result includes evidence that the intended state change happened: a changed accessibility value, a server response, a file on disk, or a structured read-back. An action without verification does not count as compiled.
- **Reach.** The system can perform the action by some means, including the pixel-and-input floor.
- **Compiled coverage.** The share of an application's actions that are compiled, zero-step, and verified.
- **100%.** Compiled coverage of 100% of the actions in a defined action inventory for an application version, excluding actions blocked by policy (section 7.6), which are counted and reported separately.

## 3. Prior work and the gap

### 3.1 Research

| Work | What it does | Scope | Runtime reasoning | Limits relevant here |
|---|---|---|---|---|
| DMI (EuroSys 2026, arXiv 2510.04607) | Models app navigation from UI Automation into a navigation graph; exposes declarative `visit` and state primitives | Windows, Office | Agent still plans; 61% of successes in one LLM call | ~1.5 person-days manual setup per app; misses conditional UI changes; no canvas or precise positioning; legacy and game UIs lack UIA; web too dynamic |
| ActionEngine (arXiv 2602.20502) | Crawler builds a state-machine graph of an app; planner writes a full program in one call; patcher repairs failures | Web (WebArena) | One planning call per task | Crawler coverage incomplete; fails when the plan depends on data seen only at runtime (search results) |
| Neuro-Symbolic Computer Use (Simular, arXiv 2609.36927) | Learns a code policy per recurring workflow by iterating from one trajectory; pre-action verifier | Desktop (OSWorld), Mac and Windows | Neural grounding and state checks at runtime | Per workflow, not per app; judges miss failures that are invisible on screen |
| AutoRPA (ICML 2026, arXiv 2605.21082) | Distills ReAct agent runs into RPA functions with hybrid repair | Several GUI environments | Low; ReAct fallback | Per task family |
| TraceCompiler (arXiv 2608.02680) | Mines agent traces into mostly deterministic workflows; refuses to compile under-determined irreversible effects | API tools | Residual LLM decisions marked explicitly | Not GUI; needs existing traces |
| Hybrid Computer Use (arXiv 2610.41432) | One interface over code, accessibility, and GUI channels; AX diffs as feedback | Linux, macOS, Windows | Full agent loop | Interface for agents, not a compiler |
| LUMOS (arXiv 2606.30697) | OS layer that turns accessibility data into stable semantic blueprints | Desktop and browser | Full agent loop | Observation layer only |
| APISensor (arXiv 2603.23852) | Discovers undocumented web APIs from runtime traffic | Web | n/a | Network layer only |

### 3.2 Products

| Product | Approach | Scope |
|---|---|---|
| Simular (Sai, Simular API) | Neuro-symbolic: successful trajectories become deterministic code | macOS, Windows |
| Stagehand caching (Browserbase) | Caches resolved selectors per action, replays without LLM calls | Browser |
| Workflow Use (Browser Use) | Record once, replay deterministic workflows with self-healing | Browser |
| Skyvern | Generates Playwright code from agent runs; later runs use no LLM | Browser |
| UiPath Healing Agent | LLM repairs broken selectors in recorded RPA | Desktop and web, enterprise |
| Orby, Caddi | Learn workflows from demonstrations; Caddi targets API calls | Vertical enterprise |
| Muscle Mem (pig.dev, later Butter) | Behavior cache for agent tool calls | SDK; author reported strong interest but few users |
| Integuru, reverse-api-engineer | Generate API clients from captured browser traffic | Web |

### 3.3 The gap

Everything above compiles one of two things: a **single workflow** (a recorded trajectory) or a **single channel** (web selectors, web traffic, or accessibility on one OS). Nothing compiles **a whole application** into a complete, typed action surface:

1. across every access channel (network, app scripting, accessibility, pixels), choosing the most direct one per action,
2. on every operating system, through one artifact format,
3. with zero model calls at runtime, including grounding,
4. with coverage measured against an explicit action inventory.

Points 3 and 4 are the research contribution. No published system reports compiled coverage as a number.

## 4. Research questions

- **RQ1. Inventory.** Can the full action inventory of an unknown application be discovered automatically, and how do we know it is complete?
- **RQ2. Compilation.** For each action, can a deterministic plan with no runtime model calls be synthesized and verified, including actions on canvases and actions whose outcome depends on runtime data?
- **RQ3. Channel lifting.** How often can a GUI-discovered action be lifted to a more direct channel (app scripting, network API, file format), and how much faster and more reliable does that make it?
- **RQ4. Portability.** Can one intermediate representation describe applications on Windows, macOS, Linux, Android, iOS, and the web?
- **RQ5. Maintenance.** When an application updates, what fraction of compiled actions break, and what fraction repair automatically?
- **RQ6. Safety.** Can irreversible actions be explored and verified safely?

## 5. Architecture

```
caller (agent or program)
        |  MCP / typed SDK
        v
+---------------------------------------------------+
| Runtime: executes compiled plans, verifies,       |
|          zero model calls on the hot path         |
+---------------------------------------------------+
| Interface Manifest (per app + version)            |
|   actions, types, plans, verifiers, channel used  |
+---------------------------------------------------+
| Compiler: explore -> inventory -> synthesize ->   |
|           lift -> verify -> publish               |
+---------------------------------------------------+
| Channel adapters (one per OS)                     |
|   network | app scripting | accessibility | pixels |
+---------------------------------------------------+
| Sandbox: VM/container with snapshots              |
+---------------------------------------------------+
```

### 5.1 Channel adapters

Each adapter exposes the same abstract operations: `observe`, `locate`, `act`, `read_back`, `diff`.

| Channel | Windows | macOS | Linux | Android | iOS | Web / Electron |
|---|---|---|---|---|---|---|
| Network | proxy + HAR capture | same | same | same (user CA in emulator) | same (simulator) | CDP network domain |
| App scripting | COM, PowerShell, CLI | AppleScript, JXA, Shortcuts | D-Bus, CLI | Intents, ADB | URL schemes, App Intents | page JS, extension APIs |
| Accessibility | UI Automation | AX API | AT-SPI2 | AccessibilityService | XCUITest | DOM + accessibility tree |
| Pixels + input | screen capture + SendInput | ScreenCaptureKit + CGEvent | X11/Wayland portals | screencap + input | simulator | screenshot + CDP input |
| Files | document formats | same | same | app storage | n/a | downloads |

The pixel channel exists on every platform, including VMs and remote desktops. It guarantees reach. The other channels exist to make compiled actions faster and more robust.

### 5.2 Compiler pipeline

1. **Explore.** A crawling agent drives the app inside a snapshotted sandbox. It records a state graph: states (screens, dialogs, modes), controls per state, transitions, and the observations from every channel at each step (accessibility tree, network traffic, file changes, screenshots).
2. **Inventory.** Cluster transitions into user-level actions. Cross-check the inventory against independent sources: menus and command palettes, keyboard shortcut tables, scripting dictionaries (AppleScript `sdef`, COM type libraries), help documentation, and observed network endpoints. Disagreement between sources flags missing actions (RQ1).
3. **Synthesize.** For each action, generate a parameterized plan from primitives: `navigate(state)`, `invoke(control)`, `set(control, value)`, `read(control)`, `wait_for(condition)`, `branch(condition)`, `pointer_path(points)`. Grounding is resolved at compile time into stable locators with ordered fallbacks (automation ID, role+name path, relative structure, image template). No neural grounding at runtime.
4. **Lift.** Try to replace the plan with a more direct route: a scripting call, a network request replayed with session state, or a file-format edit. Accept the lift only if verification shows the same end state as the GUI plan.
5. **Verify.** Run each action on generated parameter and initial-state variants inside the sandbox. Compare the end state with the expected effect through an independent read-back channel. Restore the snapshot after each run.
6. **Publish.** Emit the Interface Manifest and serve it as an MCP server.

### 5.3 Interface Manifest

A versioned, OS-neutral description of an application:

```yaml
app: { id: com.example.app, version: "12.4.1", platform: windows }
actions:
  - name: set_cell_value
    params: { sheet: string, cell: string, value: string }
    channel: scripting            # lifted from accessibility
    plan: [...]                   # deterministic primitives
    fallback_plans: [...]         # accessibility, then pixels
    verify: { read_back: cell_value, equals: $value }
    reversible: true
    preconditions: [workbook_open]
```

### 5.4 Runtime

- Executes the primary plan; on locator miss, tries fallback plans in order. Still zero model calls.
- Returns `{ ok, result, evidence, channel_used, duration }`.
- When every plan fails, returns a typed failure and queues the action for recompilation. The caller can choose to run a live agent; the system never silently invokes a model on the hot path.

### 5.5 Self-healing

A background repair loop reruns the compiler on failed actions, diffing the old and new state graphs to localize what changed. Repairs go through the same verification as the original compilation before replacing the manifest entry.

## 6. Key ideas to test

1. **Snapshot exploration.** Explore destructive actions (delete, send, pay) inside a VM snapshot, observe effects, roll back. This removes the safety barrier for local effects. For remote effects, use test accounts, recorded network fixtures, or dry-run endpoints.
2. **Multi-source inventory.** Use independent sources (menus, shortcuts, scripting dictionaries, docs, network endpoints) to estimate inventory completeness, similar to capture-recapture estimation in ecology.
3. **Compile-time grounding.** Move every neural decision to compile time and store the result as layered locators. Runtime grounding becomes deterministic matching.
4. **Data-dependent plans without reasoning.** ActionEngine fails when the plan depends on runtime data. Instead of planning, expose read actions that return structured data and let the caller compose. The system stays zero-step; composition is the caller's job.
5. **Parametric continuous actions.** Canvas and position-precise actions (DMI's stated gap) become functions over geometry, such as `draw_path(points)` or `move_object(id, dx, dy)`, executed through the pixel channel with coordinates computed deterministically from the accessibility bounds or a compile-time template.
6. **Channel lifting by equivalence.** Treat GUI plans as the specification and direct channels as optimizations, accepted only when end states match.

## 7. Hard problems

1. **Inventory completeness.** Black-box exploration cannot prove it found everything (ActionEngine, section 3.2). Mitigation: multi-source inventory, coverage estimates with confidence intervals, refinement from runtime misses.
2. **Conditional UI.** Controls that rename or appear based on input (DMI's Find and Replace example). Mitigation: explore with generated input variants; key states on predicates, not names.
3. **Apps without semantic structure.** Games, custom-drawn UIs, legacy apps without UIA. Mitigation: pixel channel with compile-time templates and OCR-free matching; this is where coverage will be hardest to earn.
4. **Locator stability across versions.** Mitigation: layered locators, version-specific manifests, diff-based repair.
5. **Authentication and sessions.** Credentials stay on the user's machine; the runtime borrows the app's existing session and never stores secrets in the manifest.
6. **Policy-blocked actions.** Anti-bot defenses, legally required human steps (2FA, payment confirmation). These are reported as a separate category and never bypassed.
7. **Verification of invisible effects.** Effects that do not show on screen (Neuro-Symbolic CU judges scored 0% on these). Mitigation: verify through a second channel (network response, file, scripting read-back), not through screenshots.

## 8. Metrics

| Metric | Definition | Target |
|---|---|---|
| Reach | Actions performable by any channel / inventory size | 100% |
| Compiled coverage | Compiled, zero-step, verified actions / inventory size | Primary research number |
| Policy-blocked share | Actions excluded under 7.6 / inventory size | Reported, not hidden |
| Runtime model calls | Model calls inside the system per invocation | 0 |
| Success rate (Pass^k) | Action succeeds in all k repeated runs on variants | k = 3 and k = 10 |
| Latency | p50 and p95 per action, by channel | Report per channel |
| Lift rate | Actions served by a channel above pixels / compiled actions | Maximize |
| Compile cost | Wall time, model tokens, and human minutes per app | Human minutes -> 0 |
| Heal rate | Broken actions repaired automatically after an app update | Maximize |
| Inventory completeness estimate | Estimated true inventory size vs discovered | Report interval |

## 9. Evaluation plan

### 9.1 External benchmarks (comparability)

- OSWorld-Verified and OSWorld 2.0 (Linux desktop)
- Windows Agent Arena
- MacAgentBench
- WebArena (compare with ActionEngine)
- AndroidWorld

Protocol: compile the applications used by each benchmark, then let a standard agent solve tasks using only the compiled interface plus a reported fallback. Report success, steps, latency, cost, and how often fallback was needed.

Baselines: GUI-only computer-use agent, Hybrid Computer Use, DMI (Office), ActionEngine (web), Neuro-Symbolic CU, AutoRPA.

### 9.2 Coverage benchmark (new contribution)

Benchmarks measure tasks, not coverage. Build one:

- Pick a set of applications per platform, including at least one with no accessibility support.
- Build a ground-truth action inventory per app by hand, from documentation, menus, and scripting dictionaries.
- Measure discovered inventory, compiled coverage, and Pass^k per action.
- Re-run after a real application update to measure heal rate.

## 10. Phases

1. **Phase 0: Foundations (2 to 3 weeks).** Channel adapter interface; Windows adapters for accessibility, pixels, and network; sandbox with snapshots (Hyper-V or a VM manager); manifest schema v0.
2. **Phase 1: One app, end to end (3 to 4 weeks).** Explore, inventory, synthesize, verify, publish for one Windows app. Report compiled coverage against a hand-built inventory.
3. **Phase 2: Lifting (3 weeks).** Add scripting and network lifting; measure lift rate and latency gains.
4. **Phase 3: Second OS (4 weeks).** macOS or Linux adapters; same manifest format; test RQ4.
5. **Phase 4: External benchmarks (4 weeks).** OSWorld and Windows Agent Arena runs against baselines.
6. **Phase 5: Maintenance (ongoing).** Version updates, heal rate, coverage benchmark release.

## 11. First application: selection criteria

To be chosen after Phase 0. A good first target:

- has a full action inventory that can be built by hand in under two days,
- exposes at least two channels (for example accessibility plus scripting),
- includes at least a few actions that are canvas-like or conditional,
- appears in an external benchmark, so results compare against prior work.

## 12. Market risks

- Simular already ships neuro-symbolic workflow compilation on macOS and Windows and leads OSWorld. Differentiation must be app-level compilation, zero runtime grounding, measured coverage, and cross-OS manifests.
- Browser-only players (Browserbase, Browser Use, Skyvern) can extend to desktop.
- Muscle Mem gained developer attention but few users. Distribution through MCP, where agents already look for tools, is part of the design for this reason.
- Reverse engineering private network APIs carries terms-of-service risk when run as a hosted service. Run the runtime locally, on the user's machine, under the user's own session.

## 13. References

- DMI: https://arxiv.org/abs/2510.04607
- ActionEngine: https://arxiv.org/abs/2602.20502
- Neuro-Symbolic Computer Use: https://arxiv.org/abs/2609.36927
- AutoRPA: https://arxiv.org/abs/2605.21082
- TraceCompiler: https://arxiv.org/abs/2608.02680
- Hybrid Computer Use: https://arxiv.org/abs/2610.41432
- LUMOS: https://arxiv.org/abs/2606.30697
- APISensor: https://arxiv.org/abs/2603.23852
- AXIS: https://arxiv.org/abs/2409.17140
- UFO2: https://arxiv.org/abs/2504.14603
- CoAct-1: https://arxiv.org/abs/2508.03923
- API Agents vs. GUI Agents: https://arxiv.org/abs/2503.11069
- Stagehand caching: https://www.browserbase.com/blog/stagehand-caching
- Workflow Use: https://github.com/browser-use/workflow-use
- Muscle Mem retrospective: https://blog.butter.dev/muscle-mem-as-a-proxy
- Integuru: https://github.com/Integuru-AI/Integuru
