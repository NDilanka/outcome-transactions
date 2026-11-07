"""Amendment 2 renderability predicates for group A. Post hoc: written after the group A renders and before
any judge run. See exp9-preregistration.md section 11.

It reads the PDFs that renderability_checks.py already rendered (no re-render) and reports both readings:
the registered check (renderability_checks.py) and this amended check. The registered check for 66399b0d state_17
has no amended replacement: a render cannot show that error, so the state is not renderable.

Usage: renderability_amendment2.py --work DIR --result FILE
"""
import argparse
import glob
import json
import os
import sys

import pymupdf

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import renderability_checks as rc  # noqa: E402

GREEN_TEXT = 0x9EEFBC  # colour of the slide 5 text runs in the before deck (57667013), from the before PDF
OLIVE_TEXT = 0x999900  # colour of the slide 5 text runs after lumMod 60000 (state_20)
SPAN_TOL = 10  # per-channel tolerance for matching a span colour in the render


def span_rects(page, colour):
    rects = []
    for block in page.get_text('dict')['blocks']:
        for line in block.get('lines', []):
            for span in line['spans']:
                if span['color'] == colour and span['text'].strip():
                    rects.append(tuple(span['bbox']))
    return rects


def near(colour):
    r0, g0, b0 = (colour >> 16) & 255, (colour >> 8) & 255, colour & 255

    def pred(r, g, b):
        return abs(r - r0) <= SPAN_TOL and abs(g - g0) <= SPAN_TOL and abs(b - b0) <= SPAN_TOL
    return pred


def pdf_of(work, bid, side):
    hits = glob.glob(os.path.join(work, bid, side, 'f01', 'pdf', '*.pdf'))
    if len(hits) != 1:
        raise ValueError(f'{bid} {side}: expected one PDF, found {len(hits)}')
    return hits[0]


def amended_alpha(before_pdf, after_pdf):
    """state_19: the before slide 5 text is visible (green), and it is gone after (alpha 0)."""
    pb, page_b = rc.page_pixmap(before_pdf, rc.SLIDE_5)
    pa, _ = rc.page_pixmap(after_pdf, rc.SLIDE_5)
    rects = span_rects(page_b, GREEN_TEXT)
    before = rc.count_px(pb, rects, near(GREEN_TEXT))
    after = rc.count_px(pa, rects, near(GREEN_TEXT))
    return {'before_green_px': before, 'after_green_px': after, 'span_rects': len(rects),
            'renderable': before >= rc.MIN_PX and after <= rc.TOL_FRAC * before}


def amended_luminance(before_pdf, after_pdf):
    """state_20: the after slide 5 text is dark olive (not yellow). Counts are taken inside the after text spans."""
    pa, page_a = rc.page_pixmap(after_pdf, rc.SLIDE_5)
    pb, _ = rc.page_pixmap(before_pdf, rc.SLIDE_5)
    rects = span_rects(page_a, OLIVE_TEXT)
    olive = rc.count_px(pa, rects, rc.is_olive)
    yellow = rc.count_px(pa, rects, rc.is_yellow)
    return {'after_olive_px': olive, 'after_yellow_px': yellow, 'span_rects': len(rects),
            'before_yellow_px_in_same_rects': rc.count_px(pb, rects, rc.is_yellow),
            'renderable': olive >= rc.MIN_PX and yellow <= rc.TOL_FRAC * olive}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--work', required=True)
    ap.add_argument('--result', required=True)
    args = ap.parse_args()
    # bids and registered decisions come from a_result.json, written by renderability_checks.py
    a_rows = json.load(open(os.path.join(os.path.dirname(args.result), 'a_result.json')))
    by_state = {(r['task'], r['state']): r for r in a_rows}
    out = []
    for task, state, fn in [(rc.T57, 'state_19', amended_alpha), (rc.T57, 'state_20', amended_luminance)]:
        bid = by_state[(task, state)]['bid']
        ev = fn(pdf_of(args.work, bid, 'start'), pdf_of(args.work, bid, 'end'))
        out.append({'task': task, 'state': state, 'bid': bid, 'amended_check': fn.__name__,
                    'registered_renderable': by_state[(task, state)]['renderable'], 'evidence': ev,
                    'renderable': ev['renderable']})
        print(bid, state, fn.__name__, ev, flush=True)
    bid22 = by_state[(rc.T57, 'state_22')]['bid']
    ev22 = rc.check_black_fills(pdf_of(args.work, bid22, 'start'), pdf_of(args.work, bid22, 'end'))
    out.append({'task': rc.T57, 'state': 'state_22', 'bid': bid22, 'amended_check': 'check_black_fills (unchanged)',
                'registered_renderable': by_state[(rc.T57, 'state_22')]['renderable'], 'evidence': ev22,
                'renderable': ev22['renderable']})
    print(bid22, 'state_22 unchanged', ev22, flush=True)
    bid17 = by_state[(rc.T66, 'state_17')]['bid']
    out.append({'task': rc.T66, 'state': 'state_17', 'bid': bid17, 'amended_check': None,
                'registered_renderable': by_state[(rc.T66, 'state_17')]['renderable'],
                'evidence': {'reason': 'no amended check: the before render already has the full-width rows, '
                                       'so a render cannot show this error'},
                'renderable': False})
    with open(args.result, 'w', encoding='utf-8') as fh:
        json.dump(out, fh, indent=1)
    print('amended renderable:', sum(r['renderable'] for r in out), 'of', len(out),
          '| registered renderable:', sum(r['registered_renderable'] for r in out))


if __name__ == '__main__':
    main()
