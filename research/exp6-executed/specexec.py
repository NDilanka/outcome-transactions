"""Spec executor for Exp 6: runs the must-predicates of grounded outcome specs (exp5) on a real end state.

Scope (deliberately small): only the predicate grammar and readers that the Exp 6 subset uses.
- Paths in predicates are Ubuntu paths. A machine root maps /home/user/x to <root>/home/user/x.
- before(e) evaluates e against the starting root.
- Indices are one-based and slices are inclusive (paragraphs[3..28]); an open end (rendered_pages[3..]) is allowed.
- Decision per spec: REJECT if any must-predicate FAILs; UNDECIDED if none FAILs but one is UNSUPPORTED or ERROR
  (the executor cannot decide, so it never accepts by skipping a predicate); ACCEPT if all PASS.
- Footprint items are prose in these specs. They are reported as NOT_EXECUTED, not checked.
"""
import collections, functools, hashlib, inspect, os, re, stat, subprocess, tempfile, codecs, zipfile

import openpyxl
from openpyxl.utils import range_boundaries, get_column_letter
from docx import Document
from docx.oxml.ns import qn
from pptx import Presentation
from lxml import etree
from pypdf import PdfReader

EMU_PER_CM = 360000
# ODF namespaces (Clark notation) for .odt files
T_NS = '{urn:oasis:names:tc:opendocument:xmlns:text:1.0}'
TB_NS = '{urn:oasis:names:tc:opendocument:xmlns:table:1.0}'
OF_NS = '{urn:oasis:names:tc:opendocument:xmlns:office:1.0}'


class Unsupported(Exception):
    """Predicate uses syntax or a reader the executor does not implement."""


class ReaderMiss(Exception):
    """A named object (sheet, shape, file, page) is absent in the end state. This is a FAIL, not an error."""


# ---------------------------------------------------------------- tokenizer and parser

KEYWORDS = {'and', 'or', 'not', 'in', 'for', 'if', 'where', 'within', 'matches', 'startswith', 'endswith',
            'set_equal', 'multiset_equal', 'subset_of', 'includes', 'includes_any', 'equals_by_character'}
TOKEN = re.compile(r"""
 (?P<ws>\s+)
|(?P<num>0o[0-7]+|\d+\.\d+|\d+)
|(?P<str>'(?:\\.|[^'\\])*'|"(?:\\.|[^"\\])*")
|(?P<id>[A-Za-z_][A-Za-z0-9_]*)
|(?P<op>==|!=|<=|>=|\.\.|[<>+\-*/().,\[\]{}:])
""", re.X)


def strip_comment(pred):
    """Drop a trailing '# ...' comment that is not inside quotes."""
    q = None
    for i, ch in enumerate(pred):
        if q:
            if ch == q: q = None
        elif ch in "'\"": q = ch
        elif ch == '#' and i > 0 and pred[i - 1] == ' ': return pred[:i].rstrip()
    return pred.strip()


def tokenize(src):
    out, pos = [], 0
    while pos < len(src):
        m = TOKEN.match(src, pos)
        if not m: raise Unsupported(f"cannot tokenize at {src[pos:pos+20]!r}")
        pos = m.end()
        kind = m.lastgroup
        if kind == 'ws': continue
        val = m.group(kind)
        if kind == 'id' and val in KEYWORDS: kind = 'kw'
        out.append((kind, val))
    out.append(('eof', None))
    return out


