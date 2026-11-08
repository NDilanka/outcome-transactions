// Webmail stub for the browser probe. Node 24, no dependencies.
//
// Ours, not a real webmail product. Mailpit is the local mail server: it
// receives mail over SMTP and keeps it. This stub is the browser-facing
// client on top of it: an inbox, reading, compose, reply, drafts, folders,
// contacts and settings. It keeps the server behaviour that matters for held
// requests:
//   - a login session; a CSRF token on every unsafe form
//   - a draft save with a version field (409 on a stale save)
//   - sending by real SMTP to Mailpit (the send is an effect, not a mock)
//   - a GET that changes state: opening a message marks it read, and so does
//     opening the reply form, as IMAP-backed webmail does with the \Seen flag
//   - settings with a version field (409 on a stale save)
// Not included: IMAP, attachments, HTML mail, spam filtering, filters, push.
//
// Usage:
//   node webmail.mjs --seed    reset the webmail database, create the account,
//                              and deliver three inbox messages to Mailpit
//                              (Mailpit must be running on SMTP_PORT and MAILPIT_API)
//   node webmail.mjs           serve on WEBMAIL_PORT (default 8201)

import http from 'node:http';
import net from 'node:net';
import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import { DatabaseSync } from 'node:sqlite';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const PORT = Number(process.env.WEBMAIL_PORT || 8201);
const DB_FILE = process.env.WEBMAIL_DB || path.join(HERE, 'data', 'webmail.db');
const SECRETS_FILE = process.env.PROBE_SECRETS || path.join(HERE, '..', '..', 'state', 'secrets.json');
const LOG_FILE = process.env.WEBMAIL_LOG || path.join(HERE, 'logs', 'webmail-app.jsonl');
const MAILPIT_API = process.env.MAILPIT_API || 'http://127.0.0.1:8025';
const SMTP_HOST = process.env.SMTP_HOST || '127.0.0.1';
const SMTP_PORT = Number(process.env.SMTP_PORT || 1025);
const ACCOUNT = 'alex@local.test';
const MAX_BODY = 64 * 1024;

const now = () => new Date().toISOString();
const rand = (n = 16) => crypto.randomBytes(n).toString('hex');
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);

class HttpError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}

function applog(event, data = {}) {
  fs.mkdirSync(path.dirname(LOG_FILE), { recursive: true });
  fs.appendFileSync(LOG_FILE, JSON.stringify({ ts: now(), event, ...data }) + '\n');
}

const SCHEMA = `
CREATE TABLE IF NOT EXISTS account (
  id INTEGER PRIMARY KEY, email TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL,
  display_name TEXT NOT NULL, settings_version INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS sessions (
  id TEXT PRIMARY KEY, logged_in INTEGER NOT NULL DEFAULT 0, csrf TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS folders (
  id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL);
CREATE TABLE IF NOT EXISTS message_meta (
  message_id TEXT PRIMARY KEY, folder TEXT NOT NULL DEFAULT 'inbox', seen INTEGER NOT NULL DEFAULT 0,
  version INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS drafts (
  id INTEGER PRIMARY KEY AUTOINCREMENT, to_addr TEXT NOT NULL, subject TEXT NOT NULL,
  body TEXT NOT NULL, version INTEGER NOT NULL DEFAULT 1, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS contacts (
  id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, email TEXT UNIQUE NOT NULL);
CREATE TABLE IF NOT EXISTS effects (
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT NULL, kind TEXT NOT NULL,
  ref TEXT NOT NULL, detail TEXT NOT NULL DEFAULT '');
`;

function openDb(file = DB_FILE) {
  fs.mkdirSync(path.dirname(file), { recursive: true });
  const db = new DatabaseSync(file);
  db.exec('PRAGMA journal_mode = DELETE; PRAGMA busy_timeout = 5000;');
  db.exec(SCHEMA);
  return db;
}

function effect(db, kind, ref, detail = '') {
  db.prepare('INSERT INTO effects (ts, kind, ref, detail) VALUES (?, ?, ?, ?)').run(now(), kind, ref, detail);
}

