// Fake payment provider for the browser probe. Node 24, no dependencies.
//
// It stands in for a hosted payment page plus a server API. It is not a
// processor: no card network, no 3-D Secure, no webhooks. It does keep the
// behaviour a store relies on: bearer-key auth, idempotency keys that return
// the same object for the same request and refuse a reused key with different
// parameters, a hosted page with its own token, and a redirect back to the
// store's return URL.
//
// Usage:
//   node psp.mjs --seed    create the provider database
//   node psp.mjs           serve on PSP_PORT (default 8102), 127.0.0.1 and ::1
//
// The provider writes its own request log. That log is server-side evidence
// that the store and the browser did or did not reach the provider.

import http from 'node:http';
import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import { DatabaseSync } from 'node:sqlite';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const PORT = Number(process.env.PSP_PORT || 8102);
const DB_FILE = process.env.PSP_DB || path.join(HERE, 'data', 'psp.db');
const SECRETS_FILE = process.env.PROBE_SECRETS || path.join(HERE, '..', '..', 'state', 'secrets.json');
const LOG_FILE = process.env.PSP_LOG || path.join(HERE, 'logs', 'psp.jsonl');
const MAX_BODY = 16 * 1024;

const now = () => new Date().toISOString();
const rand = (n = 16) => crypto.randomBytes(n).toString('hex');
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);

const SCHEMA = `
CREATE TABLE IF NOT EXISTS intents (
  id TEXT PRIMARY KEY, idem_key TEXT UNIQUE NOT NULL, amount INTEGER NOT NULL,
  currency TEXT NOT NULL, status TEXT NOT NULL, return_url TEXT NOT NULL,
  hosted_token TEXT NOT NULL, metadata TEXT NOT NULL DEFAULT '{}',
  card_last4 TEXT, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS refunds (
  id TEXT PRIMARY KEY, intent_id TEXT NOT NULL, amount INTEGER NOT NULL,
  idem_key TEXT UNIQUE NOT NULL, created_at TEXT NOT NULL);
`;

function openDb(file = DB_FILE) {
  fs.mkdirSync(path.dirname(file), { recursive: true });
  const db = new DatabaseSync(file);
  db.exec('PRAGMA journal_mode = DELETE; PRAGMA busy_timeout = 5000;');
  db.exec(SCHEMA);
  return db;
}

function applog(event, data = {}) {
  fs.mkdirSync(path.dirname(LOG_FILE), { recursive: true });
  fs.appendFileSync(LOG_FILE, JSON.stringify({ ts: now(), event, ...data }) + '\n');
}

function readSecretKey() {
  return JSON.parse(fs.readFileSync(SECRETS_FILE, 'utf8')).checkout.psp_secret_key;
}

class HttpError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}