class Parser:
    def __init__(self, src):
        self.t = tokenize(src)
        self.i = 0

    def peek(self, k=0): return self.t[self.i + k]
    def take(self): tok = self.t[self.i]; self.i += 1; return tok
    def is_(self, kind, val=None, k=0):
        t = self.peek(k)
        return t[0] == kind and (val is None or t[1] == val)
    def expect(self, kind, val=None):
        if not self.is_(kind, val): raise Unsupported(f"expected {val or kind}, got {self.peek()[1]!r}")
        return self.take()

    def parse(self):
        e = self.or_()
        if not self.is_('eof'): raise Unsupported(f"trailing tokens at {self.peek()[1]!r}")
        return e

    def or_(self):
        l = self.and_()
        while self.is_('kw', 'or'):
            self.take(); l = ('or', l, self.and_())
        return l

    def and_(self):
        l = self.not_()
        while self.is_('kw', 'and'):
            self.take(); l = ('and', l, self.not_())
        return l

    def not_(self):
        if self.is_('kw', 'not') and not self.is_('kw', 'in', 1):
            self.take(); return ('not', self.not_())
        return self.cmp()

    def cmp(self):
        l = self.add()
        while True:
            t = self.peek()
            if t[0] == 'op' and t[1] in ('==', '!=', '<', '<=', '>', '>='):
                self.take(); l = ('cmp', t[1], l, self.add())
            elif self.is_('kw', 'in'):
                self.take(); l = ('in', l, self.rhs_with_range())
            elif self.is_('kw', 'not') and self.is_('kw', 'in', 1):
                self.take(); self.take(); l = ('not', ('in', l, self.rhs_with_range()))
            elif self.is_('kw', 'within'):
                self.take(); self.expect('op', '('); tol = self.or_(); self.expect('op', ')')
                l = ('within', l, tol, self.add())
            elif t[0] == 'kw' and t[1] in ('matches', 'startswith', 'endswith', 'set_equal', 'multiset_equal',
                                           'subset_of', 'includes', 'includes_any', 'equals_by_character'):
                self.take(); l = ('op', t[1], l, self.add())
            else:
                return l

    def rhs_with_range(self):
        r = self.add()
        if self.is_('op', '..'):
            self.take(); hi = self.add(); return ('range', r, hi)
        return r

    def add(self):
        l = self.mul()
        while self.peek()[0] == 'op' and self.peek()[1] in ('+', '-'):
            op = self.take()[1]; l = ('arith', op, l, self.mul())
        return l

    def mul(self):
        l = self.unary()
        while self.peek()[0] == 'op' and self.peek()[1] in ('*', '/'):
            op = self.take()[1]; l = ('arith', op, l, self.unary())
        return l

    def unary(self):
        if self.is_('op', '-'):
            self.take(); return ('arith', '-', ('lit', 0), self.unary())
        return self.postfix()

    def postfix(self):
        e = self.primary()
        while True:
            if self.is_('op', '.'):
                self.take(); e = ('attr', e, self.expect('id')[1])
            elif self.is_('op', '('):
                e = ('call', e, self.args())
            elif self.is_('op', '['):
                self.take()
                if self.is_('op', '*'):
                    self.take(); self.expect('op', ']'); e = ('star', e)
                else:
                    a = self.add()
                    if self.is_('op', '..'):
                        self.take()
                        b = None if self.is_('op', ']') else self.add()
                        self.expect('op', ']'); e = ('span', e, a, b)
                    else:
                        self.expect('op', ']'); e = ('index', e, a)
            else:
                return e

    def args(self):
        self.expect('op', '(')
        if self.is_('op', ')'):
            self.take(); return []
        first = self.or_()
        if self.is_('kw', 'for'):  # generator: any(expr for v in it if cond)
            self.take(); var = self.expect('id')[1]; self.expect('kw', 'in'); it = self.or_()
            cond = None
            if self.is_('kw', 'if'): self.take(); cond = self.or_()
            self.expect('op', ')')
            return [('gen', first, var, it, cond)]
        if self.is_('kw', 'where') or self.is_('op', ':'):  # quantifier: all(v in it where cond: body)
            if first[0] != 'in': raise Unsupported("quantifier needs 'v in iterable'")
            var, it = first[1][1], first[2]
            cond = None
            if self.is_('kw', 'where'): self.take(); cond = self.or_()
            self.expect('op', ':'); body = self.or_(); self.expect('op', ')')
            return [('quant', var, it, cond, body)]
        args = [first]
        while self.is_('op', ','):
            self.take(); args.append(self.or_())
        self.expect('op', ')')
        return args

    def quant_stmt(self):
        """Statement form without parentheses: all|exists [NOUN] v in ITER [where COND]: BODY.
        NOUN is an optional label such as 'chart' (the iterable defines what is checked). BODY runs to the end of the predicate."""
        kind = self.take()[1]
        if self.is_('id', None, 1): self.take()  # NOUN
        var = self.expect('id')[1]
        self.expect('kw', 'in')
        it = self.rhs_with_range()
        cond = None
        if self.is_('kw', 'where'): self.take(); cond = self.or_()
        self.expect('op', ':')
        return ('qstmt', kind, var, it, cond, self.or_())

    def primary(self):
        t = self.peek()
        if t[0] == 'num':
            self.take(); v = t[1]
            return ('lit', int(v, 8) if v.startswith('0o') else (float(v) if '.' in v else int(v)))
        if t[0] == 'str':
            self.take(); s = t[1][1:-1]
            if '\\' in s: s = codecs.decode(s, 'unicode_escape')
            return ('lit', s)
        if t[0] == 'id' and t[1] in ('all', 'exists') and self.is_('id', None, 1) and (
                self.is_('kw', 'in', 2) or (self.is_('id', None, 2) and self.is_('kw', 'in', 3))):
            return self.quant_stmt()
        if t[0] == 'id':
            self.take()
            if t[1] in ('null', 'None'): return ('lit', None)
            if t[1] in ('true', 'True'): return ('lit', True)
            if t[1] in ('false', 'False'): return ('lit', False)
            return ('name', t[1])
        if self.is_('op', '('):
            self.take(); e = self.or_(); self.expect('op', ')'); return e
        if self.is_('op', '['):
            self.take()
            if self.is_('op', ']'): self.take(); return ('list', [])
            first = self.or_()
            if self.is_('kw', 'for'):
                self.take(); var = self.expect('id')[1]; self.expect('kw', 'in'); it = self.or_()
                cond = None
                if self.is_('kw', 'if'): self.take(); cond = self.or_()
                self.expect('op', ']'); return ('listcomp', first, var, it, cond)
            items = [first]
            while self.is_('op', ','):
                self.take()
                if self.is_('op', ']'): break
                items.append(self.or_())
            self.expect('op', ']'); return ('list', items)
        if self.is_('op', '<'):  # <one of [...]>
            self.take()
            if not self.is_('id', 'one'): raise Unsupported("only <one of [...]> is supported")
            self.take(); self.expect('id', 'of'); lst = self.primary(); self.expect('op', '>')
            return ('oneof', lst)
        if self.is_('op', '{'):
            self.take(); items = []
            while not self.is_('op', '}'):
                items.append(self.or_())
                if self.is_('op', ','): self.take()
            self.take(); return ('set', items)
        raise Unsupported(f"unexpected token {t[1]!r}")


