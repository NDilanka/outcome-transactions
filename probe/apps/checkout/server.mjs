// Checkout store for the browser probe. Node 24, no dependencies.
//
// This is a stand-in written for the probe, not a production store and not
// an open-source product. It keeps the server behaviour that matters when
// writes are held in a browser:
//   - login sessions; a CSRF token on every unsafe form, rotated at login
//   - version fields on carts, addresses, products and orders; a stale
//     version returns 409
//   - ETag and If-Match on the admin JSON API (428 without If-Match, 412 on
//     mismatch)
//   - idempotency keys on order creation and on payment and refund calls
//   - payment by redirect to a separate provider process (psp.mjs)
//   - a return URL that the browser reaches with a GET that changes state
// Not included: card processing, webhooks, session expiry, rate limits, HTTPS.
//
// Usage:
//   node server.mjs --seed    create the database, seed data, write secrets
//   node server.mjs           serve on CHECKOUT_PORT (default 8101)

import http from 'node:http';
import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import { DatabaseSync } from 'node:sqlite';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const PORT = Number(process.env.CHECKOUT_PORT || 8101);
const DB_FILE = process.env.CHECKOUT_DB || path.join(HERE, 'data', 'checkout.db');
const SECRETS_FILE = process.env.PROBE_SECRETS || path.join(HERE, '..', '..', 'state', 'secrets.json');
const PSP_URL = process.env.PSP_URL || 'http://127.0.0.1:8102';
const PSP_HOSTED_BASE = process.env.PSP_HOSTED_BASE || 'http://localhost:8102';
const PUBLIC_URL = process.env.PUBLIC_URL || 'http://127.0.0.1:8100';
const LOG_FILE = process.env.CHECKOUT_LOG || path.join(HERE, 'logs', 'checkout-app.jsonl');
const MAX_BODY = 64 * 1024;

const now = () => new Date().toISOString();
const rand = (n = 16) => crypto.randomBytes(n).toString('hex');
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
const money = (cents) => `$${(cents / 100).toFixed(2)}`;

class HttpError extends Error {
  constructor(status, message, extra = {}) {
    super(message);
    this.status = status;
    this.extra = extra;
  }
}

function applog(event, data = {}) {
  fs.mkdirSync(path.dirname(LOG_FILE), { recursive: true });
  fs.appendFileSync(LOG_FILE, JSON.stringify({ ts: now(), event, ...data }) + '\n');
}

// ---------- database ----------

const SCHEMA = `
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY, email TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL,
  is_admin INTEGER NOT NULL DEFAULT 0, address TEXT NOT NULL DEFAULT '',
  address_version INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS sessions (
  id TEXT PRIMARY KEY, user_id INTEGER, csrf TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS products (
  sku TEXT PRIMARY KEY, name TEXT NOT NULL, price_cents INTEGER NOT NULL,
  version INTEGER NOT NULL DEFAULT 1, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS carts (
  user_id INTEGER PRIMARY KEY, version INTEGER NOT NULL DEFAULT 1, promo TEXT);
CREATE TABLE IF NOT EXISTS cart_items (
  user_id INTEGER NOT NULL, sku TEXT NOT NULL, qty INTEGER NOT NULL, PRIMARY KEY (user_id, sku));
CREATE TABLE IF NOT EXISTS orders (
  id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, status TEXT NOT NULL,
  items TEXT NOT NULL, subtotal_cents INTEGER NOT NULL, total_cents INTEGER NOT NULL,
  promo TEXT, psp_intent TEXT, version INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS quotes (
  id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, status TEXT NOT NULL,
  items TEXT NOT NULL, total_cents INTEGER NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS discounts (
  code TEXT PRIMARY KEY, percent_off INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS idempotency (
  key TEXT PRIMARY KEY, order_id INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS effects (
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT NULL, kind TEXT NOT NULL,
  ref TEXT NOT NULL, detail TEXT NOT NULL DEFAULT '');
`;

