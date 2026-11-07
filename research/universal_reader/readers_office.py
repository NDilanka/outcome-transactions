"""Office documents as canonical trees.

OOXML (docx, xlsx, pptx) is read from the raw XML parts with lxml. ODF (odt, ods, odp) is read from
content.xml and styles.xml. Legacy .xls is read with xlrd (values only). Every reader returns plain
dicts, lists and scalars. Records are keyed by stable identity: 1-based index strings for paragraphs,
runs, rows and slides; A1 references for cells; shape names for shapes.
"""
import colorsys
import datetime
import functools
import os
import posixpath
import re
import shutil
import subprocess
import tempfile
import zipfile

from lxml import etree
from openpyxl.formula.translate import Translator

W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
A = '{http://schemas.openxmlformats.org/drawingml/2006/main}'
P = '{http://schemas.openxmlformats.org/presentationml/2006/main}'
S = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
C = '{http://schemas.openxmlformats.org/drawingml/2006/chart}'
R = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'
PR = '{http://schemas.openxmlformats.org/package/2006/relationships}'
EMU_PER_CM = 360000

ODF_T = '{urn:oasis:names:tc:opendocument:xmlns:text:1.0}'
ODF_TB = '{urn:oasis:names:tc:opendocument:xmlns:table:1.0}'
ODF_OF = '{urn:oasis:names:tc:opendocument:xmlns:office:1.0}'
ODF_ST = '{urn:oasis:names:tc:opendocument:xmlns:style:1.0}'
ODF_FO = '{urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0}'
ODF_DR = '{urn:oasis:names:tc:opendocument:xmlns:drawing:1.0}'
ODF_PR = '{urn:oasis:names:tc:opendocument:xmlns:presentation:1.0}'
ODF_SVG = '{urn:oasis:names:tc:opendocument:xmlns:svg-compatible:1.0}'
ODF_NUM = '{urn:oasis:names:tc:opendocument:xmlns:datastyle:1.0}'
ODF_XL = '{http://www.w3.org/1999/xlink}'


def col_letters(n):
    out = ''
    while n:
        n, r = divmod(n - 1, 26)
        out = chr(65 + r) + out
    return out


def _rels_all(z, part):
    """Relationships of a package part, external ones included: {rId: (type name, target, external)}.
    Internal targets are resolved part names; external targets (hyperlinks) are the target string as written."""
    d, b = posixpath.split(part)
    rel = f'{d}/_rels/{b}.rels' if d else f'_rels/{b}.rels'
    if rel not in z.namelist():
        return {}
    out = {}
    for r in etree.fromstring(z.read(rel)).findall(PR + 'Relationship'):
        target = r.get('Target')
        if r.get('TargetMode') == 'External':
            out[r.get('Id')] = (r.get('Type').rsplit('/', 1)[-1], target, True)
            continue
        full = target.lstrip('/') if target.startswith('/') else posixpath.normpath(posixpath.join(d, target))
        out[r.get('Id')] = (r.get('Type').rsplit('/', 1)[-1], full, False)
    return out


def _rels(z, part):
    """Internal relationships of a package part: {rId: (type name, resolved part name)}."""
    return {k: (t, p) for k, (t, p, ext) in _rels_all(z, part).items() if not ext}


def _link_targets(z, part):
    """External targets of a part's relationships (hyperlinks): {rId: target string}."""
    return {k: p for k, (t, p, ext) in _rels_all(z, part).items() if ext}


def _xml(z, name):
    return etree.fromstring(z.read(name))


def _num(v):
    if v is None:
        return None
    try:
        f = float(v)
    except ValueError:
        return v
    return int(f) if f.is_integer() and 'e' not in v.lower() and '.' not in v else f


# Canonical formatting vocabulary, the same for every office format. A reader writes these keys on cells, runs,
# paragraphs, table cells and shapes wherever the format has the property; a key the format does not have is absent
# (readers treat an absent key as the default below). Values: bold and italic are booleans; underline is a style name
# or None; strike is 'single', 'double' or 'none'; font is the family name; size is points; colours are 6-digit
# upper-case hex or None; alignment is left, center, right, justify or None; number_format is an Excel-style code;
# hyperlink is the target string.
FORMAT_KEYS = ('bold', 'italic', 'underline', 'strike', 'font', 'size', 'color', 'background_color', 'highlight',
               'number_format', 'alignment', 'hyperlink')
FORMAT_DEFAULTS = {'bold': False, 'italic': False, 'underline': None, 'strike': 'none', 'font': None, 'size': None,
                   'color': None, 'background_color': None, 'highlight': None, 'number_format': None,
                   'alignment': None, 'hyperlink': None}
CELL_FORMAT_DEFAULTS = dict(FORMAT_DEFAULTS, number_format='General')
ALIGNMENT = {'left': 'left', 'start': 'left', 'l': 'left', 'right': 'right', 'end': 'right', 'r': 'right',
             'center': 'center', 'ctr': 'center', 'justify': 'justify', 'both': 'justify', 'just': 'justify',
             'distribute': 'justify', 'dist': 'justify'}
# Word's named highlight colours (w:highlight), as RGB.
HIGHLIGHT_NAMES = {'yellow': 'FFFF00', 'green': '00FF00', 'cyan': '00FFFF', 'magenta': 'FF00FF', 'blue': '0000FF',
                   'red': 'FF0000', 'darkBlue': '000080', 'darkCyan': '008080', 'darkGreen': '008000',
                   'darkMagenta': '800080', 'darkRed': '800000', 'darkYellow': '808000', 'darkGray': 'A9A9A9',
                   'lightGray': 'D3D3D3', 'black': '000000', 'white': 'FFFFFF'}
# Built-in SpreadsheetML number formats (ECMA-376 part 1, 18.8.30), so an id and its code compare equal.
BUILTIN_NUMFMT = {0: 'General', 1: '0', 2: '0.00', 3: '#,##0', 4: '#,##0.00', 9: '0%', 10: '0.00%', 11: '0.00E+00',
                  12: '# ?/?', 13: '# ??/??', 14: 'mm-dd-yy', 15: 'd-mmm-yy', 16: 'd-mmm', 17: 'mmm-yy',
                  18: 'h:mm AM/PM', 19: 'h:mm:ss AM/PM', 20: 'h:mm', 21: 'h:mm:ss', 22: 'm/d/yy h:mm',
                  37: '#,##0 ;(#,##0)', 38: '#,##0 ;[Red](#,##0)', 39: '#,##0.00;(#,##0.00)',
                  40: '#,##0.00;[Red](#,##0.00)', 45: 'mm:ss', 46: '[h]:mm:ss', 47: 'mmss.0', 48: '##0.0E+0',
                  49: '@'}


def _hex(v):
    """6-digit upper-case RGB, or None for automatic, transparent or unset colours. Other names are kept as written."""
    if v is None:
        return None
    s = str(v).strip().lstrip('#').upper()
    if s in ('', 'AUTO', 'NONE', 'TRANSPARENT'):
        return None
    if len(s) == 8 and re.fullmatch(r'[0-9A-F]{8}', s):
        s = s[2:]
    if re.fullmatch(r'[0-9A-F]{6}', s):
        return s
    return str(v).strip()


