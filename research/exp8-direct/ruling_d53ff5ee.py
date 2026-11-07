"""Exp 8: check the d53ff5ee ruling on the files. POST-HOC GT check, not pre-registered.

Ruling (orchestrator): "all uppercase text" means text written in uppercase, the ALL-CAPS text. Lowercasing ordinary
capitals elsewhere (sentence starts, names, ordinary-case table text) is collateral damage, so it is wrong.

Each d53ff5ee end state is compared with the input copy, paragraph by paragraph (tables included). A letter is
all-caps text when its paragraph is all-caps (every letter uppercase), or when it sits in a word of 2+ letters that
are all uppercase. Every other uppercase letter is ordinary-case text. The script counts uppercase letters that
became lowercase in each kind, and lists the ordinary-case words that were lowercased.

Run with the exp8 venv:
  /home/factory-user/venvs/exp8/bin/python ruling_d53ff5ee.py > ruling_d53ff5ee_output.txt
"""
import json
import os
import re
import zipfile
from xml.etree import ElementTree as ET

W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
INPUT = '/home/factory-user/exp8/run/699226e8/input/presentation_instruction_2023_Feb.docx'
EXEC = '/home/factory-user/exp8/exec'
CODES = ['699226e8', 'de97694c', 'a6cac88c', 'b9d8b59c']
WORD = re.compile(r'\S+')


def paragraphs(path):
    root = ET.fromstring(zipfile.ZipFile(path).read('word/document.xml'))
    return [''.join(t.text or '' for t in p.iter(W + 't')) for p in root.iter(W + 'p')]


def end_docx(code):
    return json.load(open(os.path.join(EXEC, code, 'result.json')))['end_state']


def all_caps_paragraph(text):
    letters = [ch for ch in text if ch.isalpha()]
    return bool(letters) and all(ch.isupper() for ch in letters)


def classify(orig, out):
    """Counts for one paragraph pair. Positions align when the lengths match (true for these files)."""
    stats = {'lowered_allcaps': 0, 'lowered_ordinary': 0, 'examples': []}
    para_caps = all_caps_paragraph(orig)
    for m in WORD.finditer(orig):
        w = m.group(0)
        letters = [ch for ch in w if ch.isalpha()]
        allcaps = para_caps or (len(letters) >= 2 and all(ch.isupper() for ch in letters))
        for i, ch in enumerate(w):
            j = m.start() + i
            if ch.isupper() and out[j].islower():
                if allcaps:
                    stats['lowered_allcaps'] += 1
                else:
                    stats['lowered_ordinary'] += 1
                    if len(stats['examples']) < 8:
                        stats['examples'].append(w)
    return stats


def main():
    inp = paragraphs(INPUT)
    caps = sum(all_caps_paragraph(p) for p in inp)
    print(f'input: {len(inp)} paragraphs (tables included), {caps} all-caps paragraphs, '
          f'{len(inp) - caps} other paragraphs')
    for code in CODES:
        out = paragraphs(end_docx(code))
        if len(out) != len(inp):
            print(f'{code}: paragraph count differs ({len(out)} vs {len(inp)}), not compared')
            continue
        changed = [(a, b) for a, b in zip(inp, out) if a != b]
        tot_caps = tot_ord = 0
        examples = []
        for a, b in changed:
            s = classify(a, b)
            tot_caps += s['lowered_allcaps']
            tot_ord += s['lowered_ordinary']
            examples += s['examples']
        kinds = (sum(all_caps_paragraph(a) for a, _ in changed), len(changed) - sum(all_caps_paragraph(a) for a, _ in changed))
        print(f'{code}: changed paragraphs {len(changed)} ({kinds[0]} all-caps, {kinds[1]} other); '
              f'uppercase letters lowered in all-caps text {tot_caps}; in ordinary-case text {tot_ord}')
        if examples:
            print(f'  ordinary-case words lowered (first examples): {", ".join(examples[:8])}')
        print(f'  lowers ordinary-case text: {"yes" if tot_ord else "no"}')


if __name__ == '__main__':
    main()
