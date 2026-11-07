# Exp 5 reader names to canonical tree paths

This maps each reader name in the Exp 5 must-predicates to the place it reads in the canonical tree (`canon.dir_tree`).
The predicate grammar and the decision rule come unchanged from `research/exp6-executed/specexec.py` (read-only import).
Only the readers differ: `evaluate.py` binds each name to a view over the tree. A name with no view, a value the state
does not hold on disk, or an unreadable file gives UNSUPPORTED, which makes the spec UNDECIDED. It never passes.

Notation: `content` is the parsed node of a readable file (`canon.load_file`). `before(x)` evaluates `x` on the
snapshot tree, as in specexec.

## Office documents (LibreOffice roots)

| Exp 5 name | Tree path | Notes |
|---|---|---|
| `libreoffice.calc.file(p)` | `p` node, format `xlsx`/`xls`/`ods`, `content.sheets[name]` | Sheet names from `content.sheet_names` |
| `.sheet(n).cell(ref).value / .formula / .text` | `sheets[n].cells[ref]` | Cell refs are A1 style |
| `.sheet(n).range(ref).values / .formulas / .coords / .nonempty_cells` | `sheets[n].cells` over the box | One row or column flattens to a list, as in specexec |
| `.charts`, `chart.type / .title / .series[i].values` | `sheets[*].charts` | `series` is zero-based (`ZeroList`), as in specexec. `values` flattens row-major |
| `.pivot_tables` | `sheets[n].pivot_tables` | |
| `.cell(ref).bold / .italic / .underline / .strike / .font / .size / .color` | `sheets[n].cells[ref]` | Formatting keys, see "Formatting" below. An unstyled or missing cell has the defaults |
| `.cell(ref).background_color` (also `.fill`) | same | Cell fill (solid pattern colour in xlsx, cell background in ODS) |
| `.cell(ref).number_format / .alignment / .hyperlink` | same | Format code; left, center, right or justify; link target |
| `.range(ref).bold` (any formatting key) | same | The same grid shape as `.values`, one formatting value per cell |
| `range(ref)` (bare) | the last sheet selected in the same spec | Shared across predicates of one spec, as in specexec |
| `libreoffice.writer.file(p)` | `p` node, format `docx`/`odt` | |
| `.paragraphs[i] / .paragraph(i)` | `paragraphs[i]` (text, style, alignment, background_color, runs) | Page and column breaks add no text; line breaks do (python-docx rule) |
| `.tables[i] / .table(i).rows / .cells` | `tables[i]` | `.cells[*].background_color` (also `.fill`) |
| `.body_order` | `body_order` | Paragraphs and tables in document order |
| `.text_runs / .text_run_containing(s)` | paragraph `runs` | Run formatting keys below. `r.highlight` is the highlight or character background |
| `.rendered_pages` | LibreOffice PDF render of the file (`readers_misc.render_pages`) | Renders through the owning app. Page text from pypdf |
| `libreoffice.impress.file(p)` | `p` node, format `pptx`/`odp` | |
| `.slides[i] / .slide(i)` | `slides[i]` | `shape_order` gives shape order |
| `.shapes / .shape(name)` | slide `shapes` (kind, text, position, paragraphs, background_color) | `.background_color` (also `.fill`) is the pptx solid shape fill. Shape fill in odp is not read yet |
| `.shape(name).paragraph(i).alignment / .runs` | `paragraphs[i]` | Alignment is left, center, right or justify |
| `.shape(name).text_runs[*].color / .strike / .bold / .size / .font / .hyperlink` | paragraph runs | Run keys, see "Formatting" |
| `.transition.type` | slide `transition` | |
| `.slide_count` | number of slides | |
| `libreoffice.config` | no reader | Live application configuration is not in the tree |

## Files, directories and the OS

| Exp 5 name | Tree path | Notes |
|---|---|---|
| `os.file(p)`, `filesystem.file(p)`, `fs.file(p)` | node at `p` | `.sha256`, `.size`, `.mode`, `.exists`, `.text` (text files only) |
| `os.tree(p)` / `filesystem.tree(p)` / `fs.tree(p)` | all entries under `p` | `.paths`, `.regular_files`, `.content` (a map path to sha256) |
| `filesystem.dir(p)` | any entry under `p` | `.exists` |
| `os.user`, `os.service`, `os.processes`, `filesystem.find` | no reader | Live OS state |
| `basename`, `uri_to_path`, `urldecode` | builtins | Added here; plain string functions |

