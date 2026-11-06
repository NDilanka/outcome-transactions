import json, os, re, csv, collections
ROOT = r"D:\dev\interface-compiler\research\OSWorld"
OUT = r"D:\dev\interface-compiler\research"

# name: (metric_readers, derived_measures, predicate_kind, needs_original, uses_gold_artifact, expressible, fuzzy, graded, reason)
# metric_readers: readers the checker itself parses from the file it is handed; getter-supplied readers are added per task below.
Y, YN, P, N = "yes", "yes_with_new_reader", "partial", "no"
R = {
"compare_table": ("xlsx.cells;xlsx.format;xlsx.objects", "", "reference_file_compare;literal_equal;numeric_tolerance;regex;similarity_threshold", 0, 1, Y, 0, 0, "Rule list of cell/sheet equalities vs gold or literals; 10 tasks need chart/pivot readers (xlsx.objects); preserve_cells rules (13 tasks) are a footprint check done via gold"),
"compare_pptx_files": ("pptx.shapes;pptx.text_format;pptx.slide_props", "", "reference_file_compare;numeric_tolerance", 0, 1, Y, 0, 0, "Attribute-wise equality vs gold deck over a projection chosen by ~20 examine_* flags with position/color tolerances"),
"infeasible": ("", "", "agent_output", 0, 0, N, 0, 0, "Checks that the agent declared the task infeasible (FAIL action); no state to read"),
"check_include_exclude": ("", "", "contains_exclude", 0, 0, P, 0, 0, "Substring include/exclude over arbitrary command output; 13 tasks wrap a typed reader, 7 delegate to an opaque downloaded eval.sh/check_password.sh"),
"exact_match": ("", "", "literal_equal", 0, 0, Y, 0, 0, "Literal equality over browser prefs, gsettings, dir listings, file-exists tests, or output of running the agent's script"),
"check_direct_json_object": ("", "", "literal_equal;contains_exclude", 0, 0, YN, 0, 0, "Dict equality over fields scraped from the live page DOM / URL; 12 tasks compute expected values relative to the evaluation date"),
"compare_docx_files": ("docx.text", "string_similarity", "reference_file_compare;similarity_threshold", 0, 1, Y, 0, 0, "Paragraph text equality (optionally fuzzy, order/case/blank-insensitive) vs gold"),
"compare_pdfs": ("pdf.text", "string_similarity", "reference_file_compare;similarity_threshold", 0, 1, Y, 0, 1, "Mean fuzz.ratio of extracted text vs gold; returns graded score, needs a threshold in our format"),
"is_expected_url_pattern_match": ("", "", "regex", 0, 0, Y, 0, 0, "All regexes must match active tab URL"),
"compare_images": ("image.pixels", "image_ssim", "reference_file_compare;similarity_threshold", 0, 1, YN, 0, 0, "SSIM vs gold image after resize; needs SSIM derived measure"),
"check_list": ("file.text", "", "regex;contains_exclude", 0, 0, Y, 0, 0, "Line regex expect/unexpect; in practice used on diff output, i.e. file bytes == reference"),
"check_json_settings": ("json.path", "", "literal_equal", 0, 0, Y, 0, 0, "Each expected top-level key equals value in settings.json"),
"compare_text_file": ("file.text", "", "reference_file_compare", 0, 1, Y, 0, 0, "Text equality vs gold after regex line removal / whitespace normalization"),
"is_extension_installed": ("", "", "contains_exclude", 0, 0, Y, 0, 0, "Substring in `code --list-extensions` or ls output"),
"is_expected_active_tab": ("", "", "literal_equal", 0, 0, Y, 0, 0, "Normalized URL equality of active tab"),
"check_config_status": ("config.key", "", "literal_equal", 0, 0, Y, 0, 0, "Key/value in GIMP sessionrc"),
"compare_csv": ("csv.rows", "", "reference_file_compare", 0, 1, Y, 0, 0, "Line equality vs one of several gold CSVs"),
"compare_docx_tables": ("docx.tables", "", "reference_file_compare", 0, 1, Y, 0, 0, "Table shape and cell text equality vs gold"),
"check_thunderbird_prefs": ("config.key", "", "literal_equal;regex", 0, 0, Y, 0, 0, "prefs.js key expect/unexpect with eq/regex rules"),
"is_expected_tabs": ("", "", "set_list_equal", 0, 0, Y, 0, 0, "Open tab URL list equality"),
"is_expected_bookmarks": ("", "", "set_list_equal", 0, 0, Y, 0, 0, "Set equality of bookmark-bar folder names / URLs (with alternatives)"),
"check_url_and_content_include": ("", "", "contains_exclude;literal_equal", 0, 0, Y, 0, 0, "URL host/query/substring checks plus page body include/exclude"),
"check_structure_sim": ("image.pixels;image.size", "image_ssim", "reference_file_compare;similarity_threshold", 0, 1, YN, 0, 0, "Same size and SSIM>=0.9 vs gold"),
"compare_audios": ("audio.samples", "audio_mfcc_dtw", "reference_file_compare;similarity_threshold", 0, 1, YN, 0, 0, "MFCC + DTW distance vs the source audio file; could be a hash equality since the reference is the input asset"),
"compare_config": ("file.text;json.path", "", "contains_exclude;literal_equal", 0, 0, YN, 0, 0, "JSON subset / text containment over a VS Code state dump produced by a helper extension"),
"compare_archive": ("archive.members;pdf.text;file.text", "string_similarity", "reference_file_compare;set_list_equal", 0, 1, Y, 0, 1, "Member name list equality then per-member delegate compare vs gold archive"),
"check_json": ("json.path", "", "literal_equal;regex", 0, 0, Y, 0, 0, "Key-path expect/unexpect rules over JSON/YAML"),
"check_accessibility_tree": ("", "string_similarity", "literal_equal;similarity_threshold", 0, 0, Y, 0, 1, "CSS/XPath selector must match; optional exact or fuzzy text"),
"match_in_list": ("", "", "set_list_equal", 0, 0, Y, 0, 0, "Value is one of allowed literals"),
"is_in_list": ("", "", "contains_exclude", 0, 0, Y, 0, 0, "Expected path is in list of unpacked extension paths"),
"check_brightness_decrease_and_structure_sim": ("image.pixels", "image_brightness;image_mse", "structural_property;similarity_threshold", 1, 0, YN, 0, 0, "Brightness lower than original image AND MSE structure match after brightness normalization"),
"check_image_size": ("image.size;image.pixels", "", "literal_equal", 0, 0, Y, 0, 0, "Width/height (optionally of non-transparent bbox) equals literal"),
"compare_line_spacing": ("docx.text;docx.format", "", "reference_file_compare", 0, 1, Y, 0, 0, "Text guard vs gold then per-paragraph line_spacing equality vs gold"),
"compare_docx_images": ("docx.media", "", "reference_file_compare", 0, 1, Y, 0, 0, "Embedded image count and pixel bytes equal gold"),
"compare_image_list": ("image.pixels", "", "reference_file_compare", 0, 1, Y, 0, 0, "Exact pixel equality vs gold list (after resize)"),
"check_thunderbird_folder": ("mail.messages", "", "reference_file_compare;set_list_equal", 0, 1, YN, 0, 0, "mbox message multiset equality vs gold folders, ignoring deleted/status headers"),
"diff_text_file": ("file.text", "string_similarity", "reference_file_compare;similarity_threshold", 0, 1, Y, 0, 1, "difflib line ratio vs gold; graded"),
"python_test_suite_score": ("", "", "numeric_tolerance", 0, 0, YN, 0, 1, "Runs a hidden test suite against the agent's code; score is pass fraction"),
"file_contains": ("file.text", "", "contains_exclude", 0, 0, Y, 0, 0, "All substrings present in file"),
"check_line_include_exclude": ("", "", "regex", 0, 0, Y, 0, 0, "Some terminal line fullmatches each include regex; none matches exclude"),
"check_thunderbird_filter": ("mail.filters", "", "set_list_equal;literal_equal", 0, 0, Y, 0, 0, "Parsed filter records contain expected records"),
"is_vlc_playing": ("", "", "literal_equal;contains_exclude", 0, 0, YN, 0, 0, "VLC HTTP status: state==playing and current file/url matches"),
"check_json_keybindings": ("json.path", "", "contains_exclude", 0, 0, Y, 0, 0, "Expected binding object is an element of keybindings.json list"),
"is_cookie_deleted": ("", "", "contains_exclude", 0, 0, Y, 0, 0, "No cookie domain matches the listed domains"),
"is_shortcut_on_desktop": ("", "", "contains_exclude;literal_equal", 0, 0, Y, 0, 0, "Some .desktop file has Name= equal to or containing expected name"),
"check_font_size": ("", "", "range_ordering;literal_equal", 0, 0, Y, 0, 0, "Default font size within range"),
"is_expected_active_tab_approximate": ("", "", "literal_equal", 0, 0, Y, 0, 0, "Active URL equal ignoring query string"),
"is_added_to_steam_cart": ("", "", "contains_exclude", 0, 0, Y, 0, 0, "Cart page content contains every expected item name"),
"check_nfl_super_bowl_liv": ("", "", "regex;custom_logic", 0, 0, Y, 0, 0, "Host whitelist, path blacklist, then one of three score regexes on body; needs a disjunction"),
"check_history_deleted": ("", "", "contains_exclude", 0, 0, Y, 0, 0, "No history URL contains keyword"),
"check_saturation_increase_and_structure_sim": ("image.pixels", "image_saturation;image_ssim", "structural_property;similarity_threshold", 1, 0, YN, 0, 0, "Saturation higher than original AND H,V channels SSIM-similar to original"),
"check_file_exists_and_structure_sim": ("file.exists;image.pixels", "image_ssim", "similarity_threshold", 1, 0, YN, 0, 0, "File exists and SSIM-similar to the original photo"),
"check_triangle_position": ("image.pixels", "object_detector", "custom_logic;numeric_tolerance", 0, 0, YN, 0, 0, "Detect yellow triangle centroid; within 5% of image center"),
"check_structure_sim_resized": ("image.pixels", "image_ssim", "similarity_threshold", 1, 0, YN, 0, 0, "Crop to alpha bbox, resize to original size, SSIM vs original"),
"check_palette_and_structure_sim": ("image.pixels;file.meta", "image_ssim", "literal_equal;similarity_threshold", 1, 0, YN, 0, 0, "Image mode == 'P' and SSIM-similar to original"),
"check_textbox_on_leftside": ("image.pixels", "pixel_scan", "custom_logic;range_ordering", 0, 0, YN, 0, 0, "Leftmost dark pixel x < 35% of width (weak proxy for 'text box on left')"),
"check_contrast_increase_and_structure_sim": ("image.pixels", "image_contrast;image_ssim", "structural_property;similarity_threshold", 1, 0, YN, 0, 0, "Contrast higher than original AND SSIM>=0.65 vs original"),
"check_image_mirror": ("image.pixels", "image_ssim;image_transform", "structural_property;similarity_threshold", 1, 0, YN, 0, 0, "Result SSIM>=0.99 to horizontally flipped original"),
"check_green_background": ("image.pixels", "pixel_mask", "structural_property;custom_logic", 1, 0, YN, 0, 0, "Foreground pixels identical to original; background pixels green-dominant"),
"check_pdf_pages": ("pdf.pages", "", "literal_equal;range_ordering", 0, 0, Y, 0, 0, "Page count relation to literal"),
"check_image_stretch_and_center": ("pptx.shapes;pptx.media;pptx.slide_props", "", "numeric_tolerance", 1, 0, Y, 0, 0, "Find original image by blob in result; size ~ slide size and centered within 0.5in"),
"check_left_panel": ("", "", "literal_equal", 0, 0, Y, 0, 0, "a11y node 'Slides View' exists"),
"check_presenter_console_disable": ("config.key", "", "literal_equal", 0, 0, Y, 0, 0, "LibreOffice registry key EnablePresenterScreen == false"),
"check_slide_orientation_Portrait": ("pptx.slide_props", "", "range_ordering", 0, 0, Y, 0, 0, "slide_width < slide_height"),
"evaluate_presentation_fill_to_rgb_distance": ("pptx.slide_props", "color_distance", "numeric_tolerance;structural_property", 1, 0, Y, 0, 0, "Every slide background closer to target RGB than to original RGB (original passed as literal)"),
"check_transition": ("pptx.slide_props", "", "literal_equal", 0, 0, Y, 0, 0, "Slide N has transition of given type"),
"check_page_number_colors": ("pptx.text_format", "color_family", "numeric_tolerance", 0, 0, Y, 0, 0, "Slide-number placeholder runs are 'red' by RGB threshold"),
"check_auto_saving_time": ("config.key", "", "literal_equal", 0, 0, Y, 0, 0, "AutoSaveTimeIntervall == literal"),
"check_continuation_line_indent_no_bullet": ("pptx.text_format", "", "numeric_tolerance", 0, 0, Y, 0, 0, "Target paragraph left offset equals reference paragraphs' within tolerance, no bullet (reader vs reader)"),
"compare_pptx_files_tolerant": ("pptx.shapes;pptx.text_format;pptx.slide_props", "", "reference_file_compare;numeric_tolerance", 0, 1, Y, 0, 0, "compare_pptx_files with color tolerance 50"),
"compare_pptx_files_robust": ("pptx.shapes;pptx.text_format;pptx.slide_props", "", "reference_file_compare;numeric_tolerance", 0, 1, Y, 0, 0, "compare_pptx_files with theme-color resolution in the reader"),
"check_tabstops": ("docx.text;docx.layout", "", "reference_file_compare;numeric_tolerance", 0, 1, Y, 0, 0, "Tab-stop alignment equality and position tolerance vs gold, word count before tab"),
"compare_subscript_contains": ("docx.format", "", "reference_file_compare", 0, 1, Y, 0, 0, "Any aligned run pair where both result and gold are subscript (weak)"),
"has_page_numbers_in_footers": ("docx.layout", "", "regex", 0, 0, Y, 0, 0, "Each section footer contains a digit (does not check 'bottom left')"),
"compare_font_names": ("docx.format", "", "literal_equal", 0, 0, Y, 0, 0, "Every run font == literal (universal quantifier)"),
"is_first_line_centered": ("docx.format", "", "literal_equal", 0, 0, Y, 0, 0, "First paragraph alignment == CENTER"),
"check_highlighted_words": ("docx.text;docx.format", "", "reference_file_compare;contains_exclude", 0, 1, Y, 0, 0, "Text guard vs gold then no span with yellow background (ODT)"),
"compare_unique_train_records": ("docx.text", "", "set_list_equal;custom_logic", 1, 1, Y, 0, 0, "Result lines subset of original lines, ids unique, id set == gold ids, count == gold"),
"evaluate_strike_through_last_paragraph": ("docx.text;docx.format", "", "reference_file_compare;literal_equal", 0, 1, Y, 0, 0, "Text guard vs gold then every run in last paragraph struck"),
"evaluate_colored_words_in_tables": ("docx.tables;docx.format", "color_family", "custom_logic;reference_file_compare", 0, 1, Y, 0, 0, "Text guard vs gold; per word color family must be red iff first letter is a vowel (quantified conditional)"),
"check_italic_font_size_14": ("docx.text;docx.format", "", "reference_file_compare;literal_equal", 0, 1, Y, 0, 0, "Text guard vs gold then every italic run size == 14"),
"contains_page_break": ("docx.layout", "", "literal_equal", 0, 0, Y, 0, 0, "Page-break count == literal"),
"find_default_font": ("config.key", "", "literal_equal", 0, 0, Y, 0, 0, "LibreOffice registry default font == literal"),
"compare_htmls": ("html.dom", "", "reference_file_compare", 0, 1, Y, 0, 0, "Element-wise tag/text/attr equality vs gold HTML"),
"is_expected_search_query": ("", "", "regex", 0, 0, Y, 0, 0, "Active URL matches search-query regex"),
"compare_pdf_form_fields": ("pdf.form_fields;pdf.text", "", "literal_equal;custom_logic", 0, 0, Y, 0, 1, "Weighted per-field equality to literal employee data across 7 PDFs; graded"),
"compare_references_gain": ("docx.text", "string_similarity", "similarity_threshold;custom_logic", 1, 1, P, 1, 1, "Score = normalized similarity gain toward gold relative to original; arithmetic over measures, graded; gold stands in for 'correct APA style'"),
"compare_docx_files_and_ignore_new_lines": ("docx.text", "", "reference_file_compare", 0, 1, Y, 0, 0, "Non-empty paragraph text equality vs gold"),
"check_clipboard_path": ("", "", "literal_equal", 0, 0, Y, 0, 0, "Clipboard text == literal path"),
"is_expected_installed_extensions": ("", "", "set_list_equal", 0, 0, Y, 0, 0, "Expected extension names subset of installed (with alias table)"),
"compare_conference_city_in_order": ("xlsx.cells", "", "set_list_equal", 0, 0, Y, 0, 0, "Ordered list of cells equals expected with per-position alternatives"),
"check_line_number": ("file.text", "", "regex;literal_equal", 0, 0, Y, 0, 0, "Count of lines matching time regex == literal (needs count aggregate)"),
"compare_zip_files": ("archive.members;pdf.text;file.bytes", "string_similarity", "reference_file_compare;similarity_threshold", 0, 1, Y, 0, 0, "Member set equal; PDFs text-similar >=0.95, others byte-equal vs gold"),
"compare_image_text": ("image.pixels", "ocr", "contains_exclude", 0, 0, YN, 0, 0, "OCR text of image contains expected string"),
"compare_pdf_images": ("pdf.images", "image_phash", "reference_file_compare;similarity_threshold", 0, 1, YN, 0, 1, "Same embedded image count; fraction with phash distance <=5 vs gold"),
"literal_match": ("xlsx.cells", "", "set_list_equal", 0, 0, YN, 0, 0, "Last table row equals values scraped live from Google Scholar at evaluation time"),
"fuzzy_place_math": ("docx.text", "string_similarity", "similarity_threshold", 0, 0, Y, 0, 1, "Each word best fuzz.ratio vs candidate answers; entry count fixed; graded"),
"compare_python_pure_text": ("file.text", "", "reference_file_compare", 0, 1, Y, 0, 0, "Whitespace-normalized text equality vs gold"),
"check_mp3_meta": ("audio.tags", "", "literal_equal", 0, 0, Y, 0, 0, "ID3 title/artist equal literals"),
"compare_epub_semantic": ("epub.content", "string_similarity", "reference_file_compare;similarity_threshold", 0, 1, YN, 0, 1, "Title and chapter text fuzzy-aligned to gold epub; graded"),
"check_structure_sim_with_threshold": ("image.pixels", "image_ssim", "reference_file_compare;similarity_threshold", 0, 1, YN, 0, 0, "SSIM >= 0.85 vs gold cut-out"),
"check_image_file_size": ("file.meta", "", "range_ordering", 0, 0, Y, 0, 0, "File size < literal"),
"compare_result_files": ("file.text", "", "reference_file_compare;numeric_tolerance", 0, 1, Y, 0, 0, "A number in result within 1e-4 of the gold number"),
"compare_docx_paper_records": ("docx.text", "string_similarity", "similarity_threshold;custom_logic", 0, 1, P, 0, 1, "Parse records, fuzzy-align by title, weighted field similarity vs gold; graded scoring scheme"),
"compare_table_records": ("xlsx.cells", "", "set_list_equal;range_ordering;custom_logic", 0, 1, Y, 0, 0, "Rows keyed by column match gold rows, sorted order, prefilled rows kept"),
"check_gnome_favorite_apps": ("", "", "set_list_equal", 0, 0, Y, 0, 0, "gsettings favorite-apps set == literal"),
"is_utc_0": ("", "", "regex", 0, 0, Y, 0, 0, "timedatectl Time zone ends with +0000"),
"check_moved_jpgs": ("", "", "set_list_equal", 0, 0, Y, 0, 0, "Directory listing set == literal"),
"check_csv": ("csv.rows", "", "contains_exclude", 0, 0, Y, 0, 0, "No account record matches the removed account"),
"run_sqlite3": ("sqlite.query", "", "custom_logic", 0, 0, Y, 0, 0, "Task-authored SQL over Thunderbird global-messages-db returns truthy"),
"check_thunderbird_smtp_only": ("config.key", "", "custom_logic;literal_equal", 0, 0, Y, 0, 0, "Join over prefs: identity with given email has SMTP server and account has no incoming server"),
"is_vlc_recordings_folder": ("config.key", "", "literal_equal", 0, 0, Y, 0, 0, "vlcrc input-record-path == literal"),
"is_vlc_fullscreen": ("", "", "literal_equal", 0, 0, Y, 0, 0, "Window size == screen size (reader vs reader)"),
"compare_videos": ("video.frames", "image_phash", "reference_file_compare;similarity_threshold", 0, 1, YN, 0, 0, "Per-frame phash vs gold for first 100 frames, mismatch count <= 5"),
"check_global_key_play_pause": ("config.key", "", "literal_equal", 0, 0, Y, 0, 0, "vlcrc key == literal"),
"check_qt_max_volume": ("config.key", "", "literal_equal", 0, 0, Y, 0, 0, "vlcrc key == literal"),
"check_qt_slider_colours": ("config.key", "color_family", "numeric_tolerance", 0, 0, Y, 0, 0, "Slider colours all 'blackish' (each channel < 100)"),
"check_qt_minimal_view": ("config.key", "", "literal_equal", 0, 0, Y, 0, 0, "vlcrc key == literal"),
"check_play_and_exit": ("config.key", "", "literal_equal", 0, 0, Y, 0, 0, "vlcrc key == literal (with default when absent)"),
"check_one_instance_when_started_from_file": ("config.key", "", "literal_equal", 0, 0, Y, 0, 0, "vlcrc key == literal (with default when absent)"),
"check_qt_bgcone": ("config.key", "", "literal_equal", 0, 0, Y, 0, 0, "vlcrc key == literal; reader must apply the app default when key absent"),
}