function luhnOk(digits) {
  let sum = 0;
  let double = false;
  for (let i = digits.length - 1; i >= 0; i--) {
    let d = Number(digits[i]);
    if (double) {
      d *= 2;
      if (d > 9) d -= 9;
    }
    sum += d;
    double = !double;
  }
  return digits.length >= 13 && sum % 10 === 0;
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

function sendJson(res, status, obj) {
  res.writeHead(status, { 'content-type': 'application/json' });
  res.end(JSON.stringify(obj));
}

function sendHtml(res, status, title, body) {
  res.writeHead(status, { 'content-type': 'text/html; charset=utf-8' });
  res.end(`<!doctype html><html lang="en"><head><meta charset="utf-8"><title>${esc(title)}</title></head><body><main>${body}</main></body></html>`);
}

function intentJson(row) {
  return {
    id: row.id,
    object: 'payment_intent',
    status: row.status,
    amount: row.amount,
    currency: row.currency,
    metadata: JSON.parse(row.metadata),
    hosted_path: `/psp/hosted/${row.id}`,
  };
}

function requireKey(req) {
  const expected = Buffer.from(`Bearer ${readSecretKey()}`);
  const given = Buffer.from(String(req.headers.authorization || ''));
  if (given.length !== expected.length || !crypto.timingSafeEqual(given, expected)) {
    throw new HttpError(401, 'Invalid API key.');
  }
}

async function handle(req, res) {
  const url = new URL(req.url, 'http://127.0.0.1');
  const db = openDb(DB_FILE);
  let status = 500;
  try {
    const raw = req.method === 'GET' ? '' : await readBody(req);
    const isJson = (req.headers['content-type'] || '').includes('application/json');
    const body = isJson && raw ? JSON.parse(raw) : Object.fromEntries(new URLSearchParams(raw).entries());
    const p = url.pathname;

    if (p === '/v1/payment_intents' && req.method === 'POST') {
      requireKey(req);
      const key = req.headers['idempotency-key'];
      if (!key) throw new HttpError(400, 'Idempotency-Key is required.');
      const amount = Number(body.amount);
      if (!Number.isInteger(amount) || amount <= 0) throw new HttpError(400, 'amount must be a positive integer.');
      const metadata = JSON.stringify(body.metadata || {});
      const existing = db.prepare('SELECT * FROM intents WHERE idem_key = ?').get(key);
      if (existing) {
        if (existing.amount !== amount || existing.metadata !== metadata || existing.return_url !== body.return_url) {
          status = 409;
          throw new HttpError(409, 'Idempotency-Key was used with different parameters.');
        }
        status = 200;
        sendJson(res, 200, intentJson(existing));
        return;
      }
      const id = `pi_${rand(12)}`;
      db.prepare(`INSERT INTO intents (id, idem_key, amount, currency, status, return_url, hosted_token, metadata, created_at)
        VALUES (?, ?, ?, ?, 'requires_payment_method', ?, ?, ?, ?)`)
        .run(id, key, amount, body.currency || 'usd', String(body.return_url || ''), rand(12), metadata, now());
      status = 200;
      sendJson(res, 200, intentJson(db.prepare('SELECT * FROM intents WHERE id = ?').get(id)));
      return;
    }

    let m = p.match(/^\/v1\/payment_intents\/([\w]+)$/);
    if (m && req.method === 'GET') {
      requireKey(req);
      const row = db.prepare('SELECT * FROM intents WHERE id = ?').get(m[1]);
      if (!row) throw new HttpError(404, 'No such payment intent.');
      status = 200;
      sendJson(res, 200, intentJson(row));
      return;
    }

    if (p === '/v1/refunds' && req.method === 'POST') {
      requireKey(req);
      const key = req.headers['idempotency-key'];
      if (!key) throw new HttpError(400, 'Idempotency-Key is required.');
      const same = db.prepare('SELECT * FROM refunds WHERE idem_key = ?').get(key);
      if (same) {
        status = 200;
        sendJson(res, 200, { id: same.id, object: 'refund', status: 'succeeded', amount: same.amount, payment_intent: same.intent_id });
        return;
      }
      const intent = db.prepare('SELECT * FROM intents WHERE id = ?').get(String(body.payment_intent || ''));
      if (!intent) throw new HttpError(404, 'No such payment intent.');
      if (intent.status !== 'succeeded') throw new HttpError(409, 'Only succeeded payments can be refunded.');
      const id = `re_${rand(12)}`;
      db.exec('BEGIN IMMEDIATE');
      try {
        db.prepare('INSERT INTO refunds (id, intent_id, amount, idem_key, created_at) VALUES (?, ?, ?, ?, ?)')
          .run(id, intent.id, intent.amount, key, now());
        db.prepare("UPDATE intents SET status = 'refunded' WHERE id = ?").run(intent.id);
        db.exec('COMMIT');
      } catch (err) {
        db.exec('ROLLBACK');
        throw err;
      }
      status = 200;
      sendJson(res, 200, { id, object: 'refund', status: 'succeeded', amount: intent.amount, payment_intent: intent.id });
      return;
    }

    m = p.match(/^\/psp\/hosted\/([\w]+)$/);
    if (m && req.method === 'GET') {
      const row = db.prepare('SELECT * FROM intents WHERE id = ?').get(m[1]);
      if (!row) throw new HttpError(404, 'Unknown payment page.');
      status = 200;
      if (row.status !== 'requires_payment_method') {
        sendHtml(res, 200, 'Payment page', `<h1>This payment is already ${esc(row.status)}.</h1>`);
        return;
      }
      sendHtml(res, 200, 'Pay', `
        <h1>Pay with card</h1>
        <p>Amount ${(row.amount / 100).toFixed(2)} ${esc(row.currency.toUpperCase())}</p>
        <form method="post" action="/psp/hosted/${esc(row.id)}/pay">
          <input type="hidden" name="psp_token" value="${esc(row.hosted_token)}">
          <label>Card number <input name="card" type="text" value="4242 4242 4242 4242" autocomplete="cc-number"></label>
          <label>Expiry <input name="expiry" type="text" value="12/30" autocomplete="cc-exp"></label>
          <label>CVC <input name="cvc" type="text" value="123" autocomplete="cc-csc"></label>
          <button type="submit">Pay ${(row.amount / 100).toFixed(2)}</button>
        </form>`);
      return;
    }

    m = p.match(/^\/psp\/hosted\/([\w]+)\/pay$/);
    if (m && req.method === 'POST') {
      const row = db.prepare('SELECT * FROM intents WHERE id = ?').get(m[1]);
      if (!row) throw new HttpError(404, 'Unknown payment page.');
      if (row.status !== 'requires_payment_method') throw new HttpError(409, 'This payment was already processed.');
      if (body.psp_token !== row.hosted_token) throw new HttpError(403, 'The payment page expired. Reload it and try again.');
      const digits = String(body.card || '').replace(/\D/g, '');
      if (!luhnOk(digits)) throw new HttpError(422, 'The card number is not valid.');
      const declined = digits.endsWith('0002');
      const outcome = declined ? 'requires_payment_method' : 'succeeded';
      db.prepare('UPDATE intents SET status = ?, card_last4 = ? WHERE id = ?').run(outcome, digits.slice(-4), row.id);
      const back = new URL(row.return_url);
      back.searchParams.set('intent', row.id);
      back.searchParams.set('status', outcome);
      status = 303;
      res.writeHead(303, { location: back.toString() });
      res.end();
      return;
    }

    throw new HttpError(404, 'Not found.');
  } catch (err) {
    status = err instanceof HttpError ? err.status : 500;
    if (status === 500) console.error(err);
    if (!res.headersSent) {
      if (req.url.startsWith('/v1/')) sendJson(res, status, { error: err.message });
      else sendHtml(res, status, 'Error', `<h1>${esc(err.message || 'Error')}</h1>`);
    }
  } finally {
    applog('request', { method: req.method, path: url.pathname, status });
    db.close();
  }
}

if (process.argv.includes('--seed')) {
  if (fs.existsSync(DB_FILE)) fs.rmSync(DB_FILE);
  openDb(DB_FILE).close();
  console.log('psp: database reset (secret key read from the state folder, not printed)');
} else {
  readSecretKey();
  for (const host of ['127.0.0.1', '::1']) {
    http.createServer((req, res) => handle(req, res)).listen(PORT, host, () => {
      console.log(`psp listening on ${host}:${PORT}`);
    }).on('error', (err) => console.error(`psp ${host}: ${err.code}`));
  }
}
