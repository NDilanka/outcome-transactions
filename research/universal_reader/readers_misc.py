"""Plain text, PDF, SQLite, archives, media, and mbox mail folders as canonical trees."""
import hashlib
import json
import mailbox
import os
import re
import shutil
import sqlite3
import subprocess
import tarfile
import tempfile
import zipfile
from email import policy
from email.header import decode_header
from email.parser import BytesParser
from email.policy import compat32

from pypdf import PdfReader


def read_text(raw):
    if b'\0' in raw[:4096]:
        raise ValueError('binary data where text was expected')
    for enc in ('utf-8-sig', 'cp1252', 'latin-1'):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    lines = text.split('\n')
    if lines and lines[-1] == '':
        lines = lines[:-1]
    return {'encoding': enc, 'final_newline': text.endswith('\n'),
            'lines': {str(i + 1): ln.rstrip('\r') for i, ln in enumerate(lines)}}


def read_pdf(path):
    reader = PdfReader(path)
    pages = {}
    for i, page in enumerate(reader.pages, 1):
        text = re.sub(r'\s+', ' ', page.extract_text() or '').strip()
        try:
            n_images = len(list(page.images))
        except Exception:  # image listing is optional in pypdf for some encodings
            n_images = None
        pages[str(i)] = {'text': text, 'image_count': n_images}
    return {'page_count': len(reader.pages), 'pages': pages}


_RENDER_CACHE = {}


def render_pages(path, stamp):
    """Rendered pages of a word-processing file: [(text, image_count)] per page.

    The owning app's own layout: LibreOffice converts the saved file to PDF and pypdf reads each page. Same method
    as specexec._render_pdf. Cached per (path, stamp) so a file is rendered once per state."""
    key = (path, stamp)
    if key not in _RENDER_CACHE:
        tmp = tempfile.mkdtemp(prefix='ur_render_')
        subprocess.run(['soffice', '--headless', '--convert-to', 'pdf', '--outdir', tmp, path],
                       check=True, capture_output=True, timeout=180)
        pdf = os.path.join(tmp, os.path.splitext(os.path.basename(path))[0] + '.pdf')
        pages = []
        for page in PdfReader(pdf).pages:
            text = re.sub(r'\s+', ' ', page.extract_text() or '').strip()
            pages.append((text, len(list(page.images))))
        shutil.rmtree(tmp, ignore_errors=True)
        _RENDER_CACHE[key] = pages
    return _RENDER_CACHE[key]


def read_sqlite(path):
    con = sqlite3.connect(f'file:{path}?mode=ro&immutable=1', uri=True)
    try:
        tables, failed = {}, []
        # FTS virtual tables cannot be queried without their tokenizer (Thunderbird uses 'mozporter').
        # Their content is in plain shadow tables, which are read instead; the virtual table itself is listed.
        rows_meta = con.execute("select name, sql from sqlite_master where type='table' order by name").fetchall()
        virtual = sorted(n for n, sql in rows_meta if sql and sql.upper().startswith('CREATE VIRTUAL TABLE'))
        names = [n for n, sql in rows_meta if not (sql and sql.upper().startswith('CREATE VIRTUAL TABLE'))]
        for name in names:
            try:
                cols = [r[1] for r in con.execute(f'pragma table_info("{name}")')]
                count = con.execute(f'select count(*) from "{name}"').fetchone()[0]
                rows = {}
                if count <= 5000:
                    for i, row in enumerate(con.execute(f'select * from "{name}"'), 1):
                        rows[str(i)] = {c: (v if not isinstance(v, bytes) else hashlib.sha256(v).hexdigest())
                                        for c, v in zip(cols, row)}
            except sqlite3.OperationalError as e:
                failed.append(f'{name}: {e}')
                continue
            tables[name] = {'columns': cols, 'row_count': count, 'rows': rows}
        if failed:  # a partly read database is not a readable state: fail closed
            raise ValueError('tables not readable: ' + '; '.join(failed))
        return {'tables': tables, 'virtual_tables': virtual}
    finally:
        con.close()


def read_mozlz4(path):
    import lz4.block
    with open(path, 'rb') as fh:
        raw = fh.read()
    size = int.from_bytes(raw[8:12], 'little')
    data = lz4.block.decompress(raw[12:], uncompressed_size=size)
    return {'value': json.loads(data.decode('utf-8'))}


