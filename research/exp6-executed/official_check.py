"""Runs OSWorld's own evaluator functions (research/OSWorld, unmodified) on a local end state.

Only file-based checkers run here. A VM command or live-app postconfig cannot run on a local copy, so those
tasks are reported NOT_RUNNABLE. Optional OSWorld imports that the subset's checkers never call (easyocr, pdfplumber,
mutagen) are replaced by stubs that raise if actually used, so an OCR path would fail loudly instead of passing.
"""
import json, os, sys, types, glob

HERE = os.path.dirname(os.path.abspath(__file__))
OSW = os.path.join(HERE, '..', 'OSWorld')


def _stub(name, **attrs):
    m = types.ModuleType(name)
    m.__dict__.update(attrs)
    sys.modules.setdefault(name, m)


def _no_ocr(*a, **k):
    raise RuntimeError('OCR stub: easyocr is not installed; this checker path is not supported locally')


_stub('easyocr', Reader=_no_ocr)
_stub('pdfplumber', open=_no_ocr)
_stub('mutagen')
_stub('mutagen.easyid3', EasyID3=_no_ocr)
sys.path.insert(0, os.path.abspath(OSW))
# Import the metric modules without running OSWorld's package __init__ (it imports every checker family,
# e.g. vlc needs acoustid and chrome needs borb). Parent packages are registered as bare namespaces.
for _name, _rel in [('desktop_env', ''), ('desktop_env.evaluators', 'evaluators'),
                    ('desktop_env.evaluators.metrics', os.path.join('evaluators', 'metrics'))]:
    _pkg = types.ModuleType(_name)
    _pkg.__path__ = [os.path.join(os.path.abspath(OSW), 'desktop_env', _rel)]
    sys.modules.setdefault(_name, _pkg)

import logging  # noqa: E402
logging.getLogger('desktopenv').setLevel(logging.ERROR)  # OSWorld's checkers log every shape at DEBUG
from desktop_env.evaluators.metrics.table import compare_table  # noqa: E402
from desktop_env.evaluators.metrics.slides import compare_pptx_files, check_transition  # noqa: E402
from desktop_env.evaluators.metrics.docs import compare_docx_files, compare_docx_tables, contains_page_break  # noqa: E402

FUNCS = {'compare_table': compare_table, 'compare_pptx_files': compare_pptx_files,
         'compare_docx_files': compare_docx_files, 'compare_docx_tables': compare_docx_tables,
         'check_transition': check_transition, 'contains_page_break': contains_page_break}


def config_for(task_full):
    """OSWorld evaluator config for a task id (prefix match on the examples folder)."""
    hits = glob.glob(os.path.join(OSW, 'evaluation_examples', 'examples', '*', task_full[:8] + '*.json'))
    if not hits: raise FileNotFoundError(task_full)
    return json.load(open(hits[0]))['evaluator']


def _as_list(x, n):
    if isinstance(x, list): return x
    return [x] * n


def run_official(task_full, after_root, cache_root=None):
    """Returns {'verdict': PASS|FAIL|NOT_RUNNABLE|ERROR, 'detail': [...]} using OSWorld's own functions.
    OSWorld's checkers print per-shape debug lines to stdout; they are captured here."""
    import io, contextlib
    with contextlib.redirect_stdout(io.StringIO()):
        return _run_official(task_full, after_root)


def _run_official(task_full, after_root):
    ev = config_for(task_full)
    funcs = ev['func'] if isinstance(ev['func'], list) else [ev['func']]
    conj = ev.get('conj', 'and')
    n = len(funcs)
    results = _as_list(ev.get('result'), n)
    expected = _as_list(ev.get('expected'), n)
    options = _as_list(ev.get('options', {}), n)
    if any(f not in FUNCS for f in funcs):
        return {'verdict': 'NOT_RUNNABLE', 'detail': [f'unsupported function {funcs} or non-file checker']}
    if any(r.get('type') != 'vm_file' for r in results if isinstance(r, dict)):
        return {'verdict': 'NOT_RUNNABLE', 'detail': ['checker reads VM command output, not a file']}
    detail, passes = [], []
    for i, fn in enumerate(funcs):
        res_path = os.path.join(after_root, results[i]['path'].lstrip('/'))
        exp = expected[i]
        exp_path = None
        if isinstance(exp, dict) and exp.get('type') == 'cloud_file':
            exp_path = os.path.join(HERE, 'osworld_gold', task_full[:8], exp['dest'])
        try:
            if fn == 'compare_table':
                score = compare_table(res_path, exp_path, **options[i])
            elif fn in ('compare_pptx_files', 'compare_docx_files', 'compare_docx_tables'):
                score = FUNCS[fn](res_path, exp_path, **options[i])
            elif fn == 'check_transition':
                score = check_transition(res_path, exp['rules'])
            elif fn == 'contains_page_break':
                score = contains_page_break(res_path, exp['rules'])
            ok = score is True or (isinstance(score, (int, float)) and score == 1)
            detail.append({'func': fn, 'score': score if isinstance(score, (bool, int, float)) else str(score)[:80], 'ok': bool(ok)})
            passes.append(bool(ok))
        except Exception as e:  # checker crash on a malformed end state is an ERROR, not a pass
            detail.append({'func': fn, 'error': f'{type(e).__name__}: {str(e)[:160]}'})
            passes.append(None)
    if any(p is None for p in passes) and not any(p is True for p in passes):
        return {'verdict': 'ERROR', 'detail': detail}
    verdict = (any if conj == 'or' else all)(p is True for p in passes)
    return {'verdict': 'PASS' if verdict else 'FAIL', 'detail': detail}
