"""Evaluate Exp 5 must-predicates against canonical trees (the path-query layer and the evaluator).

The grammar parser is imported read-only from research/exp6-executed/specexec.py (frozen, not modified), so both
executors parse the same predicates. Only the readers differ: the names in the predicates resolve to views over
the canonical tree (see MAPPING.md). A name with no view raises Unsupported, and so does any value that depends
on state the tree cannot see (live apps, windows, network, unsaved edits, defaults that are not on disk).

Decision per spec, as in specexec: REJECT if any predicate FAILs, UNDECIDED if none FAILs but one is
UNSUPPORTED or ERROR, ACCEPT if all PASS. A predicate that reads an unreadable file is UNSUPPORTED, never PASS.
"""
import collections
import fnmatch
import hashlib
import importlib.util
import inspect
import os
import re
import urllib.parse

import numpy as np

from . import readers_image
from . import readers_misc
from . import readers_config as cfg
from .readers_office import FORMAT_KEYS, FORMAT_DEFAULTS, CELL_FORMAT_DEFAULTS

_HERE = os.path.dirname(os.path.abspath(__file__))
_SPECEXEC = os.path.join(_HERE, '..', 'exp6-executed', 'specexec.py')
_spec = importlib.util.spec_from_file_location('specexec_frozen', _SPECEXEC)
_frozen = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_frozen)
parse = _frozen.parse
strip_comment = _frozen.strip_comment
Unsupported = _frozen.Unsupported
ReaderMiss = _frozen.ReaderMiss


class Unknown:
    """A value the state does not determine (for example an unset pref whose default is not on disk)."""

    def __init__(self, reason):
        self.reason = reason

    def _fail(self, *a, **k):
        raise Unsupported(f'unknown value: {self.reason}')
    __eq__ = __ne__ = __lt__ = __le__ = __gt__ = __ge__ = __bool__ = __hash__ = _fail
    __contains__ = __iter__ = __len__ = _fail

    def __repr__(self):
        return f'<unknown: {self.reason}>'


class Seq(list):
    def at(self, n):
        if not isinstance(n, int) or not 1 <= n <= len(self):
            raise ReaderMiss(f'index {n} out of range (len {len(self)})')
        return self[n - 1]

    def span(self, a, b):
        return Seq(self[a - 1:(len(self) if b is None else b)])


class RowList(Seq):
    pass


class IntRange:
    def __init__(self, lo, hi):
        self.lo, self.hi = lo, hi

    def __contains__(self, x):
        return self.lo <= x <= self.hi

    def __iter__(self):
        return iter(range(self.lo, self.hi + 1))


class OneOf:
    def __init__(self, options):
        self.options = options

    def __eq__(self, other):
        return other in self.options


def getattr_(obj, name):
    if isinstance(obj, list):
        if name == 'texts':
            return [x.text for x in obj]
        return [getattr_(x, name) for x in obj]
    try:
        return getattr(obj, name)
    except AttributeError:
        raise Unsupported(f'no attribute {name!r} on {type(obj).__name__}')


# ---------------------------------------------------------------- state access

class StateTree:
    """A directory state with lookup by Ubuntu path. Created once per state."""

    def __init__(self, tree):
        self.tree = tree

    def get(self, ub_path, allow_dir=False):
        rel = ub_path.strip().lstrip('/')
        node = self.tree.get(rel)
        if node is None:
            raise ReaderMiss(f'no file {ub_path}')
        kind = node.get('kind')
        if kind == 'unreadable':
            raise Unsupported(f"unreadable: {node.get('reason')}")
        if kind == 'derived_index':
            raise Unsupported('derived index is not read')
        if kind == 'dir' and not allow_dir:
            raise Unsupported(f'{ub_path} is a directory')
        return node

    def content(self, ub_path, fmt_set):
        node = self.get(ub_path)
        if node.get('format') not in fmt_set:
            raise Unsupported(f"{ub_path} has format {node.get('format')}, not {sorted(fmt_set)}")
        return node

    def under(self, ub_prefix):
        pre = ub_prefix.strip().rstrip('/').lstrip('/')
        return sorted(p for p in self.tree if p == pre or p.startswith(pre + '/'))


class Ctx:
    """Evaluation context for one predicate. The sheet holder is shared across the predicates of one spec, as in
    specexec: a bare range() refers to the last sheet selected in that spec."""

    def __init__(self, end, start, root_end, root_start, sheet_holder):
        self.end, self.start = end, start
        self.root_end, self.root_start = root_end, root_start
        self.cur, self.cur_root = end, root_end
        self.in_before = 0
        self.opened = []            # (ubuntu path, document, opened inside before())
        self.vacuous = []           # all() calls with no values in this predicate (logged)
        self.strict_empty = False   # counterfactual pass: such an all() is UNSUPPORTED (Amendment 2 rule)
        self.proxy = False          # a value came from a saved file standing in for a live document
        self.sheet_holder = sheet_holder

    def st(self):
        return self.cur

    def root(self):
        return self.cur_root

    def open(self, ub_path, doc):
        self.opened.append((ub_path, doc, self.in_before > 0))
        return doc


# ---------------------------------------------------------------- views: calc

class CellView:
    def __init__(self, node):
        node = node or {}
        self.value = node.get('value')
        self.formula = node.get('formula')
        self.text = node.get('text', self.value)
        for k in FORMAT_KEYS:
            setattr(self, k, node.get(k, CELL_FORMAT_DEFAULTS[k]))
        self.fill = self.background_color


def _a1(ref):
    m = re.match(r'([A-Z]+)(\d+)$', ref)
    col = 0
    for ch in m.group(1):
        col = col * 26 + ord(ch) - 64
    return int(m.group(2)), col


def _nonempty(v):
    return v not in (None, '')