function openDb(file = DB_FILE) {
  fs.mkdirSync(path.dirname(file), { recursive: true });
  const db = new DatabaseSync(file);
  db.exec('PRAGMA foreign_keys = ON; PRAGMA journal_mode = DELETE; PRAGMA busy_timeout = 5000;');
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

// ---------- seed ----------

function seed() {
  fs.mkdirSync(path.dirname(SECRETS_FILE), { recursive: true });
  const secrets = fs.existsSync(SECRETS_FILE) ? JSON.parse(fs.readFileSync(SECRETS_FILE, 'utf8')) : {};
  secrets.checkout = secrets.checkout || {
    shopper: { email: 'shopper@shop.test', password: rand(12) },
    admin: { email: 'admin@shop.test', password: rand(12) },
    psp_secret_key: 'sk_probe_' + rand(16),
  };
  fs.writeFileSync(SECRETS_FILE, JSON.stringify(secrets, null, 2));
  const s = secrets.checkout;

  if (fs.existsSync(DB_FILE)) fs.rmSync(DB_FILE);
  const db = openDb(DB_FILE);
  const t = now();
  const products = [
    ['LMP-1', 'Desk lamp', 2999],
    ['NTB-1', 'Notebook, A5', 499],
    ['PEN-3', 'Pen pack (3)', 899],
    ['MUG-1', 'Ceramic mug', 1200],
  ];
  for (const [sku, name, price] of products) {
    db.prepare('INSERT INTO products (sku, name, price_cents, version, updated_at) VALUES (?, ?, ?, 1, ?)').run(sku, name, price, t);
  }
  db.prepare('INSERT INTO discounts (code, percent_off) VALUES (?, ?)').run('SPRING10', 10);
  db.prepare('INSERT INTO users (email, password_hash, is_admin, address) VALUES (?, ?, 0, ?)')
    .run(s.shopper.email, hashPassword(s.shopper.password), '12 Harbour Road, Leeds LS1 4AB, UK');
  db.prepare('INSERT INTO users (email, password_hash, is_admin, address) VALUES (?, ?, 1, ?)')
    .run(s.admin.email, hashPassword(s.admin.password), '1 Shop Street, Leeds LS1 1AA, UK');
  db.close();
  console.log('checkout: database reset and seeded; secrets written to the state folder (not printed)');
}

// ---------- passwords and sessions ----------

function hashPassword(pw) {
  const salt = crypto.randomBytes(16).toString('hex');
  const hash = crypto.scryptSync(pw, salt, 32).toString('hex');
  return `scrypt$${salt}$${hash}`;
}

function checkPassword(pw, stored) {
  const [, salt, hash] = stored.split('$');
  const candidate = crypto.scryptSync(pw, salt, 32);
  const expected = Buffer.from(hash, 'hex');
  return candidate.length === expected.length && crypto.timingSafeEqual(candidate, expected);
}

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
  const row = db.prepare(`
    SELECT s.id, s.user_id, s.csrf, u.email, u.is_admin
    FROM sessions s LEFT JOIN users u ON u.id = s.user_id WHERE s.id = ?`).get(sid);
  if (!row) return null;
  return {
    sid: row.id,
    csrf: row.csrf,
    user: row.user_id ? { id: row.user_id, email: row.email, isAdmin: !!row.is_admin } : null,
  };
}

function requireUser(sess) {
  if (!sess?.user) throw new HttpError(401, 'Log in first.', { redirect: '/login' });
  return sess.user;
}

function requireAdmin(sess) {
  const user = requireUser(sess);
  if (!user.isAdmin) throw new HttpError(403, 'Admins only.');
  return user;
}

function checkCsrf(form, sess) {
  if (!sess || !form.csrf || form.csrf !== sess.csrf) throw new HttpError(403, 'Your form expired. Reload the page and try again.');
}

// ---------- HTTP helpers ----------

function readBody(req) {
  return new Promise((resolve, reject) => {
    let size = 0;
    const chunks = [];
    req.on('data', (c) => {
      size += c.length;
      if (size > MAX_BODY) {
        reject(new HttpError(413, 'Request too large.'));
        req.destroy();
        return;
      }
      chunks.push(c);
    });
    req.on('end', () => resolve(Buffer.concat(chunks).toString('utf8')));
    req.on('error', reject);
  });
}

function parseBody(req, raw) {
  const type = req.headers['content-type'] || '';
  if (!raw) return {};
  if (type.includes('application/json')) {
    try {
      return JSON.parse(raw);
    } catch {
      throw new HttpError(400, 'Invalid JSON.');
    }
  }
  const params = new URLSearchParams(raw);
  return Object.fromEntries(params.entries());
}

function sendHtml(res, status, title, body, sess, headers = {}) {
  const user = sess?.user;
  const nav = user
    ? `<nav><a href="/">Shop</a> <a href="/cart">Cart</a> <a href="/account">Account</a>` +
      (user.isAdmin ? ` <a href="/admin/products">Admin products</a> <a href="/admin/orders">Admin orders</a>` : '') +
      ` <span>Signed in as ${esc(user.email)}</span>` +
      `<form method="post" action="/logout"><input type="hidden" name="csrf" value="${esc(sess.csrf)}"><button type="submit">Log out</button></form></nav>`
    : `<nav><a href="/login">Log in</a></nav>`;
  const page = `<!doctype html><html lang="en"><head><meta charset="utf-8"><title>${esc(title)} | Shop</title></head><body>${nav}<main>${body}</main></body></html>`;
  res.writeHead(status, { 'content-type': 'text/html; charset=utf-8', ...headers });
  res.end(page);
}

function sendJson(res, status, obj, headers = {}) {
  res.writeHead(status, { 'content-type': 'application/json', ...headers });
  res.end(JSON.stringify(obj));
}

function redirect(res, location, headers = {}) {
  res.writeHead(303, { location, ...headers });
  res.end();
}

function setSessionCookie(res, sid) {
  return { 'set-cookie': `sid=${sid}; Path=/; HttpOnly; SameSite=Lax` };
}

// ---------- cart helpers ----------

function ensureCart(db, userId) {
  db.prepare('INSERT OR IGNORE INTO carts (user_id, version, promo) VALUES (?, 1, NULL)').run(userId);
}

