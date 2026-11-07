"""Canonical tree for a directory state.

A state is a dict: relative path -> node. A node is one of
  {'kind': 'dir', 'mode'}
  {'kind': 'symlink', 'mode', 'target'}
  {'kind': 'file', 'mode', 'size', 'sha256', 'format', 'content'}     readable file
  {'kind': 'unreadable', 'mode', 'size', 'sha256', 'reason'}        no reader, held-out family, or parse error

The format is found from magic bytes first and the file name second, so a JPEG named .png is read as a JPEG.
'unreadable' is never treated as unchanged. diff.py reports such paths as UNVERIFIED.
"""
import functools
import gzip
import hashlib
import json
import os
import re
import stat
import tarfile
import zipfile

from . import readers_config as cfg
from . import readers_image
from . import readers_misc
from . import readers_office

# Held-out families: no reader is built, so their files are reported as unreadable.
HELD_OUT_PATTERNS = {
    'vlc': re.compile(r'(^|/)\.config/vlc(/|$)|(^|/)(vlcrc|vlc-qt-interface\.conf)$'),
}

RASTER_MAGIC = (b'\x89PNG', b'\xff\xd8\xff', b'GIF8', b'BM', b'RIFF')
MEDIA_EXT = ('.mp4', '.mov', '.mp3', '.m4a', '.wav', '.mkv', '.webm', '.avi')
TEXT_EXT_JSON = ('.json', '.jsonc', '.code-workspace')
TEXT_EXT_INI = ('.ini', '.conf', '.cfg', '.desktop', '.list')


def held_out_family(rel):
    for fam, pat in HELD_OUT_PATTERNS.items():
        if pat.search(rel):
            return fam
    return None


def _read(path, n=None):
    with open(path, 'rb') as f:
        return f.read() if n is None else f.read(n)


def _sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def parse_content(path, rel):
    """(format, content) for a readable file, or (None, reason) when no reader applies."""
    head = _read(path, 4096)
    name = os.path.basename(rel).lower()
    ext = os.path.splitext(name)[1]
    stamp = (os.stat(path).st_mtime_ns, os.path.getsize(path))
    if head.startswith(b'gimp xcf '):
        return 'xcf', readers_image.read_xcf(path, stamp)
    if head.startswith(RASTER_MAGIC):
        node = readers_image.read_raster(path)
        return 'raster', node
    if head.startswith(b'PK\x03\x04'):
        kind = readers_office.office_kind(path)
        if kind:
            return kind, readers_office.read_office(path, kind)
        return 'zip', readers_misc.read_archive(path, 'zip')
    if head.startswith(b'\xd0\xcf\x11\xe0'):
        if ext == '.xls':
            return 'xls', readers_office.read_office(path, 'xls')
        return None, 'OLE2 container with no reader'
    if head.startswith(b'\x1f\x8b'):
        with tarfile.open(path) as t:
            return 'tar.gz', readers_misc.read_archive(path, 'tar')
    if head.startswith(b'%PDF'):
        return 'pdf', readers_misc.read_pdf(path)
    if head.startswith(b'SQLite format 3\0'):
        return 'sqlite', readers_misc.read_sqlite(path)
    if head.startswith(b'mozLz40\0'):  # Mozilla LZ4: 8-byte magic, 4-byte little-endian size, LZ4 block
        return 'mozlz4', readers_misc.read_mozlz4(path)
    if ext in MEDIA_EXT or head[4:8] == b'ftyp' or head.startswith(b'ID3'):
        return 'media', readers_misc.read_media(path)
    if ext == '.msf':
        return 'derived_index', None  # Thunderbird rebuilds this index from the mbox; excluded and listed
    raw = _read(path)
    if name in ('prefs.js', 'user.js'):
        return 'prefs', cfg.read_prefs_js(raw.decode('utf-8', 'replace'))
    if name == 'msgfilterrules.dat':
        return 'msg_filter_rules', cfg.read_msg_filter_rules(raw.decode('utf-8', 'replace'))
    if ext in TEXT_EXT_JSON:
        return 'json', {'value': cfg.read_json(raw)}
    if ext == '.py':
        content = {'text': readers_misc.read_text(raw), 'ast': None, 'ast_error': None}
        try:
            content['ast'] = cfg.read_python(raw.decode('utf-8', 'replace'))
        except SyntaxError as e:  # broken source is still readable as text; the parse error is recorded
            content['ast_error'] = f'SyntaxError line {e.lineno}'
        return 'python', content
    if ext in TEXT_EXT_INI or name in ('mimeapps.list', 'gitconfig'):
        return 'ini', cfg.read_ini(raw.decode('utf-8', 'replace'))
    if name in ('gimprc',):
        return 'gimprc', cfg.read_gimprc(raw.decode('utf-8', 'replace'))
    if raw.startswith(b'From ') and ext == '':
        return 'mbox', readers_misc.read_mbox(path)
    try:
        return 'text', readers_misc.read_text(raw)
    except ValueError:
        return None, 'binary data with no reader'


def load_file(abs_path, rel):
    st = os.lstat(abs_path)
    mode = oct(stat.S_IMODE(st.st_mode))
    if stat.S_ISLNK(st.st_mode):
        return {'kind': 'symlink', 'mode': mode, 'target': os.readlink(abs_path)}
    if stat.S_ISDIR(st.st_mode):
        return {'kind': 'dir', 'mode': mode}
    if not stat.S_ISREG(st.st_mode):
        return {'kind': 'unreadable', 'mode': mode, 'size': None, 'sha256': None, 'reason': 'special file'}
    node = {'kind': 'file', 'mode': mode, 'size': st.st_size, 'sha256': _sha256(abs_path)}
    fam = held_out_family(rel)
    if fam:
        node.update(kind='unreadable', reason=f'held-out family {fam}: no reader built')
        return node
    try:
        fmt, content = parse_content(abs_path, rel)
    except Exception as e:  # a parse failure is a finding, never a silent pass
        node.update(kind='unreadable', reason=f'parse error: {type(e).__name__}: {str(e)[:160]}')
        return node
    if fmt is None:
        node.update(kind='unreadable', reason=content)
        return node
    if fmt == 'derived_index':
        node.update(kind='derived_index', reason='derived index, excluded from the nothing-else-changed scope')
        return node
    if fmt in ('raster', 'xcf'):
        content.setdefault('pixel_source', {'file': rel})
    node.update(format=fmt, content=content)
    return node


def dir_tree(root):
    """All entries under root: {relative path: node}. Symlinks are not followed."""
    tree = {}
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames.sort()
        for name in sorted(dirnames) + sorted(filenames):
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, root).replace(os.sep, '/')
            tree[rel] = load_file(full, rel)
    return tree


def unreadable_paths(tree):
    return sorted(p for p, n in tree.items() if n.get('kind') == 'unreadable')


def family_of(rel):
    """Coarse family label for a path, used by the validator's per-family report."""
    if held_out_family(rel):
        return held_out_family(rel)
    return 'other'
