"""Save-noise measurement: what a save does to a file in the canonical tree, and whether noise subtraction works.

Two producers are measured separately, as the north-star asks:
  library  the library that wrote the blind end states (openpyxl, python-docx, python-pptx). Every blind end state
           of an office file was written by one of these, so a no-op re-save with the same library is the producer's
           own noise. Measured on all office files of all 238 end states.
  libreoffice  LibreOffice headless re-save (the owning app of the office formats). Measured on the 68 correct
           end states, because the question is whether subtraction recovers the intended edit after an app save.

For one file, with start S (the snapshot), end E (the blind state), and noise N = diff(S, resave(S)):
  raw   = diff(S, E)            every change the end state makes
  sub   = subtract(raw, N)      changes that are not explained by the producer's no-op save
Library check:   raw, N, sub counts, and idempotence = diff(E, resave(E)) (the tree's sensitivity to a re-save of E).
LibreOffice check: sub_lo = subtract(diff(S, LO(E)), diff(S, LO(S))) should equal intended = subtract(diff(S, E),
noise) by path. The library's own noise is not part of the intended edit, so it is removed first.
Paths in sub_lo but not intended are unexplained save differences, and paths in intended but not sub_lo are intended
changes that the app save lost. Both are reported.

Usage: noise.py --blind-src <dir> --endstates <dir> [--snapshots <dir>] [--out <dir>] [--skip-lo]
"""
import argparse
import collections
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, REPO)

from research.universal_reader import canon, diff  # noqa: E402
from research.universal_reader.dryrun import load_families, load_labels  # noqa: E402

LIB_EXT = ('.xlsx', '.docx', '.pptx')
LO_PROFILE = 'file:///tmp/ur_lo_profile_noise'


def lib_resave(path, out):
    ext = os.path.splitext(path)[1].lower()
    if ext == '.xlsx':
        import openpyxl
        openpyxl.load_workbook(path).save(out)
    elif ext == '.docx':
        from docx import Document
        Document(path).save(out)
    elif ext == '.pptx':
        from pptx import Presentation
        Presentation(path).save(out)
    else:
        raise ValueError(ext)
    return out


def lo_resave(path, tmp):
    """LibreOffice headless round trip to the same format. Returns the new file path."""
    ext = os.path.splitext(path)[1].lower().lstrip('.')
    outdir = tempfile.mkdtemp(prefix='ur_lo_', dir=tmp)
    subprocess.run(['soffice', f'-env:UserInstallation={LO_PROFILE}', '--headless', '--convert-to', ext,
                    '--outdir', outdir, path], check=True, capture_output=True, timeout=240)
    out = os.path.join(outdir, os.path.splitext(os.path.basename(path))[0] + '.' + ext)
    if not os.path.exists(out):
        raise FileNotFoundError(out)
    return out


def file_diff(before_path, after_path, rel):
    """Diff of one file: both sides keyed by the same relative path."""
    before = {rel: canon.load_file(before_path, rel)}
    after = {rel: canon.load_file(after_path, rel)}
    return diff.diff_states(before, after)


def pattern(path):
    """A path with cell refs, indices and numbers replaced by '#', to group changes by kind."""
    return '/'.join(re.sub(r'[A-Z]{1,3}\d+|\d+', '#', str(p)) for p in path)


def sub_paths(d):
    return collections.Counter(c.path for c in d.changes)


