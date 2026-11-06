# Experiments 1 and 2: memory divergence and time-warp headroom

Date: 2026-11-06. Setup: LibreOffice Calc under Xvfb + openbox in WSL2 Ubuntu (i5-11400H, 2.9 GB RAM given to WSL). Script: `research/exp1/memdiff.py`, aggregated in `research/exp1/aggregate.json`. Three verified runs (B2 = 5000 saved, F2–F6 = 1001–1005).

## Question

If the engine forks a live desktop to search for an outcome, how much memory does each fork really cost, and how much of a GUI task's wall time is the app just waiting?

## Method

- Snapshot every writable page of the soffice process before and after each task (`/proc/<pid>/pagemap` + `/proc/<pid>/mem`).
- **Naive CoW cost**: number of pages that differ, times 4 KB. This is what a fork pays with plain copy-on-write.
- **Sub-page delta**: for each changed page, XOR it with the old page and compress the result (zlib). For new pages, compress the page itself. **Full**: compress changed pages without a delta.
- **Asleep share**: during the task, sample every thread's state every 10 ms. Report the share of samples where all threads were asleep.

## Results (run 3; runs 1–2 within 10%)

| Task | Resident MB | Naive CoW MB | Sub-page delta KB | Delta vs naive | Delta vs plain compression | All threads asleep | Settle time s |
|---|---|---|---|---|---|---|---|
| T1 edit one cell | 74.4 | 7.8 | 676 | 11.9× | 1.9× | 0.89 | 1.19 |
| T2 type 50 values | 75.8 | 18.5 | 1189 | 15.9× | 1.4× | 0.95 | 4.76 |
| T3 open/close format dialog | 76.0 | 56.8 | 6471 | 9.0× | 1.1× | 0.91 | 1.68 |
| T4 bold a column | 123.0 | 20.9 | 1311 | 16.3× | 1.7× | 0.96 | 0.44 |
| T5 scroll 1000 rows | 123.0 | 21.3 | 1683 | 13.0× | 1.4× | 0.93 | 0.16 |
| T6 save | 123.8 | 39.4 | 3248 | 12.4× | 1.4× | 0.61 | 0.76 |

## What this means

1. **Forks are cheap.** A fork of a live office app that does a real task diverges by 8–57 MB naive, and by 0.7–6.5 MB if divergence is stored compressed. Ten forks of this app fit in under 70 MB. That is cheap enough for a laptop with 8 GB of RAM.
2. **Honest caveat on sub-page deltas.** Against naive CoW they save 9–16×, but most of that comes from plain compression. Against compressing changed pages without a delta, XOR deltas add only 1.1–1.9×. Sub-page deltas are a modest gain, not a breakthrough, and the Difference Engine (OSDI'08) already published the idea.
3. **Dialogs and saves dominate.** T3 and T6 create many brand-new pages (83% and 70% new). Those cannot be delta-encoded. The real cost driver is allocator churn, not edits.
4. **The app is mostly asleep.** In 60–96% of samples, every thread was blocked. A fork whose app is asleep and waiting on a timer can jump its clock forward (time warp). Waiting on I/O cannot be skipped, but it can be treated as an event.
5. **Agents waste time on fixed sleeps.** OSWorld's harness pauses 2 s after every step, and task scripts sleep 1–10 s. Measured settle times were 0.16–4.8 s. An engine that can see "all threads asleep, no pending I/O, no new frames" can emit a **UI-settled event** instead. Per step, that saves the gap between the fixed sleep and the real settle time.

## Fixes discovered while running

- Without a window manager, keyboard focus was unreliable. Fixed with openbox.
- xdotool needed `--delay 20`; repeated `Right Right` in one call dropped keys, so each key is sent separately.
- xlsx save prompts a "keep format" dialog. The tests use ODS.