function tx(db, fn) {
  db.exec('BEGIN IMMEDIATE');
  try {
    const out = fn();
    db.exec('COMMIT');
    return out;
  } catch (err) {
    db.exec('ROLLBACK');
    throw err;
  }
}

function hashPassword(pw) {
  const salt = crypto.randomBytes(16).toString('hex');
  return `scrypt$${salt}$${crypto.scryptSync(pw, salt, 32).toString('hex')}`;
}

function checkPassword(pw, stored) {
  const [, salt, hash] = stored.split('$');
  const candidate = crypto.scryptSync(pw, salt, 32);
  const expected = Buffer.from(hash, 'hex');
  return candidate.length === expected.length && crypto.timingSafeEqual(candidate, expected);
}

// Resets the webmail database and puts three inbox messages into Mailpit.
// Run it after Mailpit has started with an empty store.
async function seed() {
  fs.mkdirSync(path.dirname(SECRETS_FILE), { recursive: true });
  const secrets = fs.existsSync(SECRETS_FILE) ? JSON.parse(fs.readFileSync(SECRETS_FILE, 'utf8')) : {};
  secrets.mail = secrets.mail || { email: ACCOUNT, password: rand(12) };
  fs.writeFileSync(SECRETS_FILE, JSON.stringify(secrets, null, 2));
  if (fs.existsSync(DB_FILE)) fs.rmSync(DB_FILE);
  const db = openDb(DB_FILE);
  db.prepare('INSERT INTO account (email, password_hash, display_name) VALUES (?, ?, ?)')
    .run(ACCOUNT, hashPassword(secrets.mail.password), 'Alex Reed');
  db.prepare('INSERT INTO contacts (name, email) VALUES (?, ?)').run('Bob Ng', 'bob@example.test');
  db.prepare('INSERT INTO drafts (to_addr, subject, body, updated_at) VALUES (?, ?, ?, ?)')
    .run('bob@example.test', 'Agenda', 'Hi Bob,\n\nAgenda for Thursday:\n1. Budget\n2. Hiring\n', now());
  db.close();
  const inbox = [
    ['Bob Ng', 'bob@example.test', 'Thursday agenda', 'Hi Alex,\n\nCan we add a hiring item to Thursday?\n\nBob'],
    ['Priya Shah', 'priya@example.test', 'Invoice 4411', 'Hello,\n\nThe invoice for March is attached to our portal.\n\nPriya'],
    ['Team Calendar', 'calendar@example.test', 'Room booked: Blue', 'Blue room is booked for Thursday 10:00.'],
  ];
  for (const [name, addr, subject, body] of inbox) {
    await smtpSend({ fromName: name, fromAddress: addr, to: ACCOUNT, subject, body });
  }
  console.log('webmail: database seeded and three inbox messages delivered; account secret written to the state folder (not printed)');
}

// ---------- Mailpit (local mail server) ----------

async function mailpit(method, p, body) {
  const res = await fetch(MAILPIT_API + p, {
    method,
    headers: body ? { 'content-type': 'application/json' } : {},
    body: body ? JSON.stringify(body) : undefined,
  });
  applog('mailpit_call', { method, path: p, status: res.status });
  if (res.status === 404) throw new HttpError(404, 'That message no longer exists.');
  if (!res.ok) throw new HttpError(502, `The mail server returned an error (${res.status}).`);
  return res.status === 204 ? null : res.json();
}