def read_archive(path, kind):
    members = {}
    if kind == 'zip':
        with zipfile.ZipFile(path) as z:
            for info in z.infolist():
                members[info.filename] = {'size': info.file_size, 'is_dir': info.is_dir()}
    else:
        with tarfile.open(path) as t:
            for m in t.getmembers():
                members[m.name] = {'size': m.size, 'is_dir': m.isdir(), 'mode': oct(m.mode & 0o7777)}
    return {'archive': kind, 'members': dict(sorted(members.items()))}


def read_media(path):
    """Container metadata from ffprobe (the decoder is not used; frames need ffmpeg and are not read here)."""
    try:
        out = subprocess.run(['ffprobe', '-v', 'error', '-print_format', 'json', '-show_format', '-show_streams', path],
                             capture_output=True, timeout=60, check=True).stdout
    except (OSError, subprocess.SubprocessError) as e:
        raise ValueError(f'ffprobe failed: {e}')
    info = json.loads(out)
    streams = {str(i + 1): {k: s.get(k) for k in ('codec_type', 'codec_name', 'width', 'height', 'duration')}
               for i, s in enumerate(info.get('streams', []))}
    fmt = info.get('format', {})
    return {'format_name': fmt.get('format_name'), 'duration': fmt.get('duration'), 'streams': streams}


def _decode_part(part):
    payload = part.get_payload(decode=True) or b''
    return payload


_HEADER_NAME = re.compile(rb'^[!-9;-~]+:')


def _repair_headers(raw):
    """Join header lines that have no field name to the header above them (a malformed fold, as in a From line
    split over two lines). Python's email parser would end the header block at such a line and lose Subject and
    To; Thunderbird reads them. Returns (bytes, number of lines joined). Only the header block is touched."""
    out, joined, in_head = [], 0, True
    for ln in raw.split(b'\n'):
        if in_head and ln.strip(b'\r ') == b'':
            in_head = False
        elif in_head and out and ln[:1] not in (b' ', b'\t') and not _HEADER_NAME.match(ln):
            out[-1] = out[-1].rstrip(b'\r') + b' ' + ln.strip()
            joined += 1
            continue
        out.append(ln)
    return b'\n'.join(out), joined


def _plain(value):
    """A header value as written: RFC 2047 words decoded, folds unfolded, nothing re-formatted (no address
    normalisation, so a comment such as '(formerly Twitter)' in From stays)."""
    if value is None:
        return ''
    parts = []
    for text, enc in decode_header(str(value)):
        parts.append(text.decode(enc or 'utf-8', 'replace') if isinstance(text, bytes) else text)
    return ' '.join(''.join(parts).split())


def read_mbox(path):
    """Messages of a Thunderbird mbox folder. Flags come from X-Mozilla-Status (0x0001 read, 0x0004 flagged)."""
    box = mailbox.mbox(path, create=False)
    messages = {}
    for i, key in enumerate(box.keys(), 1):
        raw, joined = _repair_headers(box.get_bytes(key))
        msg = BytesParser(policy=policy.default).parsebytes(raw)
        hdr = BytesParser(policy=compat32).parsebytes(raw)
        status = int(str(hdr.get('X-Mozilla-Status', '0')).strip() or '0', 16)
        body_parts, attachments = [], {}
        for part in msg.walk():
            if part.is_multipart():
                continue
            disp = (part.get_content_disposition() or '')
            fname = part.get_filename()
            if disp == 'attachment' or fname:
                payload = _decode_part(part)
                attachments[str(len(attachments) + 1)] = {'name': fname, 'sha256': hashlib.sha256(payload).hexdigest(),
                                                          'size': len(payload), 'content_type': part.get_content_type()}
            elif part.get_content_type() == 'text/plain':
                try:
                    body_parts.append(part.get_content())
                except (LookupError, UnicodeDecodeError, KeyError):
                    body_parts.append(_decode_part(part).decode('utf-8', 'replace'))
        messages[str(i)] = {'subject': _plain(hdr.get('Subject')), 'from': _plain(hdr.get('From')),
                            'to': _plain(hdr.get('To')), 'cc': _plain(hdr.get('Cc')), 'bcc': _plain(hdr.get('Bcc')),
                            'date': _plain(hdr.get('Date')), 'message_id': _plain(hdr.get('Message-ID')),
                            'read': bool(status & 0x0001), 'flagged': bool(status & 0x0004),
                            'tags': str(hdr.get('X-Mozilla-Keys', '')).strip(), 'body': '\n'.join(body_parts),
                            'attachments': attachments, 'header_lines_joined': joined}
    box.close()
    return {'message_count': len(messages), 'messages': messages}


def mbox_like(path, raw_head):
    """True for an mbox file: a Thunderbird folder file whose first line is a 'From ' separator."""
    return raw_head.startswith(b'From ')