class RangeView:
    def __init__(self, sheet, ref):
        self.sheet = sheet
        self.ref = ref.replace('$', '')
        if ':' in self.ref:
            a, b = self.ref.split(':')
        else:
            a = b = self.ref
        self.r0, self.c0 = _a1(a)
        self.r1, self.c1 = _a1(b)

    def _grid(self, field):
        default = CELL_FORMAT_DEFAULTS.get(field)
        rows = []
        for r in range(self.r0, self.r1 + 1):
            row = []
            for c in range(self.c0, self.c1 + 1):
                cell = self.sheet.cells.get(f'{_col(c)}{r}')
                row.append(default if cell is None else cell.get(field, default))
            rows.append(row)
        if len(rows) == 1:
            return rows[0]
        if rows and all(len(x) == 1 for x in rows):
            return [x[0] for x in rows]
        return rows

    @property
    def values(self):
        return self._grid('value')

    @property
    def formulas(self):
        return self._grid('formula')

    @property
    def coords(self):
        return {f'{_col(c)}{r}' for r in range(self.r0, self.r1 + 1) for c in range(self.c0, self.c1 + 1)}

    @property
    def nonempty_cells(self):
        out = []
        for ref in sorted(self.coords, key=_a1):
            cell = self.sheet.cells.get(ref)
            if cell is not None and _nonempty(cell.get('value')):
                out.append(ref)
        return out


def _col(n):
    s = ''
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def _grid_property(field):
    return property(lambda self: self._grid(field))


# range(ref).bold, .italic, ..., .fill: the formatting of each cell, in the same grid shape as .values
for _k in FORMAT_KEYS:
    setattr(RangeView, _k, _grid_property(_k))
RangeView.fill = _grid_property('background_color')


class ZeroList(list):
    """Chart series: indexed from 0, as the specs write them (series[0] is the first series). Same as specexec."""

    def at(self, n):
        return self[n]


class SeriesView:
    def __init__(self, book, ser):
        self.book, self.ser = book, ser

    @property
    def values(self):
        """Plotted values, flattened row-major (as specexec.SeriesObj.values)."""
        ref = self.ser.get('ref')
        if not ref or '!' not in ref:
            return self.ser.get('cached_values')
        sheet_part, rng = ref.rsplit('!', 1)
        name = sheet_part.strip("'").replace("''", "'")
        if name not in self.book.node.get('sheets', {}):
            raise ReaderMiss(f'no sheet {name!r}')
        # Not via CalcBook.sheet(): a series lookup does not select the sheet for bare range() (as in specexec).
        sheet = CalcSheet(self.book, name, self.book.node['sheets'][name])
        grid = RangeView(sheet, rng)._grid('value')
        return [v for row in grid for v in (row if isinstance(row, list) else [row])]


class ChartView:
    def __init__(self, book, ch):
        self.book, self.ch = book, ch
        self.type = ch.get('type')
        self.title = ch.get('title')
        self.series = ZeroList(SeriesView(book, s) for _, s in sorted(ch.get('series', {}).items(), key=lambda kv: int(kv[0])))


class PivotView:
    def __init__(self, p):
        self.row_fields = p.get('row_fields', [])
        self.data_fields = p.get('data_fields', [])
        self.name = p.get('name')


class CalcSheet:
    def __init__(self, book, name, node):
        self.book, self.name = book, name
        self.cells = {k: v for k, v in node.get('cells', {}).items()}
        self.hidden_rows = node.get('hidden_rows', [])
        self.hidden_columns = node.get('hidden_columns', [])
        self.autofilter = node.get('autofilter')
        self._charts = node.get('charts', {})
        self._pivots = node.get('pivot_tables', {})

    def _bbox(self):
        refs = [(_a1(r)) for r, c in self.cells.items() if _nonempty(c.get('value'))]
        if not refs:
            return None
        rows = [r for r, _ in refs]
        cols = [c for _, c in refs]
        return min(rows), min(cols), max(rows), max(cols)

    def _grid(self, field):
        box = self._bbox()
        if box is None:
            return []
        r0, c0, r1, c1 = box
        return RangeView(self, f'{_col(c0)}{r0}:{_col(c1)}{r1}')._grid(field)

    @property
    def values(self):
        return self._grid('value')

    @property
    def formulas(self):
        return self._grid('formula')

    @property
    def nonempty_cells(self):
        refs = [r for r, c in self.cells.items() if _nonempty(c.get('value'))]
        return sorted(refs, key=_a1)

    @property
    def used_range(self):
        box = self._bbox()
        return None if box is None else f'{_col(box[1])}{box[0]}:{_col(box[3])}{box[2]}'

    @property
    def pivot_tables(self):
        return Seq(PivotView(p) for _, p in sorted(self._pivots.items(), key=lambda kv: int(kv[0])))

    def cell(self, ref):
        return CellView(self.cells.get(ref))

    def range(self, ref):
        return RangeView(self, ref)


class CalcBook:
    def __init__(self, node, ctx):
        self.node = node
        self.ctx = ctx

    @property
    def sheet_names(self):
        return list(self.node.get('sheet_names', []))

    def sheet(self, name):
        if name not in self.node.get('sheets', {}):
            raise ReaderMiss(f'no sheet {name!r}')
        sh = CalcSheet(self, name, self.node['sheets'][name])
        self.ctx.sheet_holder['sheet'] = sh  # a bare range('B1:C29') in the same spec refers to this sheet
        return sh

    @property
    def charts(self):
        out = []
        for name in self.sheet_names:
            for _, ch in sorted(self.node['sheets'][name].get('charts', {}).items(), key=lambda kv: int(kv[0])):
                out.append(ChartView(self, ch))
        return out


# ---------------------------------------------------------------- views: writer / impress

class RunView:
    def __init__(self, d):
        self.text = d.get('text', '')
        for k in FORMAT_KEYS:
            setattr(self, k, d.get(k, FORMAT_DEFAULTS[k]))
        self.fill = self.background_color


