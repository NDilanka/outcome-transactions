"""Recalculates end-state workbooks whose formula cells have no cached values.

Why: the blind-state generators wrote some .xlsx files with openpyxl, which drops cached formula results. A user saving
in Calc would keep them. The executor and OSWorld's compare_table both read cached values, so an uncached formula looks
like an empty cell. This step re-saves only those workbooks through LibreOffice (as a GUI save would). Formulas, values,
sheets and charts are checked before and after. Nothing else is changed. It applies to every state the same way and
does not read labels or specs.

Usage: normalize_states.py <endstates_dir> <out_dir> <snapshots_dir>
Writes <out_dir> (a full copy) and <out_dir>/../normalize_report.json.
"""
import glob, json, os, shutil, subprocess, sys, tempfile, zipfile
import openpyxl

HERE = os.path.dirname(os.path.abspath(__file__))


def cell_map(path, data_only):
    wb = openpyxl.load_workbook(path, data_only=data_only)
    out = {}
    for ws in wb.worksheets:
        for row in ws.iter_rows():
            for c in row:
                if c.value is not None:
                    out[(ws.title, c.coordinate)] = c.value
    return out, wb.sheetnames


def uncached(path):
    f, _ = cell_map(path, False)
    d, _ = cell_map(path, True)
    return [k for k, v in f.items() if isinstance(v, str) and v.startswith('=') and d.get(k) is None]


def charts(path):
    with zipfile.ZipFile(path) as z:
        return sorted(n for n in z.namelist() if n.startswith('xl/charts/chart'))


def lo_resave(path):
    tmp = tempfile.mkdtemp(prefix='exp6norm_')
    subprocess.run(['soffice', '--headless', '--convert-to', 'xlsx', '--outdir', tmp, path],
                   check=True, capture_output=True, timeout=240)
    new = os.path.join(tmp, os.path.basename(path))
    shutil.move(new, path)
    shutil.rmtree(tmp)


def main():
    src, dst, snaps = (os.path.abspath(p) for p in sys.argv[1:4])
    if os.path.exists(dst):
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
    report = []
    for p in sorted(glob.glob(os.path.join(dst, '*', '*', '**', '*.xlsx'), recursive=True)):
        rel = os.path.relpath(p, dst)
        unc = uncached(p)
        if not unc:
            continue
        task = rel.split(os.sep)[0]
        before_f, before_names = cell_map(p, False)
        before_v, _ = cell_map(p, True)
        before_charts = charts(p)
        lo_resave(p)
        after_f, after_names = cell_map(p, False)
        after_v, _ = cell_map(p, True)
        checks = {}
        checks['sheet_names_same'] = before_names == after_names
        checks['formulas_same'] = before_f.keys() == after_f.keys() and all(
            str(before_f[k]) == str(after_f[k]) for k in before_f if isinstance(before_f[k], str) and before_f[k].startswith('='))
        nonformula_before = {k: v for k, v in before_f.items() if not (isinstance(v, str) and v.startswith('='))}
        nonformula_after = {k: v for k, v in after_f.items() if not (isinstance(v, str) and v.startswith('='))}
        checks['constants_same'] = nonformula_before == nonformula_after
        checks['no_uncached_left'] = not uncached(p)
        checks['charts_same'] = len(before_charts) == len(charts(p))
        # Cached values the generator kept must match the recalculated ones (same formula, same inputs).
        kept = [k for k in before_v if k in after_v and before_v[k] is not None and isinstance(before_f.get(k), str)
                and before_f[k].startswith('=')]
        mism = [k for k in kept if before_v[k] != after_v[k] and not (
            isinstance(before_v[k], (int, float)) and isinstance(after_v[k], (int, float)) and abs(before_v[k] - after_v[k]) < 1e-9)]
        checks['kept_cached_values_match'] = len(mism) == 0
        # Independent check: a formula the state did not change must recalculate to the snapshot's own cached value.
        snap_p = os.path.join(snaps, task, os.path.relpath(p, os.path.join(dst, task)).split(os.sep, 1)[1])
        snap_match = None
        if os.path.exists(snap_p):
            sf, _ = cell_map(snap_p, False)
            sv, _ = cell_map(snap_p, True)
            snap_consts = {k: v for k, v in sf.items() if not (isinstance(v, str) and v.startswith('='))}
            # The snapshot cache is a valid expectation only where the state did not change any input constant.
            inputs_unchanged = snap_consts == nonformula_after
            if inputs_unchanged:
                same_formulas = [k for k in sf if isinstance(sf[k], str) and sf[k].startswith('=')
                                 and after_f.get(k) == sf[k] and sv.get(k) is not None]
                bad = [k for k in same_formulas if not (sv[k] == after_v.get(k) or (
                    isinstance(sv[k], (int, float)) and isinstance(after_v.get(k), (int, float)) and abs(sv[k] - after_v[k]) < 1e-6))]
                snap_match = {'applicable': True, 'formulas_checked': len(same_formulas), 'mismatched': len(bad)}
                checks['unchanged_formulas_match_snapshot_cache'] = len(bad) == 0
            else:
                snap_match = {'applicable': False, 'reason': 'state changed input constants; snapshot caches not an expectation'}
        report.append({'state_path': rel, 'uncached_before': len(unc), 'checks': checks,
                       'snapshot_formula_check': snap_match, 'mismatches': [list(map(str, m)) for m in mism[:5]]})
        print(rel, 'uncached', len(unc), 'checks', all(checks.values()), flush=True)
    rep = os.path.join(os.path.dirname(dst), 'normalize_report.json')
    json.dump(report, open(rep, 'w'), indent=1)
    print('normalized', len(report), 'workbooks; report', rep)


if __name__ == '__main__':
    main()