def parse(src):
    return Parser(src).parse()


# ---------------------------------------------------------------- values

class OneOf:
    def __init__(self, options): self.options = options
    def __eq__(self, other): return other in self.options
    def __repr__(self): return f"<one of {self.options}>"


class Seq(list):
    """Reader sequence: one-based indexing and inclusive spans."""
    def at(self, n):
        if not 1 <= n <= len(self): raise ReaderMiss(f"index {n} out of range (len {len(self)})")
        return self[n - 1]
    def span(self, a, b):
        return Seq(self[a - 1:(len(self) if b is None else b)])


class RowList(Seq):
    """Table rows. Compared with an integer, it means the row count (fix table_rows)."""


class IntRange:
    def __init__(self, lo, hi): self.lo, self.hi = lo, hi
    def __contains__(self, x): return self.lo <= x <= self.hi
    def __iter__(self): return iter(range(self.lo, self.hi + 1))


def getattr_(obj, name):
    if isinstance(obj, list):
        if name == 'texts': return [x.text for x in obj]
        return [getattr_(x, name) for x in obj]
    try:
        return getattr(obj, name)
    except AttributeError:
        raise Unsupported(f"no attribute {name!r} on {type(obj).__name__}")


def as_str_list(fn, x):
    return [fn(i) for i in x] if isinstance(x, list) else fn(x)


def proper_word(w):
    out, done = [], False
    for ch in w:
        if not done and ch.isalpha(): out.append(ch.upper()); done = True
        else: out.append(ch.lower() if ch.isalpha() else ch)
    return ''.join(out)


FUNCS = {
    'lower': lambda x: as_str_list(lambda s: s.lower(), x),
    'trim': lambda x: as_str_list(lambda s: s.strip(), x),
    'collapse_whitespace': lambda x: as_str_list(lambda s: re.sub(r'\s+', ' ', s), x),
    'proper_case': lambda x: as_str_list(lambda s: ' '.join(proper_word(w) for w in re.sub(r'\s+', ' ', s).split(' ')), x),
    'replace': lambda x, a, b: as_str_list(lambda s: s.replace(a, b), x),
    'len': len,
    'count': len,
}


# ---------------------------------------------------------------- readers

@functools.lru_cache(maxsize=None)
def _calc_book(path, stamp):
    return (openpyxl.load_workbook(path, data_only=True), openpyxl.load_workbook(path))


class CalcFile:
    def __init__(self, path):
        self.path = path
        self.stamp = (os.path.getmtime(path), os.path.getsize(path))
        self.vwb, self.fwb = _calc_book(path, self.stamp)
    @property
    def sheet_names(self): return list(self.vwb.sheetnames)
    def sheet(self, name):
        if name not in self.vwb.sheetnames: raise ReaderMiss(f"no sheet {name!r}")
        sh = CalcSheet(self, name)
        CURRENT['sheet'] = sh  # a bare range('B1:C29') in the same predicate refers to this sheet
        return sh
    @property
    def charts(self):
        """Charts of every sheet, in sheet order (openpyxl reads them from the file)."""
        return [ChartObj(ch, self) for ws in self.fwb.worksheets for ch in getattr(ws, '_charts', [])]


class CalcSheet:
    def __init__(self, book, name):
        self.book, self.name = book, name
        self.wv, self.wf = book.vwb[name], book.fwb[name]
    def _bbox(self):
        cells = [(c.row, c.column) for row in self.wv.iter_rows() for c in row if c.value not in (None, '')]
        if not cells: return None
        return min(r for r, _ in cells), min(c for _, c in cells), max(r for r, _ in cells), max(c for _, c in cells)
    def _grid(self, ws, box):
        if box is None: return []
        r0, c0, r1, c1 = box
        return [list(r) for r in ws.iter_rows(min_row=r0, max_row=r1, min_col=c0, max_col=c1, values_only=True)]
    @property
    def values(self): return self._grid(self.wv, self._bbox())
    @property
    def formulas(self): return self._grid(self.wf, self._bbox())
    @property
    def nonempty_cells(self):
        return [c.coordinate for row in self.wv.iter_rows() for c in row if c.value not in (None, '')]
    @property
    def hidden_rows(self): return sorted(r for r, d in self.wf.row_dimensions.items() if d.hidden)
    @property
    def hidden_columns(self): return sorted(k for k, d in self.wf.column_dimensions.items() if d.hidden)
    @property
    def autofilter(self): return self.wf.auto_filter.ref
    def cell(self, ref): return CalcCell(self.wv[ref].value, self.wf[ref].value)
    def range(self, ref): return CalcRange(self, ref)


class CalcCell:
    def __init__(self, value, formula): self.value, self.formula = value, formula


class ChartObj:
    """A chart in a workbook. type: 'column' or 'bar' (bar chart direction), 'line', or the chart kind."""
    def __init__(self, ch, book): self.ch, self.book = ch, book
    @property
    def type(self):
        name = type(self.ch).__name__
        if name == 'BarChart': return 'column' if self.ch.type == 'col' else 'bar'
        if name == 'LineChart': return 'line'
        return name.replace('Chart', '').lower()
    @property
    def title(self):
        t = self.ch.title
        if t is None or isinstance(t, str): return t
        if t.tx is None or t.tx.rich is None: return None
        return ''.join(r.t for p in t.tx.rich.p for r in (p.r or []))
    @property
    def series(self): return ZeroList(SeriesObj(s, self.book) for s in self.ch.series)