GETTER = {
 "googledrive_file": "cloud.drive", "vm_terminal_output": "terminal.buffer",
 "active_url_from_accessTree": "browser.active_tab", "active_tab_info": "browser.active_tab", "active_tab_url_parse": "browser.active_tab",
 "url_path_parse": "browser.active_tab", "url_dashPart": "browser.active_tab",
 "active_tab_html_parse": "browser.page", "active_tab_url_and_body_text": "browser.active_tab;browser.page", "page_info": "browser.page",
 "gotoRecreationPage_and_get_html_content": "oracle.web_live", "rule_relativeTime": "oracle.clock",
 "info_from_website": "oracle.web_live", "pdf_from_url": "oracle.web_live",
 "vlc_config": "config.key", "vlc_playing_info": "media.player_status", "accessibility_tree": "a11y.tree", "gimp_config_file": "config.key",
 "open_tabs_info": "browser.tabs", "bookmarks": "browser.bookmarks", "find_unpacked_extension_path": "browser.extensions",
 "find_installed_extension_name": "browser.extensions", "audio_in_slide": "pptx.media", "background_image_in_slide": "pptx.media",
 "vscode_config": "app.internal_state", "python_test_suite_result": "exec.result", "vm_wallpaper": "os.settings",
 "default_search_engine": "browser.prefs", "cookie_data": "browser.cookies", "shortcuts_on_desktop": "dir.listing;file.text",
 "profile_name": "browser.prefs", "chrome_font_size": "browser.prefs", "data_delete_automacally": "browser.prefs",
 "chrome_appearance_mode_ui": "browser.prefs", "new_startup_page": "browser.prefs", "enable_do_not_track": "browser.prefs",
 "enable_safe_browsing": "browser.prefs", "history": "browser.history", "default_video_player": "os.settings",
 "content_from_vm_file": "xlsx.cells", "list_directory": "dir.listing", "vm_screen_size": "window.geometry", "vm_window_size": "window.geometry",
}
def cmd_reader(c):
    if re.search(r"eval\.sh|check_password\.sh", c): return "cmd.opaque_script"
    if "bash_history" in c: return "shell.history"
    if "ps aux" in c: return "process.list"
    if re.search(r"gsettings|timedatectl|pactl", c): return "os.settings"
    if "xsel" in c: return "clipboard"
    if "list-extensions" in c: return "app.extensions"
    if re.search(r"^\s*(PYMUPDF_MESSAGE=\S+\s+)?python3? /home|python -c from", c): return "exec.result"
    if re.search(r"\[ -[fd] ", c): return "file.exists"
    if re.search(r"^ls |\bls /home", c): return "dir.listing"
    if "git log" in c: return "vcs.log"
    if re.search(r"file --mime-type", c): return "file.meta"
    if "which " in c: return "file.exists"
    if re.search(r"cat |grep ", c): return "file.text"
    return "cmd.output"