class ParaView:
    def __init__(self, idx, d):
        self.index = int(idx)
        self.text = d.get('text', '')
        self.style = d.get('style')
        self.alignment = d.get('alignment')
        self.background_color = d.get('background_color')
        self.fill = self.background_color
        self.runs = Seq(RunView(r) for _, r in sorted(d.get('runs', {}).items(), key=lambda kv: int(kv[0])))

    def __eq__(self, o):
        return isinstance(o, ParaView) and o.text == self.text

    def __repr__(self):
        return f'P{self.index}({self.text[:30]!r})'


class TableCell:
    def __init__(self, text, background_color=None):
        self.text = text
        self.background_color = background_color
        self.fill = background_color


class TableView:
    def __init__(self, idx, d):
        self.index = int(idx)
        self._rows = d.get('rows', {})
        self.columns = d.get('columns', 0)

    @property
    def rows(self):
        return RowList(Seq(TableCell(c.get('text', ''), c.get('background_color')) for _, c in sorted(r.get('cells', {}).items(), key=lambda kv: int(kv[0])))
                       for _, r in sorted(self._rows.items(), key=lambda kv: int(kv[0])))

    @property
    def cells(self):
        return Seq(c for row in self.rows for c in row)

    def __eq__(self, o):
        return isinstance(o, TableView) and [[c.text for c in r] for r in self.rows] == [[c.text for c in r] for r in o.rows]


class PageView:
    def __init__(self, text, n_images):
        self.text = text
        self.objects = [None] * (n_images or 0)


class PageList:
    def __init__(self, pages):
        self.pages = pages

    @property
    def count(self):
        return len(self.pages)

    def at(self, n):
        if not 1 <= n <= len(self.pages):
            raise ReaderMiss(f'page {n} out of range')
        return self.pages[n - 1]

    def span(self, a, b):
        return self.pages[a - 1:(len(self.pages) if b is None else b)]


class WriterDoc:
    def __init__(self, node, ctx, path_abs, stamp):
        self.node = node
        self.ctx = ctx
        self.path_abs = path_abs
        self.stamp = stamp
        self.paragraphs = Seq(ParaView(i, d) for i, d in sorted(node.get('paragraphs', {}).items(), key=lambda kv: int(kv[0])))
        self.tables = Seq(TableView(i, d) for i, d in sorted(node.get('tables', {}).items(), key=lambda kv: int(kv[0])))

    def paragraph(self, n):
        return self.paragraphs.at(n)

    def table(self, n):
        return self.tables.at(n)

    @property
    def body_order(self):
        out = []
        for kind, i in self.node.get('body_order', []):
            out.append(self.paragraphs.at(i) if kind == 'p' else self.tables.at(i))
        return Seq(out)

    @property
    def all_text(self):
        parts = [p.text for p in self.paragraphs] + [c.text for t in self.tables for c in t.cells]
        return '\n'.join(parts)

    @property
    def text_runs(self):
        return Seq(r for p in self.paragraphs for r in p.runs)

    def text_run_containing(self, s):
        for r in self.text_runs:
            if s in r.text:
                return r
        raise ReaderMiss(f'no run containing {s!r}')

    def text_lines_before_paragraph_with_text(self, s):
        for i, p in enumerate(self.paragraphs):
            if s in p.text:
                return [q.text for q in self.paragraphs[:i]]
        raise ReaderMiss(f'no paragraph containing {s!r}')

    def paragraphs_from_text(self, s):
        for i, p in enumerate(self.paragraphs):
            if s in p.text:
                return Seq(self.paragraphs[i:])
        raise ReaderMiss(f'no paragraph containing {s!r}')

    @property
    def rendered_pages(self):
        """Pages as LibreOffice lays them out (readers_misc.render_pages). The saved file is the state itself."""
        return PageList([PageView(text, n) for text, n in readers_misc.render_pages(self.path_abs, self.stamp)])


class ShapeView:
    def __init__(self, d):
        self.name = d.get('name')
        self.kind = d.get('kind')
        self.text = d.get('text', '')
        self.has_text = bool(self.text.strip())
        self.height_cm = d.get('height_cm')
        self.width_cm = d.get('width_cm')
        self.left = d.get('x_cm')
        self.top = d.get('y_cm')
        self.picture_fill = d.get('picture_fill', False)
        self.background_color = d.get('background_color')
        self.fill = self.background_color
        self.paragraphs = Seq(ParaP(i, p) for i, p in sorted(d.get('paragraphs', {}).items(), key=lambda kv: int(kv[0])))

    def paragraph(self, n):
        return self.paragraphs.at(n)

    @property
    def text_runs(self):
        return Seq(r for p in self.paragraphs for r in p.runs)

    def _snap(self):
        # Paragraph text and bullet types are part of the shape: a bullet added to a title changes the shape.
        return (self.name, self.left, self.top, self.width_cm, self.height_cm, self.text, self.background_color,
                [r.color for r in self.text_runs],
                [(p.text, p.bullet.type) for p in self.paragraphs])

    def __eq__(self, o):
        return isinstance(o, ShapeView) and o._snap() == self._snap()

    def __repr__(self):
        return f'Shape({self.name!r})'


class BulletView:
    def __init__(self, t):
        self.type = t


class ParaP:
    def __init__(self, idx, d):
        self.index = int(idx)
        self.text = d.get('text', '')
        self.bullet = BulletView(d.get('bullet', 'inherited'))
        self.alignment = d.get('alignment')
        self.background_color = d.get('background_color')
        self.fill = self.background_color
        self.runs = Seq(RunView(r) for _, r in sorted(d.get('runs', {}).items(), key=lambda kv: int(kv[0])))


class SlideView:
    def __init__(self, idx, d):
        self.index = int(idx)
        self._d = d
        self.shapes = Seq(ShapeView(d['shapes'][k]) for k in d.get('shape_order', []))
        self.transition = _Transition(d.get('transition'))

    def shape(self, name):
        for sh in self.shapes:
            if sh.name == name:
                return sh
        raise ReaderMiss(f'no shape {name!r} on slide {self.index}')

    @property
    def pictures(self):
        return Seq(sh for sh in self.shapes if sh.kind == 'picture' or sh.picture_fill)

    def __eq__(self, o):
        return isinstance(o, SlideView) and [s._snap() for s in self.shapes] == [s._snap() for s in o.shapes] \
            and self.transition == o.transition