class ZeroList(list):
    """Chart series: indexed from 0, as the specs write them (series[0] is the first series)."""
    def at(self, n): return self[n]


class SeriesObj:
    def __init__(self, s, book): self.s, self.book = s, book
    @property
    def values(self):
        """Plotted values, read from the cells the series refers to (row-major for a 2-D range)."""
        ref = getattr(self.s, 'val', None) or getattr(self.s, 'yVal', None)
        f = ref.numRef.f if ref is not None and ref.numRef is not None else None
        if not f or '!' not in f: return None
        sheet_part, rng = f.rsplit('!', 1)
        sheet_name = sheet_part[1:-1].replace("''", "'") if sheet_part.startswith("'") else sheet_part
        ws = self.book.vwb[sheet_name]
        c0, r0, c1, r1 = range_boundaries(rng.replace('$', ''))
        return [v for row in ws.iter_rows(min_row=r0, max_row=r1, min_col=c0, max_col=c1, values_only=True) for v in row]


class CalcRange:
    def __init__(self, sheet, ref):
        self.sheet, self.ref = sheet, ref
        self.box = range_boundaries(ref)
    @property
    def coords(self):
        c0, r0, c1, r1 = self.box
        return {f"{get_column_letter(c)}{r}" for r in range(r0, r1 + 1) for c in range(c0, c1 + 1)}
    def _flat(self, rows):
        if len(rows) == 1: return rows[0]
        if rows and all(len(r) == 1 for r in rows): return [r[0] for r in rows]
        return rows
    @property
    def values(self):
        c0, r0, c1, r1 = self.box
        return self._flat([list(r) for r in self.sheet.wv.iter_rows(min_row=r0, max_row=r1, min_col=c0, max_col=c1, values_only=True)])
    @property
    def formulas(self):
        c0, r0, c1, r1 = self.box
        return self._flat([list(r) for r in self.sheet.wf.iter_rows(min_row=r0, max_row=r1, min_col=c0, max_col=c1, values_only=True)])
    @property
    def nonempty_cells(self):
        return [c for c in sorted(self.coords) if self.sheet.wv[c].value not in (None, '')]


class PageObj:
    def __init__(self, text, images): self.text, self.objects = text, images
class PageList:
    def __init__(self, pages): self.pages = pages
    @property
    def count(self): return len(self.pages)
    def at(self, n):
        if not 1 <= n <= len(self.pages): raise ReaderMiss(f"page {n} out of range")
        return self.pages[n - 1]
    def span(self, a, b): return self.pages[a - 1:(len(self.pages) if b is None else b)]


@functools.lru_cache(maxsize=None)
def _render_pdf(path, stamp):
    """LibreOffice renders the file to PDF (the same engine the user sees); page text comes from pypdf."""
    tmp = tempfile.mkdtemp(prefix='exp6pdf_')
    subprocess.run(['soffice', '--headless', '--convert-to', 'pdf', '--outdir', tmp, path],
                   check=True, capture_output=True, timeout=180)
    pdf = os.path.join(tmp, os.path.splitext(os.path.basename(path))[0] + '.pdf')
    r = PdfReader(pdf)
    # PDF text extraction returns renderer spacing (double spaces, line breaks inside words); collapse it.
    return [PageObj(re.sub(r'\s+', ' ', p.extract_text() or '').strip(), list(p.images)) for p in r.pages]


class DocxFile:
    def __init__(self, path):
        self.path = path
        self.stamp = (os.path.getmtime(path), os.path.getsize(path))
        self.doc = Document(path)
    @functools.cached_property
    def paragraphs(self): return Seq([ParaObj(i + 1, p.text) for i, p in enumerate(self.doc.paragraphs)])
    @functools.cached_property
    def tables(self): return Seq([TableObj(i + 1, t) for i, t in enumerate(self.doc.tables)])
    @property
    def body_order(self):
        """Body paragraphs and tables in document order, as the same objects paragraphs and tables return."""
        out, pi, ti = [], 0, 0
        for el in self.doc.element.body.iterchildren():
            if el.tag == qn('w:p'): out.append(self.paragraphs[pi]); pi += 1
            elif el.tag == qn('w:tbl'): out.append(self.tables[ti]); ti += 1
        return Seq(out)
    def paragraph(self, n): return self.paragraphs.at(n)
    def table(self, n): return self.tables.at(n)
    @property
    def all_text(self):
        parts = [p.text for p in self.paragraphs] + [c.text for t in self.tables for c in t.cells]
        return '\n'.join(parts)
    def text_lines_before_paragraph_with_text(self, s):
        for i, p in enumerate(self.paragraphs):
            if s in p.text: return [q.text for q in self.paragraphs[:i]]
        raise ReaderMiss(f"no paragraph containing {s!r}")
    def paragraphs_from_text(self, s):
        for i, p in enumerate(self.paragraphs):
            if s in p.text: return Seq(self.paragraphs[i:])
        raise ReaderMiss(f"no paragraph containing {s!r}")
    @property
    def rendered_pages(self):
        return PageList(_render_pdf(self.path, self.stamp))


