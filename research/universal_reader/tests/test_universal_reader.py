"""Tests for the universal state reader.

Run from the repository root:
  python -m unittest research.universal_reader.tests.test_universal_reader -v
Set UR_ENDSTATES to the materialized end-state directory to load every end state too (otherwise that test skips).
The snapshot test needs research/exp5-grounded/snapshots (made by fetch.py); it skips when that is missing.
"""
import glob
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, REPO)

from research.universal_reader import canon, diff, evaluate, readers_image, readers_config as cfg, readers_misc  # noqa: E402
from research.universal_reader import readers_office  # noqa: E402

SNAP = os.path.join(REPO, 'research', 'exp5-grounded', 'snapshots')
ENDSTATES = os.environ.get('UR_ENDSTATES', '')

# Unreadable files are allowed only for these recorded reasons. Anything else is a gap and fails the test.
ALLOWED_UNREADABLE = ('binary data', 'held-out family', 'parse error', 'special file', 'OLE2 container')


def _check_loads(root_dir, test):
    bad, count = [], 0
    for task in sorted(os.listdir(root_dir)):
        base = os.path.join(root_dir, task)
        if not os.path.isdir(base):
            continue
        tree = canon.dir_tree(base)  # any crash here is a failure of the reader
        for rel, node in tree.items():
            count += 1
            if node['kind'] not in ('dir', 'symlink', 'file', 'unreadable', 'derived_index'):
                bad.append((task, rel, 'unknown kind ' + str(node['kind'])))
            if node['kind'] == 'unreadable':
                reason = node.get('reason') or ''
                if not reason.startswith(ALLOWED_UNREADABLE):
                    bad.append((task, rel, reason))
    test.assertGreater(count, 0)
    test.assertEqual(bad, [], f'{len(bad)} unexpected unreadable files')
    return count


class SnapshotLoadTests(unittest.TestCase):
    def test_every_snapshot_file_loads(self):
        if not os.path.isdir(SNAP):
            self.skipTest('snapshots not fetched (research/exp5-grounded/fetch.py)')
        _check_loads(SNAP, self)

    def test_every_end_state_file_loads(self):
        if not ENDSTATES or not os.path.isdir(ENDSTATES):
            self.skipTest('set UR_ENDSTATES to the materialized end-state directory')
        for task in sorted(os.listdir(ENDSTATES)):
            for state in sorted(os.listdir(os.path.join(ENDSTATES, task))):
                base = os.path.join(ENDSTATES, task, state)
                for rel, node in canon.dir_tree(base).items():
                    if node['kind'] == 'unreadable':
                        reason = node.get('reason') or ''
                        self.assertTrue(reason.startswith(ALLOWED_UNREADABLE), f'{task}/{state}/{rel}: {reason}')