class _Transition:
    def __init__(self, t):
        self.type = t

    def __eq__(self, o):
        return isinstance(o, _Transition) and o.type == self.type


class ImpressDoc:
    def __init__(self, node, ctx):
        self.node = node
        self.ctx = ctx
        self.slides = Seq(SlideView(i, d) for i, d in sorted(node.get('slides', {}).items(), key=lambda kv: int(kv[0])))

    @property
    def slide_count(self):
        return len(self.slides)

    def slide(self, n):
        return self.slides.at(n)


# ---------------------------------------------------------------- views: files, OS, images, GIMP, config

class FileView:
    def __init__(self, node, ub_path):
        self.node = node
        self.ub_path = ub_path

    @property
    def sha256(self):
        return self.node.get('sha256')

    @property
    def size(self):
        return self.node.get('size')

    @property
    def mode(self):
        return int(self.node.get('mode', '0o0'), 8)

    @property
    def exists(self):
        return True

    @property
    def text(self):
        content = self.node.get('content') or {}
        if self.node.get('format') != 'text':
            raise Unsupported(f'{self.ub_path} is not a text file')
        return '\n'.join(content['lines'][k] for k in sorted(content['lines'], key=int))

    def __eq__(self, o):
        return isinstance(o, FileView) and o.sha256 == self.sha256

    def __ne__(self, o):
        return not self.__eq__(o)


class OsFile:
    def __init__(self, node):
        self.node = node

    @property
    def mode(self):
        return int(self.node.get('mode', '0o0'), 8)


class OsTree:
    def __init__(self, st, ub):
        self.st, self.ub = st, ub

    def _entries(self):
        pre = self.ub.rstrip('/').lstrip('/')
        if pre and pre not in self.st.tree:
            raise ReaderMiss(f'no directory {self.ub}')
        return self.st.under(self.ub)

    @property
    def paths(self):
        return sorted('/' + p for p in self._entries())

    @property
    def regular_files(self):
        return Seq(OsFile(self.st.tree[p]) for p in self._entries() if self.st.tree[p].get('kind') == 'file')


class FsTree:
    def __init__(self, st, ub):
        self.st, self.ub = st, ub

    def __eq__(self, o):
        return isinstance(o, FsTree) and self._map() == o._map()

    def _map(self):
        out = {}
        for p in self.st.under(self.ub):
            node = self.st.tree[p]
            out[p[len(self.ub.strip('/')):].lstrip('/')] = node.get('sha256') or node.get('kind')
        return out


class ImageView:
    def __init__(self, node, ub):
        self.node = node
        self.ub = ub

    @property
    def format(self):
        return self.node.get('format')

    @property
    def width(self):
        return self.node.get('width')

    @property
    def height(self):
        return self.node.get('height')

    @property
    def sha256(self):
        h = self.node.get('pixels_sha256')
        if h is None:
            # None means the pixels could not be decoded. Two None values must not compare equal.
            raise Unsupported(f"pixels not decoded: {self.node.get('pixels_unreadable', 'no pixel hash')}")
        return h

    @property
    def is_decodable(self):
        return True

    def __eq__(self, o):
        return isinstance(o, ImageView) and o.sha256 == self.sha256

    def __ne__(self, o):
        return not self.__eq__(o)


class PixelsView:
    def __init__(self, arr):
        self.arr = arr

    def __eq__(self, o):
        return isinstance(o, PixelsView) and self.arr.shape == o.arr.shape and np.array_equal(self.arr, o.arr)

    def __ne__(self, o):
        return not self.__eq__(o)


class LayerView:
    def __init__(self, doc, idx, node):
        self.doc, self.idx, self.node = doc, idx, node
        self.name = node.get('name')
        self.width = node.get('width')
        self.height = node.get('height')
        self.offset_x = node.get('offset_x', 0)
        self.offset_y = node.get('offset_y', 0)
        self.text = node.get('text')

    @property
    def size(self):
        return [self.width, self.height]

    @property
    def offsets(self):
        return [self.offset_x, self.offset_y]

    @property
    def pixels(self):
        return PixelsView(self.doc.layer_arr(self.idx))


class LayersView:
    def __init__(self, doc):
        self.doc = doc

    @property
    def names(self):
        return [self.doc.layers[str(i)]['name'] for i in range(1, len(self.doc.layers) + 1)]


class CompositeView:
    def __init__(self, doc):
        self.doc = doc

    @property
    def pixels(self):
        return PixelsView(self.doc.composite_arr())


class GimpDoc:
    """A GIMP document read from its saved file. The live document is not visible: this is a proxy."""

    def __init__(self, content, fmt, ctx, path_abs, stamp):
        self.node = content
        self.ctx = ctx
        self.path_abs = path_abs
        self.stamp = stamp
        self.is_xcf = fmt == 'xcf'
        ctx.proxy = True
        self.layers = content.get('layers', {}) if self.is_xcf else {}

    @property
    def size(self):
        return [self.node['width'], self.node['height']]

    @property
    def base_type(self):
        return self.node.get('base_type')

    @property
    def colormap(self):
        cm = self.node.get('colormap')
        if cm is None:
            raise Unsupported('no colormap (not an indexed image)')
        return cm

    def layer(self, name):
        for i in range(1, len(self.layers) + 1):
            if self.layers[str(i)]['name'] == name:
                return LayerView(self, i, self.layers[str(i)])
        raise ReaderMiss(f'no layer {name!r}')

    @property
    def layers_view(self):
        return LayersView(self)

    def layer_arr(self, idx):
        if not self.is_xcf:
            raise Unsupported('layer pixels of a non-XCF image')
        try:
            return readers_image.layer_pixels(self.path_abs, self.stamp, idx)
        except readers_image.XcfUnsupported as e:
            raise Unsupported(f'layer pixels not decoded: {e}')

    def composite_arr(self):
        if self.is_xcf:
            try:
                return readers_image.composite(self.path_abs, self.stamp)
            except readers_image.XcfUnsupported as e:
                raise Unsupported(f'composite not decoded: {e}')
        return readers_image.load_pixels(self.path_abs)

    @property
    def composite(self):
        return CompositeView(self)


