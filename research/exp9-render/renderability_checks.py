"""Group A renderability checks. Frozen at the lock commit; see exp9-preregistration.md section 4.

Each of the eight group A states is rendered by render_lib (the same packets the judge reads). A state is
renderable only if its check passes on the rendered pages, read from the same PDFs. Cursor states
(66399b0d 01 to 04) have no check: the docx records no cursor, so they are not renderable by design, and
they are judged and reported separately. Thresholds are fixed here and were not tuned on any render.

Usage: renderability_checks.py --salt-file FILE --states DIR --packets DIR --work DIR --result FILE
"""
import argparse
import json
import os
import sys

import pymupdf

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import render_lib as rl  # noqa: E402

T57 = '57667013-ea97-417c-9dce-2713091e6e2a'
T66 = '66399b0d-8fda-4618-95c4-bfc6191617e9'
SLIDE_5 = 4  # page index in the PDF of the presentation
YELLOW_TEXT = 0xFFFF00  # colour the text runs carry in the before state (PyMuPDF span colour)
MIN_PX = 20  # minimum count of matching pixels for a property to count as present
TOL_FRAC = 0.05  # after count must fall to this share of the before count for text to count as gone


def is_yellow(r, g, b):
    return r >= 230 and g >= 230 and b <= 60


def is_olive(r, g, b):
    # HSL lum 30% of yellow is about (153,153,0): what lumMod 60000 gives
    return 100 <= r <= 200 and abs(r - g) <= 20 and b <= 60


def is_black(r, g, b):
    return r <= 20 and g <= 20 and b <= 20


def page_pixmap(pdf, index):
    doc = pymupdf.open(pdf)
    if doc.page_count <= index:
        raise ValueError(f'{pdf}: {doc.page_count} pages, need page {index + 1}')
    page = doc[index]  # the page keeps its document open, so the text can still be read
    pix = page.get_pixmap(matrix=rl.SCALE, alpha=False)
    return pix, page


def count_px(pix, rects, pred):
    """Count pixels of the rendered page inside the PDF-point rectangles that satisfy pred."""
    s, stride, width, height = pix.samples, pix.stride, pix.width, pix.height
    k = rl.DPI / 72
    n = 0
    for x0, y0, x1, y1 in rects:
        xa, xb = max(0, int(x0 * k)), min(width, int(x1 * k) + 1)
        ya, yb = max(0, int(y0 * k)), min(height, int(y1 * k) + 1)
        for y in range(ya, yb):
            base = y * stride
            for x in range(xa, xb):
                i = base + 3 * x
                if pred(s[i], s[i + 1], s[i + 2]):
                    n += 1
    return n


def yellow_text_rects(page):
    rects = []
    for block in page.get_text('dict')['blocks']:
        for line in block.get('lines', []):
            for span in line['spans']:
                if span['color'] == YELLOW_TEXT and span['text'].strip():
                    rects.append(tuple(span['bbox']))
    return rects


def black_fill_count(page):
    n = 0
    for d in page.get_drawings():
        f = d.get('fill')
        if f is not None and all(abs(c) < 1e-3 for c in f[:3]):
            r = d['rect']
            if r.width * r.height >= 100:
                n += 1
    return n


def full_width_single_cell_rows(pdf):
    """Table rows drawn as one cell across at least 95% of their table (a horizontally merged row)."""
    doc = pymupdf.open(pdf)
    n = 0
    for page in doc:
        for table in page.find_tables().tables:
            width = table.bbox[2] - table.bbox[0]
            for row in table.rows:
                cells = [c for c in row.cells if c is not None]
                if len(cells) == 1 and cells[0][2] - cells[0][0] >= 0.95 * width:
                    n += 1
    doc.close()
    return n


def check_text_alpha(before_pdf, after_pdf):
    """57667013 state_19: slide 5 yellow text is invisible after (alpha 0)."""
    pb, page_b = page_pixmap(before_pdf, SLIDE_5)
    pa, _ = page_pixmap(after_pdf, SLIDE_5)
    rects = yellow_text_rects(page_b)
    before = count_px(pb, rects, is_yellow)
    after = count_px(pa, rects, is_yellow)
    return {'before_yellow_px': before, 'after_yellow_px': after,
            'renderable': before >= MIN_PX and after <= TOL_FRAC * before}