function cartView(db, userId) {
  ensureCart(db, userId);
  const cart = db.prepare('SELECT version, promo FROM carts WHERE user_id = ?').get(userId);
  const rows = db.prepare(`
    SELECT ci.sku, ci.qty, p.name, p.price_cents
    FROM cart_items ci JOIN products p ON p.sku = ci.sku
    WHERE ci.user_id = ? ORDER BY ci.sku`).all(userId);
  const subtotal = rows.reduce((sum, r) => sum + r.qty * r.price_cents, 0);
  const pct = cart.promo ? (db.prepare('SELECT percent_off FROM discounts WHERE code = ?').get(cart.promo)?.percent_off ?? 0) : 0;
  const total = Math.round((subtotal * (100 - pct)) / 100);
  return { version: cart.version, promo: cart.promo, rows, subtotal, total, pct };
}

function bumpCart(db, userId) {
  db.prepare('UPDATE carts SET version = version + 1 WHERE user_id = ?').run(userId);
}

function assertCartVersion(form, cart) {
  if (String(form.cart_version ?? '') !== String(cart.version)) {
    throw new HttpError(409, 'Your cart changed in another tab. Reload the cart and try again.');
  }
}

function parseQty(value) {
  const n = Number(value);
  if (!Number.isInteger(n) || n < 1 || n > 20) throw new HttpError(422, 'Quantity must be a whole number from 1 to 20.');
  return n;
}

function parseDollars(value) {
  if (!/^\d+(\.\d{1,2})?$/.test(String(value ?? '').trim())) throw new HttpError(422, 'Price must be a number such as 12.50.');
  return Math.round(Number(value) * 100);
}

// ---------- payment provider client (server to server) ----------

let pspKey = null;

async function pspCall(method, p, body, extraHeaders = {}) {
  const res = await fetch(PSP_URL + p, {
    method,
    headers: { authorization: `Bearer ${pspKey}`, 'content-type': 'application/json', ...extraHeaders },
    body: body ? JSON.stringify(body) : undefined,
  });
  const json = await res.json().catch(() => ({}));
  applog('psp_call', { method, path: p, status: res.status, idempotency: Boolean(extraHeaders['idempotency-key']) });
  if (!res.ok) throw new HttpError(502, `The payment provider returned an error (${res.status}). Nothing was charged.`);
  return json;
}

// ---------- routes ----------

const routes = [];
const route = (method, pattern, handler) => routes.push({ method, pattern, handler });

route('GET', /^\/$/, ({ db, sess, res }) => {
  const products = db.prepare('SELECT sku, name, price_cents FROM products ORDER BY sku').all();
  const rows = products
    .map((p) => `<tr><td><a href="/products/${esc(p.sku)}">${esc(p.name)}</a></td><td>${esc(p.sku)}</td><td>${money(p.price_cents)}</td></tr>`)
    .join('');
  sendHtml(res, 200, 'Shop', `<h1>Shop</h1><table><tr><th>Product</th><th>SKU</th><th>Price</th></tr>${rows}</table>`, sess);
});

route('GET', /^\/products\/([^/]+)$/, ({ db, sess, res, params }) => {
  requireUser(sess);
  const p = db.prepare('SELECT sku, name, price_cents FROM products WHERE sku = ?').get(params[1]);
  if (!p) throw new HttpError(404, 'Product not found.');
  sendHtml(res, 200, p.name, `
    <h1>${esc(p.name)}</h1><p>SKU ${esc(p.sku)} · ${money(p.price_cents)}</p>
    <form method="post" action="/cart/items">
      <input type="hidden" name="csrf" value="${esc(sess.csrf)}">
      <input type="hidden" name="sku" value="${esc(p.sku)}">
      <label>Quantity <input name="qty" type="number" min="1" max="20" value="1"></label>
      <button type="submit">Add to cart</button>
    </form>`, sess);
});

route('POST', /^\/cart\/items$/, ({ db, sess, form, res }) => {
  const user = requireUser(sess);
  checkCsrf(form, sess);
  const qty = parseQty(form.qty);
  const p = db.prepare('SELECT sku FROM products WHERE sku = ?').get(form.sku);
  if (!p) throw new HttpError(404, 'Product not found.');
  tx(db, () => {
    ensureCart(db, user.id);
    db.prepare(`
      INSERT INTO cart_items (user_id, sku, qty) VALUES (?, ?, ?)
      ON CONFLICT (user_id, sku) DO UPDATE SET qty = MIN(20, qty + excluded.qty)`).run(user.id, p.sku, qty);
    bumpCart(db, user.id);
    effect(db, 'cart.add', `cart:${user.id}`, `${p.sku} x${qty}`);
  });
  redirect(res, '/cart');
});