class SettingsView:
    """Effective VS Code setting: workspace over user over the built-in default (not on disk: UNKNOWN)."""

    def __init__(self, user, workspace=None):
        self.user, self.workspace = user or {}, workspace or {}

    def get(self, key, default=None):
        val, _src = cfg.vscode_effective(key, self.user, self.workspace)
        if val == cfg.UNKNOWN_DEFAULT:
            return Unknown(f'vscode {key}: no user or workspace value and the built-in default is not on disk')
        return val


class JsonDoc:
    def __init__(self, value):
        self.value = value

    def __getattr__(self, name):
        if name.startswith('__'):
            raise AttributeError(name)
        v = self.value
        if isinstance(v, dict) and name in v:
            return _wrap(v[name])
        raise Unsupported(f'no key {name!r} in JSON document')

    def __eq__(self, o):
        return isinstance(o, JsonDoc) and o.value == self.value

    def __ne__(self, o):
        return not self.__eq__(o)


def _wrap(v):
    if isinstance(v, dict):
        return JsonDoc(v)
    if isinstance(v, list):
        return Seq(_wrap(x) for x in v)
    return v


class PrefsView:
    def __init__(self, user):
        self.user = user

    def __getitem__(self, key):
        if key in self.user:
            return self.user[key]
        return Unknown(f'pref {key}: not set in prefs.js and the default is not on disk')

    def matching(self, pattern):
        return {k: v for k, v in self.user.items() if fnmatch.fnmatch(k, pattern)}


class RuleView:
    def __init__(self, d):
        self.name = d.get('name')
        self.enabled = d.get('enabled')
        self.type = d.get('type')
        self.condition = d.get('condition')
        self.matches_all_messages = d.get('matches_all_messages', False)
        self.actions = Seq(ActionView(a) for _, a in sorted(d.get('actions', {}).items(), key=lambda kv: int(kv[0])))


class ActionView:
    def __init__(self, a):
        self.action = a.get('action')
        self.value = a.get('value')


class MessageView:
    def __init__(self, d):
        self.subject = d.get('subject')
        self.flagged = d.get('flagged')
        self.read = d.get('read')
        self.tags = d.get('tags')
        self.body = d.get('body')
        self.from_ = d.get('from')
        self.to = d.get('to')
        self.cc = d.get('cc')
        self.bcc = d.get('bcc')
        self.date = d.get('date')


class FolderView:
    def __init__(self, messages):
        self._messages = messages

    @property
    def messages(self):
        return Seq(MessageView(m) for _, m in sorted(self._messages.items(), key=lambda kv: int(kv[0])))


class Unreadable:
    """Placeholder root for a held-out family (VLC): every access and every comparison is UNSUPPORTED."""

    def __init__(self, family):
        self.family = family

    def _fail(self, *a, **k):
        raise Unsupported(f'{self.family}: held-out family, UNREADABLE (no reader built)')

    __len__ = __iter__ = __contains__ = __bool__ = __eq__ = __ne__ = __lt__ = __le__ = __gt__ = __ge__ = _fail
    __hash__ = _fail

    def __getattr__(self, name):
        if name.startswith('__'):
            raise AttributeError(name)
        raise Unsupported(f'{self.family}: no reader built (held-out family)')

    def __call__(self, *a, **k):
        raise Unsupported(f'{self.family}: no reader built (held-out family)')


class NoReader:
    """Placeholder for a family whose state is not in a file tree. Any use is UNSUPPORTED, including len(), iteration
    and comparison (so a predicate over it is UNDECIDED, not an executor error)."""

    def __init__(self, family):
        self.family = family

    def _fail(self, *a, **k):
        raise Unsupported(f'{self.family}: live or external state, no file reader')

    __len__ = __iter__ = __contains__ = __bool__ = __eq__ = __ne__ = __lt__ = __le__ = __gt__ = __ge__ = _fail
    __hash__ = _fail

    def __getattr__(self, name):
        if name.startswith('__'):
            raise AttributeError(name)
        raise Unsupported(f'{self.family}.{name}: live or external state, no file reader')

    def __call__(self, *a, **k):
        raise Unsupported(f'{self.family}(): live or external state, no file reader')


class _NS:
    def __init__(self, **kw):
        self.__dict__.update(kw)


def _calc_file(ctx):
    def f(p):
        node = ctx.st().content(p, {'xlsx', 'xls', 'ods'})
        return ctx.open(p, CalcBook(node['content'], ctx))
    return f


def _writer_file(ctx):
    def f(p):
        node = ctx.st().content(p, {'docx', 'odt'})
        path = os.path.join(ctx.root(), p.lstrip('/'))
        return ctx.open(p, WriterDoc(node['content'], ctx, path, _stamp(path)))
    return f


def _impress_file(ctx):
    def f(p):
        node = ctx.st().content(p, {'pptx', 'odp'})
        return ctx.open(p, ImpressDoc(node['content'], ctx))
    return f


def _libreoffice(ctx):
    return _NS(calc=_NS(file=_calc_file(ctx)), writer=_NS(file=_writer_file(ctx)),
               impress=_NS(file=_impress_file(ctx)),
               config=NoReader('libreoffice.config'))


def _os_root(ctx):
    def file_(p):
        st = ctx.st()
        if p.strip('/') not in st.tree:
            raise ReaderMiss(f'no file {p}')
        return OsFile(st.tree[p.strip('/')])
    return _NS(file=file_, tree=lambda p: OsTree(ctx.st(), p), user=NoReader('os.user'),
               service=NoReader('os.service'), processes=NoReader('os.processes'))