## Images, GIMP and video

| Exp 5 name | Tree path | Notes |
|---|---|---|
| `image.file(p)` / `image(p)` | raster or XCF node at `p` | `.format`, `.width`, `.height`, `.sha256` (of decoded pixels) |
| `gimp.live_document(p)` / `gimp.document(p)` | the **saved** file at `p` (XCF or raster) | Proxy: the live document is not visible. Results are counted as proxy evidence |
| `.size`, `.base_type`, `.colormap` | XCF/raster node | `colormap` is UNSUPPORTED on a non-indexed image |
| `.layer(name)`, `.layers.names`, `.layer(n).offsets / .size / .text / .pixels` | XCF `layers` | `.text` is the `(text "...")` field of the `gimp-text-layer` parasite (not its font or colour settings). `.pixels` is UNSUPPORTED until the tile decoder is validated against GIMP output (`TILE_DECODE_VALIDATED`) |
| `.composite.pixels` | composited XCF (normal blend over white) | |
| `gimp.ui`, `gimp.preferences` | no reader | Live GIMP state |
| `video.file(p).stream(1).frame_at(t)` | no reader | Only container metadata (ffprobe) is read; no frames |

## Config, JSON and mail

| Exp 5 name | Tree path | Notes |
|---|---|---|
| `json.file(p)` | JSON or JSONC node, `content.value` | JSONC: comments and trailing commas removed, string contents untouched |
| `vscode.user_settings(p).get(key)` | `content.value` at `p` | Effective value: workspace over user over built-in. No value anywhere gives UNKNOWN (UNSUPPORTED) |
| `vscode.user_keybindings(p)` | keybindings list | |
| `vscode.keybindings.resolve`, `vscode.extensions`, `vscode.windows` | no reader | The built-in keymap and live windows are not on disk |
| `thunderbird.profile(dir).prefs[key]` | `<dir>/prefs.js` (`user_prefs`) | Unset key gives UNKNOWN_DEFAULT (defaults are in omni.ja, not read). It is never a match |
| `thunderbird.profile(dir).prefs.matching(glob)` | same | |
| `thunderbird.filters(p).rules` | `msgFilterRules.dat` | `enabled`, `type`, `condition`, `actions` |
| `thunderbird.folder(uri).messages` | `<profile>/Mail/<folder>` (mbox) | Flags from `X-Mozilla-Status`. Header fields are unfolded; a folded `From` line is repaired (see `header_lines_joined`) |
| `thunderbird.compose_windows`, `.ui`, `.all_messages`, `.sent_messages_since`, `.folders` | no reader | Live application state |
| `imap.server(...)`, `outlook.*`, `googledrive.*`, `chrome.*`, `probe.*`, `run.*`, `terminal.*`, `desktop.*`, `display.*`, `session.*`, `snap.*`, `apt.*`, `flatpak.*`, `xdg_mime.*`, `git.*`, `forum.*` | no reader | Live or remote state. Structurally out of reach of a file tree |
| `gnome.gsettings(schema, key)`, `gsettings(...)` | UNKNOWN | The dconf database is binary and not read. The schema default is not evidence of the effective value |
| `python_ast` | Python files parsed by `ast` (`content.ast`) | No predicate in the Exp 5 set uses it yet |

## Held-out family

| Exp 5 name | Tree path | Notes |
|---|---|---|
| `vlc.config(p)`, `vlc.qt_settings(p)`, `vlc.probe_restart(...)` | `.config/vlc/vlcrc`, `vlc-qt-interface.conf` | Held out. These files are UNREADABLE, never PASS and never "unchanged". A VLC predicate is UNSUPPORTED |

## Formatting (xlsx, ods, docx, odt, pptx)

The same keys in every format, written by `readers_office` (`FORMAT_KEYS`). An absent key is the default
(`FORMAT_DEFAULTS`; `CELL_FORMAT_DEFAULTS` also sets `number_format` to `General`).