// Minimal SMTP client for the local mail server: one message, no TLS, no
// auth. A reply ends at the first line of the form "NNN " (code, space).
function smtpSend({ fromName, fromAddress, to, subject, body, host = SMTP_HOST, port = SMTP_PORT }) {
  for (const v of [fromName, fromAddress, to, subject]) {
    if (/[\r\n]/.test(v)) return Promise.reject(new HttpError(422, 'Header values must be one line.'));
  }
  const encodedSubject = /^[\x20-\x7e]*$/.test(subject)
    ? subject
    : `=?UTF-8?B?${Buffer.from(subject, 'utf8').toString('base64')}?=`;
  const text = body.replace(/\r?\n$/, '').replace(/\r?\n/g, '\r\n');
  const data = [
    `From: ${fromName} <${fromAddress}>`,
    `To: ${to}`,
    `Subject: ${encodedSubject}`,
    `Date: ${new Date().toUTCString()}`,
    `Message-ID: <${rand(12)}@webmail.local.test>`,
    'MIME-Version: 1.0',
    'Content-Type: text/plain; charset=utf-8',
    'Content-Transfer-Encoding: 8bit',
    '',
    ...text.split('\r\n').map((l) => (l.startsWith('.') ? '.' + l : l)),
  ].join('\r\n') + '\r\n.\r\n';

  return new Promise((resolve, reject) => {
    const sock = net.createConnection({ host, port });
    sock.setTimeout(8000);
    let buf = '';
    let lines = [];
    const replies = [];
    let waiter = null;
    let done = false;

    const finish = (err) => {
      if (done) return;
      done = true;
      sock.destroy();
      if (err) reject(err);
      else resolve();
    };
    const pump = () => {
      if (waiter && replies.length) {
        const w = waiter;
        waiter = null;
        w(replies.shift());
      }
    };
    const nextReply = () => new Promise((res) => {
      waiter = res;
      pump();
    });
    const checkCode = (reply, code) => {
      const got = Number(reply[reply.length - 1].slice(0, 3));
      if (got !== code) throw new HttpError(502, `The mail server refused the message (${got}).`);
    };
    const command = async (line, code) => {
      sock.write(line + '\r\n');
      checkCode(await nextReply(), code);
    };

    sock.on('data', (chunk) => {
      buf += chunk.toString('utf8');
      let i;
      while ((i = buf.indexOf('\r\n')) !== -1) {
        const line = buf.slice(0, i);
        buf = buf.slice(i + 2);
        lines.push(line);
        if (/^\d{3} /.test(line)) {
          replies.push(lines);
          lines = [];
        }
      }
      pump();
    });
    sock.on('timeout', () => finish(new HttpError(504, 'The mail server did not answer in time. The message was not sent.')));
    sock.on('error', () => finish(new HttpError(502, 'The mail server is not reachable. The message was not sent.')));
    sock.on('close', () => finish(new HttpError(502, 'The mail server closed the connection. The message was not sent.')));

    (async () => {
      checkCode(await nextReply(), 220);
      await command('EHLO webmail.local.test', 250);
      await command(`MAIL FROM:<${fromAddress}>`, 250);
      await command(`RCPT TO:<${to}>`, 250);
      await command('DATA', 354);
      sock.write(data);
      checkCode(await nextReply(), 250);
      await command('QUIT', 221);
      finish();
    })().catch(finish);
  });
}

// ---------- sessions and HTTP helpers ----------

function parseCookies(req) {
  const out = {};
  for (const part of (req.headers.cookie || '').split(';')) {
    const i = part.indexOf('=');
    if (i > 0) out[part.slice(0, i).trim()] = part.slice(i + 1).trim();
  }
  return out;
}

function loadSession(db, req) {
  const sid = parseCookies(req).sid;
  if (!sid) return null;
  const row = db.prepare('SELECT id, logged_in, csrf FROM sessions WHERE id = ?').get(sid);
  if (!row) return null;
  return { sid: row.id, csrf: row.csrf, loggedIn: !!row.logged_in };
}

function requireLogin(sess) {
  if (!sess?.loggedIn) throw new HttpError(401, 'Log in first.');
}

function checkCsrf(form, sess) {
  if (!sess || !form.csrf || form.csrf !== sess.csrf) throw new HttpError(403, 'Your form expired. Reload the page and try again.');
}

function readBody(req) {
  return new Promise((resolve, reject) => {
    let size = 0;
    const chunks = [];
    req.on('data', (c) => {
      size += c.length;
      if (size > MAX_BODY) {
        req.destroy();
        reject(new HttpError(413, 'Request too large.'));
        return;
      }
      chunks.push(c);
    });
    req.on('end', () => resolve(Buffer.concat(chunks).toString('utf8')));
    req.on('error', reject);
  });
}