def _filesystem(ctx):
    def file_(p):
        node = ctx.st().get(p)
        return FileView(node, p)

    def dir_(p):
        st = ctx.st()
        if p.strip('/') not in st.tree and not st.under(p):
            raise ReaderMiss(f'no directory {p}')
        return _NS(exists=True, path=p)
    return _NS(file=file_, dir=dir_, tree=lambda p: FsTree(ctx.st(), p), find=NoReader('filesystem.find'))


def _gimp(ctx):
    def live_document(p):
        node = ctx.st().get(p)
        if node.get('format') not in ('xcf', 'raster'):
            raise Unsupported(f"{p} is not a GIMP document")
        path = os.path.join(ctx.root(), p.lstrip('/'))
        return GimpDoc(node['content'], node['format'], ctx, path, _stamp(path))
    return _NS(live_document=live_document, document=live_document,
               preferences=NoReader('gimp.preferences'), ui=NoReader('gimp.ui'))


def _stamp(path):
    st = os.stat(path)
    return (st.st_mtime_ns, st.st_size)


class ImageRoot:
    def __init__(self, ctx):
        self.ctx = ctx

    def file(self, p):
        node = self.ctx.st().get(p)
        if node.get('format') not in ('raster', 'xcf'):
            raise Unsupported(f'{p} is not an image')
        return ImageView(node['content'], p)

    def __call__(self, p):
        return self.file(p)


def _json_root(ctx):
    def file_(p):
        node = ctx.st().content(p, {'json'})
        return JsonDoc(node['content']['value'])
    return _NS(file=file_)


def _vscode(ctx):
    def user_settings(p):
        node = ctx.st().content(p, {'json'})
        return SettingsView(node['content']['value'])

    def user_keybindings(p):
        node = ctx.st().content(p, {'json'})
        return Seq(_KB(x) for x in node['content']['value'])
    return _NS(user_settings=user_settings, user_keybindings=user_keybindings,
               extensions=NoReader('vscode.extensions'), windows=NoReader('vscode.windows'),
               keybindings=NoReader('vscode.keybindings.resolve'))


class _KB:
    def __init__(self, d):
        self.key = d.get('key')
        self.command = d.get('command')
        self.when = d.get('when')


def _thunderbird(ctx):
    def profile(p):
        st = ctx.st()
        prefs_node = st.get(p.rstrip('/') + '/prefs.js')
        return _NS(prefs=PrefsView(prefs_node['content']['user_prefs']))

    def filters(p):
        node = ctx.st().content(p, {'msg_filter_rules'})
        return _NS(rules=Seq(RuleView(r) for _, r in sorted(node['content']['rules'].items(), key=lambda kv: int(kv[0]))))

    def folder(uri):
        # mailbox://nobody@Local%20Folders/Bills  ->  <profile>/Mail/Local Folders/Bills
        name = urllib.parse.unquote(uri.split('@', 1)[-1])
        st = ctx.st()
        hits = [p for p in st.tree if p.endswith('/Mail/' + name) or p == 'Mail/' + name]
        if len(hits) != 1:
            raise Unsupported(f'folder {uri}: {len(hits)} matches in the state')
        node = st.get('/' + hits[0])
        if node.get('format') != 'mbox':
            raise Unsupported(f"folder {uri}: {hits[0]} is {node.get('format') or node.get('kind')}, not an mbox")
        return FolderView(node['content']['messages'])
    return _NS(profile=profile, filters=filters, folder=folder,
               all_messages=NoReader('thunderbird.all_messages'),
               sent_messages_since=NoReader('thunderbird.sent_messages_since'),
               compose_windows=NoReader('thunderbird.compose_windows'), ui=NoReader('thunderbird.ui'))


def _gsettings(ctx):
    def g(schema, key):
        # The dconf database is binary and not read; a schema default is not evidence of the effective value.
        return Unknown(f'gsettings {schema} {key}: the dconf database is not read (schema default {_schema_default(schema, key)!r})')
    return g


def _schema_default(schema, key):
    v = cfg.gsettings_schema_defaults().get(schema, {}).get(key, cfg.UNKNOWN_DEFAULT)
    return v


def build_roots(ctx):
    roots = {
        'libreoffice': _libreoffice(ctx),
        'os': _os_root(ctx),
        'filesystem': _filesystem(ctx),
        'fs': _filesystem(ctx),
        'gimp': _gimp(ctx),
        'image': ImageRoot(ctx),
        'json': _json_root(ctx),
        'vscode': _vscode(ctx),
        'thunderbird': _thunderbird(ctx),
        'gsettings': _gsettings(ctx),
        'gnome': _NS(gsettings=_gsettings(ctx)),
        'vlc': Unreadable('vlc'),
        'probe': NoReader('probe'), 'run': NoReader('run'), 'terminal': NoReader('terminal'),
        'googledrive': NoReader('googledrive'), 'outlook': NoReader('outlook'), 'imap': NoReader('imap'),
        'chrome': NoReader('chrome'), 'desktop': NoReader('desktop'), 'display': NoReader('display'),
        'session': NoReader('session'), 'snap': NoReader('snap'), 'apt': NoReader('apt'),
        'flatpak': NoReader('flatpak'), 'xdg_mime': NoReader('xdg_mime'), 'git': NoReader('git'),
        'python_ast': NoReader('python_ast'), 'pdf': NoReader('pdf'), 'video': NoReader('video'),
        'script': NoReader('script'), 'forum': NoReader('forum'), 'mail': NoReader('mail'),
    }
    return roots


# ---------------------------------------------------------------- builtins

def _as_str_list(fn, x):
    return [fn(i) for i in x] if isinstance(x, list) else fn(x)


def _collapse(s):
    return re.sub(r'\s+', ' ', s)


def _proper_word(w):
    out, done = [], False
    for ch in w:
        if not done and ch.isalpha():
            out.append(ch.upper())
            done = True
        else:
            out.append(ch.lower() if ch.isalpha() else ch)
    return ''.join(out)