class EffectiveValueTests(unittest.TestCase):
    def test_vscode_workspace_overrides_user(self):
        self.assertEqual(cfg.vscode_effective('editor.tabSize', {'editor.tabSize': 4}, {'editor.tabSize': 2}),
                         (2, 'workspace'))

    def test_vscode_unset_key_is_unknown_not_a_default(self):
        self.assertEqual(cfg.vscode_effective('editor.tabSize', {}, {}),
                         (cfg.UNKNOWN_DEFAULT, 'unknown'))

    def test_vscode_builtin_default_used_only_when_supplied(self):
        self.assertEqual(cfg.vscode_effective('k', {}, {}, builtin_defaults={'k': 4}), (4, 'builtin'))

    def test_jsonc_comments_and_trailing_commas_are_removed(self):
        text = '{ // comment\n "a": 1, /* block */ "b": [1, 2,], }'
        self.assertEqual(cfg.read_json(text.encode()), {'a': 1, 'b': [1, 2]})

    def test_jsonc_does_not_touch_string_contents(self):
        text = '{ "msg": "keep, } and , ] inside", "x": 1, }'
        self.assertEqual(cfg.read_json(text.encode()), {'msg': 'keep, } and , ] inside', 'x': 1})

    def test_prefs_unset_key_is_unknown_and_set_key_is_its_value(self):
        tree = cfg.read_prefs_js('user_pref("mail.identity.id1.auto_quote", false);\n')
        self.assertEqual(cfg.prefs_effective(tree, 'mail.identity.id1.auto_quote'), (False, 'user'))
        self.assertEqual(cfg.prefs_effective(tree, 'mail.identity.id2.auto_quote'),
                         (cfg.UNKNOWN_DEFAULT, 'unknown'))

    def test_gsettings_schema_default_is_not_evidence_of_the_effective_value(self):
        spec = {'must': ["gnome.gsettings('org.gnome.desktop.interface','color-scheme') == 'default'"]}
        empty = canon.dir_tree(tempfile.mkdtemp())
        res = evaluate.run_spec(spec, empty, empty, '/nonexistent', '/nonexistent')
        self.assertEqual(res['predicates'][0]['status'], 'UNSUPPORTED')
        self.assertNotEqual(res['decision'], 'ACCEPT')

    def test_vscode_unset_setting_never_passes(self):
        root = tempfile.mkdtemp()
        try:
            user = '/home/user/.config/Code/User/settings.json'
            tree = {'home/user/.config/Code/User/settings.json': {
                'kind': 'file', 'mode': '0o644', 'sha256': 'x', 'format': 'json',
                'content': {'value': {'editor.tabSize': 4}}}}
            spec = {'must': [f"vscode.user_settings('{user}').get('debug.focusEditorOnBreak') == false"]}
            res = evaluate.run_spec(spec, tree, tree, root, root)
            self.assertEqual(res['predicates'][0]['status'], 'UNSUPPORTED')
            self.assertEqual(res['decision'], 'UNDECIDED')
        finally:
            shutil.rmtree(root, ignore_errors=True)