function sendHtml(res, status, title, body, sess, headers = {}) {
  const nav = sess?.loggedIn
    ? `<nav><a href="/">Inbox</a> <a href="/compose">Compose</a> <a href="/drafts">Drafts</a> <a href="/contacts">Contacts</a> <a href="/settings">Settings</a>
       <form method="post" action="/logout"><input type="hidden" name="csrf" value="${esc(sess.csrf)}"><button type="submit">Log out</button></form></nav>`
    : '<nav><a href="/login">Log in</a></nav>';
  const page = `<!doctype html><html lang="en"><head><meta charset="utf-8"><title>${esc(title)} | Webmail</title></head><body>${nav}<main>${body}</main></body></html>`;
  res.writeHead(status, { 'content-type': 'text/html; charset=utf-8', ...headers });
  res.end(page);
}

function redirect(res, location, headers = {}) {
  res.writeHead(303, { location, ...headers });
  res.end();
}

function metaOf(db, id) {
  return db.prepare('SELECT folder, seen, version FROM message_meta WHERE message_id = ?').get(id) ?? { folder: 'inbox', seen: 0, version: 1 };
}

function setMeta(db, id, patch) {
  const m = metaOf(db, id);
  const next = { ...m, ...patch };
  db.prepare(`INSERT INTO message_meta (message_id, folder, seen, version) VALUES (?, ?, ?, ?)
    ON CONFLICT (message_id) DO UPDATE SET folder = excluded.folder, seen = excluded.seen, version = version + 1`)
    .run(id, next.folder, next.seen, 1);
}

function folderName(db, folder) {
  if (folder === 'inbox' || folder === 'archive' || folder === 'trash' || folder === 'sent') return folder;
  const row = db.prepare('SELECT name FROM folders WHERE id = ?').get(Number(folder.replace(/^f:/, '')));
  return row ? row.name : null;
}

const routes = [];
const route = (method, pattern, handler) => routes.push({ method, pattern, handler });

route('GET', /^\/login$/, ({ db, sess, res }) => {
  let current = sess;
  let headers = {};
  if (!current) {
    const sid = rand(16);
    const csrf = rand(16);
    db.prepare('INSERT INTO sessions (id, logged_in, csrf, created_at) VALUES (?, 0, ?, ?)').run(sid, csrf, now());
    current = { sid, csrf, loggedIn: false };
    headers = { 'set-cookie': `sid=${sid}; Path=/; HttpOnly; SameSite=Lax` };
  }
  sendHtml(res, 200, 'Log in', `
    <h1>Log in</h1>
    <form method="post" action="/login">
      <input type="hidden" name="csrf" value="${esc(current.csrf)}">
      <label>Email <input name="email" type="email" value="${ACCOUNT}"></label>
      <label>Password <input name="password" type="password"></label>
      <button type="submit">Log in</button>
    </form>`, current, headers);
});

route('POST', /^\/login$/, ({ db, sess, form, res }) => {
  checkCsrf(form, sess);
  const acct = db.prepare('SELECT password_hash FROM account WHERE email = ?').get(String(form.email ?? ''));
  if (!acct || !checkPassword(String(form.password ?? ''), acct.password_hash)) throw new HttpError(422, 'Email or password is wrong.');
  // Rotate the session id and the CSRF token at login.
  const newSid = rand(16);
  db.prepare('UPDATE sessions SET id = ?, logged_in = 1, csrf = ? WHERE id = ?').run(newSid, rand(16), sess.sid);
  redirect(res, '/', { 'set-cookie': `sid=${newSid}; Path=/; HttpOnly; SameSite=Lax` });
});

route('POST', /^\/logout$/, ({ db, sess, form, res }) => {
  checkCsrf(form, sess);
  db.prepare('DELETE FROM sessions WHERE id = ?').run(sess.sid);
  redirect(res, '/login', { 'set-cookie': 'sid=; Path=/; Max-Age=0; HttpOnly; SameSite=Lax' });
});