def _odt_text(el):
    """Visible text of an ODF paragraph: character data, text:s spaces, tabs, and line breaks. Notes are skipped."""
    out = [el.text or '']
    for ch in el:
        local = etree.QName(ch).localname
        if local in ('note', 'annotation'): pass
        elif local == 's': out.append(' ' * int(ch.get(T_NS + 'c', '1')))
        elif local == 'tab': out.append('\t')
        elif local == 'line-break': out.append('\n')
        else: out.append(_odt_text(ch))
        out.append(ch.tail or '')
    return ''.join(out)


def _repeat(el, attr):
    """Number of times an ODF element repeats (table:number-*-repeated). Capped so a blank tail cannot blow up memory."""
    return min(int(el.get(TB_NS + attr, '1')), 1024)


class OdtCell:
    def __init__(self, paras): self.text = '\n'.join(paras)


class OdtRow:
    def __init__(self, cells): self.cells = cells


class OdtTable:
    """Table with the python-docx surface TableObj uses: rows (each with cells), and columns (grid columns)."""
    def __init__(self, el):
        self.columns = [None] * sum(_repeat(c, 'number-columns-repeated') for c in self._col_elems(el))
        self.rows = [OdtRow(self._cells(r)) for r in self._row_elems(el)]
    @staticmethod
    def _col_elems(el):
        for ch in el:
            if ch.tag == TB_NS + 'table-column': yield ch
            elif ch.tag in (TB_NS + 'table-column-group', TB_NS + 'table-header-columns'):
                yield from OdtTable._col_elems(ch)
    @staticmethod
    def _row_elems(el):
        for ch in el:
            if ch.tag == TB_NS + 'table-row':
                for _ in range(_repeat(ch, 'number-rows-repeated')): yield ch
            elif ch.tag in (TB_NS + 'table-header-rows', TB_NS + 'table-row-group', TB_NS + 'table-rows'):
                yield from OdtTable._row_elems(ch)
    @staticmethod
    def _cells(row):
        out = []
        for c in row:
            if c.tag not in (TB_NS + 'table-cell', TB_NS + 'covered-table-cell'): continue
            paras = [_odt_text(p) for p in c if p.tag in (T_NS + 'p', T_NS + 'h')]
            out.extend([OdtCell(paras)] * _repeat(c, 'number-columns-repeated'))
        return out


class OdtFile(DocxFile):
    """ODF text document (.odt). Same surface as DocxFile: body paragraphs (lists and sections are flattened into
    the body, as Word does), body tables, all_text, and rendered_pages. Text runs and body_order are not read."""
    def __init__(self, path):
        self.path = path
        self.stamp = (os.path.getmtime(path), os.path.getsize(path))
        with zipfile.ZipFile(path) as z:
            self.root = etree.fromstring(z.read('content.xml'))
        self.body = self.root.find(f'{OF_NS}body/{OF_NS}text')
        self.blocks = list(self._blocks(self.body))
    @staticmethod
    def _blocks(el):
        for ch in el:
            if ch.tag in (T_NS + 'p', T_NS + 'h'): yield ('p', ch)
            elif ch.tag == TB_NS + 'table': yield ('t', ch)
            elif ch.tag in (T_NS + 'list', T_NS + 'list-item', T_NS + 'list-header', T_NS + 'section'):
                yield from OdtFile._blocks(ch)
    @functools.cached_property
    def paragraphs(self):
        return Seq([ParaObj(i + 1, _odt_text(e)) for i, (kind, e) in enumerate(p for p in self.blocks if p[0] == 'p')])
    @functools.cached_property
    def tables(self):
        return Seq([TableObj(i + 1, OdtTable(e)) for i, (kind, e) in enumerate(t for t in self.blocks if t[0] == 't')])


class ParaObj:
    def __init__(self, index, text): self.index, self.text = index, text
    def __eq__(self, o): return isinstance(o, ParaObj) and o.text == self.text
    def __repr__(self): return f"P{self.index}({self.text[:30]!r})"


class CellObj:
    def __init__(self, text): self.text = text


class TableObj:
    def __init__(self, index, t): self.index, self.t = index, t
    @property
    def rows(self):
        return RowList([Seq([CellObj(c.text) for c in r.cells]) for r in self.t.rows])
    @property
    def columns(self): return len(self.t.columns)
    @property
    def cells(self): return Seq([c for r in self.rows for c in r])
    def __eq__(self, o):
        return isinstance(o, TableObj) and [[c.text for c in r] for r in self.rows] == [[c.text for c in r] for r in o.rows]


class PptxFile:
    def __init__(self, path):
        self.prs = Presentation(path)
    @functools.cached_property
    def slides(self): return Seq([SlideObj(s, i + 1) for i, s in enumerate(self.prs.slides)])
    @property
    def slide_count(self): return len(self.slides)
    def slide(self, n): return self.slides.at(n)


class SlideObj:
    def __init__(self, s, index): self.s, self.index = s, index
    @property
    def shapes(self): return Seq([ShapeObj(sh) for sh in self.s.shapes])
    def __eq__(self, o):
        """Same shapes (names, positions, text, run colours) and same transition. Identity alone is never equal across files."""
        return (isinstance(o, SlideObj) and [sh._snap() for sh in self.shapes] == [sh._snap() for sh in o.shapes]
                and self.transition == o.transition)
    def __repr__(self): return f"Slide({self.index})"
    def shape(self, name):
        for sh in self.shapes:
            if sh.name == name: return sh
        raise ReaderMiss(f"no shape {name!r} on slide {self.index}")
    @property
    def transition(self):
        el = self.s._element.find('{http://schemas.openxmlformats.org/presentationml/2006/main}transition')
        if el is None: return TransitionObj(None)
        kids = [c for c in el if etree.QName(c).localname not in ('extLst', 'sndAc')]
        return TransitionObj(etree.QName(kids[0]).localname if kids else 'none')


