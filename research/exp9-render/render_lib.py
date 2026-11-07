"""Exp 9 render pipeline. Frozen at the lock commit; see exp9-preregistration.md section 3.

Each state's office files are copied to a private work directory, converted to PDF by LibreOffice
(headless, a new user profile per state), and every page is rasterised to PNG at 150 dpi with PyMuPDF.
The judge packet is one directory per blind id:

    <out>/<bid>/request.txt      the request text, then the file list
    <out>/<bid>/start/fNN_pNNN.png   pages of the starting state
    <out>/<bid>/end/fNN_pNNN.png     pages of the end state

fNN numbers the files in sorted order of the relative paths present in either state. pNNN is the page
number inside that file, from 1. A file present on one side only has pages on that side only.
Inputs are read only: they are hashed before and after the render, and the run stops on any change.
"""
import hashlib
import os
import shutil
import struct
import subprocess
import time

import pymupdf

SOFFICE = '/usr/bin/soffice'
DPI = 150
SCALE = pymupdf.Matrix(DPI / 72, DPI / 72)
OFFICE_EXT = {'.docx', '.pptx', '.xlsx', '.odt', '.ods', '.odp'}
PNG_SIGNATURE = b'\x89PNG\r\n\x1a\n'
PNG_CHUNKS_ALLOWED = {'IHDR', 'pHYs', 'IDAT', 'IEND'}  # no text or metadata chunks
READ_LIMIT_BYTES = 5 * 1024 * 1024  # the judge's Read tool limit for images
CONVERT_TIMEOUT = 180
REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
SNAPSHOTS = os.path.join(REPO, 'research', 'exp5-grounded', 'snapshots')


def bid9(salt, task, state):
    """Fresh salted blind id. salt is the SALT text (the private file content without its final newline)."""
    return hashlib.sha256((salt + '|exp9|' + task + '|' + state).encode()).hexdigest()[:12]


def request_for(task):
    """The request text the Exp 6 and Exp 7 packets used for this task (same loader as judge_packets_exp7.py)."""
    import sys
    here = os.path.join(REPO, 'research', 'exp6-executed')
    sys.path.insert(0, here)
    sys.path.insert(0, os.path.join(REPO, 'research', 'exp5-grounded'))
    import judge_packets as jp
    return jp.load_requests()[task[:8]]


def list_files(root):
    """Sorted relative paths of every file under root. Every file must be an office document."""
    out = []
    for dp, dn, fn in os.walk(root):
        for f in fn:
            rel = os.path.relpath(os.path.join(dp, f), root)
            if os.path.splitext(f)[1].lower() not in OFFICE_EXT:
                raise ValueError(f'non-office file in {root}: {rel}')
            out.append(rel)
    return sorted(out)


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def tree_hashes(root):
    """[(relative path, sha256)] for every file under root, sorted by path."""
    return [(rel, sha256_file(os.path.join(root, rel))) for rel in list_files(root)]


def check_png(path):
    """Return the PNG chunk types. Raise if the file is not PNG or has a chunk outside the allowed set."""
    with open(path, 'rb') as fh:
        data = fh.read()
    if data[:8] != PNG_SIGNATURE:
        raise ValueError(f'{path}: not a PNG')
    kinds, i = [], 8
    while i < len(data):
        n = struct.unpack('>I', data[i:i + 4])[0]
        kinds.append(data[i + 4:i + 8].decode('latin1'))
        i += 12 + n
    bad = set(kinds) - PNG_CHUNKS_ALLOWED
    if bad:
        raise ValueError(f'{path}: unexpected PNG chunks {sorted(bad)}')
    return kinds


def soffice_to_pdf(src, out_dir, profile_dir):
    """Convert one office file to PDF. src must be a private copy: LibreOffice writes lock files next to it."""
    os.makedirs(out_dir, exist_ok=True)
    cmd = [SOFFICE, f'-env:UserInstallation=file://{profile_dir}', '--headless',
           '--convert-to', 'pdf', '--outdir', out_dir, src]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=CONVERT_TIMEOUT)
    pdf = os.path.join(out_dir, os.path.splitext(os.path.basename(src))[0] + '.pdf')
    if r.returncode != 0 or not os.path.isfile(pdf):
        raise RuntimeError(f'conversion failed for {src}: rc={r.returncode} {r.stderr[-300:]}')
    return pdf


def render_state(before_root, after_root, bid, request_text, out_root, work_root):
    """Render both sides of one state into the packet directory out_root/bid.

    Returns (stats, pdfs). pdfs maps (side, relative path) to the PDF path, for the renderability checks.
    """
    in_before = tree_hashes(before_root)
    in_after = tree_hashes(after_root)
    present = {'start': [r for r, _ in in_before], 'end': [r for r, _ in in_after]}
    rels = sorted(set(present['start']) | set(present['end']))
    num = {rel: i + 1 for i, rel in enumerate(rels)}
    roots = {'start': before_root, 'end': after_root}

    work = os.path.join(work_root, bid)
    shutil.rmtree(work, ignore_errors=True)
    profile = os.path.join(work, 'lo_profile')  # new profile for every state, so every timing has a cold start
    os.makedirs(profile)
    packet = os.path.join(out_root, bid)
    shutil.rmtree(packet, ignore_errors=True)
    os.makedirs(packet)

    pdfs, pages, png_bytes, pngs = {}, {'start': 0, 'end': 0}, 0, 0
    t0 = time.perf_counter()
    for side in ('start', 'end'):
        os.makedirs(os.path.join(packet, side))
        for rel in present[side]:
            n = num[rel]
            copy_dir = os.path.join(work, side, f'f{n:02d}')
            os.makedirs(copy_dir)
            src = os.path.join(copy_dir, os.path.basename(rel))
            shutil.copy2(os.path.join(roots[side], rel), src)
            pdf = soffice_to_pdf(src, os.path.join(copy_dir, 'pdf'), profile)
            pdfs[(side, rel)] = pdf
            doc = pymupdf.open(pdf)
            for p in range(doc.page_count):
                out_png = os.path.join(packet, side, f'f{n:02d}_p{p + 1:03d}.png')
                doc[p].get_pixmap(matrix=SCALE, alpha=False).save(out_png)
                check_png(out_png)
                size = os.path.getsize(out_png)
                if size > READ_LIMIT_BYTES:
                    raise ValueError(f'{out_png} is {size} bytes, over the judge read limit')
                png_bytes = max(png_bytes, size)
                pngs += 1
                pages[side] += 1
            doc.close()
    seconds = time.perf_counter() - t0
    shutil.rmtree(profile)

    if tree_hashes(before_root) != in_before or tree_hashes(after_root) != in_after:
        raise RuntimeError(f'input changed during render of {bid}')

    lines = [request_text.rstrip('\n'), '', 'Files (number, path inside the state, folders that hold its pages):']
    for rel in rels:
        sides = [s for s in ('start', 'end') if rel in present[s]]
        lines.append(f'f{num[rel]:02d}  {rel}  {", ".join(sides)}')
    with open(os.path.join(packet, 'request.txt'), 'w', encoding='utf-8') as fh:
        fh.write('\n'.join(lines) + '\n')

    stats = {'bid': bid, 'files_start': len(present['start']), 'files_end': len(present['end']),
             'pages_start': pages['start'], 'pages_end': pages['end'], 'pngs': pngs,
             'max_png_bytes': png_bytes, 'seconds': round(seconds, 3)}
    return stats, pdfs