route('GET', /^\/$/, async ({ db, sess, res, url }) => {
  requireLogin(sess);
  const folder = url.searchParams.get('folder') || 'inbox';
  const name = folderName(db, folder);
  if (!name) throw new HttpError(404, 'No such folder.');
  const list = await mailpit('GET', '/api/v1/messages?limit=200');
  const rows = [];
  for (const m of list.messages || []) {
    // Mail sent from this account goes to Sent; everything else is received mail.
    const isSent = m.From?.Address === ACCOUNT;
    const meta = metaOf(db, m.ID);
    if (folder === 'sent' ? !isSent : isSent || meta.folder !== folder) continue;
    const from = m.From ? `${m.From.Name ? m.From.Name + ' ' : ''}<${m.From.Address}>` : '';
    rows.push(`<tr class="${meta.seen ? 'read' : 'unread'}"><td>${esc(from)}</td><td><a href="/message/${esc(m.ID)}">${esc(m.Subject || '(no subject)')}</a></td><td>${esc(m.Created)}</td></tr>`);
  }
  const folders = db.prepare('SELECT id, name FROM folders ORDER BY name').all()
    .map((f) => `<a href="/?folder=f:${f.id}">${esc(f.name)}</a>`).join(' ');
  sendHtml(res, 200, name, `
    <h1>${esc(name)}</h1>
    <p><a href="/?folder=inbox">Inbox</a> <a href="/?folder=sent">Sent</a> <a href="/?folder=archive">Archive</a> <a href="/?folder=trash">Trash</a> ${folders}</p>
    <table><tr><th>From</th><th>Subject</th><th>Received</th></tr>${rows.join('')}</table>
    <form method="post" action="/folders">
      <input type="hidden" name="csrf" value="${esc(sess.csrf)}">
      <label>New folder <input name="name" type="text" maxlength="30"></label>
      <button type="submit">Create folder</button>
    </form>
    ${folder === 'trash' ? `<form method="post" action="/trash/empty"><input type="hidden" name="csrf" value="${esc(sess.csrf)}"><button type="submit">Empty trash</button></form>` : ''}`, sess);
});

// Opening a message marks it read in the mail server and in this webmail. A
// state-changing GET, as with IMAP's \Seen flag.
route('GET', /^\/message\/([^/]+)$/, async ({ db, sess, res, params }) => {
  requireLogin(sess);
  const id = params[1];
  const m = await mailpit('GET', `/api/v1/message/${encodeURIComponent(id)}`);
  setMeta(db, id, { seen: 1 });
  const folder = metaOf(db, id).folder;
  const from = m.From ? `${m.From.Name ? m.From.Name + ' ' : ''}<${m.From.Address}>` : '';
  const to = (m.To || []).map((a) => a.Address).join(', ');
  const folderOptions = db.prepare('SELECT id, name FROM folders ORDER BY name').all()
    .map((f) => `<option value="f:${f.id}">${esc(f.name)}</option>`).join('');
  sendHtml(res, 200, m.Subject || 'Message', `
    <h1>${esc(m.Subject || '(no subject)')}</h1>
    <p>From ${esc(from)} to ${esc(to)} · in ${esc(folder)}</p>
    <pre>${esc(m.Text || '')}</pre>
    <p><a href="/compose?reply=${esc(id)}">Reply</a></p>
    <form method="post" action="/message/${esc(id)}/unread"><input type="hidden" name="csrf" value="${esc(sess.csrf)}"><button type="submit">Mark as unread</button></form>
    <form method="post" action="/message/${esc(id)}/archive"><input type="hidden" name="csrf" value="${esc(sess.csrf)}"><button type="submit">Archive</button></form>
    <form method="post" action="/message/${esc(id)}/trash"><input type="hidden" name="csrf" value="${esc(sess.csrf)}"><button type="submit">Delete</button></form>
    <form method="post" action="/message/${esc(id)}/move"><input type="hidden" name="csrf" value="${esc(sess.csrf)}">
      <label>Move to <select name="folder_id">${folderOptions}</select></label><button type="submit">Move</button></form>`, sess);
});