# specexec's builtins (lower, trim, collapse_whitespace, proper_case, replace, len, count) plus the helpers the
# universal reader needs for file and state values. Each extra is listed in MAPPING.md.
FUNCS = {
    'lower': lambda x: _as_str_list(lambda s: s.lower(), x),
    'trim': lambda x: _as_str_list(lambda s: s.strip(), x),
    'collapse_whitespace': lambda x: _as_str_list(_collapse, x),
    'proper_case': lambda x: _as_str_list(lambda s: ' '.join(_proper_word(w) for w in _collapse(s).split(' ')), x),
    'replace': lambda x, a, b: _as_str_list(lambda s: s.replace(a, b), x),
    'len': len,
    'count': len,
    'exists': lambda x: x is not None,
    'basename': lambda p: os.path.basename(p),
    'uri_to_path': lambda uri: urllib.parse.unquote(uri.replace('file://', '')),
    'urldecode': lambda s: urllib.parse.unquote(s),
    'join': lambda xs, sep='': sep.join(xs),
}


# ---------------------------------------------------------------- evaluator

def lookup(name, env, ctx, roots):
    """Same order as specexec: predicate variables, range(), builtins, reader roots, then the methods of the one
    document the predicate opened outside before(). Document properties are not reachable bare (methods only)."""
    if name in env:
        return env[name]
    if name == 'range':
        def bare_range(ref):
            sh = ctx.sheet_holder['sheet']
            if sh is None:
                raise Unsupported('range() with no sheet selected')
            return sh.range(ref)
        return bare_range
    if name in FUNCS:
        return FUNCS[name]
    if name in roots:
        return roots[name]
    docs = {p: o for p, o, in_before in ctx.opened if not in_before}
    if len(docs) == 1:
        obj = next(iter(docs.values()))
        if not name.startswith('_') and inspect.isfunction(getattr(type(obj), name, None)):
            return getattr(obj, name)
    raise Unsupported(f'unknown name {name!r}')


def ev(n, env, ctx, roots):
    k = n[0]
    if k == 'lit':
        return n[1]
    if k == 'name':
        return lookup(n[1], env, ctx, roots)
    if k == 'attr':
        return getattr_(ev(n[1], env, ctx, roots), n[2])
    if k == 'list':
        return [ev(x, env, ctx, roots) for x in n[1]]
    if k == 'set':
        return {ev(x, env, ctx, roots) for x in n[1]}
    if k == 'oneof':
        return OneOf(ev(n[1], env, ctx, roots))
    if k == 'range':
        return IntRange(ev(n[1], env, ctx, roots), ev(n[2], env, ctx, roots))
    if k == 'star':
        return ev(n[1], env, ctx, roots)
    if k == 'index':
        obj, idx = ev(n[1], env, ctx, roots), ev(n[2], env, ctx, roots)
        if hasattr(obj, 'at'):
            return obj.at(idx)
        if isinstance(obj, list):
            return Seq(obj).at(idx)
        return obj[idx]
    if k == 'span':
        obj = ev(n[1], env, ctx, roots)
        a = ev(n[2], env, ctx, roots)
        b = None if n[3] is None else ev(n[3], env, ctx, roots)
        if hasattr(obj, 'span'):
            return obj.span(a, b)
        return Seq(obj).span(a, b)
    if k == 'arith':
        a, b = ev(n[2], env, ctx, roots), ev(n[3], env, ctx, roots)
        return {'+': lambda: a + b, '-': lambda: a - b, '*': lambda: a * b, '/': lambda: a / b}[n[1]]()
    if k == 'not':
        return not ev(n[1], env, ctx, roots)
    if k == 'and':
        return bool(ev(n[1], env, ctx, roots)) and bool(ev(n[2], env, ctx, roots))
    if k == 'or':
        return bool(ev(n[1], env, ctx, roots)) or bool(ev(n[2], env, ctx, roots))
    if k == 'cmp':
        a, b = ev(n[2], env, ctx, roots), ev(n[3], env, ctx, roots)
        op = n[1]
        if isinstance(a, RowList) and isinstance(b, int) and not isinstance(b, bool):
            a = len(a)
        if isinstance(a, list) and not isinstance(b, list) and not isinstance(b, OneOf):
            eq = all(x == b for x in a)
            return eq if op == '==' else not eq
        if op == '==':
            return a == b
        if op == '!=':
            return a != b
        return {'<': lambda: a < b, '<=': lambda: a <= b, '>': lambda: a > b, '>=': lambda: a >= b}[op]()
    if k == 'in':
        a, b = ev(n[1], env, ctx, roots), ev(n[2], env, ctx, roots)
        return a in b
    if k == 'within':
        a, b, tol = ev(n[1], env, ctx, roots), ev(n[3], env, ctx, roots), ev(n[2], env, ctx, roots)
        if isinstance(a, list) and isinstance(b, list):
            return len(a) == len(b) and all(abs(x - y) <= tol for x, y in zip(a, b))
        return abs(a - b) <= tol
    if k == 'op':
        op, a, b = n[1], ev(n[2], env, ctx, roots), ev(n[3], env, ctx, roots)
        if op == 'matches':
            if isinstance(b, list):
                return a == b
            return re.search(b, a) is not None
        if op == 'startswith':
            return a.startswith(b)
        if op == 'endswith':
            return a.endswith(b)
        if op == 'set_equal':
            return set(a) == set(_coords(b))
        if op == 'multiset_equal':
            return collections.Counter(a) == collections.Counter(b)
        if op == 'equals_by_character':
            return _by_char(a) == _by_char(b)
        if op == 'subset_of':
            return set(a) <= set(_coords(b))
        if op == 'includes_any':
            return any(x in a for x in b)
        if op == 'includes':
            return b in a
        raise Unsupported(f'operator {op}')
    if k == 'listcomp':
        out = []
        for x in ev(n[3], env, ctx, roots):
            e2 = dict(env, **{n[2]: x})
            if n[4] is None or ev(n[4], e2, ctx, roots):
                out.append(ev(n[1], e2, ctx, roots))
        return out
    if k == 'gen':
        items = []
        for x in ev(n[3], env, ctx, roots):
            e2 = dict(env, **{n[2]: x})
            if n[4] is None or ev(n[4], e2, ctx, roots):
                items.append(ev(n[1], e2, ctx, roots))
        return items
    if k == 'qstmt':
        _, kind, var, it, cond, body = n
        vals = []
        for x in ev(it, env, ctx, roots):
            e2 = dict(env, **{var: x})
            if cond is None or ev(cond, e2, ctx, roots):
                vals.append(bool(ev(body, e2, ctx, roots)))
        if kind == 'all' and not vals:
            vacuous(ctx, var)
        return all(vals) if kind == 'all' else any(vals)
    if k == 'quant':
        raise Unsupported('quantifier outside all()/any()')
    if k == 'call':
        fn, args = n[1], n[2]
        if fn[0] == 'name' and fn[1] == 'before':
            saved, saved_root = ctx.cur, ctx.cur_root
            ctx.cur, ctx.cur_root = ctx.start, ctx.root_start
            ctx.in_before += 1
            try:
                return ev(args[0], env, ctx, roots)
            except ReaderMiss as e:
                # The start state has no such item, so there is no baseline to compare with. That is not a
                # FAIL: the spec's comparison cannot be decided (a file the task creates has no start copy).
                raise Unsupported(f'baseline missing: {e}')
            finally:
                ctx.cur, ctx.cur_root = saved, saved_root
                ctx.in_before -= 1
        if fn[0] == 'name' and fn[1] in ('all', 'any') and len(args) == 1 and args[0][0] in ('gen', 'quant'):
            a = args[0]
            if a[0] == 'gen':
                vals = ev(a, env, ctx, roots)
            else:
                vals = []
                for x in ev(a[2], env, ctx, roots):
                    e2 = dict(env, **{a[1]: x})
                    if a[3] is None or ev(a[3], e2, ctx, roots):
                        vals.append(ev(a[4], e2, ctx, roots))
            if fn[1] == 'all' and not vals:
                vacuous(ctx, a[1] if a[0] == 'quant' else 'generator')
            return all(vals) if fn[1] == 'all' else any(vals)
        if fn[0] == 'attr' and fn[2] == 'index':
            base = ev(fn[1], env, ctx, roots)
            if isinstance(base, list):
                return base.index(*[ev(x, env, ctx, roots) for x in args])
            callee = getattr_(base, 'index')
        else:
            callee = ev(fn, env, ctx, roots)
        if not callable(callee):
            raise Unsupported(f'not callable: {fn}')
        return callee(*[ev(x, env, ctx, roots) for x in args])
    raise Unsupported(f'node {k}')