ta = json.load(open(os.path.join(ROOT, "evaluation_examples", "test_all.json")))
ORDER = {Y: 3, YN: 2, P: 1, N: 0}
func_tasks = collections.defaultdict(set); func_readers = collections.defaultdict(set)
func_task_expr = collections.defaultdict(dict)
tasks = []
for dom, ids in ta.items():
    for i in ids:
        t = json.load(open(os.path.join(ROOT, "evaluation_examples", "examples", dom, i + ".json"), encoding="utf-8"))
        ev = t["evaluator"]; f = ev["func"]; multi = isinstance(f, list); fs = f if multi else [f]
        def L(x): return x if (multi and isinstance(x, list)) else [x] * len(fs)
        rs, es, os_ = L(ev.get("result")), L(ev.get("expected")), L(ev.get("options", {}))
        treaders, texpr, oracle, orig, gold, graded, fuzzy = set(), [], set(), False, False, False, False
        ct_rules = set()
        for k, fn in enumerate(fs):
            if fn not in R: raise SystemExit("unmapped func " + fn)
            mr, dm, pk, no, ug, ex, fz, gr, why = R[fn]
            rd = set(x for x in mr.split(";") if x)
            for g in (rs[k] if k < len(rs) else None, es[k] if k < len(es) else None):
                gs = g if isinstance(g, list) else [g]
                for gg in gs:
                    if not isinstance(gg, dict): continue
                    ty = gg.get("type")
                    if ty in ("vm_command_line", "vm_command_error"):
                        c = gg.get("command"); c = " ".join(c) if isinstance(c, list) else str(c)
                        rd.add(cmd_reader(c))
                    elif ty in GETTER:
                        for x in GETTER[ty].split(";"):
                            (oracle if x.startswith("oracle.") else rd).add(x)
            ex_task = ex
            if fn == "check_include_exclude":
                ex_task = P if "cmd.opaque_script" in rd else Y
            if fn == "compare_table":
                o = os_[k] if k < len(os_) else {}
                rts = {r["type"] for r in (o or {}).get("rules", [])}
                ct_rules |= rts
                comparative = rts - {"check_cell", "zoom", "data_validation"}
                ug = 1 if comparative else 0
                rd = {"xlsx.cells"} | ({"xlsx.format"} if rts & {"style", "freeze", "zoom", "data_validation", "row_props", "col_props", "check_cell", "sheet_print"} else set()) | ({"xlsx.objects"} if rts & {"chart", "pivot_table", "filter", "sparkline"} else set())
                if rts & {"chart", "pivot_table"}: ex_task = YN
            if oracle and ex_task == Y: ex_task = YN
            func_tasks[fn].add(i); func_readers[fn] |= rd; func_task_expr[fn][i] = ex_task
            treaders |= rd; texpr.append(ex_task)
            orig |= bool(no); gold |= bool(ug); graded |= bool(gr); fuzzy |= bool(fz)
        conj = ev.get("conj", "and") if multi else "and"
        tasks.append(dict(domain=dom, id=i, funcs=fs, conj=conj, readers=treaders, oracle=oracle,
                          expr=min(texpr, key=lambda e: ORDER[e]), orig=orig, gold=gold, graded=graded, fuzzy=fuzzy,
                          ct_rules=ct_rules, postconfig=[p.get("type") for p in (ev.get("postconfig") or [])],
                          infeasible=("infeasible" in fs)))