def _points(v):
    """A length such as '11pt' or '11' as a float (points), or None."""
    if v is None:
        return None
    m = re.match(r'\s*(-?\d+(?:\.\d+)?)', str(v))
    return float(m.group(1)) if m else None


def _has_format(node):
    """True when a cell or run carries a formatting value that is not the default."""
    for k in FORMAT_KEYS:
        v = node.get(k)
        if v is None or v == CELL_FORMAT_DEFAULTS[k] or v is False or v == 'none':
            continue
        return True
    return False


def _split_a1(ref):
    m = re.match(r'([A-Z]+)(\d+)$', ref)
    col = 0
    for ch in m.group(1):
        col = col * 26 + ord(ch) - 64
    return int(m.group(2)), col


def _refs(ref):
    """The A1 references of a cell or a rectangular range (one cell when the range is very large)."""
    a, _, b = ref.replace('$', '').partition(':')
    r0, c0 = _split_a1(a)
    r1, c1 = _split_a1(b or a)
    if (r1 - r0 + 1) * (c1 - c0 + 1) > 10000:
        return [a]
    return [f'{col_letters(c)}{r}' for r in range(r0, r1 + 1) for c in range(c0, c1 + 1)]


# ---------------------------------------------------------------- DOCX

def _docx_run_props(rpr):
    out = dict(FORMAT_DEFAULTS)
    if rpr is None:
        return out

    def on(tag):
        el = rpr.find(W + tag)
        return el is not None and el.get(W + 'val', 'true') not in ('0', 'false', 'none')
    out['bold'] = on('b')
    out['italic'] = on('i')
    u = rpr.find(W + 'u')
    if u is not None and u.get(W + 'val') not in (None, 'none'):
        out['underline'] = u.get(W + 'val')
    out['strike'] = 'single' if on('strike') else ('double' if on('dstrike') else 'none')
    c = rpr.find(W + 'color')
    if c is not None and c.get(W + 'val') not in (None, 'auto'):
        out['color'] = _hex(c.get(W + 'val'))
    h = rpr.find(W + 'highlight')
    if h is not None:
        val = h.get(W + 'val')
        out['highlight'] = _hex(HIGHLIGHT_NAMES.get(val, val))
    shd = rpr.find(W + 'shd')
    if shd is not None and shd.get(W + 'fill') not in (None, 'auto'):
        out['background_color'] = _hex(shd.get(W + 'fill'))
    f = rpr.find(W + 'rFonts')
    if f is not None:
        out['font'] = f.get(W + 'ascii')
    sz = rpr.find(W + 'sz')
    if sz is not None:
        out['size'] = int(sz.get(W + 'val')) / 2
    return out


def _docx_styles(z):
    """Paragraph styles from word/styles.xml: the default paragraph style, each style's basedOn and jc, and the
    document default jc. Used to resolve what a paragraph with no pStyle or jc actually uses."""
    out = {'default': None, 'styles': {}, 'doc_jc': None}
    if 'word/styles.xml' not in z.namelist():
        return out
    root = _xml(z, 'word/styles.xml')
    for st in root.findall(W + 'style'):
        if st.get(W + 'type') != 'paragraph':
            continue
        sid = st.get(W + 'styleId')
        if st.get(W + 'default') == '1':
            out['default'] = sid
        based, jc = st.find(W + 'basedOn'), st.find(f'{W}pPr/{W}jc')
        out['styles'][sid] = {'based_on': based.get(W + 'val') if based is not None else None,
                              'jc': _jc_value(jc)}
    out['doc_jc'] = _jc_value(root.find(f'{W}docDefaults/{W}pPrDefault/{W}pPr/{W}jc'))
    return out


def _jc_value(jc):
    return ALIGNMENT.get(jc.get(W + 'val'), jc.get(W + 'val')) if jc is not None else None


def _docx_effective(style_id, jc, styles):
    """Paragraph style and alignment as Word applies them (ECMA-376 cascade): a paragraph with no pStyle uses the
    default paragraph style; direct alignment wins, then the style chain, then the document default, then left."""
    style_id = style_id or styles['default']
    if jc is not None:
        return style_id, jc
    seen, sid = set(), style_id
    while sid in styles['styles'] and sid not in seen:
        seen.add(sid)
        st = styles['styles'][sid]
        if st['jc'] is not None:
            return style_id, st['jc']
        sid = st['based_on']
    return style_id, styles['doc_jc'] or 'left'


def _run_key(run):
    return tuple(sorted((k, repr(v)) for k, v in run.items() if k != 'text'))


def _docx_paragraph(p, links=None, styles=None):
    styles = styles or {'default': None, 'styles': {}, 'doc_jc': None}
    runs, texts = {}, []
    for r in p.iter(W + 'r'):
        parts = []
        for ch in r:
            if ch.tag == W + 't':
                parts.append(ch.text or '')
            elif ch.tag == W + 'tab':
                parts.append('\t')
            elif ch.tag in (W + 'br', W + 'cr'):
                # python-docx convention (used by specexec): page and column breaks add no text; line breaks do.
                if ch.tag == W + 'br' and ch.get(W + 'type') in ('page', 'column'):
                    continue
                parts.append('\n')
        text = ''.join(parts)
        if not text:
            continue
        node = _docx_run_props(r.find(W + 'rPr'))
        node['text'] = text
        parent = r.getparent()
        if parent is not None and parent.tag == W + 'hyperlink':
            target = (links or {}).get(parent.get(R + 'id'))
            if target is None and parent.get(W + 'anchor'):
                target = '#' + parent.get(W + 'anchor')
            node['hyperlink'] = target
        # Adjacent runs with the same formatting are one span. Apps split runs at points where nothing visible changes.
        prev = runs.get(str(len(runs)))
        if prev is not None and _run_key(prev) == _run_key(node):
            prev['text'] += text
        else:
            runs[str(len(runs) + 1)] = node
        texts.append(text)
    ppr = p.find(W + 'pPr')
    style = jc = None
    bg = None
    numbered = False
    if ppr is not None:
        ps = ppr.find(W + 'pStyle')
        style = ps.get(W + 'val') if ps is not None else None
        j = ppr.find(W + 'jc')
        jc = ALIGNMENT.get(j.get(W + 'val'), j.get(W + 'val')) if j is not None else None
        shd = ppr.find(W + 'shd')
        if shd is not None and shd.get(W + 'fill') not in (None, 'auto'):
            bg = _hex(shd.get(W + 'fill'))
        numbered = ppr.find(W + 'numPr') is not None
    style, jc = _docx_effective(style, jc, styles)
    return {'text': ''.join(texts), 'style': style, 'alignment': jc, 'background_color': bg,
            'numbered': numbered, 'runs': runs}


def _docx_table(tbl, links=None, styles=None):
    rows = {}
    grid = tbl.find(W + 'tblGrid')
    for i, tr in enumerate(tbl.findall(W + 'tr'), 1):
        cells = {}
        for j, tc in enumerate(tr.findall(W + 'tc'), 1):
            paras = [_docx_paragraph(p, links, styles) for p in tc.findall(W + 'p')]
            shd = tc.find(f'{W}tcPr/{W}shd')
            bg = _hex(shd.get(W + 'fill')) if shd is not None and shd.get(W + 'fill') not in (None, 'auto') else None
            cells[str(j)] = {'text': '\n'.join(p['text'] for p in paras), 'background_color': bg,
                             'paragraphs': {str(k + 1): p for k, p in enumerate(paras)}}
        rows[str(i)] = {'cells': cells}
    return {'rows': rows, 'columns': len(grid.findall(W + 'gridCol')) if grid is not None else 0}