class TransitionObj:
    def __init__(self, t): self.type = t
    def __eq__(self, o): return isinstance(o, TransitionObj) and o.type == self.type
    def __repr__(self): return f"Transition({self.type})"


A = '{http://schemas.openxmlformats.org/drawingml/2006/main}'


class ShapeObj:
    def __init__(self, sh):
        self.sh = sh
        self.name = sh.name
    @property
    def text(self): return self.sh.text_frame.text if self.sh.has_text_frame else ''
    @property
    def has_text(self): return bool(self.text.strip())
    @property
    def height_cm(self): return None if self.sh.height is None else self.sh.height / EMU_PER_CM
    @property
    def width_cm(self): return None if self.sh.width is None else self.sh.width / EMU_PER_CM
    @property
    def paragraphs(self):
        if not self.sh.has_text_frame: return Seq()
        return Seq([ParaP(p) for p in self.sh.text_frame.paragraphs])
    def paragraph(self, n): return self.paragraphs.at(n)
    @property
    def text_runs(self):
        out = []
        if self.sh.has_text_frame:
            for p in self.sh.text_frame.paragraphs:
                for r in p.runs:
                    rp = r._r.find(A + 'rPr')
                    clr = None
                    if rp is not None:
                        c = rp.find(f'{A}solidFill/{A}srgbClr')
                        # hex colour case is an encoding detail (LibreOffice writes lowercase): normalise it
                        clr = c.get('val').upper() if c is not None else None
                    out.append(RunP(r.text, clr))
        return Seq(out)
    def _snap(self):
        return (self.name, self.sh.left, self.sh.top, self.sh.width, self.sh.height, self.text,
                [r.color for r in self.text_runs])
    def __eq__(self, o): return isinstance(o, ShapeObj) and o._snap() == self._snap()
    def __repr__(self): return f"Shape({self.name!r})"


class ParaP:
    def __init__(self, p): self.p = p
    @property
    def text(self): return self.p.text
    @property
    def bullet(self):
        pPr = self.p._p.find(A + 'pPr')
        if pPr is None: return BulletObj('inherited')
        tags = [etree.QName(c).localname for c in pPr]
        for name, kind in (('buNone', 'none'), ('buChar', 'char'), ('buAutoNum', 'number'), ('buBlip', 'picture')):
            if name in tags: return BulletObj(kind)
        return BulletObj('inherited')


class BulletObj:
    def __init__(self, t): self.type = t


class RunP:
    def __init__(self, text, color): self.text, self.color = text, color


class OsFile:
    def __init__(self, abs_path, ub_path):
        self.abs_path, self.ub_path = abs_path, ub_path
    @property
    def mode(self):
        if not os.path.lexists(self.abs_path): raise ReaderMiss(f"no file {self.ub_path}")
        return stat.S_IMODE(os.stat(self.abs_path).st_mode)
    @property
    def exists(self): return os.path.lexists(self.abs_path)


class OsTree:
    def __init__(self, abs_root, ub_root):
        self.abs_root, self.ub_root = abs_root, ub_root
        if not os.path.isdir(abs_root): raise ReaderMiss(f"no directory {ub_root}")
    def _walk(self):
        for dp, dns, fns in os.walk(self.abs_root):
            for n in dns + fns:
                full = os.path.join(dp, n)
                rel = os.path.relpath(full, self.abs_root)
                yield full, self.ub_root.rstrip('/') + '/' + rel
    @property
    def paths(self): return sorted(ub for _, ub in self._walk())
    @property
    def regular_files(self):
        return Seq([OsFile(f, ub) for f, ub in sorted(self._walk(), key=lambda x: x[1]) if os.path.isfile(f) and not os.path.islink(f)])


def writer_file(path):
    return OdtFile(path) if path.lower().endswith('.odt') else DocxFile(path)


class LibreOfficeRoot:
    def __init__(self, ctx): self.ctx = ctx
    @property
    def calc(self): return _Namespace(file=lambda p: self.ctx.open(p, CalcFile))
    @property
    def writer(self): return _Namespace(file=lambda p: self.ctx.open(p, writer_file))
    @property
    def impress(self): return _Namespace(file=lambda p: self.ctx.open(p, PptxFile))


class OsRoot:
    def __init__(self, ctx): self.ctx = ctx
    def file(self, p): return OsFile(self.ctx.resolve(p), p)
    def tree(self, p): return OsTree(self.ctx.resolve(p), p)


class _Namespace:
    def __init__(self, **kw): self.__dict__.update(kw)


class Ctx:
    def __init__(self, root, start_root):
        self.root, self.start_root = root, start_root
        self.opened = []      # (ubuntu path, document, opened inside before()) for the current predicate
        self.in_before = 0
        self.vacuous = []     # all() calls with no values in the current predicate (logged)
        self.strict_empty = False  # counterfactual pass: such an all() is UNDECIDED (Amendment 2 rule)
    def resolve(self, ubuntu_path):
        if not ubuntu_path.startswith('/'): raise Unsupported(f"relative path {ubuntu_path}")
        return os.path.join(self.root, ubuntu_path.lstrip('/'))
    def open(self, ubuntu_path, factory):
        obj = factory(self.resolve(ubuntu_path))
        self.opened.append((ubuntu_path, obj, self.in_before > 0))
        return obj