route('GET', /^\/cart$/, ({ db, sess, res }) => {
  const user = requireUser(sess);
  const cart = cartView(db, user.id);
  const lines = cart.rows.map((r) => `
    <tr>
      <td>${esc(r.name)}</td>
      <td>
        <form method="post" action="/cart/items/${esc(r.sku)}/qty">
          <input type="hidden" name="csrf" value="${esc(sess.csrf)}">
          <input type="hidden" name="cart_version" value="${cart.version}">
          <label>Quantity for ${esc(r.name)} <input name="qty" type="number" min="1" max="20" value="${r.qty}"></label>
          <button type="submit">Update</button>
        </form>
      </td>
      <td>${money(r.qty * r.price_cents)}</td>
      <td>
        <form method="post" action="/cart/items/${esc(r.sku)}/remove">
          <input type="hidden" name="csrf" value="${esc(sess.csrf)}">
          <input type="hidden" name="cart_version" value="${cart.version}">
          <button type="submit">Remove ${esc(r.name)}</button>
        </form>
      </td>
    </tr>`).join('');
  const body = `
    <h1>Cart</h1>
    ${cart.rows.length ? `<table>${lines}</table>` : '<p>Your cart is empty.</p>'}
    <p>Subtotal ${money(cart.subtotal)}${cart.promo ? ` · promo ${esc(cart.promo)} (${cart.pct}% off)` : ''} · Total <strong>${money(cart.total)}</strong></p>
    <form method="post" action="/cart/promo">
      <input type="hidden" name="csrf" value="${esc(sess.csrf)}">
      <label>Promo code <input name="code" type="text"></label>
      <button type="submit">Apply code</button>
    </form>
    ${cart.rows.length ? `
    <p><a href="/checkout">Continue to checkout</a></p>
    <form method="post" action="/quotes">
      <input type="hidden" name="csrf" value="${esc(sess.csrf)}">
      <input type="hidden" name="cart_version" value="${cart.version}">
      <button type="submit">Save as quote</button>
    </form>` : ''}`;
  sendHtml(res, 200, 'Cart', body, sess);
});

route('POST', /^\/cart\/items\/([^/]+)\/qty$/, ({ db, sess, form, res, params }) => {
  const user = requireUser(sess);
  checkCsrf(form, sess);
  const qty = parseQty(form.qty);
  tx(db, () => {
    const cart = cartView(db, user.id);
    assertCartVersion(form, cart);
    const r = db.prepare('UPDATE cart_items SET qty = ? WHERE user_id = ? AND sku = ?').run(qty, user.id, params[1]);
    if (r.changes === 0) throw new HttpError(404, 'That item is not in your cart.');
    bumpCart(db, user.id);
    effect(db, 'cart.qty', `cart:${user.id}`, `${params[1]} -> ${qty}`);
  });
  redirect(res, '/cart');
});

route('POST', /^\/cart\/items\/([^/]+)\/remove$/, ({ db, sess, form, res, params }) => {
  const user = requireUser(sess);
  checkCsrf(form, sess);
  tx(db, () => {
    assertCartVersion(form, cartView(db, user.id));
    db.prepare('DELETE FROM cart_items WHERE user_id = ? AND sku = ?').run(user.id, params[1]);
    bumpCart(db, user.id);
    effect(db, 'cart.remove', `cart:${user.id}`, params[1]);
  });
  redirect(res, '/cart');
});

route('POST', /^\/cart\/promo$/, ({ db, sess, form, res }) => {
  const user = requireUser(sess);
  checkCsrf(form, sess);
  const code = String(form.code ?? '').trim().toUpperCase();
  const d = db.prepare('SELECT code FROM discounts WHERE code = ?').get(code);
  if (!d) throw new HttpError(422, 'That promo code is not valid.');
  tx(db, () => {
    ensureCart(db, user.id);
    db.prepare('UPDATE carts SET promo = ? WHERE user_id = ?').run(code, user.id);
    bumpCart(db, user.id);
    effect(db, 'cart.promo', `cart:${user.id}`, code);
  });
  redirect(res, '/cart');
});

route('GET', /^\/checkout$/, ({ db, sess, res }) => {
  const user = requireUser(sess);
  const cart = cartView(db, user.id);
  if (!cart.rows.length) {
    sendHtml(res, 200, 'Checkout', '<h1>Checkout</h1><p>Your cart is empty.</p>', sess);
    return;
  }
  const address = db.prepare('SELECT address FROM users WHERE id = ?').get(user.id).address;
  sendHtml(res, 200, 'Checkout', `
    <h1>Review and place order</h1>
    <p>Ship to: ${esc(address)}</p>
    <p>${cart.rows.map((r) => `${esc(r.name)} x${r.qty}`).join(', ')}</p>
    <p>Total ${money(cart.total)}</p>
    <form method="post" action="/checkout/orders">
      <input type="hidden" name="csrf" value="${esc(sess.csrf)}">
      <input type="hidden" name="cart_version" value="${cart.version}">
      <input type="hidden" name="idem" value="${rand(12)}">
      <button type="submit">Place order</button>
    </form>`, sess);
});

route('POST', /^\/checkout\/orders$/, ({ db, sess, form, res }) => {
  const user = requireUser(sess);
  checkCsrf(form, sess);
  if (!form.idem) throw new HttpError(422, 'Missing order key.');
  const orderId = tx(db, () => {
    const existing = db.prepare('SELECT order_id FROM idempotency WHERE key = ?').get(form.idem);
    if (existing) return existing.order_id;
    const cart = cartView(db, user.id);
    if (!cart.rows.length) throw new HttpError(409, 'Your cart is empty.');
    assertCartVersion(form, cart);
    const address = db.prepare('SELECT address FROM users WHERE id = ?').get(user.id).address;
    if (!address) throw new HttpError(422, 'Add a shipping address in your account first.');
    const items = JSON.stringify(cart.rows.map((r) => ({ sku: r.sku, qty: r.qty, price_cents: r.price_cents })));
    const t = now();
    const r = db.prepare(`
      INSERT INTO orders (user_id, status, items, subtotal_cents, total_cents, promo, version, created_at, updated_at)
      VALUES (?, 'pending_payment', ?, ?, ?, ?, 1, ?, ?)`).run(user.id, items, cart.subtotal, cart.total, cart.promo, t, t);
    const id = Number(r.lastInsertRowid);
    db.prepare('INSERT INTO idempotency (key, order_id) VALUES (?, ?)').run(form.idem, id);
    effect(db, 'order.create', `order:${id}`, `total ${cart.total}`);
    return id;
  });
  redirect(res, `/checkout/pay/${orderId}`);
});