def read_docx(z):
    root = _xml(z, 'word/document.xml')
    body = root.find(W + 'body')
    links = _link_targets(z, 'word/document.xml')
    styles = _docx_styles(z)
    paragraphs, tables, order = {}, {}, []
    for el in body:
        if el.tag == W + 'p':
            paragraphs[str(len(paragraphs) + 1)] = _docx_paragraph(el, links, styles)
            order.append(['p', len(paragraphs)])
        elif el.tag == W + 'tbl':
            tables[str(len(tables) + 1)] = _docx_table(el, links, styles)
            order.append(['t', len(tables)])
    return {'paragraphs': paragraphs, 'tables': tables, 'body_order': order}


# ---------------------------------------------------------------- XLSX

def _xlsx_theme(z):
    """Theme colours in SpreadsheetML theme-index order: 0 lt1, 1 dk1, 2 lt2, 3 dk2, 4-9 accent1-6, 10 hlink, 11 folHlink."""
    if 'xl/theme/theme1.xml' not in z.namelist():
        return []
    scheme = _xml(z, 'xl/theme/theme1.xml').find(f'.//{A}clrScheme')
    if scheme is None:
        return []
    by_name = {}
    for el in scheme:
        clr = el[0] if len(el) else None
        val = None
        if clr is not None:
            val = clr.get('val') if etree.QName(clr).localname == 'srgbClr' else clr.get('lastClr')
        by_name[etree.QName(el).localname] = _hex(val)
    order = ('lt1', 'dk1', 'lt2', 'dk2', 'accent1', 'accent2', 'accent3', 'accent4', 'accent5', 'accent6', 'hlink',
             'folHlink')
    return [by_name.get(n) for n in order]


def _tint(hex6, tint):
    """Excel's theme tint: lighten (tint > 0) or darken (tint < 0) in HLS lightness."""
    r, g, b = (int(hex6[i:i + 2], 16) / 255 for i in (0, 2, 4))
    h, lightness, s = colorsys.rgb_to_hls(r, g, b)
    lightness = lightness * (1 + tint) if tint < 0 else lightness * (1 - tint) + tint
    return '%02X%02X%02X' % tuple(round(x * 255) for x in colorsys.hls_to_rgb(h, lightness, s))


def _xlsx_color(el, theme=()):
    """A colour element as RGB. A theme colour resolves through the theme part (with its tint). An indexed colour
    keeps its index, since the default palette is not read."""
    if el is None:
        return None
    if el.get('rgb'):
        return _hex(el.get('rgb'))
    if el.get('theme') is not None:
        idx = int(el.get('theme'))
        base = theme[idx] if idx < len(theme) else None
        if base is None:
            return f'theme:{idx}'
        tint = float(el.get('tint') or 0)
        return _tint(base, tint) if tint and re.fullmatch(r'[0-9A-F]{6}', base) else base
    if el.get('indexed') is not None:
        return f"indexed:{el.get('indexed')}"
    return None


def _xlsx_styles(z):
    """Cell formats (cellXfs) resolved to their font, fill, number format and alignment.
    The raw xf index is not kept: an app renumbers it on every save, so it is not a property of the cell."""
    if 'xl/styles.xml' not in z.namelist():
        return [], [], []
    root = _xml(z, 'xl/styles.xml')
    theme = _xlsx_theme(z)
    # An escaped space ("\ ") is a literal space; ODF and most writers store the plain space.
    numfmts = {nf.get('numFmtId'): re.sub(r'\\ ', ' ', nf.get('formatCode')) for nf in root.iter(S + 'numFmt')}
    fonts = []
    fonts_el = root.find(S + 'fonts')
    for f in (fonts_el if fonts_el is not None else []):
        u, sz, nm = f.find(S + 'u'), f.find(S + 'sz'), f.find(S + 'name')
        fonts.append({'bold': f.find(S + 'b') is not None, 'italic': f.find(S + 'i') is not None,
                      'underline': None if u is None else (u.get('val') or 'single'),
                      'strike': 'single' if f.find(S + 'strike') is not None else 'none',
                      'font': nm.get('val') if nm is not None else None,
                      'size': _points(sz.get('val')) if sz is not None else None,
                      'color': _xlsx_color(f.find(S + 'color'), theme)})
    fills = []
    fills_el = root.find(S + 'fills')
    for fl in (fills_el if fills_el is not None else []):
        pf = fl.find(S + 'patternFill')
        fg = pf.find(S + 'fgColor') if pf is not None and pf.get('patternType') == 'solid' else None
        fills.append(_xlsx_color(fg, theme))
    xfs = []
    cell_xfs = root.find(S + 'cellXfs')
    for xf in (cell_xfs if cell_xfs is not None else []):
        nid = xf.get('numFmtId', '0')
        code = numfmts.get(nid)
        if code is None:
            code = BUILTIN_NUMFMT.get(int(nid), nid) if nid.isdigit() else nid
        al = xf.find(S + 'alignment')
        horiz = al.get('horizontal') if al is not None else None
        xfs.append({'number_format': code, 'font': int(xf.get('fontId', '0')), 'fill': int(xf.get('fillId', '0')),
                    'alignment': ALIGNMENT.get(horiz, horiz) if horiz not in (None, 'general') else None})
    return xfs, fonts, fills


def _xlsx_format(xf, fonts, fills):
    """The formatting keys of one cell format."""
    f = fonts[xf['font']] if xf['font'] < len(fonts) else {}
    out = dict(FORMAT_DEFAULTS, number_format=xf['number_format'], alignment=xf['alignment'])
    out.update({'bold': bool(f.get('bold')), 'italic': bool(f.get('italic')), 'underline': f.get('underline'),
                'strike': f.get('strike', 'none'), 'font': f.get('font'), 'size': f.get('size'),
                'color': f.get('color'),
                'background_color': fills[xf['fill']] if xf['fill'] < len(fills) else None})
    return out


def _xlsx_shared(z):
    if 'xl/sharedStrings.xml' not in z.namelist():
        return []
    root = _xml(z, 'xl/sharedStrings.xml')
    return [''.join(t.text or '' for t in si.iter(S + 't')) for si in root.findall(S + 'si')]


def _xlsx_shared_masters(root):
    """Shared-formula groups of a sheet: group index -> (origin cell, formula text without '=')."""
    masters = {}
    for c in root.iter(S + 'c'):
        f = c.find(S + 'f')
        if f is not None and f.get('t') == 'shared' and f.text:
            masters[f.get('si')] = (c.get('r'), f.text)
    return masters