for (const [action, patch] of [
  ['unread', { seen: 0 }],
  ['archive', { folder: 'archive' }],
  ['trash', { folder: 'trash' }],
]) {
  route('POST', new RegExp(`^/message/([^/]+)/${action}$`), ({ db, sess, form, res, params }) => {
    requireLogin(sess);
    checkCsrf(form, sess);
    tx(db, () => {
      setMeta(db, params[1], patch);
      effect(db, `mail.${action}`, `message:${params[1]}`);
    });
    redirect(res, '/');
  });
}

route('POST', /^\/message\/([^/]+)\/move$/, ({ db, sess, form, res, params }) => {
  requireLogin(sess);
  checkCsrf(form, sess);
  const target = String(form.folder_id || '');
  if (!folderName(db, target)) throw new HttpError(422, 'Choose a folder.');
  tx(db, () => {
    setMeta(db, params[1], { folder: target });
    effect(db, 'mail.move', `message:${params[1]}`, target);
  });
  redirect(res, '/');
});

// Compose page. Opening a reply reads the original, which marks it read.
route('GET', /^\/compose$/, async ({ db, sess, res, url }) => {
  requireLogin(sess);
  let to = '';
  let subject = '';
  let body = '';
  let draftId = '';
  let draftVersion = '';
  const replyId = url.searchParams.get('reply');
  const draftParam = url.searchParams.get('draft');
  if (replyId) {
    const m = await mailpit('GET', `/api/v1/message/${encodeURIComponent(replyId)}`);
    setMeta(db, replyId, { seen: 1 });
    to = m.From?.Address || '';
    subject = /^re:/i.test(m.Subject || '') ? m.Subject : `Re: ${m.Subject || ''}`;
    body = `\n\nOn ${m.Created}, ${to} wrote:\n> ${String(m.Text || '').split('\n').join('\n> ')}`;
  } else if (draftParam) {
    const d = db.prepare('SELECT * FROM drafts WHERE id = ?').get(Number(draftParam));
    if (!d) throw new HttpError(404, 'Draft not found.');
    to = d.to_addr;
    subject = d.subject;
    body = d.body;
    draftId = String(d.id);
    draftVersion = String(d.version);
  }
  sendHtml(res, 200, 'Compose', `
    <h1>Compose</h1>
    <form method="post" action="/compose/send">
      <input type="hidden" name="csrf" value="${esc(sess.csrf)}">
      <input type="hidden" name="draft_id" value="${esc(draftId)}">
      <input type="hidden" name="draft_version" value="${esc(draftVersion)}">
      <label>To <input name="to" type="email" value="${esc(to)}"></label>
      <label>Subject <input name="subject" type="text" value="${esc(subject)}"></label>
      <label>Message <textarea name="body" rows="8">${esc(body)}</textarea></label>
      <button type="submit">Send</button>
    </form>
    <form method="post" action="/compose/draft">
      <input type="hidden" name="csrf" value="${esc(sess.csrf)}">
      <input type="hidden" name="draft_id" value="${esc(draftId)}">
      <input type="hidden" name="draft_version" value="${esc(draftVersion)}">
      <input type="hidden" name="to" value="${esc(to)}">
      <input type="hidden" name="subject" value="${esc(subject)}">
      <input type="hidden" name="body" value="${esc(body)}">
      <button type="submit">Save draft</button>
    </form>`, sess);
});

route('POST', /^\/compose\/draft$/, ({ db, sess, form, res }) => {
  requireLogin(sess);
  checkCsrf(form, sess);
  const to = String(form.to ?? '').trim();
  const subject = String(form.subject ?? '').trim();
  const body = String(form.body ?? '');
  let id;
  tx(db, () => {
    if (form.draft_id) {
      id = Number(form.draft_id);
      const r = db.prepare('UPDATE drafts SET to_addr = ?, subject = ?, body = ?, version = version + 1, updated_at = ? WHERE id = ? AND version = ?')
        .run(to, subject, body, now(), id, Number(form.draft_version));
      if (r.changes === 0) throw new HttpError(409, 'This draft was saved in another window. Reload it and try again.');
      effect(db, 'draft.update', `draft:${id}`);
    } else {
      const r = db.prepare('INSERT INTO drafts (to_addr, subject, body, updated_at) VALUES (?, ?, ?, ?)').run(to, subject, body, now());
      id = Number(r.lastInsertRowid);
      effect(db, 'draft.create', `draft:${id}`);
    }
  });
  redirect(res, `/compose?draft=${id}`);
});