route('GET', /^\/checkout\/pay\/(\d+)$/, ({ db, sess, res, params }) => {
  const user = requireUser(sess);
  const o = db.prepare('SELECT * FROM orders WHERE id = ? AND user_id = ?').get(Number(params[1]), user.id);
  if (!o) throw new HttpError(404, 'Order not found.');
  if (o.status !== 'pending_payment' && o.status !== 'payment_failed') {
    return redirect(res, `/orders/${o.id}`);
  }
  sendHtml(res, 200, 'Pay', `
    <h1>Order ${o.id}</h1><p>Amount due ${money(o.total_cents)}</p>
    ${o.status === 'payment_failed' ? '<p>Your last payment was not completed.</p>' : ''}
    <form method="post" action="/checkout/pay/${o.id}">
      <input type="hidden" name="csrf" value="${esc(sess.csrf)}">
      <button type="submit">Pay ${money(o.total_cents)}</button>
    </form>`, sess);
});

route('POST', /^\/checkout\/pay\/(\d+)$/, async ({ db, sess, form, res, params }) => {
  const user = requireUser(sess);
  checkCsrf(form, sess);
  const id = Number(params[1]);
  const o = db.prepare('SELECT * FROM orders WHERE id = ? AND user_id = ?').get(id, user.id);
  if (!o) throw new HttpError(404, 'Order not found.');
  if (o.status !== 'pending_payment' && o.status !== 'payment_failed') throw new HttpError(409, 'This order is not waiting for payment.');
  const intent = await pspCall('POST', '/v1/payment_intents', {
    amount: o.total_cents,
    currency: 'usd',
    metadata: { order_id: String(id) },
    return_url: `${PUBLIC_URL}/checkout/return?order=${id}`,
  }, { 'idempotency-key': `order-${id}` });
  tx(db, () => {
    db.prepare('UPDATE orders SET psp_intent = ?, updated_at = ? WHERE id = ?').run(intent.id, now(), id);
    effect(db, 'order.pay_init', `order:${id}`, intent.id);
  });
  redirect(res, `${PSP_HOSTED_BASE}${intent.hosted_path}`);
});

route('GET', /^\/checkout\/return$/, async ({ db, sess, url, res }) => {
  const user = requireUser(sess);
  const id = Number(url.searchParams.get('order'));
  const intentId = url.searchParams.get('intent') || '';
  const o = db.prepare('SELECT * FROM orders WHERE id = ? AND user_id = ?').get(id, user.id);
  if (!o) throw new HttpError(404, 'Order not found.');
  if (o.status === 'paid') return redirect(res, `/orders/${id}`);
  if (!o.psp_intent || o.psp_intent !== intentId) throw new HttpError(400, 'This payment does not match the order.');
  const intent = await pspCall('GET', `/v1/payment_intents/${encodeURIComponent(intentId)}`);
  if (intent.status === 'succeeded') {
    tx(db, () => {
      db.prepare("UPDATE orders SET status = 'paid', version = version + 1, updated_at = ? WHERE id = ? AND status <> 'paid'").run(now(), id);
      db.prepare('DELETE FROM cart_items WHERE user_id = ?').run(user.id);
      bumpCart(db, user.id);
      effect(db, 'order.paid', `order:${id}`, intentId);
    });
    return redirect(res, `/orders/${id}`);
  }
  tx(db, () => {
    db.prepare("UPDATE orders SET status = 'payment_failed', version = version + 1, updated_at = ? WHERE id = ? AND status = 'pending_payment'").run(now(), id);
    effect(db, 'order.payment_failed', `order:${id}`, intent.status);
  });
  sendHtml(res, 402, 'Payment not completed', `<h1>Payment not completed</h1><p><a href="/checkout/pay/${id}">Try again</a></p>`, sess);
});

route('GET', /^\/orders\/(\d+)$/, ({ db, sess, res, params }) => {
  const user = requireUser(sess);
  const o = db.prepare('SELECT * FROM orders WHERE id = ? AND user_id = ?').get(Number(params[1]), user.id);
  if (!o) throw new HttpError(404, 'Order not found.');
  sendHtml(res, 200, `Order ${o.id}`, `<h1>Order ${o.id}</h1><p>Status: <span id="status">${esc(o.status)}</span></p><p>Total ${money(o.total_cents)}</p>`, sess);
});

route('GET', /^\/account$/, ({ db, sess, res }) => {
  const user = requireUser(sess);
  const a = db.prepare('SELECT address, address_version FROM users WHERE id = ?').get(user.id);
  sendHtml(res, 200, 'Account', `
    <h1>Account</h1>
    <form method="post" action="/account/address">
      <input type="hidden" name="csrf" value="${esc(sess.csrf)}">
      <input type="hidden" name="address_version" value="${a.address_version}">
      <label>Shipping address <textarea name="address" rows="3">${esc(a.address)}</textarea></label>
      <button type="submit">Save address</button>
    </form>`, sess);
});