def _xlsx_cell(c, shared, xfs, fonts, fills, masters=None):
    ref = c.get('r')
    t = c.get('t')
    v = c.find(S + 'v')
    f = c.find(S + 'f')
    raw = v.text if v is not None else None
    if t == 's' and raw is not None:
        value = shared[int(raw)]
    elif t == 'inlineStr':
        value = ''.join(x.text or '' for x in c.iter(S + 't'))
    elif t in ('str', 'e'):
        value = raw
    elif t == 'b':
        value = bool(int(raw)) if raw is not None else None
    else:
        value = _num(raw) if raw is not None else None
    s = int(c.get('s', '0'))
    formula = ('=' + f.text) if f is not None and f.text else None
    if f is not None and f.get('t') == 'shared' and not f.text and masters and f.get('si') in masters:
        # A shared-formula child stores no text; its formula is the group master's, moved to this cell.
        origin, text = masters[f.get('si')]
        formula = Translator('=' + text, origin=origin).translate_formula(ref)
    node = {'value': value, 'formula': formula}
    node.update(_xlsx_format(xfs[s], fonts, fills) if s < len(xfs) else CELL_FORMAT_DEFAULTS)
    return ref, node


def _xlsx_hyperlinks(root, links, cells):
    """Hyperlink targets of the sheet, applied to every cell of each linked reference."""
    hl = root.find(S + 'hyperlinks')
    if hl is None:
        return
    for h in hl.findall(S + 'hyperlink'):
        target = links.get(h.get(R + 'id')) or h.get('location')
        for ref in _refs(h.get('ref')):
            node = cells.setdefault(ref, dict(CELL_FORMAT_DEFAULTS, value=None, formula=None))
            node['hyperlink'] = target


def _chart_tree(root):
    out = {'type': None, 'title': None, 'series': {}}
    plot = root.find(f'{C}chart/{C}plotArea')
    if plot is None:
        return out
    for el in plot:
        name = etree.QName(el).localname
        if name == 'barChart':
            bd = el.find(C + 'barDir')
            out['type'] = 'column' if bd is not None and bd.get('val') == 'col' else 'bar'
        elif name == 'lineChart':
            out['type'] = 'line'
        elif name.endswith('Chart') and out['type'] is None:
            out['type'] = name[:-5].lower()
        if name.endswith('Chart'):
            for ser in el.findall(C + 'ser'):
                idx = str(len(out['series']) + 1)
                ref = ser.find(f'{C}val/{C}numRef/{C}f')
                cache = ser.find(f'{C}val/{C}numRef/{C}numCache')
                vals = []
                if cache is not None:
                    for pt in cache.findall(C + 'pt'):
                        vals.append(_num(pt.find(C + 'v').text))
                out['series'][idx] = {'ref': ref.text if ref is not None else None, 'cached_values': vals}
    title = root.find(f'{C}chart/{C}title')
    if title is not None:
        out['title'] = ''.join(t.text or '' for t in title.iter(A + 't')) or None
    return out