route('POST', /^\/compose\/send$/, async ({ db, sess, form, res }) => {
  requireLogin(sess);
  checkCsrf(form, sess);
  const to = String(form.to ?? '').trim();
  const subject = String(form.subject ?? '').trim();
  const body = String(form.body ?? '');
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(to)) throw new HttpError(422, 'Enter one valid recipient address.');
  if (!subject) throw new HttpError(422, 'Add a subject.');
  if (/[\r\n]/.test(subject)) throw new HttpError(422, 'The subject must be one line.');
  const acct = db.prepare('SELECT display_name FROM account WHERE email = ?').get(ACCOUNT);
  await smtpSend({ fromName: acct.display_name, fromAddress: ACCOUNT, to, subject, body });
  tx(db, () => {
    if (form.draft_id) db.prepare('DELETE FROM drafts WHERE id = ?').run(Number(form.draft_id));
    effect(db, 'mail.send', `to:${to}`, subject);
  });
  applog('smtp_sent', { to_domain: to.split('@')[1] });
  redirect(res, '/?folder=inbox');
});

route('GET', /^\/drafts$/, ({ db, sess, res }) => {
  requireLogin(sess);
  const rows = db.prepare('SELECT id, to_addr, subject, updated_at FROM drafts ORDER BY id').all()
    .map((d) => `<tr><td><a href="/compose?draft=${d.id}">${esc(d.subject)}</a></td><td>${esc(d.to_addr)}</td><td>${esc(d.updated_at)}</td></tr>`).join('');
  sendHtml(res, 200, 'Drafts', `<h1>Drafts</h1><table><tr><th>Subject</th><th>To</th><th>Saved</th></tr>${rows}</table>`, sess);
});

route('GET', /^\/contacts$/, ({ db, sess, res }) => {
  requireLogin(sess);
  const rows = db.prepare('SELECT name, email FROM contacts ORDER BY name').all()
    .map((c) => `<tr><td>${esc(c.name)}</td><td>${esc(c.email)}</td></tr>`).join('');
  sendHtml(res, 200, 'Contacts', `
    <h1>Contacts</h1>
    <table><tr><th>Name</th><th>Email</th></tr>${rows}</table>
    <form method="post" action="/contacts">
      <input type="hidden" name="csrf" value="${esc(sess.csrf)}">
      <label>Name <input name="name" type="text"></label>
      <label>Email <input name="email" type="email"></label>
      <button type="submit">Add contact</button>
    </form>`, sess);
});

route('POST', /^\/contacts$/, ({ db, sess, form, res }) => {
  requireLogin(sess);
  checkCsrf(form, sess);
  const name = String(form.name ?? '').trim();
  const email = String(form.email ?? '').trim();
  if (!name) throw new HttpError(422, 'Name is required.');
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) throw new HttpError(422, 'Enter a valid email address.');
  tx(db, () => {
    if (db.prepare('SELECT 1 FROM contacts WHERE email = ?').get(email)) throw new HttpError(422, 'That contact already exists.');
    db.prepare('INSERT INTO contacts (name, email) VALUES (?, ?)').run(name, email);
    effect(db, 'contact.create', `contact:${email}`);
  });
  redirect(res, '/contacts');
});

route('POST', /^\/folders$/, ({ db, sess, form, res }) => {
  requireLogin(sess);
  checkCsrf(form, sess);
  const name = String(form.name ?? '').trim();
  if (!/^[A-Za-z0-9 ]{1,30}$/.test(name)) throw new HttpError(422, 'Folder names use letters, digits and spaces, up to 30 characters.');
  tx(db, () => {
    if (db.prepare('SELECT 1 FROM folders WHERE name = ?').get(name)) throw new HttpError(422, 'A folder with that name exists.');
    const r = db.prepare('INSERT INTO folders (name) VALUES (?)').run(name);
    effect(db, 'folder.create', `folder:${r.lastInsertRowid}`, name);
  });
  redirect(res, '/');
});