class HeldOutFamilyTests(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        cfg_dir = os.path.join(self.root, 'home', 'user', '.config', 'vlc')
        os.makedirs(cfg_dir)
        with open(os.path.join(cfg_dir, 'vlcrc'), 'wb') as fh:
            fh.write(b'global-key-play-pause=Unset\n')

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def test_vlc_config_is_unreadable_with_reason(self):
        tree = canon.dir_tree(self.root)
        node = tree['home/user/.config/vlc/vlcrc']
        self.assertEqual(node['kind'], 'unreadable')
        self.assertIn('held-out family vlc', node['reason'])

    def test_vlc_unchanged_bytes_are_unverified_not_unchanged(self):
        before = canon.dir_tree(self.root)
        after = canon.dir_tree(self.root)
        d = diff.diff_states(before, after, roots=(self.root, self.root))
        verdict, violations, unverified = diff.verdict(d, allowed=[])
        self.assertEqual(verdict, 'UNVERIFIED')
        self.assertTrue(any('vlc' in u['path'] for u in unverified))

    def test_vlc_predicate_is_undecided(self):
        tree = canon.dir_tree(self.root)
        spec = {'must': ["vlc.config('/home/user/.config/vlc/vlcrc')['global-key-play-pause'] == 'Unset'"]}
        res = evaluate.run_spec(spec, tree, tree, self.root, self.root)
        self.assertEqual(res['predicates'][0]['status'], 'UNSUPPORTED')
        self.assertEqual(res['decision'], 'UNDECIDED')


class LiveStateTests(unittest.TestCase):
    def test_live_state_predicates_are_unsupported_not_executor_errors(self):
        empty = {}
        spec = {'must': ["count(thunderbird.compose_windows) >= 1",
                         "any(w.subject == 'x' for w in thunderbird.compose_windows)"]}
        res = evaluate.run_spec(spec, empty, empty, '/nonexistent', '/nonexistent')
        self.assertEqual([p['status'] for p in res['predicates']], ['UNSUPPORTED', 'UNSUPPORTED'])
        self.assertEqual(res['decision'], 'UNDECIDED')


class VerdictTests(unittest.TestCase):
    def _text_node(self, line):
        return {'kind': 'file', 'mode': '0o644', 'sha256': line, 'format': 'text',
                'content': {'encoding': 'utf-8', 'final_newline': True, 'lines': {'1': line}}}

    def test_pass_when_the_only_change_is_allowed(self):
        before = {'a.txt': self._text_node('x'), 'b.txt': self._text_node('y')}
        after = {'a.txt': self._text_node('z'), 'b.txt': self._text_node('y')}
        d = diff.diff_states(before, after)
        verdict, violations, _ = diff.verdict(d, allowed=[diff.prefix('a.txt')])
        self.assertEqual((verdict, violations), ('PASS', []))

    def test_fail_on_a_change_outside_scope(self):
        before = {'a.txt': self._text_node('x'), 'b.txt': self._text_node('y')}
        after = {'a.txt': self._text_node('x'), 'b.txt': self._text_node('q')}
        d = diff.diff_states(before, after)
        verdict, violations, _ = diff.verdict(d, allowed=[diff.prefix('a.txt')])
        self.assertEqual(verdict, 'FAIL')
        self.assertTrue(violations)

    def test_noise_subtraction_removes_only_matching_after_values(self):
        d = diff.Diff()
        d.changes = [diff.Change(('x', 'content', 'k'), 'changed', 1, 2), diff.Change(('y',), 'changed', 1, 3)]
        noise = diff.Diff()
        noise.changes = [diff.Change(('x', 'content', 'k'), 'changed', 1, 2),
                         diff.Change(('y',), 'changed', 1, 9)]  # same path, different after: must be kept
        kept, spurious = diff.subtract_noise(d, noise)
        self.assertEqual([c.path for c in spurious], [('x', 'content', 'k')])
        self.assertEqual([c.path for c in kept.changes], [('y',)])


class FormatRepairTests(unittest.TestCase):
    def test_mbox_folded_from_header_keeps_subject(self):
        raw = (b'From MAILER-DAEMON Sat Jan  1 00:00:00 2024\n'
               b'X-Mozilla-Status: 0000\n'
               b'From: X (formerly Twitter)\n'
               b'<invoice@example.com>\n'
               b'Subject: Your receipt\n'
               b'To: a@example.com\n\n'
               b'Body text\n\n')
        d = tempfile.mkdtemp()
        try:
            path = os.path.join(d, 'Bills')
            with open(path, 'wb') as fh:
                fh.write(raw)
            msg = readers_misc.read_mbox(path)['messages']['1']
            self.assertEqual(msg['subject'], 'Your receipt')
            self.assertEqual(msg['from'], 'X (formerly Twitter) <invoice@example.com>')
            self.assertEqual(msg['header_lines_joined'], 1)
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_docx_page_break_adds_no_paragraph_text(self):
        try:
            from docx import Document
            from docx.enum.text import WD_BREAK
        except ImportError:
            self.skipTest('python-docx not installed')
        d = tempfile.mkdtemp()
        try:
            path = os.path.join(d, 'x.docx')
            doc = Document()
            doc.add_paragraph('First page')
            p = doc.add_paragraph('Tail')
            p.runs[0].add_break(WD_BREAK.PAGE)
            doc.add_paragraph('Second page')
            doc.save(path)
            content = readers_office.read_office(path, 'docx')
            got = [p['text'] for _, p in sorted(content['paragraphs'].items(), key=lambda kv: int(kv[0]))]
            want = [p.text for p in Document(path).paragraphs]
            self.assertEqual(got, want)
        finally:
            shutil.rmtree(d, ignore_errors=True)


class FormattingTests(unittest.TestCase):
    """Formatting is part of the canonical tree: the same keys for every office format (readers_office.FORMAT_KEYS)."""

    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.mkdtemp()

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.dir, ignore_errors=True)

    def _path(self, name):
        return os.path.join(self.dir, name)

    def test_xlsx_cell_formatting_and_no_raw_style_index(self):
        try:
            import openpyxl
            from openpyxl.styles import Alignment, Font, PatternFill
        except ImportError:
            self.skipTest('openpyxl not installed')
        wb = openpyxl.Workbook()
        ws = wb.active
        ws['A1'] = 'Total'
        ws['A1'].font = Font(bold=True, italic=True, underline='single', size=14, name='Arial', color='FF0000')
        ws['A1'].fill = PatternFill('solid', fgColor='FFFF00')
        ws['A1'].alignment = Alignment(horizontal='center')
        ws['A2'] = 0.25
        ws['A2'].number_format = '0.00%'
        ws['A3'] = 'link'
        ws['A3'].hyperlink = 'https://example.com/report'
        ws['B5'].fill = PatternFill('solid', fgColor='00FF00')  # styled and empty: kept, it is visible
        ws['C5'] = None
        ws['D9'] = 'plain'
        path = self._path('fmt.xlsx')
        wb.save(path)
        cells = readers_office.read_office(path, 'xlsx')['sheets']['Sheet']['cells']
        a1 = cells['A1']
        self.assertTrue(a1['bold'] and a1['italic'])
        self.assertEqual((a1['underline'], a1['size'], a1['font'], a1['color']), ('single', 14.0, 'Arial', 'FF0000'))
        self.assertEqual((a1['background_color'], a1['alignment']), ('FFFF00', 'center'))
        self.assertEqual(cells['A2']['number_format'], '0.00%')
        self.assertEqual(cells['A3']['hyperlink'], 'https://example.com/report')
        self.assertEqual(cells['B5']['background_color'], '00FF00')
        self.assertIsNone(cells['B5']['value'])
        self.assertNotIn('C5', cells)            # empty and unstyled: not recorded
        self.assertEqual(cells['D9']['number_format'], 'General')
        self.assertNotIn('style', a1)            # the raw xf index is not a property of the cell

    def test_xlsx_escaped_space_in_number_format_is_a_plain_space(self):
        try:
            import openpyxl
        except ImportError:
            self.skipTest('openpyxl not installed')
        wb = openpyxl.Workbook()
        ws = wb.active
        ws['A1'] = 1
        ws['A1'].number_format = 'm/d/yy\\ hh:mm'
        path = self._path('nf.xlsx')
        wb.save(path)
        cells = readers_office.read_office(path, 'xlsx')['sheets']['Sheet']['cells']
        self.assertEqual(cells['A1']['number_format'], 'm/d/yy hh:mm')

    def test_theme_colour_resolves_through_the_theme_and_tint(self):
        theme = ['FFFFFF', '000000', 'EEECE1', '1F497D', '4F81BD']
        el = readers_office.etree.fromstring(
            '<color xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" theme="1"/>')
        self.assertEqual(readers_office._xlsx_color(el, theme), '000000')
        el = readers_office.etree.fromstring(
            '<color xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" theme="0" tint="-0.5"/>')
        self.assertEqual(readers_office._xlsx_color(el, theme), '808080')
        self.assertEqual(readers_office._tint('000000', 0.5), '808080')

    def test_docx_run_paragraph_table_and_hyperlink_formatting(self):
        try:
            from docx import Document
            from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_COLOR_INDEX
            from docx.oxml import OxmlElement
            from docx.oxml.ns import qn
            from docx.opc.constants import RELATIONSHIP_TYPE as RT
        except ImportError:
            self.skipTest('python-docx not installed')
        doc = Document()
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run('Bold')
        r.bold = True
        r2 = p.add_run(' under')
        r2.underline = True
        r2.font.highlight_color = WD_COLOR_INDEX.YELLOW
        rid = doc.part.relate_to('https://example.com/doc', RT.HYPERLINK, is_external=True)
        link = OxmlElement('w:hyperlink')
        link.set(qn('r:id'), rid)
        lr = OxmlElement('w:r')
        t = OxmlElement('w:t')
        t.text = 'linked'
        lr.append(t)
        link.append(lr)
        p._p.append(link)
        table = doc.add_table(rows=1, cols=1)
        shd = OxmlElement('w:shd')
        shd.set(qn('w:val'), 'clear')
        shd.set(qn('w:fill'), '00ff00')
        table.cell(0, 0)._tc.get_or_add_tcPr().append(shd)
        path = self._path('fmt.docx')
        doc.save(path)
        content = readers_office.read_office(path, 'docx')
        para = content['paragraphs']['1']
        self.assertEqual(para['alignment'], 'center')
        runs = [para['runs'][k] for k in sorted(para['runs'], key=int)]
        self.assertTrue(runs[0]['bold'])
        self.assertEqual(runs[1]['underline'], 'single')
        self.assertEqual(runs[1]['highlight'], 'FFFF00')
        self.assertEqual(runs[2]['hyperlink'], 'https://example.com/doc')
        self.assertEqual(content['tables']['1']['rows']['1']['cells']['1']['background_color'], '00FF00')
        self.assertEqual(runs[0]['strike'], 'none')

    def test_pptx_run_paragraph_shape_and_hyperlink_formatting(self):
        try:
            from pptx import Presentation
            from pptx.dml.color import RGBColor
            from pptx.enum.text import PP_ALIGN
            from pptx.util import Pt
        except ImportError:
            self.skipTest('python-pptx not installed')
        prs = Presentation()
        slide = prs.slides.add_slide(prs.slide_layouts[5])
        box = slide.shapes.add_textbox(0, 0, prs.slide_width, prs.slide_height)
        box.fill.solid()
        box.fill.fore_color.rgb = RGBColor(0x2A, 0x1A, 0x00)
        para = box.text_frame.paragraphs[0]
        para.alignment = PP_ALIGN.RIGHT
        run = para.add_run()
        run.text = 'Hello'
        run.font.bold = True
        run.font.size = Pt(20)
        run.font.color.rgb = RGBColor(0xFF, 0xFF, 0x00)
        run.hyperlink.address = 'https://example.com/slide'
        path = self._path('fmt.pptx')
        prs.save(path)
        content = readers_office.read_office(path, 'pptx')
        shape = [s for s in content['slides']['1']['shapes'].values() if s.get('background_color')][0]
        self.assertEqual(shape['background_color'], '2A1A00')
        p1 = shape['paragraphs']['1']
        self.assertEqual(p1['alignment'], 'right')
        r1 = p1['runs']['1']
        self.assertTrue(r1['bold'])
        self.assertEqual((r1['size'], r1['color'], r1['hyperlink']),
                         (20.0, 'FFFF00', 'https://example.com/slide'))

    def test_ods_formatting_matches_the_xlsx_it_was_converted_from(self):
        """LibreOffice converts the workbook; the same cells must read the same formatting in both files."""
        try:
            import openpyxl
            from openpyxl.styles import Alignment, Font, PatternFill
        except ImportError:
            self.skipTest('openpyxl not installed')
        soffice = shutil.which('soffice')
        if soffice is None:
            self.skipTest('LibreOffice (soffice) not installed')
        import datetime
        wb = openpyxl.Workbook()
        ws = wb.active
        ws['A1'] = 'Header'
        ws['A1'].font = Font(bold=True, name='Arial', size=12)
        ws['A1'].fill = PatternFill('solid', fgColor='FFFF00')
        ws['A2'] = 0.5
        ws['A2'].number_format = '0.00%'
        ws['A3'] = datetime.datetime(2015, 2, 19, 22, 13)
        ws['A3'].number_format = 'm/d/yy hh:mm'
        ws['A4'] = 'right'
        ws['A4'].alignment = Alignment(horizontal='right')
        ws['A5'] = 'site'
        ws['A5'].hyperlink = 'https://example.com/ods'
        src = self._path('ods_src.xlsx')
        wb.save(src)
        outdir = os.path.join(self.dir, 'ods_out')
        os.makedirs(outdir)
        profile = 'file://' + os.path.join(self.dir, 'lo_profile')
        subprocess.run([soffice, f'-env:UserInstallation={profile}', '--headless', '--convert-to', 'ods',
                        '--outdir', outdir, src], check=True, capture_output=True, timeout=240)
        ods = os.path.join(outdir, 'ods_src.ods')
        xs = readers_office.read_office(src, 'xlsx')['sheets']['Sheet']['cells']
        os_ = readers_office.read_office(ods, 'ods')['sheets']['Sheet']['cells']
        for ref in ('A1', 'A2', 'A3', 'A4', 'A5'):
            for key in ('bold', 'background_color', 'alignment', 'hyperlink', 'number_format', 'font', 'size'):
                self.assertEqual(os_[ref].get(key), xs[ref].get(key), f'{ref} {key}')
        # ODS stores a date as ISO text with second precision, so the serial agrees to about 1e-9 days.
        self.assertAlmostEqual(os_['A3']['value'], xs['A3']['value'], places=8)

    def test_formatting_predicates_evaluate_through_the_views(self):
        try:
            import openpyxl
            from openpyxl.styles import Alignment, Font, PatternFill
            from pptx import Presentation
            from pptx.enum.text import PP_ALIGN
        except ImportError:
            self.skipTest('openpyxl or python-pptx not installed')
        state = os.path.join(self.dir, 'state')
        home = os.path.join(state, 'home', 'user')
        os.makedirs(home)
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = 'Sheet'
        ws['A1'] = 'Total'
        ws['A1'].font = Font(bold=True)
        ws['A1'].fill = PatternFill('solid', fgColor='FFFF00')
        ws['A1'].alignment = Alignment(horizontal='center')
        ws['A2'] = 0.25
        ws['A2'].number_format = '0.00%'
        ws['A3'] = 'site'
        ws['A3'].hyperlink = 'https://example.com/report'
        wb.save(os.path.join(home, 'Book.xlsx'))
        prs = Presentation()
        slide = prs.slides.add_slide(prs.slide_layouts[5])
        box = slide.shapes.add_textbox(0, 0, prs.slide_width, prs.slide_height)
        box.name = 'Callout'
        box.text_frame.paragraphs[0].alignment = PP_ALIGN.RIGHT
        box.text_frame.paragraphs[0].add_run().text = 'Note'
        prs.save(os.path.join(home, 'Deck.pptx'))
        tree = canon.dir_tree(state)
        cases = [
            ("libreoffice.calc.file('/home/user/Book.xlsx').sheet('Sheet').cell('A1').bold == true", 'PASS'),
            ("libreoffice.calc.file('/home/user/Book.xlsx').sheet('Sheet').cell('A1').italic == false", 'PASS'),
            ("libreoffice.calc.file('/home/user/Book.xlsx').sheet('Sheet').cell('A1').fill == 'FFFF00'", 'PASS'),
            ("libreoffice.calc.file('/home/user/Book.xlsx').sheet('Sheet').cell('A1').alignment == 'center'", 'PASS'),
            ("libreoffice.calc.file('/home/user/Book.xlsx').sheet('Sheet').cell('A2').number_format == '0.00%'", 'PASS'),
            ("libreoffice.calc.file('/home/user/Book.xlsx').sheet('Sheet').cell('A3').hyperlink == "
             "'https://example.com/report'", 'PASS'),
            ("libreoffice.calc.file('/home/user/Book.xlsx').sheet('Sheet').cell('A1').italic == true", 'FAIL'),
            ("libreoffice.impress.file('/home/user/Deck.pptx').slide(1).shape('Callout').paragraph(1).alignment"
             " == 'right'", 'PASS'),
        ]
        for pred, want in cases:
            res = evaluate.run_spec({'must': [pred]}, tree, tree, state, state)
            self.assertEqual(res['predicates'][0]['status'], want, pred)

    def test_formatting_keys_are_the_same_names_across_formats(self):
        """Every reader writes only canonical keys (no format-specific names such as font_color)."""
        for key in ('font_color', 'para_bg', 'style'):
            self.assertNotIn(key, readers_office.FORMAT_KEYS)
        self.assertIn('background_color', readers_office.FORMAT_KEYS)
        self.assertIn('number_format', readers_office.FORMAT_KEYS)