def _coords(x):
    return x.coords if hasattr(x, 'coords') else x


def _by_char(x):
    if isinstance(x, str):
        return tuple(x)
    if isinstance(x, list):
        return [_by_char(i) for i in x]
    return x


def vacuous(ctx, what):
    """An all() with no values is true by convention. It is logged; in the counterfactual pass it is UNSUPPORTED."""
    ctx.vacuous.append(what)
    if ctx.strict_empty:
        raise Unsupported(f'all() over no values ({what})')


def _eval_pred(ast, ctx):
    """(status, reason) of one parsed predicate, as specexec: FAIL on a reader miss, UNSUPPORTED on an
    unsupported name or value, ERROR on an unexpected exception (never a silent pass)."""
    try:
        val = ev(ast, {}, ctx, build_roots(ctx))
        if isinstance(val, Unknown):
            raise Unsupported(f'unknown value: {val.reason}')
        return ('PASS' if bool(val) else 'FAIL'), repr(val)[:160]
    except ReaderMiss as e:
        return 'FAIL', f'missing: {e}'
    except Unsupported as e:
        return 'UNSUPPORTED', f'eval: {e}'
    except Exception as e:
        return 'ERROR', f'{type(e).__name__}: {str(e)[:120]}'


def _decide(statuses):
    if 'FAIL' in statuses:
        return 'REJECT'
    if any(s in ('UNSUPPORTED', 'ERROR') for s in statuses):
        return 'UNDECIDED'
    return 'ACCEPT'


def run_spec(spec, end_state, start_state, root_end, root_start):
    """Decision and per-predicate records for one spec on one end state.

    end_state, start_state: canonical trees (canon.dir_tree output). root_end, root_start: directories on disk,
    used only for pixel data. Same decision rule and counterfactual pass as specexec.run_spec."""
    end_state = end_state if isinstance(end_state, StateTree) else StateTree(end_state)
    start_state = start_state if isinstance(start_state, StateTree) else StateTree(start_state)
    holder = {'sheet': None}
    recs = []
    for src in spec.get('must', []):
        pred = strip_comment(src)
        try:
            ast = parse(pred)
        except Unsupported as e:
            recs.append({'pred': pred, 'status': 'UNSUPPORTED', 'reason': f'parse: {e}', 'proxy': False})
            continue
        ctx = Ctx(end_state, start_state, root_end, root_start, holder)
        status, reason = _eval_pred(ast, ctx)
        rec = {'pred': pred, 'status': status, 'reason': reason, 'proxy': ctx.proxy}
        if ctx.vacuous:
            rec['vacuous_all'] = list(ctx.vacuous)
            cf = Ctx(end_state, start_state, root_end, root_start, holder)
            cf.strict_empty = True
            rec['if_vacuous_all_undecided'] = _eval_pred(ast, cf)[0]
        recs.append(rec)
    statuses = [r['status'] for r in recs]
    counterfactual = [r.get('if_vacuous_all_undecided', r['status']) for r in recs]
    return {'decision': _decide(statuses), 'predicates': recs,
            'empty_all_undecided_decision': _decide(counterfactual)}
