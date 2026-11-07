"""Derive the UI state that each Exp 8 task's setup steps leave behind.

Reads only the starting files and the setup steps of research/exp4b/blind_tasks.json.
Uses a headless LibreOffice listener on localhost:2002 (started by the caller).
Output is JSON on stdout. These facts go into the UI-context block of the agent prompt.
"""
import json, os, shutil, sys
import uno
from com.sun.star.beans import PropertyValue

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..", "exp5-grounded", "snapshots")
TASKS = {t["id"]: t for t in json.load(open(os.path.join(HERE, "..", "exp4b", "blind_tasks.json")))}


def pv(name, value):
    p = PropertyValue()
    p.Name, p.Value = name, value
    return p


def snap(task_prefix, basename):
    import glob
    hits = glob.glob(os.path.join(ROOT, task_prefix + "*", "**", basename), recursive=True)
    assert len(hits) == 1, hits
    return hits[0]


def connect():
    local = uno.getComponentContext()
    resolver = local.ServiceManager.createInstanceWithContext("com.sun.star.bridge.UnoUrlResolver", local)
    ctx = resolver.resolve("uno:socket,host=localhost,port=2002;urp;StarOffice.ComponentContext")
    return ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)


def load_hidden(desktop, path):
    url = uno.systemPathToFileUrl(path)
    return desktop.loadComponentFromURL(url, "_blank", 0, (pv("Hidden", True),))


def _page(vc):
    try:
        return vc.getPage()
    except Exception as e:  # headless hidden view has no page layout in some builds
        return f"unavailable: {str(e)[:60]}"


def writer_probe(desktop, path, presses):
    doc = load_hidden(desktop, path)
    ctrl = doc.getCurrentController()
    vc = ctrl.getViewCursor()
    vc.gotoStart(False)
    for _ in range(presses):
        vc.goDown(1, False)
    text = doc.getText()
    # Context: text of the paragraph before the cursor and after it.
    before = text.createTextCursorByRange(vc)
    before.gotoStartOfParagraph(True)
    after = text.createTextCursorByRange(vc)
    after.gotoEndOfParagraph(True)
    tbl = vc.getPropertyValue("TextTable") if vc.getPropertySetInfo().hasPropertyByName("TextTable") else None
    # Index of the body element that holds the cursor (paragraphs and tables counted in order).
    idx = None
    body = []
    en = text.createEnumeration()
    i = 0
    while en.hasMoreElements():
        el = en.nextElement()
        kind = "table" if el.supportsService("com.sun.star.text.TextTable") else "paragraph"
        body.append((i, kind))
        if idx is None:
            # Element holds the cursor if the cursor lies between its start and end.
            rng = el.getAnchor() if kind == "table" else el
            s_cmp = text.compareRegionStarts(vc, rng)
            e_cmp = text.compareRegionEnds(vc, rng)
            if kind == "paragraph":
                ok = s_cmp >= 0 and e_cmp <= 0
            else:
                ok = s_cmp >= 0 and e_cmp <= 0
            if ok:
                idx = i
                cur_kind = kind
        i += 1
    before_s, after_s, page = before.getString(), after.getString(), _page(vc)
    doc.close(True)
    return {
        "page": page,
        "presses": presses,
        "body_element_index": idx,
        "body_element_kind": cur_kind if idx is not None else None,
        "in_table": bool(tbl),
        "text_before_cursor_in_paragraph": before_s,
        "text_after_cursor_in_paragraph": after_s,
        "body_elements": len(body),
    }


def impress_probe(desktop, path):
    doc = load_hidden(desktop, path)
    pages = doc.getDrawPages()
    out = {"slides": pages.getCount(), "slide_texts": []}
    for n in range(pages.getCount()):
        page = pages.getByIndex(n)
        texts = []
        for k in range(page.getCount()):
            sh = page.getByIndex(k)
            if sh.supportsService("com.sun.star.drawing.TextShape") or sh.supportsService("com.sun.star.presentation.OutlinerShape") or sh.supportsService("com.sun.star.drawing.GraphicObjectShape") or True:
                try:
                    s = sh.getString()
                except Exception:
                    s = ""
                pos, size = sh.getPosition(), sh.getSize()
                texts.append({"pos_mm": [pos.X / 100, pos.Y / 100], "size_mm": [size.Width / 100, size.Height / 100], "text": s[:80]})
        out["slide_texts"].append({"slide": n + 1, "shapes": texts})
    doc.close(True)
    return out


if __name__ == "__main__":
    which = sys.argv[1]
    desktop = connect()
    if which == "writer_66399b0d":
        t = [v for k, v in TASKS.items() if k.startswith("66399b0d")][0]
        src = snap("66399b0d", "Table_Of_Work_Effort_Instructions.docx")
        tmp = "/tmp/exp8_probe_" + which + ".docx"
        shutil.copy(src, tmp)
        print(json.dumps(writer_probe(desktop, tmp, 40), ensure_ascii=False, indent=1))
    elif which == "impress_550ce7e7":
        src = snap("550ce7e7", "New_Club_Spring_2018_Training.pptx")
        tmp = "/tmp/exp8_probe_" + which + ".pptx"
        shutil.copy(src, tmp)
        print(json.dumps(impress_probe(desktop, tmp), ensure_ascii=False, indent=1))
    elif which == "impress_21760ecb":
        src = snap("21760ecb", "Ch4 Video Effect.pptx")
        tmp = "/tmp/exp8_probe_" + which + ".pptx"
        shutil.copy(src, tmp)
        print(json.dumps(impress_probe(desktop, tmp), ensure_ascii=False, indent=1))
    elif which == "impress_f23acfd2":
        src = snap("f23acfd2", "69_4.pptx")
        tmp = "/tmp/exp8_probe_" + which + ".pptx"
        shutil.copy(src, tmp)
        print(json.dumps(impress_probe(desktop, tmp), ensure_ascii=False, indent=1))