def read_xlsx(z):
    xfs, fonts, fills = _xlsx_styles(z)
    shared = _xlsx_shared(z)
    wb = _xml(z, 'xl/workbook.xml')
    wrels = _rels(z, 'xl/workbook.xml')
    sheets = {}
    order = []
    for sh in wb.iter(S + 'sheet'):
        name = sh.get('name')
        order.append(name)
        part = wrels[sh.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id')][1]
        root = _xml(z, part)
        cells, hidden_rows, hidden_cols, merged = {}, [], [], []
        masters = _xlsx_shared_masters(root)
        for row in root.iter(S + 'row'):
            rnum = int(row.get('r'))
            if row.get('hidden') in ('1', 'true'):
                hidden_rows.append(rnum)
            for c in row.findall(S + 'c'):
                ref, node = _xlsx_cell(c, shared, xfs, fonts, fills, masters)
                if node['value'] not in (None, '') or node['formula'] or _has_format(node):
                    cells[ref] = node
        _xlsx_hyperlinks(root, _link_targets(z, part), cells)
        for col in root.iter(S + 'col'):
            if col.get('hidden') in ('1', 'true'):
                for i in range(int(col.get('min')), int(col.get('max')) + 1):
                    hidden_cols.append(col_letters(i))
        af = root.find(S + 'autoFilter')
        for mc in root.iter(S + 'mergeCell'):
            merged.append(mc.get('ref'))
        charts, pivots = {}, {}
        rels = _rels(z, part)
        for rid, (typ, target) in rels.items():
            if typ == 'drawing' and target in z.namelist():
                drels = _rels(z, target)
                for did, (dtyp, dtarget) in drels.items():
                    if dtyp == 'chart' and dtarget in z.namelist():
                        charts[str(len(charts) + 1)] = _chart_tree(_xml(z, dtarget))
            if typ == 'pivotTable' and target in z.namelist():
                pvt = _xml(z, target)
                cache_names = []
                for pr in _rels(z, target).values():
                    if pr[0] == 'pivotCacheDefinition' and pr[1] in z.namelist():
                        cdef = _xml(z, pr[1])
                        cache_names = [cf.get('name') for cf in cdef.iter(S + 'cacheField')]
                pivots[str(len(pivots) + 1)] = _xlsx_pivot_from_root(pvt, cache_names)
        sheets[name] = {'cells': dict(sorted(cells.items(), key=_a1_key)),
                        'hidden_rows': sorted(hidden_rows), 'hidden_columns': sorted(hidden_cols, key=lambda s: (len(s), s)),
                        'autofilter': af.get('ref') if af is not None else None,
                        'merged': merged, 'charts': charts, 'pivot_tables': pivots}
    return {'sheet_names': order, 'sheets': sheets}


def _xlsx_pivot_from_root(root, cache_names):
    row_fields, data_fields = [], []
    rf = root.find(S + 'rowFields')
    if rf is not None:
        for f in rf.findall(S + 'field'):
            idx = int(f.get('x', '-2'))
            if 0 <= idx < len(cache_names):
                row_fields.append(cache_names[idx])
    for df in root.iter(S + 'dataField'):
        idx = int(df.get('fld', '0'))
        data_fields.append({'source': cache_names[idx] if idx < len(cache_names) else None,
                            'name': df.get('name'), 'function': df.get('subtotal', 'sum')})
    loc = root.find(S + 'location')
    return {'name': root.get('name'), 'location': loc.get('ref') if loc is not None else None,
            'row_fields': row_fields, 'data_fields': data_fields}


def _a1_key(item):
    ref = item[0]
    m = re.match(r'([A-Z]+)(\d+)', ref)
    col = 0
    for ch in m.group(1):
        col = col * 26 + ord(ch) - 64
    return int(m.group(2)), col


# ---------------------------------------------------------------- PPTX

def _pptx_run_props(rpr, links=None):
    out = dict(FORMAT_DEFAULTS)
    if rpr is None:
        return out
    out['bold'] = rpr.get('b') == '1'
    out['italic'] = rpr.get('i') == '1'
    u = rpr.get('u')
    out['underline'] = None if u in (None, 'none') else {'sng': 'single', 'dbl': 'double'}.get(u, u)
    out['strike'] = {'sngStrike': 'single', 'dblStrike': 'double'}.get(rpr.get('strike'), 'none')
    fill = rpr.find(A + 'solidFill')
    if fill is not None:
        clr = fill.find(A + 'srgbClr')
        if clr is not None:
            out['color'] = _hex(clr.get('val'))
    hl = rpr.find(A + 'highlight')
    if hl is not None:
        clr = hl.find(A + 'srgbClr')
        out['highlight'] = _hex(clr.get('val')) if clr is not None else None
    latin = rpr.find(A + 'latin')
    if latin is not None:
        out['font'] = latin.get('typeface')
    if rpr.get('sz') is not None:
        out['size'] = int(rpr.get('sz')) / 100
    link = rpr.find(A + 'hlinkClick')
    if link is not None:
        out['hyperlink'] = (links or {}).get(link.get(R + 'id'))
    return out


def _pptx_paragraphs(txbody, links=None):
    paras = {}
    if txbody is None:
        return paras
    for p in txbody.findall(A + 'p'):
        runs, texts = {}, []
        for r in p.iter(A + 'r', A + 'br'):
            if r.tag == A + 'br':
                texts.append('\n')
                continue
            t = r.find(A + 't')
            node = _pptx_run_props(r.find(A + 'rPr'), links)
            node['text'] = t.text if t is not None and t.text else ''
            runs[str(len(runs) + 1)] = node
            texts.append(node['text'])
        ppr = p.find(A + 'pPr')
        bullet = 'inherited'
        alignment = None
        if ppr is not None:
            tags = [etree.QName(c).localname for c in ppr]
            for name, kind in (('buNone', 'none'), ('buChar', 'char'), ('buAutoNum', 'number'), ('buBlip', 'picture')):
                if name in tags:
                    bullet = kind
                    break
            algn = ppr.get('algn')
            alignment = ALIGNMENT.get(algn, algn) if algn else None
        paras[str(len(paras) + 1)] = {'text': ''.join(texts), 'bullet': bullet, 'alignment': alignment,
                                      'background_color': None, 'runs': runs}
    return paras


def _pptx_shape(el, links=None):
    kind = etree.QName(el).localname
    cnv = el.find(f'.//{P}cNvPr')
    name = cnv.get('name') if cnv is not None else None
    node = {'kind': {'sp': 'sp', 'pic': 'picture', 'graphicFrame': 'graphic_frame', 'grpSp': 'group',
                     'cxnSp': 'connector'}.get(kind, kind), 'id': cnv.get('id') if cnv is not None else None,
            'name': name, 'x_cm': None, 'y_cm': None, 'width_cm': None, 'height_cm': None,
            'picture_fill': False, 'background_color': None, 'paragraphs': {}}
    fill = el.find(f'{P}spPr/{A}solidFill/{A}srgbClr')
    if fill is not None:
        node['background_color'] = _hex(fill.get('val'))
    xfrm = el.find(f'{P}spPr/{A}xfrm')
    if xfrm is None:
        xfrm = el.find(f'{P}xfrm')
    if xfrm is not None:
        off, ext = xfrm.find(A + 'off'), xfrm.find(A + 'ext')
        if off is not None:
            node['x_cm'] = int(off.get('x')) / EMU_PER_CM
            node['y_cm'] = int(off.get('y')) / EMU_PER_CM
        if ext is not None:
            node['width_cm'] = int(ext.get('cx')) / EMU_PER_CM
            node['height_cm'] = int(ext.get('cy')) / EMU_PER_CM
    if el.find(f'{P}spPr/{A}blipFill') is not None:
        node['picture_fill'] = True
    txbody = el.find(P + 'txBody')
    node['paragraphs'] = _pptx_paragraphs(txbody, links)
    node['text'] = '\n'.join(p['text'] for p in node['paragraphs'].values())
    if kind == 'graphicFrame':
        uri = el.find(f'.//{A}graphicData')
        node['graphic_data'] = uri.get('uri').rsplit('/', 1)[-1] if uri is not None and uri.get('uri') else None
    return node


def read_pptx(z):
    prs = _xml(z, 'ppt/presentation.xml')
    prels = _rels(z, 'ppt/presentation.xml')
    slides = {}
    for sid in prs.iter(P + 'sldId'):
        part = prels[sid.get(R + 'id')][1]
        root = _xml(z, part)
        shapes = {}
        tree = root.find(f'{P}cSld/{P}spTree')
        order = []
        links = _link_targets(z, part)
        for el in tree:
            if etree.QName(el).localname in ('sp', 'pic', 'graphicFrame', 'grpSp', 'cxnSp'):
                node = _pptx_shape(el, links)
                base = node['name'] or f'unnamed{len(order) + 1}'
                key, n = base, 2
                while key in shapes:
                    key = f'{base}#{n}'
                    n += 1
                node['z_order'] = len(order) + 1
                shapes[key] = node
                order.append(key)
        tr = root.find(P + 'transition')
        transition = None
        if tr is not None:
            kids = [c for c in tr if etree.QName(c).localname not in ('extLst', 'sndAc')]
            transition = etree.QName(kids[0]).localname if kids else 'none'
        slides[str(len(slides) + 1)] = {'shapes': shapes, 'shape_order': order, 'transition': transition}
    return {'slide_count': len(slides), 'slides': slides}


# ---------------------------------------------------------------- ODF

def _odf_text(el):
    out = [el.text or '']
    for ch in el:
        local = etree.QName(ch).localname
        if local in ('note', 'annotation'):
            pass
        elif local == 's':
            out.append(' ' * int(ch.get(ODF_T + 'c', '1')))
        elif local == 'tab':
            out.append('\t')
        elif local == 'line-break':
            out.append('\n')
        else:
            out.append(_odf_text(ch))
        out.append(ch.tail or '')
    return ''.join(out)


def _odf_style_table(roots):
    styles = {}
    for root in roots:
        if root is None:
            continue
        for st in root.iter(ODF_ST + 'style'):
            name = st.get(ODF_ST + 'name')
            tp = st.find(ODF_ST + 'text-properties')
            pp = st.find(ODF_ST + 'paragraph-properties')
            tcp = st.find(ODF_ST + 'table-cell-properties')
            tbl_r = st.find(ODF_ST + 'table-row-properties')
            tbl_c = st.find(ODF_ST + 'table-column-properties')
            styles[name] = {'parent': st.get(ODF_ST + 'parent-style-name'), 'family': st.get(ODF_ST + 'family'),
                            'text': _odf_text_props(tp), 'para': _odf_para_props(pp),
                            'cell_background': _hex(tcp.get(ODF_FO + 'background-color')) if tcp is not None else None,
                            'data_style': st.get(ODF_ST + 'data-style-name'),
                            'row_visibility': tbl_r.get(ODF_TB + 'visibility') if tbl_r is not None else None,
                            'column_visibility': tbl_c.get(ODF_TB + 'visibility') if tbl_c is not None else None}
        # The family default (style:default-style) is the root of every style chain of its family.
        for st in root.iter(ODF_ST + 'default-style'):
            family = st.get(ODF_ST + 'family')
            styles[f'__default__:{family}'] = {'parent': None, 'family': family,
                                               'text': _odf_text_props(st.find(ODF_ST + 'text-properties')),
                                               'para': _odf_para_props(st.find(ODF_ST + 'paragraph-properties')),
                                               'cell_background': None, 'data_style': None,
                                               'row_visibility': None, 'column_visibility': None}
    return styles


def _odf_para_props(pp):
    if pp is None:
        return {}
    algn = pp.get(ODF_FO + 'text-align')
    return {'alignment': ALIGNMENT.get(algn, algn) if algn else None,
            'background_color': _hex(pp.get(ODF_FO + 'background-color'))}


def _odf_text_props(tp):
    if tp is None:
        return {}
    out = {}
    fw = tp.get(ODF_FO + 'font-weight')
    if fw is not None:
        out['bold'] = fw in ('bold', '600', '700', '800', '900')
    fs = tp.get(ODF_FO + 'font-style')
    if fs is not None:
        out['italic'] = fs in ('italic', 'oblique')
    u = tp.get(ODF_ST + 'text-underline-style')
    if u is not None:
        out['underline'] = None if u == 'none' else ('single' if u == 'solid' else u)
    s = tp.get(ODF_ST + 'text-line-through-style')
    if s is not None:
        out['strike'] = 'none' if s == 'none' else (
            'double' if tp.get(ODF_ST + 'text-line-through-type') == 'double' else 'single')
    c = tp.get(ODF_FO + 'color')
    if c is not None:
        out['color'] = _hex(c)
    bg = tp.get(ODF_FO + 'background-color')
    if bg is not None:
        out['background_color'] = _hex(bg)
    fn = tp.get(ODF_ST + 'font-name') or tp.get(ODF_FO + 'font-family')
    if fn is not None:
        out['font'] = fn.strip("'")
    sz = _points(tp.get(ODF_FO + 'font-size'))
    if sz is not None:
        out['size'] = sz
    return out


def _resolve_style(styles, name, key='text', default_family=None):
    """Merge a style's properties over its parents (child values win; an unset value does not hide a parent's).
    With default_family, the family's default style (style:default-style) is the root of the chain."""
    chain, seen = [], set()
    while name and name in styles and name not in seen:
        seen.add(name)
        chain.append(styles[name])
        name = styles[name]['parent']
    if default_family and f'__default__:{default_family}' in styles:
        chain.append(styles[f'__default__:{default_family}'])
    merged = {}
    for st in reversed(chain):
        if isinstance(st.get(key), dict):
            merged.update({k: v for k, v in st[key].items() if v is not None})
    return merged


def _odf_number_code(el):
    """An Excel-style format code for an ODF data style (number:number-style and friends). Approximate: it names the
    parts a reader needs to compare (digits, decimals, grouping, percent, currency symbol, date and time fields)."""
    kind = etree.QName(el).localname
    if kind == 'boolean-style':
        return 'BOOLEAN'
    if kind == 'text-style':
        return '@'
    parts = []
    for ch in el:
        ln = etree.QName(ch).localname
        style = ch.get(ODF_NUM + 'style')
        long_ = style == 'long'
        if ln == 'number':
            dec = int(ch.get(ODF_NUM + 'decimal-places', '0') or 0)
            digits = '#,##0' if ch.get(ODF_NUM + 'grouping') == 'true' else '0'
            parts.append(digits + ('.' + '0' * dec if dec else ''))
        elif ln == 'scientific-number':
            parts.append('0.00E+00')
        elif ln == 'fraction':
            parts.append('# ?/?')
        elif ln == 'currency-symbol':
            parts.append('[$' + (ch.text or '') + ']')
        elif ln == 'text':
            parts.append(ch.text or '')
        elif ln == 'text-content':
            parts.append('@')
        elif ln == 'day':
            parts.append('dd' if long_ else 'd')
        elif ln == 'day-of-week':
            parts.append('dddd' if long_ else 'ddd')
        elif ln == 'month':
            textual = ch.get(ODF_NUM + 'textual') == 'true'
            parts.append(('mmmm' if long_ else 'mmm') if textual else ('mm' if long_ else 'm'))
        elif ln == 'year':
            parts.append('yyyy' if long_ else 'yy')
        elif ln == 'hours':
            parts.append('hh' if long_ else 'h')
        elif ln == 'minutes':
            parts.append('mm' if long_ else 'm')
        elif ln == 'seconds':
            parts.append('ss' if long_ else 's')
        elif ln == 'am-pm':
            parts.append('AM/PM')
    return ''.join(parts) or 'General'


def _odf_number_formats(roots):
    """{data style name: format code} for every number, percentage, currency, date, time, boolean and text style."""
    out = {}
    for root in roots:
        if root is None:
            continue
        for el in root.iter():
            if not isinstance(el.tag, str) or not el.tag.startswith(ODF_NUM):
                continue
            name = el.get(ODF_ST + 'name')
            if name and etree.QName(el).localname.endswith('-style'):
                out[name] = _odf_number_code(el)
    return out


def _odf_runs(p, styles, para_style, cell_text=None):
    """Runs of a paragraph with their resolved text properties. In a table cell (cell_text given), the cell style's
    text properties are the base and the paragraph style applies over them; elsewhere the paragraph style chain
    ends at the paragraph family's default style."""
    base = dict(FORMAT_DEFAULTS)
    if cell_text is None:
        base.update(_resolve_style(styles, para_style, default_family='paragraph'))
    else:
        base.update(cell_text)
        base.update(_resolve_style(styles, para_style))
    runs = {}

    def emit(text, props):
        if not text:
            return
        node = dict(base)
        node.update(props)
        node['text'] = text
        node['highlight'] = node.get('background_color')
        runs[str(len(runs) + 1)] = node

    def walk(el, props):
        emit(el.text or '', props)
        for ch in el:
            local = etree.QName(ch).localname
            if ch.tag == ODF_T + 'span':
                sprops = dict(props)
                sprops.update(_resolve_style(styles, ch.get(ODF_T + 'style-name')))
                walk(ch, sprops)
            elif ch.tag == ODF_T + 'a':
                lprops = dict(props, hyperlink=ch.get(ODF_XL + 'href'))
                walk(ch, lprops)
            elif local in ('note', 'annotation'):
                pass
            elif local == 's':
                emit(' ' * int(ch.get(ODF_T + 'c', '1')), props)
            elif local == 'tab':
                emit('\t', props)
            elif local == 'line-break':
                emit('\n', props)
            else:
                walk(ch, props)
            emit(ch.tail or '', props)
    walk(p, {})
    return runs


def _odf_paragraph(p, styles):
    style = p.get(ODF_T + 'style-name')
    text = _odf_text(p)
    para = _resolve_style(styles, style, key='para') if style else {}
    return {'text': text, 'style': style, 'alignment': para.get('alignment'),
            'background_color': para.get('background_color'), 'runs': _odf_runs(p, styles, style)}


def _odf_blocks(el):
    for ch in el:
        if ch.tag in (ODF_T + 'p', ODF_T + 'h'):
            yield ('p', ch)
        elif ch.tag == ODF_TB + 'table':
            yield ('t', ch)
        elif ch.tag in (ODF_T + 'list', ODF_T + 'list-item', ODF_T + 'list-header', ODF_T + 'section'):
            yield from _odf_blocks(ch)


def _odf_table(el, styles):
    rows = {}
    for tr in el.iter(ODF_TB + 'table-row'):
        r = {}
        for tc in tr:
            if tc.tag not in (ODF_TB + 'table-cell', ODF_TB + 'covered-table-cell'):
                continue
            paras = [_odf_text(p) for p in tc if p.tag in (ODF_T + 'p', ODF_T + 'h')]
            cst = styles.get(tc.get(ODF_TB + 'style-name'), {})
            r[str(len(r) + 1)] = {'text': '\n'.join(paras), 'background_color': cst.get('cell_background')}
        rows[str(len(rows) + 1)] = {'cells': r}
    return {'rows': rows}


def _odf_date_serial(text):
    """An ODF date or date-time (ISO 8601) as a spreadsheet serial number (days since 1899-12-30), as xlsx stores it.
    Text that does not parse is kept as written."""
    if not text:
        return None
    try:
        dt = datetime.datetime.fromisoformat(text)
    except ValueError:
        return text
    if dt.tzinfo is not None:
        dt = dt.replace(tzinfo=None)
    days = round((dt - datetime.datetime(1899, 12, 30)).total_seconds() / 86400, 10)
    return int(days) if days.is_integer() else days


def _odf_column_defaults(table):
    """[(first column, last column, default cell style name)] from the table's column definitions. A cell without a
    style of its own takes its column's default cell style (this is how LibreOffice writes formatted columns)."""
    ranges, col_no = [], 0
    for tc in table.iter(ODF_TB + 'table-column'):
        reps = min(int(tc.get(ODF_TB + 'number-columns-repeated', '1')), 1024)
        if tc.get(ODF_TB + 'default-cell-style-name'):
            ranges.append((col_no + 1, col_no + reps, tc.get(ODF_TB + 'default-cell-style-name')))
        col_no += reps
    return ranges


def _odf_column_style(ranges, col_no):
    for lo, hi, name in ranges:
        if lo <= col_no <= hi:
            return name
    return None


def _odf_cell_format(tc, sname, styles, numfmts):
    """Formatting of one table cell: the text properties of its first run, the cell fill, the number format of its
    data style, and the alignment of its paragraph. A cell's hyperlink is the link on any of its runs.
    sname is the cell style that applies (the cell's own, else its column's default)."""
    cst = styles.get(sname, {})
    out = dict(CELL_FORMAT_DEFAULTS)
    if cst.get('data_style'):
        out['number_format'] = numfmts.get(cst['data_style'], 'General')
    out['background_color'] = cst.get('cell_background')
    cell_text = _resolve_style(styles, sname, default_family='table-cell')
    text_keys = ('bold', 'italic', 'underline', 'strike', 'font', 'size', 'color', 'highlight')
    p = next((c for c in tc if c.tag in (ODF_T + 'p', ODF_T + 'h')), None)
    # Horizontal alignment is set on the paragraph style or on the cell style (LibreOffice writes it on the cell).
    out['alignment'] = _resolve_style(styles, sname, key='para').get('alignment')
    runs = {}
    if p is not None:
        pstyle = p.get(ODF_T + 'style-name')
        out['alignment'] = (_resolve_style(styles, pstyle, key='para').get('alignment') if pstyle else None) \
            or out['alignment']
        runs = _odf_runs(p, styles, pstyle, cell_text=cell_text)
    if runs:
        first = next(iter(runs.values()))
        for k in text_keys:
            out[k] = first.get(k, out[k])
    else:
        for k in text_keys:
            out[k] = cell_text.get(k, out[k])
    out['hyperlink'] = next((r['hyperlink'] for r in runs.values() if r.get('hyperlink')), None)
    return out


def _odf_sheet(table, styles, numfmts):
    cells, hidden_rows = {}, []
    row_no = 0
    col_ranges = _odf_column_defaults(table)
    formats = {}  # per source cell and effective style: a repeated cell is formatted once
    for tr in table.iter(ODF_TB + 'table-row'):
        reps = min(int(tr.get(ODF_TB + 'number-rows-repeated', '1')), 4096)
        vis = styles.get(tr.get(ODF_TB + 'style-name'), {}).get('row_visibility')
        for _ in range(reps):
            row_no += 1
            if vis == 'collapse':
                hidden_rows.append(row_no)
            col_no = 0
            for tc in tr:
                if tc.tag not in (ODF_TB + 'table-cell', ODF_TB + 'covered-table-cell'):
                    continue
                creps = min(int(tc.get(ODF_TB + 'number-columns-repeated', '1')), 1024)
                for _ in range(creps):
                    col_no += 1
                    vt = tc.get(ODF_OF + 'value-type')
                    text = '\n'.join(_odf_text(p) for p in tc if p.tag in (ODF_T + 'p', ODF_T + 'h'))
                    if vt in ('float', 'percentage', 'currency'):
                        value = _num(tc.get(ODF_OF + 'value'))
                    elif vt == 'date':
                        value = _odf_date_serial(tc.get(ODF_OF + 'date-value'))
                    elif vt == 'boolean':
                        value = tc.get(ODF_OF + 'boolean-value') == 'true'
                    elif vt == 'string':
                        value = tc.get(ODF_OF + 'string-value') or text
                    else:
                        value = text or None
                    f = tc.get(ODF_TB + 'formula')
                    formula = re.sub(r'^of:', '', f) if f else None
                    sname = tc.get(ODF_TB + 'style-name') or _odf_column_style(col_ranges, col_no)
                    key = (id(tc), sname)
                    if key not in formats:
                        formats[key] = _odf_cell_format(tc, sname, styles, numfmts)
                    fmt = formats[key]
                    # An empty cell is kept only when it has a style of its own: a column's default format describes
                    # the column, and recording every empty cell of a formatted column would be noise.
                    own_style = tc.get(ODF_TB + 'style-name') is not None
                    if value not in (None, '') or formula or (own_style and _has_format(fmt)):
                        ref = f'{col_letters(col_no)}{row_no}'
                        cells[ref] = dict(fmt, value=value, formula=formula, text=text, value_type=vt)
    hidden_cols = []
    col_no = 0
    for tc in table.iter(ODF_TB + 'table-column'):
        reps = min(int(tc.get(ODF_TB + 'number-columns-repeated', '1')), 1024)
        vis = styles.get(tc.get(ODF_TB + 'style-name'), {}).get('column_visibility')
        for _ in range(reps):
            col_no += 1
            if vis == 'collapse':
                hidden_cols.append(col_letters(col_no))
    return {'cells': dict(sorted(cells.items(), key=_a1_key)), 'hidden_rows': hidden_rows,
            'hidden_columns': hidden_cols, 'autofilter': None, 'merged': [], 'charts': {}, 'pivot_tables': {}}


def _odf_shape(el, styles):
    local = etree.QName(el).localname
    name = el.get(ODF_DR + 'name') or el.get(ODF_PR + 'name')
    node = {'kind': local, 'name': name, 'x_cm': _cm(el.get(ODF_SVG + 'x')), 'y_cm': _cm(el.get(ODF_SVG + 'y')),
            'width_cm': _cm(el.get(ODF_SVG + 'width')), 'height_cm': _cm(el.get(ODF_SVG + 'height')),
            'picture_fill': False, 'paragraphs': {}}
    paras = {}
    for p in el.iter(ODF_T + 'p', ODF_T + 'h'):
        pnode = _odf_paragraph(p, styles)
        paras[str(len(paras) + 1)] = {'text': pnode['text'], 'bullet': 'inherited', 'alignment': pnode['alignment'],
                                      'background_color': pnode['background_color'], 'runs': pnode['runs']}
    node['paragraphs'] = paras
    node['text'] = '\n'.join(p['text'] for p in paras.values())
    return node


def _cm(v):
    if not v:
        return None
    m = re.match(r'(-?[\d.]+)(cm|mm|in|pt|px)?', v)
    if not m:
        return None
    f = float(m.group(1))
    unit = m.group(2) or 'cm'
    return {'cm': f, 'mm': f / 10, 'in': f * 2.54, 'pt': f * 2.54 / 72, 'px': f * 2.54 / 96}[unit]


def read_odf(z, mime):
    content = _xml(z, 'content.xml')
    roots = [content]
    if 'styles.xml' in z.namelist():
        roots.append(_xml(z, 'styles.xml'))
    styles = _odf_style_table(roots)
    numfmts = _odf_number_formats(roots)
    body = content.find(ODF_OF + 'body')
    if 'spreadsheet' in mime:
        out = {'sheet_names': [], 'sheets': {}}
        for table in body.iter(ODF_TB + 'table'):
            name = table.get(ODF_TB + 'name')
            out['sheet_names'].append(name)
            out['sheets'][name] = _odf_sheet(table, styles, numfmts)
        return out
    if 'presentation' in mime:
        slides = {}
        for page in body.iter(ODF_DR + 'page'):
            shapes, order = {}, []
            for el in page:
                if etree.QName(el).localname in ('frame', 'custom-shape', 'rect', 'ellipse', 'image', 'line', 'g', 'polygon', 'path'):
                    node = _odf_shape(el, styles)
                    base = node['name'] or f'unnamed{len(order) + 1}'
                    key, n = base, 2
                    while key in shapes:
                        key = f'{base}#{n}'
                        n += 1
                    shapes[key] = node
                    order.append(key)
            pst = styles.get(page.get(ODF_DR + 'style-name'), {})
            transition = page.get(ODF_PR + 'transition-style') or page.get(ODF_PR + 'transition-type')
            slides[str(len(slides) + 1)] = {'shapes': shapes, 'shape_order': order,
                                            'transition': transition if transition else None,
                                            'page_name': page.get(ODF_DR + 'name'), 'style': pst.get('parent')}
        return {'slide_count': len(slides), 'slides': slides}
    # text document (odt)
    blocks = list(_odf_blocks(body.find(ODF_OF + 'text')))
    paragraphs, tables, order = {}, {}, []
    for kind, el in blocks:
        if kind == 'p':
            paragraphs[str(len(paragraphs) + 1)] = _odf_paragraph(el, styles)
            order.append(['p', len(paragraphs)])
        else:
            tables[str(len(tables) + 1)] = _odf_table(el, styles)
            order.append(['t', len(tables)])
    return {'paragraphs': paragraphs, 'tables': tables, 'body_order': order}


# ---------------------------------------------------------------- legacy XLS

def read_xls(path):
    import xlrd
    book = xlrd.open_workbook(path, formatting_info=False)
    out = {'sheet_names': list(book.sheet_names()), 'sheets': {}}
    for sh in book.sheets():
        cells = {}
        for r in range(sh.nrows):
            for c in range(sh.ncols):
                v = sh.cell_value(r, c)
                if v not in ('', None):
                    cells[f'{col_letters(c + 1)}{r + 1}'] = {'value': v, 'formula': None, 'text': str(v)}
        out['sheets'][sh.name] = {'cells': dict(sorted(cells.items(), key=_a1_key)), 'hidden_rows': [],
                                  'hidden_columns': [], 'autofilter': None, 'merged': [], 'charts': {},
                                  'pivot_tables': {}}
    return out


# ---------------------------------------------------------------- effective values of formulas

RECALC_TIMEOUT_S = 180


def _uncached_formula_cells(tree):
    return [(name, ref) for name, sh in tree['sheets'].items() for ref, node in sh['cells'].items()
            if node.get('formula') and node.get('value') is None]


@functools.lru_cache(maxsize=32)
def _recalculated_values(path, mtime_ns, size):
    """Values LibreOffice computes for every cell of a workbook: {(sheet, ref): value}.

    A generator writes formulas without cached results, so the stored value is empty. The effective value is
    the owning app's: LibreOffice recalculates on load and saves the results. Only the values are taken from
    its copy; formulas and formats are read from the file itself. The state file is never opened by LibreOffice.
    """
    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp, 'in.xlsx')
        shutil.copyfile(path, src)
        out = os.path.join(tmp, 'out')
        os.makedirs(out)
        subprocess.run(['soffice', '-env:UserInstallation=file://' + os.path.join(tmp, 'profile'), '--headless',
                        '--calc', '--convert-to', 'xlsx', '--outdir', out, src],
                       check=True, capture_output=True, timeout=RECALC_TIMEOUT_S)
        with zipfile.ZipFile(os.path.join(out, 'in.xlsx')) as z:
            calc = read_xlsx(z)
    return {(name, ref): node.get('value') for name, sh in calc['sheets'].items()
            for ref, node in sh['cells'].items()}