rows = []
for fn, (mr, dm, pk, no, ug, ex, fz, gr, why) in R.items():
    n = len(func_tasks[fn]); te = func_task_expr[fn]
    n_ok = sum(1 for v in te.values() if v in (Y, YN))
    rows.append(dict(func=fn, n_tasks=n, readers=";".join(sorted(func_readers[fn])), derived_measures=dm, predicate_kind=pk,
                     needs_original_state=bool(no), uses_gold_artifact=("mixed" if fn == "compare_table" else bool(ug)),
                     expressible=ex, tasks_expressible=n_ok, fuzzy=bool(fz), graded_score=bool(gr), reason=why))
rows.sort(key=lambda r: (-r["n_tasks"], r["func"]))
with open(os.path.join(OUT, "exp4a-checker-mapping.csv"), "w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)

# ---- aggregates ----
A = {}
real = [r for r in rows if r["func"] != "infeasible"]
A["n_funcs"] = len(real); A["n_tasks"] = len(tasks)
A["func_expr"] = collections.Counter(r["expressible"] for r in real)
A["slot_weight_expr"] = collections.Counter(); 
for r in real: A["slot_weight_expr"][r["expressible"]] += r["n_tasks"]
feas = [t for t in tasks if not t["infeasible"]]
A["n_infeasible_tasks"] = len(tasks) - len(feas)
A["task_expr"] = collections.Counter(t["expr"] for t in feas)
A["task_orig"] = sum(t["orig"] for t in feas); A["func_orig"] = sum(r["needs_original_state"] for r in real)
A["task_gold"] = sum(t["gold"] for t in feas)
A["task_gold_or_orig"] = sum(t["gold"] or t["orig"] for t in feas)
A["task_graded"] = sum(t["graded"] for t in feas); A["task_fuzzy"] = sum(t["fuzzy"] for t in feas)
A["task_oracle"] = collections.Counter(o for t in feas for o in t["oracle"]); A["task_any_oracle"] = sum(bool(t["oracle"]) for t in feas)
A["multi"] = collections.Counter(t["conj"] for t in feas if len(t["funcs"]) > 1)
A["or_same_func"] = sum(1 for t in feas if len(t["funcs"]) > 1 and t["conj"] == "or" and len(set(t["funcs"])) == 1)
A["preserve_cells_tasks"] = sum(1 for t in feas if "preserve_cells" in t["ct_rules"])
GUARD = {"compare_line_spacing", "check_highlighted_words", "evaluate_strike_through_last_paragraph", "evaluate_colored_words_in_tables", "check_italic_font_size_14"}
A["text_guard_tasks"] = sum(1 for t in feas if GUARD & set(t["funcs"]))
A["postconfig_mutating"] = sum(1 for t in feas if set(t["postconfig"]) & {"execute", "command", "close_window", "chrome_inject_js", "launch", "activate_window"})
rc_f = collections.Counter(); rc_t = collections.Counter()
for r in real:
    for x in r["readers"].split(";"):
        if x: rc_f[x] += 1
for t in feas:
    for x in t["readers"]: rc_t[x] += 1
A["readers"] = sorted(((k, rc_f[k], rc_t[k]) for k in set(rc_f) | set(rc_t)), key=lambda x: -x[2])
dm_f = collections.Counter(); dm_t = collections.Counter()
for r in real:
    for x in r["derived_measures"].split(";"):
        if x: dm_f[x] += 1; dm_t[x] += r["n_tasks"]
A["derived"] = sorted(((k, dm_f[k], dm_t[k]) for k in dm_f), key=lambda x: -x[2])
pk_f = collections.Counter(); pk_t = collections.Counter()
for r in real:
    for x in r["predicate_kind"].split(";"): pk_f[x] += 1; pk_t[x] += r["n_tasks"]
A["pred"] = sorted(((k, pk_f[k], pk_t[k]) for k in pk_f), key=lambda x: -x[2])
# coverage curve: how many readers cover what share of feasible tasks (greedy)
remaining = [set(t["readers"]) for t in feas if t["expr"] in (Y, YN)]
chosen, curve, covered = [], [], 0
allr = set().union(*remaining)
while True:
    best, bestn = None, -1
    for rdr in allr - set(chosen):
        c = sum(1 for s in remaining if s <= set(chosen) | {rdr})
        if c > bestn: best, bestn = rdr, c
    if best is None: break
    chosen.append(best); curve.append((best, bestn))
A["greedy_curve"] = curve; A["n_expr_tasks"] = len(remaining)
A["nonexpr_tasks"] = [(t["domain"], t["id"], t["funcs"], t["expr"]) for t in feas if t["expr"] in (P, N)]
A["domain_expr"] = {}
for t in feas:
    d = A["domain_expr"].setdefault(t["domain"], collections.Counter()); d[t["expr"]] += 1; d["_n"] += 1
json.dump(A, open(os.path.join(OUT, "exp4a_aggregates.json"), "w"), default=lambda o: dict(o) if isinstance(o, collections.Counter) else list(o), indent=1)

FAM = lambda x: ("file/dir/archive/text formats" if x.split(".")[0] in ("file", "dir", "archive", "csv", "json", "sqlite", "html", "epub") else
                 "office:" + x.split(".")[0] if x.split(".")[0] in ("xlsx", "docx", "pptx", "pdf") else
                 "browser" if x.startswith("browser.") else
                 "media (image/audio/video)" if x.split(".")[0] in ("image", "audio", "video") else
                 "app/OS config (config.key, os.settings)" if x in ("config.key", "os.settings") else
                 "UI state (a11y, terminal, window, clipboard, player)" if x in ("a11y.tree", "terminal.buffer", "window.geometry", "clipboard", "media.player_status") else
                 "execution / shell (exec, cmd, history, process, vcs, extensions)" if x.split(".")[0] in ("exec", "cmd", "shell", "process", "vcs", "app") else
                 "mail store" if x.startswith("mail.") else "cloud.drive" if x == "cloud.drive" else "other:" + x)
fam_sets = [set(FAM(x) for x in t["readers"]) for t in feas if t["expr"] in (Y, YN)]
allf = set().union(*fam_sets); chosen = []; fcurve = []
while len(chosen) < len(allf):
    best = max(allf - set(chosen), key=lambda f: sum(1 for s in fam_sets if s <= set(chosen) | {f}))
    chosen.append(best); fcurve.append((best, sum(1 for s in fam_sets if s <= set(chosen))))
print("FAMILY CURVE (of", len(fam_sets), "expressible feasible tasks)")
for f, c in fcurve: print(f"  {f}: {c}")
fam_t = collections.Counter(f for s in [set(FAM(x) for x in t["readers"]) for t in feas] for f in s)
print("FAMILY TASKS", fam_t.most_common())
# tasks with no reader at all (should be none among feasible)
print("NO-READER TASKS", [(t["domain"], t["id"], t["funcs"]) for t in feas if not t["readers"]])
# OR tasks: what differs between alternatives
print("OR TASK FUNCS", collections.Counter(t["funcs"][0] for t in feas if t["conj"] == "or" and len(t["funcs"]) > 1))
vague = ["check_brightness_decrease_and_structure_sim","check_saturation_increase_and_structure_sim","check_contrast_increase_and_structure_sim","check_qt_slider_colours","check_page_number_colors","evaluate_colored_words_in_tables","check_textbox_on_leftside","check_triangle_position","evaluate_presentation_fill_to_rgb_distance","check_green_background"]
print("VAGUE TASKS", sum(1 for t in feas if set(vague) & set(t["funcs"])))