XCF_SNAP = os.path.join(SNAP, 'e2dd0213-26db-4349-abe5-d5667bfd725c', 'home', 'user', 'Desktop', 'orange_background.xcf')


class SharedFormulaTests(unittest.TestCase):
    """A shared-formula child stores no text. It reads the group master's formula, moved to the child's cell."""

    def test_child_formula_is_the_master_formula_moved_to_the_child(self):
        try:
            import openpyxl
            from lxml import etree
        except ImportError:
            self.skipTest('openpyxl not installed')
        d = tempfile.mkdtemp()
        try:
            plain = os.path.join(d, 'plain.xlsx')
            wb = openpyxl.Workbook()
            ws = wb.active
            for i in (1, 2, 3):
                ws['A%d' % i] = i
            ws['B1'], ws['B2'], ws['B3'] = '=A1*10', '=A2*10', '=A3*10'
            wb.save(plain)
            with zipfile.ZipFile(plain) as zin:
                parts = {name: zin.read(name) for name in zin.namelist()}
            root = etree.fromstring(parts['xl/worksheets/sheet1.xml'])
            for c in root.iter(readers_office.S + 'c'):
                f = c.find(readers_office.S + 'f')
                if f is None:
                    continue
                if c.get('r') == 'B1':
                    f.set('t', 'shared'), f.set('ref', 'B1:B3'), f.set('si', '0')
                elif c.get('r') in ('B2', 'B3'):
                    f.text = None
                    f.set('t', 'shared'), f.set('si', '0')
            parts['xl/worksheets/sheet1.xml'] = etree.tostring(root)
            shared = os.path.join(d, 'shared.xlsx')
            with zipfile.ZipFile(shared, 'w') as zout:
                for name, data in parts.items():
                    zout.writestr(name, data)
            cells = readers_office.read_office(shared, 'xlsx')['sheets']['Sheet']['cells']
            self.assertEqual([cells[r]['formula'] for r in ('B1', 'B2', 'B3')], ['=A1*10', '=A2*10', '=A3*10'])
            self.assertNotIn('shared_formula', cells['B2'])
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_every_formula_cell_of_a_real_shared_formula_workbook_matches_openpyxl(self):
        path = os.path.join(SNAP, '51719eea-10bc-4246-a428-ac7c433dd4b3', 'home', 'user', 'BoomerangSales.xlsx')
        if not os.path.exists(path):
            self.skipTest('snapshot not fetched')
        try:
            import openpyxl
        except ImportError:
            self.skipTest('openpyxl not installed')
        read = readers_office.read_office(path, 'xlsx')['sheets']
        checked = 0
        for ws in openpyxl.load_workbook(path).worksheets:
            for row in ws.iter_rows():
                for c in row:
                    if isinstance(c.value, str) and c.value.startswith('='):
                        checked += 1
                        self.assertEqual(read[ws.title]['cells'][c.coordinate]['formula'], c.value, c.coordinate)
        self.assertGreater(checked, 0)