def check_text_luminance(before_pdf, after_pdf):
    """57667013 state_20: slide 5 text is dark olive after (lumMod 60000), not yellow."""
    pb, page_b = page_pixmap(before_pdf, SLIDE_5)
    pa, _ = page_pixmap(after_pdf, SLIDE_5)
    rects = yellow_text_rects(page_b)
    before = count_px(pb, rects, is_yellow)
    after_yellow = count_px(pa, rects, is_yellow)
    after_olive = count_px(pa, rects, is_olive)
    return {'before_yellow_px': before, 'after_yellow_px': after_yellow, 'after_olive_px': after_olive,
            'renderable': before >= MIN_PX and after_yellow <= TOL_FRAC * before and after_olive >= MIN_PX}


def check_black_fills(before_pdf, after_pdf):
    """57667013 state_22: slide 5 has at least six more black-filled shapes after, and they show in the render."""
    pb, page_b = page_pixmap(before_pdf, SLIDE_5)
    pa, page_a = page_pixmap(after_pdf, SLIDE_5)
    full_b = [(0, 0, page_b.rect.width, page_b.rect.height)]
    full_a = [(0, 0, page_a.rect.width, page_a.rect.height)]
    fills_delta = black_fill_count(page_a) - black_fill_count(page_b)
    px_delta = count_px(pa, full_a, is_black) - count_px(pb, full_b, is_black)
    return {'black_fill_delta': fills_delta, 'black_px_delta': px_delta,
            'renderable': fills_delta >= 6 and px_delta >= 500}


def check_merged_row(before_pdf, after_pdf):
    """66399b0d state_17: the inserted table has a row drawn as one cell across the table width after."""
    delta = full_width_single_cell_rows(after_pdf) - full_width_single_cell_rows(before_pdf)
    return {'full_width_row_delta': delta, 'renderable': delta >= 1}


GROUP_A = [
    (T57, 'state_19', '.pptx', check_text_alpha),
    (T57, 'state_20', '.pptx', check_text_luminance),
    (T57, 'state_22', '.pptx', check_black_fills),
    (T66, 'state_17', '.docx', check_merged_row),
]
CURSOR_STATES = [(T66, f'state_0{i}') for i in range(1, 5)]  # not renderable by design, no check


def one(pdfs, side, ext):
    hits = [pdf for (s, rel), pdf in pdfs.items() if s == side and rel.lower().endswith(ext)]
    if len(hits) != 1:
        raise ValueError(f'expected one {ext} on {side}, found {len(hits)}')
    return hits[0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--salt-file', required=True)
    ap.add_argument('--states', required=True, help='directory of normalised states: <task>/<state>')
    ap.add_argument('--packets', required=True)
    ap.add_argument('--work', required=True)
    ap.add_argument('--result', required=True)
    args = ap.parse_args()
    salt = open(args.salt_file, encoding='utf-8').read().rstrip('\n')
    results = []
    for task, state, ext, check in GROUP_A:
        bid = rl.bid9(salt, task, state)
        stats, pdfs = rl.render_state(os.path.join(rl.SNAPSHOTS, task), os.path.join(args.states, task, state),
                                      bid, rl.request_for(task), args.packets, args.work)
        evidence = check(one(pdfs, 'start', ext), one(pdfs, 'end', ext))
        results.append({'task': task, 'state': state, 'bid': bid, 'check': check.__name__,
                        'renderable': evidence['renderable'], 'evidence': evidence, 'render': stats})
        print(bid, check.__name__, evidence, flush=True)
    for task, state in CURSOR_STATES:
        results.append({'task': task, 'state': state, 'bid': rl.bid9(salt, task, state), 'check': None,
                        'renderable': False, 'evidence': {'reason': 'cursor position is not recorded in the file'}})
    with open(args.result, 'w', encoding='utf-8') as fh:
        json.dump(results, fh, indent=1)
    print('renderable:', sum(r['renderable'] for r in results), 'of', len(GROUP_A))


if __name__ == '__main__':
    main()
