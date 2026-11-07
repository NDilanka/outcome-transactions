"""Judge packets for Exp 8, built like research/exp6-executed/judge_packets.py but with no clipping.

One packet per attempt end state: the request text, the live UI state (only for the UI condition, as a separate
field), an inspection of the starting state, an inspection of the end state, and a diff. No label, spec,
task id, attempt code, or method name. The blind map (blind_id -> attempt code) stays private, outside the repo.

Usage: build_judge_packets.py <out_dir>   (writes packets, fails on any silent cut, runs the leak check)
"""
import json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import judge_packets as jp  # noqa: E402  (Exp 8 copy of the Exp 6 helpers; no clipping)
from make_attempts import UI_BLOCKS  # noqa: E402

PRIV = "/home/factory-user/exp8/private"
EXEC = "/home/factory-user/exp8/exec"
BLIND_MAP = os.path.join(PRIV, "judge_blind_map.json")
SIZE_FLAG = 120_000  # bytes; packets above this are reported so the orchestrator can batch them alone
SUBSTRING_NEEDLES = ["solve.py", "exp4b", "exp8", "osworld", "/home/factory-user"]
WORD_NEEDLES = re.compile(r"\b(spec|specs|specexec|judge|judges|executor|checker|checkers)\b", re.I)


def blind(code):
    import hashlib
    return hashlib.sha256(("exp8|" + code).encode()).hexdigest()[:12]


def silent_caps(root):
    """Inspector cuts that leave no marker: xlsx sheets after 500 non-empty cells, pptx transitions after 300 chars."""
    hits = []
    for vp, p in jp.files_under(root).items():
        if p.endswith(".xlsx"):
            import openpyxl
            wb = openpyxl.load_workbook(p)
            if any(sum(c.value is not None for row in ws.iter_rows() for c in row) > 500 for ws in wb.worksheets):
                hits.append(vp)
        elif p.endswith(".pptx"):
            from pptx import Presentation
            for s in Presentation(p).slides:
                m = re.search(r"<p:transition.*?</p:transition>|<p:transition[^>]*/>", s._element.xml, re.S)
                if m and len(m.group(0)) > 300:
                    hits.append(vp)
                    break
    return hits


def packet_for(e, res, requests):
    code = e["code"]
    before_root = os.path.dirname(e["input_path"])
    after_root = os.path.dirname(res["end_state"])
    pk = {
        "blind_id": blind(code),
        "request": requests[e["short"]],
        "before_state": jp.dump(before_root),
        "after_state": jp.dump(after_root),
        "diff": jp.diff(before_root, after_root),
    }
    if e["condition"] == "ui":
        pk["ui_state"] = UI_BLOCKS[e["short"]]
    return pk


def main(out_dir):
    entries = json.load(open(os.path.join(PRIV, "map.json")))
    tasks = {t["id"][:8]: t["instruction"] for t in json.load(open(os.path.join(HERE, "..", "exp4b", "blind_tasks.json")))}
    os.makedirs(out_dir, exist_ok=True)
    bmap, sizes, failed = {}, {}, []
    for e in entries:
        res_path = os.path.join(EXEC, e["code"], "result.json")
        res = json.load(open(res_path))
        if not res.get("end_state"):
            # No program ran: the end state is the starting copy in a fresh target folder.
            os.makedirs(os.path.join(EXEC, e["code"], "target"), exist_ok=True)
            res["end_state"] = os.path.join(EXEC, e["code"], "target", "user" if e["kind"] == "profile" else e["file"])
            if not os.path.exists(res["end_state"]):
                import shutil
                if e["kind"] == "profile":
                    shutil.copytree(e["input_path"], res["end_state"])
                else:
                    shutil.copy2(e["input_path"], res["end_state"])
        hits = silent_caps(os.path.dirname(e["input_path"])) + silent_caps(os.path.dirname(res["end_state"]))
        if hits:
            raise SystemExit(f"silent cut in {e['code']}: {hits}; not writing packets")
        pk = packet_for(e, res, tasks)
        text = json.dumps(pk, ensure_ascii=False, indent=1)
        if "[truncated" in text:
            raise SystemExit(f"truncation marker in {e['code']}; not writing packets")
        if "inspection failed" in text:
            failed.append(e["code"])
        with open(os.path.join(out_dir, pk["blind_id"] + ".json"), "w") as fh:
            fh.write(text)
        sizes[pk["blind_id"]] = len(text.encode())
        bmap[pk["blind_id"]] = e["code"]
    with open(BLIND_MAP, "w") as fh:
        json.dump(bmap, fh, indent=1)
    big = sorted(v for v in sizes.values() if v > SIZE_FLAG)
    print(f"{len(bmap)} packets written to {out_dir}")
    print(f"sizes: min {min(sizes.values())} max {max(sizes.values())} total {sum(sizes.values())} bytes")
    print(f"packets over {SIZE_FLAG} bytes: {len(big)} {big}")
    print(f"packets containing 'inspection failed': {failed}")
    leak_check(out_dir, entries, tasks)


def leak_check(out_dir, entries, tasks):
    """Fail if a packet names a task, an attempt code, a method, a run path, or a spec/judge/executor word.
    Words match on word boundaries, so ordinary text such as 'specific' or 'respectively' does not count."""
    ids = {t[:8] for t in tasks} | {e["code"] for e in entries}
    bad = []
    for fn in os.listdir(out_dir):
        text = open(os.path.join(out_dir, fn)).read()
        bad += [(fn, n) for n in SUBSTRING_NEEDLES + sorted(ids) if n in text]
        bad += [(fn, m.lower()) for m in set(WORD_NEEDLES.findall(text))]
    print("leak check:", "PASS" if not bad else f"FAIL {len(bad)} hits {bad[:5]}")
    return not bad


if __name__ == "__main__":
    main(sys.argv[1])