route('POST', /^\/account\/address$/, ({ db, sess, form, res }) => {
  const user = requireUser(sess);
  checkCsrf(form, sess);
  const address = String(form.address ?? '').trim();
  if (address.length < 5 || address.length > 300) throw new HttpError(422, 'Address must be 5 to 300 characters.');
  tx(db, () => {
    const r = db.prepare(`
      UPDATE users SET address = ?, address_version = address_version + 1
      WHERE id = ? AND address_version = ?`).run(address, user.id, Number(form.address_version));
    if (r.changes === 0) throw new HttpError(409, 'Your address changed in another tab. Reload the account page and try again.');
    effect(db, 'address.update', `user:${user.id}`);
  });
  redirect(res, '/account');
});

route('POST', /^\/quotes$/, ({ db, sess, form, res }) => {
  const user = requireUser(sess);
  checkCsrf(form, sess);
  const quoteId = tx(db, () => {
    const cart = cartView(db, user.id);
    if (!cart.rows.length) throw new HttpError(409, 'Your cart is empty.');
    assertCartVersion(form, cart);
    const items = JSON.stringify(cart.rows.map((r) => ({ sku: r.sku, qty: r.qty, price_cents: r.price_cents })));
    const r = db.prepare("INSERT INTO quotes (user_id, status, items, total_cents, created_at) VALUES (?, 'draft', ?, ?, ?)")
      .run(user.id, items, cart.total, now());
    const id = Number(r.lastInsertRowid);
    effect(db, 'quote.draft', `quote:${id}`);
    return id;
  });
  redirect(res, `/quotes/${quoteId}`);
});

route('GET', /^\/quotes\/(\d+)$/, ({ db, sess, res, params }) => {
  const user = requireUser(sess);
  const q = db.prepare('SELECT * FROM quotes WHERE id = ? AND user_id = ?').get(Number(params[1]), user.id);
  if (!q) throw new HttpError(404, 'Quote not found.');
  sendHtml(res, 200, `Quote ${q.id}`, `<h1>Quote ${q.id} (${esc(q.status)})</h1><p>Total ${money(q.total_cents)}</p>`, sess);
});

route('GET', /^\/login$/, ({ db, sess, res }) => {
  // Anonymous session for the login form. The CSRF token rotates at login.
  let current = sess;
  let headers = {};
  if (!current) {
    const sid = rand(16);
    const csrf = rand(16);
    db.prepare('INSERT INTO sessions (id, user_id, csrf, created_at) VALUES (?, NULL, ?, ?)').run(sid, csrf, now());
    current = { sid, csrf, user: null };
    headers = setSessionCookie(res, sid);
  }
  sendHtml(res, 200, 'Log in', `
    <h1>Log in</h1>
    <form method="post" action="/login">
      <input type="hidden" name="csrf" value="${esc(current.csrf)}">
      <label>Email <input name="email" type="email"></label>
      <label>Password <input name="password" type="password"></label>
      <button type="submit">Log in</button>
    </form>`, current, headers);
});

route('POST', /^\/login$/, ({ db, sess, form, res }) => {
  checkCsrf(form, sess);
  const u = db.prepare('SELECT id, password_hash FROM users WHERE email = ?').get(String(form.email ?? ''));
  if (!u || !checkPassword(String(form.password ?? ''), u.password_hash)) {
    throw new HttpError(422, 'Email or password is wrong.');
  }
  // Rotate the session id and the CSRF token at login.
  const newSid = rand(16);
  db.prepare('UPDATE sessions SET id = ?, user_id = ?, csrf = ? WHERE id = ?').run(newSid, u.id, rand(16), sess.sid);
  redirect(res, '/', setSessionCookie(res, newSid));
});

route('POST', /^\/logout$/, ({ db, sess, form, res }) => {
  checkCsrf(form, sess);
  db.prepare('DELETE FROM sessions WHERE id = ?').run(sess.sid);
  redirect(res, '/login', { 'set-cookie': 'sid=; Path=/; Max-Age=0; HttpOnly; SameSite=Lax' });
});

// Admin pages.

route('GET', /^\/admin\/products$/, ({ db, sess, res }) => {
  requireAdmin(sess);
  const rows = db.prepare('SELECT sku, name, price_cents, version FROM products ORDER BY sku').all()
    .map((p) => `<tr><td>${esc(p.sku)}</td><td>${esc(p.name)}</td><td>${money(p.price_cents)}</td><td>v${p.version}</td>
      <td><a href="/admin/products/${esc(p.sku)}/edit">Edit ${esc(p.sku)}</a></td></tr>`).join('');
  sendHtml(res, 200, 'Products', `
    <h1>Products</h1>
    <table><tr><th>SKU</th><th>Name</th><th>Price</th><th>Version</th><th></th></tr>${rows}</table>
    <h2>New product</h2>
    <form method="post" action="/admin/products">
      <input type="hidden" name="csrf" value="${esc(sess.csrf)}">
      <label>SKU <input name="sku" type="text"></label>
      <label>Name <input name="name" type="text"></label>
      <label>Price (USD) <input name="price" type="text"></label>
      <button type="submit">Create product</button>
    </form>
    <h2>New discount code</h2>
    <form method="post" action="/admin/discounts">
      <input type="hidden" name="csrf" value="${esc(sess.csrf)}">
      <label>Code <input name="code" type="text"></label>
      <label>Percent off <input name="percent" type="number" min="1" max="90"></label>
      <button type="submit">Create code</button>
    </form>`, sess);
});