def _fill_recalculated(path, tree):
    """Fill the value of each formula cell that has no cached result from LibreOffice's recalculation.

    A failed recalculation raises: the file is then unreadable, and predicates on it are UNSUPPORTED,
    never compared with an empty value.
    """
    stat = os.stat(path)
    values = _recalculated_values(os.path.abspath(path), stat.st_mtime_ns, stat.st_size)
    for name, ref in _uncached_formula_cells(tree):
        tree['sheets'][name]['cells'][ref]['value'] = values.get((name, ref))


# ---------------------------------------------------------------- dispatch

def office_kind(path):
    """'docx' | 'xlsx' | 'pptx' | 'odt' | 'ods' | 'odp' | None for a zip container."""
    try:
        with zipfile.ZipFile(path) as z:
            names = set(z.namelist())
            if 'mimetype' in names:
                mime = z.read('mimetype').decode('ascii', 'replace').strip()
                for key, kind in (('text', 'odt'), ('spreadsheet', 'ods'), ('presentation', 'odp')):
                    if mime.endswith('.' + key) or ('opendocument.' + key) in mime:
                        return kind
                return None
            if 'word/document.xml' in names:
                return 'docx'
            if 'xl/workbook.xml' in names:
                return 'xlsx'
            if 'ppt/presentation.xml' in names:
                return 'pptx'
    except zipfile.BadZipFile:
        return None
    return None


def read_office(path, kind):
    if kind == 'xls':
        return {'format': 'xls', **read_xls(path)}
    with zipfile.ZipFile(path) as z:
        if kind == 'docx':
            return {'format': 'docx', **read_docx(z)}
        if kind == 'xlsx':
            tree = read_xlsx(z)
            if _uncached_formula_cells(tree):
                _fill_recalculated(path, tree)
            return {'format': 'xlsx', **tree}
        if kind == 'pptx':
            return {'format': 'pptx', **read_pptx(z)}
        mime = z.read('mimetype').decode('ascii', 'replace').strip()
        return {'format': kind, **read_odf(z, mime)}