| Key | Values | Where it comes from |
|---|---|---|
| `bold`, `italic` | boolean | xlsx font; docx run `w:b`/`w:i`; pptx run `b`/`i`; ODF `fo:font-weight`/`fo:font-style` |
| `underline` | style name or None (`single`, `double`, ...) | xlsx font `u`; docx `w:u`; pptx `u` (`sng` mapped to `single`); ODF `style:text-underline-style` |
| `strike` | `single`, `double`, `none` | xlsx font `strike`; docx `w:strike`/`w:dstrike`; pptx `strike`; ODF line-through |
| `font` | family name | xlsx font `name`; docx `w:rFonts/@ascii`; pptx `a:latin`; ODF `style:font-name` |
| `size` | points (float) | xlsx font `sz`; docx `w:sz` / 2; pptx `sz` / 100; ODF `fo:font-size` |
| `color` | 6-digit hex, or `theme:N` / `indexed:N` when not resolvable | xlsx font colour (theme colours resolve through the theme part, tint applied); docx `w:color`; pptx run `srgbClr`; ODF `fo:color` |
| `background_color` | 6-digit hex or None | xlsx solid fill (`fgColor`); ODS cell background; docx table-cell `w:shd` and paragraph shading; pptx shape solid fill; ODF paragraph and text background |
| `highlight` | 6-digit hex or None | docx `w:highlight` (named colours mapped to hex) and run shading; pptx `a:highlight`; ODF text background (`background_color` of the run) |
| `number_format` | Excel-style code | xlsx `numFmt` (built-in ids mapped to their codes; `\ ` read as a space); ODS data styles (approximate: digits, decimals, grouping, percent, currency symbol, date and time fields) |
| `alignment` | left, center, right, justify, or None | docx `w:jc`; pptx `algn`; ODF `fo:text-align` on the paragraph or the cell style; xlsx cell `horizontal` |
| `hyperlink` | target string | xlsx `hyperlink` (external relationship or `location`); docx `w:hyperlink` (external relationship or anchor); pptx `a:hlinkClick`; ODF `text:a/@xlink:href` |

Notes:
- Colours are compared as values. `None` means the application's automatic colour. An ODS cell with no colour is
  automatic, while xlsx `theme:1` resolves to `000000`, so the two can differ for the same appearance.
- A cell's formatting is its own style, and a cell with no style of its own inherits its column's default style in
  ODS (LibreOffice writes formatted columns this way). Empty cells are recorded only when they carry their own style.
- The raw xlsx style index (`s`) is not kept. An app renumbers it on every save.
- ODS dates are converted to Excel serial numbers (days since 1899-12-30), as xlsx stores them.
- Not read: odp shape fill and odp paragraph formatting, xlsx conditional formats, indexed palette colours,
  docx and pptx theme-colour names (`schemeClr`), table borders, and cell wrap or rotation.

## Formula values (xlsx)

- A shared-formula child (`<f t="shared" si=".."/>`) reads the group master's formula text, moved to the child's
  cell with openpyxl's `Translator`. Checked cell by cell against openpyxl's own translation (BoomerangSales: 35 of 35).
- A formula cell with no cached result (generator-written files) takes the value LibreOffice computes. The file is
  copied to a temp directory, LibreOffice converts the copy (headless, own profile, 180 s limit), and only the
  values are taken from its result. A failed recalculation makes the file unreadable, so predicates on it are
  UNSUPPORTED. The state file itself is never opened by LibreOffice.

## Grammar and builtins

The parser is specexec's. Predicates it cannot parse stay UNSUPPORTED (96 of 302 predicates, counted in
`dryrun.py` output). Builtins: specexec's (`lower`, `trim`, `collapse_whitespace`, `proper_case`, `replace`,
`len`, `count`) plus `exists`, `basename`, `uri_to_path`, `urldecode`, `join`.

Not implemented (UNSUPPORTED, by design): `near`, `bbox`, `similarity`, `hsv_mean_*`, `mean_chroma`,
`grayscale`, `mean_rgb`, `content_region`, `aspect_ratio`, `where`-clauses on pixel data, and any name not listed above.