class RecalculatedValueTests(unittest.TestCase):
    """A formula cell with no cached result takes the value LibreOffice computes: the owning app's value."""

    def _soffice(self):
        try:
            import openpyxl  # noqa: F401
        except ImportError:
            self.skipTest('openpyxl not installed')
        if shutil.which('soffice') is None:
            self.skipTest('LibreOffice not installed')

    def test_formula_without_cached_value_takes_the_libreoffice_result(self):
        self._soffice()
        import openpyxl
        d = tempfile.mkdtemp()
        try:
            path = os.path.join(d, 'calc.xlsx')
            wb = openpyxl.Workbook()
            ws = wb.active
            ws['A1'], ws['A2'] = 4, 2.5
            ws['B1'] = '=A1*A2'
            ws['B2'] = '=IF(A1>3,"big","small")'
            wb.save(path)
            cells = readers_office.read_office(path, 'xlsx')['sheets']['Sheet']['cells']
            self.assertEqual((cells['B1']['formula'], cells['B1']['value']), ('=A1*A2', 10))
            self.assertEqual(cells['B2']['value'], 'big')
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_end_state_formulas_match_a_computation_from_the_stored_inputs(self):
        self._soffice()
        if not ENDSTATES:
            self.skipTest('UR_ENDSTATES not set')
        try:
            import openpyxl
        except ImportError:
            self.skipTest('openpyxl not installed')
        paths = sorted(glob.glob(os.path.join(ENDSTATES, '51719eea-10bc-4246-a428-ac7c433dd4b3', '*',
                                              'home', 'user', 'BoomerangSales.xlsx')))
        checked = 0
        for path in paths:
            wb = openpyxl.load_workbook(path)  # formulas as text; the inputs are stored values
            s1, rp = wb['Sheet1'], wb['Retail Price']
            if not str(s1['G2'].value).startswith('=VLOOKUP'):
                continue
            table = {rp.cell(r, 1).value: rp.cell(r, 2).value for r in range(2, 24)}
            cells = readers_office.read_office(path, 'xlsx')['sheets']['Sheet1']['cells']
            for row in range(2, 37):
                # G = VLOOKUP(C,'Retail Price'!A2:B23,2,0)*E*(1-F); D = IF(E<10,"Retail","Wholesale")
                expected_g = table[s1.cell(row, 3).value] * s1.cell(row, 5).value * (1 - s1.cell(row, 6).value)
                self.assertAlmostEqual(cells['G%d' % row]['value'], expected_g, places=6)
                expected_d = 'Retail' if s1.cell(row, 5).value < 10 else 'Wholesale'
                self.assertEqual(cells['D%d' % row]['value'], expected_d)
                checked += 1
        if not checked:
            self.skipTest('no end state with the VLOOKUP formulas is materialized')