route('GET', /^\/settings$/, ({ db, sess, res }) => {
  requireLogin(sess);
  const a = db.prepare('SELECT display_name, settings_version FROM account WHERE email = ?').get(ACCOUNT);
  sendHtml(res, 200, 'Settings', `
    <h1>Settings</h1>
    <form method="post" action="/settings">
      <input type="hidden" name="csrf" value="${esc(sess.csrf)}">
      <input type="hidden" name="settings_version" value="${a.settings_version}">
      <label>Display name <input name="display_name" type="text" value="${esc(a.display_name)}"></label>
      <button type="submit">Save settings</button>
    </form>`, sess);
});

route('POST', /^\/settings$/, ({ db, sess, form, res }) => {
  requireLogin(sess);
  checkCsrf(form, sess);
  const name = String(form.display_name ?? '').trim();
  if (!name || name.length > 60) throw new HttpError(422, 'Display name is required, up to 60 characters.');
  tx(db, () => {
    const r = db.prepare('UPDATE account SET display_name = ?, settings_version = settings_version + 1 WHERE email = ? AND settings_version = ?')
      .run(name, ACCOUNT, Number(form.settings_version));
    if (r.changes === 0) throw new HttpError(409, 'Your settings changed in another window. Reload and try again.');
    effect(db, 'settings.update', `account:${ACCOUNT}`, name);
  });
  redirect(res, '/settings');
});

route('POST', /^\/trash\/empty$/, async ({ db, sess, form, res }) => {
  requireLogin(sess);
  checkCsrf(form, sess);
  const ids = db.prepare("SELECT message_id FROM message_meta WHERE folder = 'trash'").all().map((r) => r.message_id);
  if (ids.length) {
    await mailpit('DELETE', '/api/v1/messages', { IDs: ids });
    tx(db, () => {
      db.prepare("DELETE FROM message_meta WHERE folder = 'trash'").run();
      effect(db, 'mail.delete', `messages:${ids.length}`);
    });
  }
  redirect(res, '/?folder=trash');
});

// ---------- server ----------

function matchRoute(method, pathname) {
  let pathMatched = false;
  for (const r of routes) {
    const m = pathname.match(r.pattern);
    if (!m) continue;
    pathMatched = true;
    if (r.method === method) return { route: r, params: m };
  }
  return { route: null, pathMatched };
}

async function handle(req, res) {
  const url = new URL(req.url, 'http://127.0.0.1');
  const db = openDb(DB_FILE);
  try {
    const raw = req.method === 'GET' ? '' : await readBody(req);
    const form = Object.fromEntries(new URLSearchParams(raw).entries());
    const sess = loadSession(db, req);
    const m = matchRoute(req.method, url.pathname);
    if (!m.route) throw new HttpError(m.pathMatched ? 405 : 404, m.pathMatched ? 'Method not allowed.' : 'Page not found.');
    await m.route.handler({ db, sess, req, res, url, form, params: m.params });
  } catch (err) {
    const status = err instanceof HttpError ? err.status : 500;
    if (status === 500) console.error(err);
    if (res.headersSent) return;
    if (err instanceof HttpError && status === 401) {
      redirect(res, '/login');
      return;
    }
    const message = err instanceof HttpError ? err.message : 'Something went wrong.';
    sendHtml(res, status, 'Error', `<h1>${esc(message)}</h1><p><a href="/">Back to the inbox</a></p>`, null);
  } finally {
    db.close();
  }
}

// Run the server or the seed only when this file is the entry point, so tests
// can import smtpSend.
const isMain = path.resolve(process.argv[1] || '') === fileURLToPath(import.meta.url);
if (isMain && process.argv.includes('--seed')) {
  seed().catch((err) => {
    console.error(err.message);
    process.exit(1);
  });
} else if (isMain) {
  http.createServer((req, res) => handle(req, res)).listen(PORT, '127.0.0.1', () => {
    console.log(`webmail listening on 127.0.0.1:${PORT}`);
  });
}

export { smtpSend, HttpError };