def bare_doc_method(name, ctx):
    """A bare method call such as table(2) means the method of the one document the predicate opened outside
    before(). With no document, or with several different ones, the name stays unknown (never guess the file)."""
    docs = {path: obj for path, obj, in_before in ctx.opened if not in_before}
    if len(docs) != 1: return None
    obj = next(iter(docs.values()))
    if not inspect.isfunction(getattr(type(obj), name, None)): return None
    return getattr(obj, name)


# ---------------------------------------------------------------- evaluator

CURRENT = {'sheet': None}


def lookup(name, env, ctx):
    if name in env: return env[name]
    if name == 'range':
        def bare_range(ref):
            if CURRENT['sheet'] is None: raise Unsupported("range() with no sheet selected")
            return CURRENT['sheet'].range(ref)
        return bare_range
    if name in FUNCS: return FUNCS[name]
    if name == 'libreoffice': return LibreOfficeRoot(ctx)
    if name == 'os': return OsRoot(ctx)
    bare = bare_doc_method(name, ctx)
    if bare is not None: return bare
    raise Unsupported(f"unknown name {name!r}")


def same(a, b):
    """Equality that treats one-of and tolerant comparisons the same way everywhere."""
    return a == b


def ev(n, env, ctx):
    k = n[0]
    if k == 'lit': return n[1]
    if k == 'name': return lookup(n[1], env, ctx)
    if k == 'attr': return getattr_(ev(n[1], env, ctx), n[2])
    if k == 'list': return [ev(x, env, ctx) for x in n[1]]
    if k == 'set': return {ev(x, env, ctx) for x in n[1]}
    if k == 'oneof': return OneOf(ev(n[1], env, ctx))
    if k == 'range': return IntRange(ev(n[1], env, ctx), ev(n[2], env, ctx))
    if k == 'star': return ev(n[1], env, ctx)
    if k == 'index':
        obj, idx = ev(n[1], env, ctx), ev(n[2], env, ctx)
        if hasattr(obj, 'at'): return obj.at(idx)
        if isinstance(obj, list): return Seq(obj).at(idx)
        raise Unsupported(f"cannot index {type(obj).__name__}")
    if k == 'span':
        obj = ev(n[1], env, ctx)
        a = ev(n[2], env, ctx)
        b = None if n[3] is None else ev(n[3], env, ctx)
        if hasattr(obj, 'span'): return obj.span(a, b)
        return Seq(obj).span(a, b)
    if k == 'arith':
        a, b = ev(n[2], env, ctx), ev(n[3], env, ctx)
        return {'+': lambda: a + b, '-': lambda: a - b, '*': lambda: a * b, '/': lambda: a / b}[n[1]]()
    if k == 'not': return not ev(n[1], env, ctx)
    if k == 'and': return bool(ev(n[1], env, ctx)) and bool(ev(n[2], env, ctx))
    if k == 'or': return bool(ev(n[1], env, ctx)) or bool(ev(n[2], env, ctx))
    if k == 'cmp':
        a, b = ev(n[2], env, ctx), ev(n[3], env, ctx)
        op = n[1]
        if isinstance(a, RowList) and isinstance(b, int) and not isinstance(b, bool):
            a = len(a)  # table(n).rows == 5 counts the rows; the projection rule below would test each row against 5
        # A projection (list) compared with a scalar is a universal condition over its items
        # (writer_conventions.txt); an empty projection is satisfied vacuously.
        if isinstance(a, list) and not isinstance(b, list) and not isinstance(b, OneOf):
            eq = all(x == b for x in a)
            return eq if op == '==' else not eq
        if op == '==': return a == b
        if op == '!=': return a != b
        return {'<': lambda: a < b, '<=': lambda: a <= b, '>': lambda: a > b, '>=': lambda: a >= b}[op]()
    if k == 'in':
        a, b = ev(n[1], env, ctx), ev(n[2], env, ctx)
        return a in b
    if k == 'within':
        a, b, tol = ev(n[1], env, ctx), ev(n[3], env, ctx), ev(n[2], env, ctx)
        def close(x, y):
            return abs(x - y) <= tol
        if isinstance(a, list) and isinstance(b, list):
            return len(a) == len(b) and all(close(x, y) for x, y in zip(a, b))
        return close(a, b)
    if k == 'op':
        op, a, b = n[1], ev(n[2], env, ctx), ev(n[3], env, ctx)
        if op == 'matches':
            if isinstance(b, list): return same(a, b)
            return re.search(b, a) is not None
        if op == 'startswith': return a.startswith(b)
        if op == 'endswith': return a.endswith(b)
        if op == 'set_equal':
            return set(a) == set(_coords(b))
        if op == 'multiset_equal': return collections.Counter(a) == collections.Counter(b)
        if op == 'equals_by_character': return _by_char(a) == _by_char(b)
        if op == 'subset_of': return set(a) <= set(_coords(b))
        raise Unsupported(f"operator {op}")
    if k == 'listcomp':
        out = []
        for x in ev(n[3], env, ctx):
            e2 = dict(env, **{n[2]: x})
            if n[4] is None or ev(n[4], e2, ctx): out.append(ev(n[1], e2, ctx))
        return out
    if k == 'gen':
        items = []
        for x in ev(n[3], env, ctx):
            e2 = dict(env, **{n[2]: x})
            if n[4] is None or ev(n[4], e2, ctx): items.append(ev(n[1], e2, ctx))
        return items
    if k == 'qstmt':
        _, kind, var, it, cond, body = n
        vals = []
        for x in ev(it, env, ctx):
            e2 = dict(env, **{var: x})
            if cond is None or ev(cond, e2, ctx): vals.append(bool(ev(body, e2, ctx)))
        if kind == 'all' and not vals: vacuous(ctx, var)
        return all(vals) if kind == 'all' else any(vals)
    if k == 'quant':
        raise Unsupported("quantifier outside all()/any()")
    if k == 'call':
        fn, args = n[1], n[2]
        if fn[0] == 'name' and fn[1] == 'before':
            saved = ctx.root
            ctx.root = ctx.start_root
            ctx.in_before += 1
            try: return ev(args[0], env, ctx)
            finally:
                ctx.root = saved
                ctx.in_before -= 1
        if fn[0] == 'name' and fn[1] in ('all', 'any') and len(args) == 1 and args[0][0] in ('gen', 'quant'):
            a = args[0]
            if a[0] == 'gen':
                vals = ev(a, env, ctx)
            else:
                vals = []
                for x in ev(a[2], env, ctx):
                    e2 = dict(env, **{a[1]: x})
                    if a[3] is None or ev(a[3], e2, ctx): vals.append(ev(a[4], e2, ctx))
            if fn[1] == 'all' and not vals: vacuous(ctx, a[1] if a[0] == 'quant' else 'generator')
            return all(vals) if fn[1] == 'all' else any(vals)
        if fn[0] == 'attr' and fn[2] == 'index':  # list.index(x), not the per-item projection of an 'index' attribute
            base = ev(fn[1], env, ctx)
            if isinstance(base, list): return base.index(*[ev(x, env, ctx) for x in args])
            callee = getattr_(base, 'index')
        else:
            callee = ev(fn, env, ctx)
        if not callable(callee): raise Unsupported(f"not callable: {fn}")
        return callee(*[ev(x, env, ctx) for x in args])
    raise Unsupported(f"node {k}")