class XcfTests(unittest.TestCase):
    """XCF v011 has 64-bit pointers and a precision field in the header. Layer metadata must come out right.
    Pixels are not read until the tile decoder is validated, so pixel predicates must be UNSUPPORTED."""

    def setUp(self):
        if not os.path.isfile(XCF_SNAP):
            self.skipTest('snapshots not fetched (research/exp5-grounded/fetch.py)')

    def test_v011_layer_names_sizes_and_offsets(self):
        st = os.stat(XCF_SNAP)
        node = readers_image.read_xcf(XCF_SNAP, (st.st_mtime_ns, st.st_size))
        self.assertEqual((node['width'], node['height']), (2192, 1118))
        layers = {v['name']: v for v in node['layers'].values()}
        self.assertEqual(set(layers), {'Thanks World', 'orange_background.png'})
        self.assertEqual((layers['Thanks World']['width'], layers['Thanks World']['height']), (422, 77))
        self.assertEqual((layers['orange_background.png']['width'], layers['orange_background.png']['height']),
                         (2192, 1118))

    def test_pixel_predicates_are_undecided_not_compared(self):
        root = os.path.join(SNAP, 'e2dd0213-26db-4349-abe5-d5667bfd725c')
        tree = canon.dir_tree(root)
        path = '/home/user/Desktop/orange_background.xcf'
        spec = {'must': [
            f"gimp.document('{path}').layer('Thanks World').size == [422, 77]",
            f"gimp.document('{path}').layer('Thanks World').pixels == before(gimp.document('{path}').layer('Thanks World').pixels)",
        ]}
        res = evaluate.run_spec(spec, tree, tree, root, root)
        self.assertEqual(res['predicates'][0]['status'], 'PASS')
        self.assertEqual(res['predicates'][1]['status'], 'UNSUPPORTED')
        self.assertEqual(res['decision'], 'UNDECIDED')

    def test_missing_baseline_file_is_undecided_not_a_fail(self):
        """The start state has no filter file (the task creates it). Its rules cannot be compared, so the
        predicate is undecided. A file missing from the end state is still a FAIL."""
        path = '/home/user/.thunderbird/p.default/ImapMail/imap.example/msgFilterRules.dat'
        node = {'kind': 'file', 'mode': '0o644', 'sha256': 'x', 'format': 'msg_filter_rules',
                'content': {'rules': {'0': {'name': 'r', 'enabled': True}}}}
        spec = {'must': [f"thunderbird.filters('{path}').rules == before(thunderbird.filters('{path}').rules)"]}
        end = {path.lstrip('/'): node}
        res = evaluate.run_spec(spec, end, {}, '/nonexistent', '/nonexistent')
        self.assertEqual(res['predicates'][0]['status'], 'UNSUPPORTED', res['predicates'][0]['reason'])
        self.assertEqual(res['decision'], 'UNDECIDED')
        res = evaluate.run_spec(spec, {}, end, '/nonexistent', '/nonexistent')
        self.assertEqual(res['predicates'][0]['status'], 'FAIL')


