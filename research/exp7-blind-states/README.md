# exp7 blind end states

Hard-coded end states for a commit rule experiment ("commit an agent's result
only if it is correct"). Every task below ships 22 hand-built document states;
the generator code is the only description of what each state contains, and the
label file is the answer key.

Nothing here was derived from an earlier experiment's specs, judge or verdict
files. The states were written from each task's instruction text plus the
starting snapshot only.

## Layout

```
research/exp7-blind-states/
  run_all.py            materialise every state, optionally verify
  statekit.py           shared helpers (snapshot copy, ODF writer, OOXML edits)
  <task_id>/states.py   22 functions state_01 ... state_22, each (snapshot_dir, out_dir)
  <task_id>/labels.json 22 entries, {"state", "label", "why"}
```

Each `states.py` is standalone: it imports `statekit` for the packing helpers and
the document library it needs (`openpyxl`, `python-docx`, `python-pptx`,
`lxml`). A state function receives a snapshot directory and an output
directory, copies the snapshot tree there and edits plain files. Functions are
independent, since each one starts from a fresh copy.

`<out_dir>/<task_id>/<state_name>/` is a complete copy of that task's snapshot
with one end state applied, so a state directory can be opened exactly like the
original machine image (documents live under `home/user/...` or
`home/user/Desktop/...`).

## Running

```powershell
py research/exp7-blind-states/run_all.py --snapshots-dir D:/dev/interface-compiler/research/exp5-grounded/snapshots --out-dir D:/tmp/exp7out
```

Add `--verify` to also check the results, and `--task <task_id>` to restrict the
run to one task. `--snapshots-dir` defaults to the path above.

`--verify` fails the run when, for any state:

- the generator raised, or wrote no output directory;
- the output tree is byte identical to the untouched snapshot (nothing was
  done);
- the output tree is identical to another state of the same task (two states
  collapse to the same result, so the pair carries no signal);
- a `.docx`, `.xlsx`, `.pptx` or `.odt` inside the state will not open, or an
  `.odt` is not a real ODF package;
- `labels.json` is missing, does not cover exactly the `state_*` functions, has
  a label other than `wrong`/`correct`, has an empty `why`, or does not hold 18
  `wrong` and 4 `correct` entries.

A clean run prints one line per task, the total state count and:

```
verify: every state differs from its snapshot, states within a task are distinct, all documents open
```

## Labels

Every task carries 18 `wrong` and 4 `correct` states in a fixed shuffled
assignment of names, so state numbering says nothing about the label. `why`
describes the state in the reviewer's terms, not the code, and is the only
channel through which the answer key is exposed.

A `correct` state must satisfy the instruction in a way a careful reviewer would
accept, without doing extra damage: a state that also changes unrelated content,
loses formatting the instruction did not mention, writes the result to a copy
while leaving the opened file untouched, or only writes a different format is
`wrong`. States that reach the requested result through a legitimate alternative
(the property form or the literal form of the same effect, borders or no
borders, a pivot-style summary sheet or plain cells) are `correct`.

## Coverage

Seventeen tasks, 374 states.

| task | app | what the state changes |
| --- | --- | --- |
| `0326d92d` | calc | monthly total and growth rows, bar and line charts |
| `1273e544` | calc | Revenue column copied to Sheet2 |
| `42e0a640` | calc | Revenue and Total Expenses sums on Sheet2 |
| `51719eea` | calc | revenue column plus per-product summary on Sheet2 |
| `6054afcb` | calc | N/A rows hidden without deleting cells |
| `a9f325aa` | calc | cleaned movie titles in the next column |
| `21760ecb` | impress | dissolve transition on slide 1 |
| `550ce7e7` | impress | strikethrough on the first two lines of slide 5 |
| `57667013` | impress | yellow font on slide 5 text boxes |
| `7ae48c60` | impress | picture resized to about 1 cm |
| `f23acfd2` | impress | bullet removed from slide 1 |
| `66399b0d` | writer | table added to the operations instructions |
| `6a33f9b9` | writer | yellow highlighting removed |
| `88fe4b2d` | writer | first sentence split into seven bullets |
| `936321ce` | writer | comma separated rows converted to a table |
| `d53ff5ee` | writer | uppercase text lowercased |
| `ecc2413d` | writer | blank page inserted after page 1 |

### Skipped

- `2cd43775-7085-45d8-89fa-9e35c0a915cf` (impress, "enable auto-save every
  3min"). The task starts no document and produces no file: the outcome is an
  application setting, so there is nothing in a snapshot tree to label.