route('POST', /^\/admin\/products$/, ({ db, sess, form, res }) => {
  requireAdmin(sess);
  checkCsrf(form, sess);
  const sku = String(form.sku ?? '').trim().toUpperCase();
  const name = String(form.name ?? '').trim();
  if (!/^[A-Z0-9-]{3,20}$/.test(sku)) throw new HttpError(422, 'SKU must be 3 to 20 letters, digits or dashes.');
  if (!name) throw new HttpError(422, 'Name is required.');
  const price = parseDollars(form.price);
  tx(db, () => {
    if (db.prepare('SELECT 1 FROM products WHERE sku = ?').get(sku)) throw new HttpError(422, 'That SKU already exists.');
    db.prepare('INSERT INTO products (sku, name, price_cents, version, updated_at) VALUES (?, ?, ?, 1, ?)').run(sku, name, price, now());
    effect(db, 'product.create', `product:${sku}`, `${price}`);
  });
  redirect(res, '/admin/products');
});

route('POST', /^\/admin\/discounts$/, ({ db, sess, form, res }) => {
  requireAdmin(sess);
  checkCsrf(form, sess);
  const code = String(form.code ?? '').trim().toUpperCase();
  const pct = Number(form.percent);
  if (!/^[A-Z0-9]{3,20}$/.test(code)) throw new HttpError(422, 'Code must be 3 to 20 letters or digits.');
  if (!Number.isInteger(pct) || pct < 1 || pct > 90) throw new HttpError(422, 'Percent must be a whole number from 1 to 90.');
  tx(db, () => {
    if (db.prepare('SELECT 1 FROM discounts WHERE code = ?').get(code)) throw new HttpError(422, 'That code already exists.');
    db.prepare('INSERT INTO discounts (code, percent_off) VALUES (?, ?)').run(code, pct);
    effect(db, 'discount.create', `discount:${code}`, `${pct}`);
  });
  redirect(res, '/admin/products');
});

route('GET', /^\/admin\/products\/([^/]+)\/edit$/, ({ db, sess, res, params }) => {
  requireAdmin(sess);
  const p = db.prepare('SELECT sku, name, price_cents, version FROM products WHERE sku = ?').get(params[1]);
  if (!p) throw new HttpError(404, 'Product not found.');
  sendHtml(res, 200, `Edit ${p.sku}`, `
    <h1>Edit ${esc(p.sku)}</h1>
    <form method="post" action="/admin/products/${esc(p.sku)}">
      <input type="hidden" name="csrf" value="${esc(sess.csrf)}">
      <input type="hidden" name="version" value="${p.version}">
      <label>Name <input name="name" type="text" value="${esc(p.name)}"></label>
      <label>Price (USD) <input name="price" type="text" value="${(p.price_cents / 100).toFixed(2)}"></label>
      <button type="submit">Save product</button>
    </form>`, sess);
});

route('POST', /^\/admin\/products\/([^/]+)$/, ({ db, sess, form, res, params }) => {
  requireAdmin(sess);
  checkCsrf(form, sess);
  const name = String(form.name ?? '').trim();
  if (!name) throw new HttpError(422, 'Name is required.');
  const price = parseDollars(form.price);
  tx(db, () => {
    const r = db.prepare(`
      UPDATE products SET name = ?, price_cents = ?, version = version + 1, updated_at = ?
      WHERE sku = ? AND version = ?`).run(name, price, now(), params[1], Number(form.version));
    if (r.changes === 0) {
      if (!db.prepare('SELECT 1 FROM products WHERE sku = ?').get(params[1])) throw new HttpError(404, 'Product not found.');
      throw new HttpError(409, 'This product changed since you opened the form. Reload and try again.');
    }
    effect(db, 'product.update', `product:${params[1]}`, `${price}`);
  });
  redirect(res, '/admin/products');
});

function productJson(p) {
  return { sku: p.sku, name: p.name, price_cents: p.price_cents, version: p.version, updated_at: p.updated_at };
}

route('GET', /^\/api\/admin\/products\/([^/]+)$/, ({ db, sess, res, params }) => {
  requireAdmin(sess);
  const p = db.prepare('SELECT * FROM products WHERE sku = ?').get(params[1]);
  if (!p) throw new HttpError(404, 'Product not found.');
  sendJson(res, 200, productJson(p), { etag: `"v${p.version}"` });
});