class GimpTextLayerTests(unittest.TestCase):
    """A text layer's text is the (text "...") field of its parasite, not the whole settings block."""

    def test_text_field_is_decoded_and_the_settings_are_dropped(self):
        blob = b'(text "Thanks World")\n(font "Sans-serif")\n(font-size 62)\n(hinting yes)\n\x00\x00'
        self.assertEqual(readers_image._gimp_text_string(blob), 'Thanks World')

    def test_scheme_escapes_inside_the_text_are_decoded(self):
        blob = b'(text "say \\"hi\\"\\nline two")\n(font "x")'
        self.assertEqual(readers_image._gimp_text_string(blob), 'say "hi"\nline two')

    def test_no_text_field_gives_none(self):
        self.assertIsNone(readers_image._gimp_text_string(b'(font "Sans-serif")\n(font-size 12)'))

    def test_snapshot_text_layer_reads_its_text(self):
        matches = glob.glob(os.path.join(SNAP, '*', 'home', 'user', 'Desktop', 'orange_background.xcf'))
        if not matches:
            self.skipTest('snapshot not fetched')
        layers = readers_image.read_xcf(matches[0], None)['layers']
        self.assertIn('Thanks World', [layer['text'] for layer in layers.values()])


if __name__ == '__main__':
    unittest.main()