def _coords(x):
    return x.coords if hasattr(x, 'coords') else x


def _by_char(x):
    """Character by character: a string is its sequence of characters; lists compare element by element."""
    if isinstance(x, str): return tuple(x)
    if isinstance(x, list): return [_by_char(i) for i in x]
    return x


def short(v):
    s = repr(v)
    return s if len(s) < 160 else s[:157] + '...'


def vacuous(ctx, what):
    """An all() with no values is true by convention. It is logged; in the counterfactual pass it is UNDECIDED."""
    ctx.vacuous.append(what)
    if ctx.strict_empty: raise Unsupported(f"all() over no values ({what})")


def _eval_pred(ast, ctx):
    """(status, reason) of one parsed predicate."""
    try:
        val = ev(ast, {}, ctx)
        return ('PASS' if bool(val) else 'FAIL'), short(val)[:160]
    except ReaderMiss as e:
        return 'FAIL', f'missing: {e}'
    except Unsupported as e:
        return 'UNSUPPORTED', f'eval: {e}'
    except Exception as e:  # executor bug or unexpected file: never silently accept
        return 'ERROR', f'{type(e).__name__}: {str(e)[:120]}'


def _decide(statuses):
    if 'FAIL' in statuses: return 'REJECT'
    if any(s in ('UNSUPPORTED', 'ERROR') for s in statuses): return 'UNDECIDED'
    return 'ACCEPT'


def run_spec(spec, end_root, start_root):
    """Evaluate every must-predicate. Returns the decision and per-predicate records.

    Logging only (the decision is computed from the status as before): a predicate with an all() that had no values
    records them in 'vacuous_all', and 'if_vacuous_all_undecided' is its status when such an all() counts as
    UNDECIDED. 'empty_all_undecided_decision' is the spec decision under that rule (the Amendment 2 candidate)."""
    ctx = Ctx(end_root, start_root)
    CURRENT['sheet'] = None
    recs = []
    for src in spec.get('must', []):
        pred = strip_comment(src)
        try:
            ast = parse(pred)
        except Unsupported as e:
            recs.append({'pred': pred, 'status': 'UNSUPPORTED', 'reason': f'parse: {e}'}); continue
        ctx.opened, ctx.vacuous, ctx.strict_empty = [], [], False  # documents are bound per predicate
        status, reason = _eval_pred(ast, ctx)
        rec = {'pred': pred, 'status': status, 'reason': reason}
        if ctx.vacuous:
            rec['vacuous_all'] = list(ctx.vacuous)
            ctx.opened, ctx.vacuous, ctx.strict_empty = [], [], True
            rec['if_vacuous_all_undecided'] = _eval_pred(ast, ctx)[0]
            ctx.strict_empty = False
        recs.append(rec)
    statuses = [r['status'] for r in recs]
    counterfactual = [r.get('if_vacuous_all_undecided', r['status']) for r in recs]
    return {'decision': _decide(statuses), 'predicates': recs,
            'empty_all_undecided_decision': _decide(counterfactual)}