route('PUT', /^\/api\/admin\/products\/([^/]+)$/, ({ db, sess, req, body, res, params }) => {
  requireAdmin(sess);
  if (req.headers['x-csrf-token'] !== sess.csrf) throw new HttpError(403, 'Missing or wrong CSRF token.');
  const ifMatch = req.headers['if-match'];
  if (!ifMatch) throw new HttpError(428, 'If-Match is required for updates.');
  const out = tx(db, () => {
    const p = db.prepare('SELECT * FROM products WHERE sku = ?').get(params[1]);
    if (!p) throw new HttpError(404, 'Product not found.');
    if (ifMatch !== `"v${p.version}"`) return { precondition: true, current: p };
    const name = body.name === undefined ? p.name : String(body.name).trim();
    const price = body.price_cents === undefined ? p.price_cents : body.price_cents;
    if (!name) throw new HttpError(422, 'Name is required.');
    if (!Number.isInteger(price) || price < 0) throw new HttpError(422, 'price_cents must be a whole number of cents.');
    db.prepare('UPDATE products SET name = ?, price_cents = ?, version = version + 1, updated_at = ? WHERE sku = ?')
      .run(name, price, now(), params[1]);
    effect(db, 'product.update', `product:${params[1]}`, `${price}`);
    return { precondition: false, updated: db.prepare('SELECT * FROM products WHERE sku = ?').get(params[1]) };
  });
  if (out.precondition) {
    sendJson(res, 412, { error: 'precondition_failed', current: productJson(out.current) }, { etag: `"v${out.current.version}"` });
    return;
  }
  sendJson(res, 200, productJson(out.updated), { etag: `"v${out.updated.version}"` });
});

route('GET', /^\/admin\/orders$/, ({ db, sess, res }) => {
  requireAdmin(sess);
  const rows = db.prepare('SELECT o.id, o.status, o.total_cents, u.email FROM orders o JOIN users u ON u.id = o.user_id ORDER BY o.id').all()
    .map((o) => `<tr><td>${o.id}</td><td>${esc(o.email)}</td><td>${esc(o.status)}</td><td>${money(o.total_cents)}</td>
      <td>${o.status === 'paid' ? `<form method="post" action="/admin/orders/${o.id}/refund"><input type="hidden" name="csrf" value="${esc(sess.csrf)}"><button type="submit">Refund order ${o.id}</button></form>` : ''}
      ${['pending_payment', 'payment_failed'].includes(o.status) ? `<form method="post" action="/admin/orders/${o.id}/cancel"><input type="hidden" name="csrf" value="${esc(sess.csrf)}"><button type="submit">Cancel order ${o.id}</button></form>` : ''}</td></tr>`)
    .join('');
  sendHtml(res, 200, 'Orders', `<h1>Orders</h1><table><tr><th>ID</th><th>Customer</th><th>Status</th><th>Total</th><th></th></tr>${rows}</table>`, sess);
});

route('POST', /^\/admin\/orders\/(\d+)\/cancel$/, ({ db, sess, form, res, params }) => {
  requireAdmin(sess);
  checkCsrf(form, sess);
  const id = Number(params[1]);
  tx(db, () => {
    const r = db.prepare("UPDATE orders SET status = 'cancelled', version = version + 1, updated_at = ? WHERE id = ? AND status IN ('pending_payment', 'payment_failed')").run(now(), id);
    if (r.changes === 0) throw new HttpError(409, 'Only unpaid orders can be cancelled.');
    effect(db, 'order.cancel', `order:${id}`);
  });
  redirect(res, '/admin/orders');
});

route('POST', /^\/admin\/orders\/(\d+)\/refund$/, async ({ db, sess, form, res, params }) => {
  requireAdmin(sess);
  checkCsrf(form, sess);
  const id = Number(params[1]);
  const o = db.prepare('SELECT * FROM orders WHERE id = ?').get(id);
  if (!o || o.status !== 'paid') throw new HttpError(409, 'Only paid orders can be refunded.');
  const refund = await pspCall('POST', '/v1/refunds', { payment_intent: o.psp_intent }, { 'idempotency-key': `refund-${id}` });
  tx(db, () => {
    db.prepare("UPDATE orders SET status = 'refunded', version = version + 1, updated_at = ? WHERE id = ?").run(now(), id);
    effect(db, 'order.refund', `order:${id}`, refund.id);
  });
  redirect(res, '/admin/orders');
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
    const raw = ['POST', 'PUT', 'PATCH', 'DELETE'].includes(req.method) ? await readBody(req) : '';
    const body = parseBody(req, raw);
    const form = req.headers['content-type']?.includes('application/json') ? {} : body;
    const sess = loadSession(db, req);
    const m = matchRoute(req.method, url.pathname);
    if (!m.route) {
      if (m.pathMatched) throw new HttpError(405, 'Method not allowed.');
      throw new HttpError(404, 'Page not found.');
    }
    await m.route.handler({ db, sess, req, res, url, form, body, params: m.params });
  } catch (err) {
    const status = err instanceof HttpError ? err.status : 500;
    if (status === 500) console.error(err);
    if (res.headersSent) return;
    if (req.url.startsWith('/api/')) {
      sendJson(res, status, { error: err.message, ...err.extra });
      return;
    }
    if (err instanceof HttpError && err.extra.redirect) {
      redirect(res, err.extra.redirect);
      return;
    }
    const message = err instanceof HttpError ? err.message : 'Something went wrong.';
    sendHtml(res, status, 'Error', `<h1>${esc(message)}</h1><p><a href="/">Back to the shop</a></p>`, null);
  } finally {
    db.close();
  }
}

if (process.argv.includes('--seed')) {
  seed();
} else {
  const secrets = JSON.parse(fs.readFileSync(SECRETS_FILE, 'utf8'));
  pspKey = secrets.checkout.psp_secret_key;
  http.createServer((req, res) => handle(req, res)).listen(PORT, '127.0.0.1', () => {
    console.log(`checkout store listening on 127.0.0.1:${PORT}`);
  });
}
