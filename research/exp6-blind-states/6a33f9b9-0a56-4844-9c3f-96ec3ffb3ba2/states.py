import os
import re
import shutil
import zipfile

REL_PATH = os.path.join("home", "user", "Desktop", "sample-recruitment-phone-script.odt")


def _prepare(snapshot_dir, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    shutil.copytree(snapshot_dir, out_dir, dirs_exist_ok=True)
    return os.path.join(out_dir, REL_PATH)


def _rewrite_odt_content(odt_path, transform_fn):
    tmp_path = odt_path + ".tmp"
    with zipfile.ZipFile(odt_path, "r") as zin, zipfile.ZipFile(tmp_path, "w") as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename == "content.xml":
                text = data.decode("utf-8")
                text = transform_fn(text)
                data = text.encode("utf-8")
            zout.writestr(item, data)
    os.replace(tmp_path, odt_path)


def correct_replace_yellow_with_transparent(snapshot_dir, out_dir):
    odt_path = _prepare(snapshot_dir, out_dir)
    _rewrite_odt_content(
        odt_path,
        lambda xml: xml.replace('fo:background-color="#ffff00"', 'fo:background-color="transparent"'),
    )


def correct_remove_yellow_background_attribute(snapshot_dir, out_dir):
    odt_path = _prepare(snapshot_dir, out_dir)
    _rewrite_odt_content(
        odt_path,
        lambda xml: xml.replace(' fo:background-color="#ffff00"', ""),
    )


def wrong_partial_only_non_italic_highlight_removed(snapshot_dir, out_dir):
    odt_path = _prepare(snapshot_dir, out_dir)

    def _partial(xml):
        return xml.replace(
            '<style:style style:name="T9" style:family="text"><style:text-properties fo:background-color="#ffff00"',
            '<style:style style:name="T9" style:family="text"><style:text-properties fo:background-color="transparent"',
        )

    _rewrite_odt_content(odt_path, _partial)


def wrong_changed_yellow_to_white_highlight(snapshot_dir, out_dir):
    odt_path = _prepare(snapshot_dir, out_dir)
    _rewrite_odt_content(
        odt_path,
        lambda xml: xml.replace('fo:background-color="#ffff00"', 'fo:background-color="#ffffff"'),
    )


def wrong_deleted_highlighted_text_spans(snapshot_dir, out_dir):
    odt_path = _prepare(snapshot_dir, out_dir)

    def _delete_spans(xml):
        xml = re.sub(r'<text:span text:style-name="T[59]">.*?</text:span>', "", xml)
        return xml.replace('fo:background-color="#ffff00"', 'fo:background-color="transparent"')

    _rewrite_odt_content(odt_path, _delete_spans)


def wrong_removed_all_bold_and_italic_formatting(snapshot_dir, out_dir):
    odt_path = _prepare(snapshot_dir, out_dir)

    def _strip_all_formatting(xml):
        xml = xml.replace('fo:background-color="#ffff00"', 'fo:background-color="transparent"')
        xml = xml.replace('fo:font-weight="bold"', 'fo:font-weight="normal"')
        xml = xml.replace('fo:font-style="italic"', 'fo:font-style="normal"')
        return xml

    _rewrite_odt_content(odt_path, _strip_all_formatting)


def wrong_changed_font_color_left_yellow_highlight(snapshot_dir, out_dir):
    odt_path = _prepare(snapshot_dir, out_dir)
    _rewrite_odt_content(
        odt_path,
        lambda xml: xml.replace(
            'fo:background-color="#ffff00"',
            'fo:color="#000000" fo:background-color="#ffff00"',
        ),
    )