def office_rels(tree):
    return sorted(rel for rel, n in tree.items() if rel.lower().endswith(LIB_EXT) and n.get('kind') == 'file')


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--blind-src', required=True)
    ap.add_argument('--endstates', required=True)
    ap.add_argument('--snapshots', default=os.path.join(REPO, 'research', 'exp5-grounded', 'snapshots'))
    ap.add_argument('--out', default=os.path.join(HERE, 'results'))
    ap.add_argument('--skip-lo', action='store_true')
    args = ap.parse_args(argv)

    fam = load_families()
    os.makedirs(args.out, exist_ok=True)
    tmp = tempfile.mkdtemp(prefix='ur_noise_')
    rows, lo_rows, patterns = [], [], collections.defaultdict(collections.Counter)
    try:
        tasks = sorted(t for t in os.listdir(args.endstates) if os.path.isdir(os.path.join(args.endstates, t)))
        for task in tasks:
            start_dir = os.path.join(args.snapshots, task)
            labels = load_labels(args.blind_src, task)
            # Library noise on the start files (once per task and file).
            noise_cache = {}
            for rel in office_rels(canon.dir_tree(start_dir)):
                s_path = os.path.join(start_dir, rel)
                r_path = lib_resave(s_path, os.path.join(tmp, 'lib_' + os.path.basename(rel)))
                noise_cache[rel] = file_diff(s_path, r_path, rel)
            for state in sorted(labels):
                end_dir = os.path.join(args.endstates, task, state)
                end_tree = canon.dir_tree(end_dir)
                for rel in office_rels(end_tree):
                    if rel not in noise_cache:
                        continue  # the file is new in the end state, so there is no start to compare with
                    s_path, e_path = os.path.join(start_dir, rel), os.path.join(end_dir, rel)
                    raw = file_diff(s_path, e_path, rel)
                    noise = noise_cache[rel]
                    sub, spurious = diff.subtract_noise(raw, noise)
                    e_r = lib_resave(e_path, os.path.join(tmp, 'libE_' + os.path.basename(rel)))
                    idem = file_diff(e_path, e_r, rel)
                    rec = {'task': task, 'family': fam[task], 'state': state, 'label': labels[state], 'file': rel,
                           'raw': len(raw.changes), 'noise_on_start': len(noise.changes),
                           'removed_as_noise': len(spurious), 'residual': len(sub.changes),
                           'idempotence_changes': len(idem.changes)}
                    rows.append(rec)
                    for c in noise.changes:
                        patterns[fam[task]][pattern(c.path)] += 1
                    for c in idem.changes:
                        patterns[fam[task] + ' (idempotence)'][pattern(c.path)] += 1
                    if (not args.skip_lo) and labels[state] == 'correct' and rel.lower().endswith(('.xlsx', '.docx', '.pptx')):
                        lo_s = lo_resave(s_path, tmp)
                        lo_e = lo_resave(e_path, tmp)
                        noise_lo = file_diff(s_path, lo_s, rel)
                        raw_lo = file_diff(s_path, lo_e, rel)
                        sub_lo, lo_spur = diff.subtract_noise(raw_lo, noise_lo)
                        want = sub_paths(sub)  # the intended edit: the library's changes after its own noise is removed
                        got = sub_paths(sub_lo)
                        lo_rows.append({'task': task, 'family': fam[task], 'state': state, 'file': rel,
                                        'intended_lib': sum(want.values()), 'noise_lo_on_start': len(noise_lo.changes),
                                        'raw_lo': len(raw_lo.changes), 'sub_lo': sum(got.values()),
                                        'agree': len(set(want) & set(got)),
                                        'only_lo_residual': len(set(got) - set(want)),
                                        'only_lib_intended_removed': len(set(want) - set(got)),
                                        'lo_paths_only': sorted(pattern(p) for p in set(got) - set(want))[:5],
                                        'lib_paths_lost': sorted(pattern(p) for p in set(want) - set(got))[:5]})
                        shutil.rmtree(os.path.dirname(lo_s), ignore_errors=True)
                        shutil.rmtree(os.path.dirname(lo_e), ignore_errors=True)
                    print(f"{task[:8]} {state[:30]:30} {rel[-22:]:22} raw={rec['raw']:3} noise={rec['noise_on_start']:3} "
                          f"residual={rec['residual']:3} idem={rec['idempotence_changes']}", flush=True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    out = {'library': rows, 'libreoffice': lo_rows,
           'noise_patterns': {k: v.most_common(12) for k, v in patterns.items()}}
    with open(os.path.join(args.out, 'noise.json'), 'w', encoding='utf-8') as fh:
        json.dump(out, fh, indent=1, ensure_ascii=False, default=str)
    summarise(rows, lo_rows)


def summarise(rows, lo_rows):
    print('\n## Library re-save noise (generator-written office files, all end states)')
    print('| family | files compared | raw changes | noise on start | removed as noise | residual | '
          'end files with idempotence changes |')
    print('|---|---|---|---|---|---|---|')
    by = collections.OrderedDict()
    for r in rows:
        c = by.setdefault(r['family'], collections.Counter())
        c['files'] += 1
        for k in ('raw', 'noise_on_start', 'removed_as_noise', 'residual'):
            c[k] += r[k]
        c['idem_files'] += r['idempotence_changes'] > 0
    tot = collections.Counter()
    for fm, c in by.items():
        print(f"| {fm} | {c['files']} | {c['raw']} | {c['noise_on_start']} | {c['removed_as_noise']} | "
              f"{c['residual']} | {c['idem_files']} |")
        tot.update(c)
    print(f"| all | {tot['files']} | {tot['raw']} | {tot['noise_on_start']} | {tot['removed_as_noise']} | "
          f"{tot['residual']} | {tot['idem_files']} |")
    if lo_rows:
        print('\n## LibreOffice re-save (correct end states): subtraction against the library-written edit')
        print('| family | files | intended changes (library) | changes after subtraction (LibreOffice) | agree | '
              'LibreOffice-only residual | intended lost by subtraction |')
        print('|---|---|---|---|---|---|---|')
        lb = collections.OrderedDict()
        for r in lo_rows:
            c = lb.setdefault(r['family'], collections.Counter())
            c['files'] += 1
            for k in ('intended_lib', 'sub_lo', 'agree', 'only_lo_residual', 'only_lib_intended_removed'):
                c[k] += r[k]
        for fm, c in lb.items():
            print(f"| {fm} | {c['files']} | {c['intended_lib']} | {c['sub_lo']} | {c['agree']} | "
                  f"{c['only_lo_residual']} | {c['only_lib_intended_removed']} |")


if __name__ == '__main__':
    main()
