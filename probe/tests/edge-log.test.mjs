// Runs the real edge logger against a small upstream and checks what it writes.
// Run: node --test probe/tests/edge-log.test.mjs

import { test } from 'node:test';
import assert from 'node:assert/strict';
import http from 'node:http';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const EDGE = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', 'apps', 'common', 'edge-log.mjs');

function freePort() {
  return new Promise((resolve, reject) => {
    const s = http.createServer();
    s.on('error', reject);
    s.listen(0, '127.0.0.1', () => {
      const { port } = s.address();
      s.close(() => resolve(port));
    });
  });
}

function request(port, method, urlPath, headers = {}, body = '') {
  return new Promise((resolve, reject) => {
    const req = http.request({ host: '127.0.0.1', port, method, path: urlPath, headers }, (res) => {
      let data = '';
      res.on('data', (chunk) => (data += chunk));
      res.on('end', () => resolve({ status: res.statusCode, body: data }));
    });
    req.on('error', reject);
    req.end(body);
  });
}

function readLines(file) {
  if (!fs.existsSync(file)) return [];
  return fs
    .readFileSync(file, 'utf8')
    .split('\n')
    .filter(Boolean)
    .map((line) => JSON.parse(line));
}

async function waitForLines(file, count, timeoutMs = 3000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const lines = readLines(file);
    if (lines.length >= count) return lines;
    await new Promise((r) => setTimeout(r, 25));
  }
  return readLines(file);
}

function startEdge(env) {
  return new Promise((resolve, reject) => {
    const child = spawn(process.execPath, [EDGE], {
      env: { ...process.env, ...env },
      windowsHide: true,
      stdio: ['ignore', 'pipe', 'pipe'],
    });
    let out = '';
    let err = '';
    const timer = setTimeout(() => reject(new Error(`edge did not start: ${err}`)), 5000);
    child.stdout.on('data', (chunk) => {
      out += chunk;
      if (out.includes('edge test:')) {
        clearTimeout(timer);
        resolve(child);
      }
    });
    child.stderr.on('data', (chunk) => (err += chunk));
    child.on('exit', (code) => {
      clearTimeout(timer);
      reject(new Error(`edge exited ${code}: ${err}`));
    });
  });
}

test('logs arrivals and answers, keeps values out of the log, and splits phases by marker', async (t) => {
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'edge-test-'));
  const logFile = path.join(tmp, 'edge.jsonl');

  const upstream = http.createServer((req, res) => {
    req.resume();
    req.on('end', () => {
      res.writeHead(req.method === 'POST' ? 201 : 200, { 'content-type': 'text/plain' });
      res.end('ok');
    });
  });
  await new Promise((r) => upstream.listen(0, '127.0.0.1', r));
  const upstreamPort = upstream.address().port;
  const listenPort = await freePort();
  const controlPort = await freePort();

  const edge = await startEdge({
    EDGE_NAME: 'test',
    EDGE_LISTEN: String(listenPort),
    EDGE_UPSTREAM: String(upstreamPort),
    EDGE_CONTROL: String(controlPort),
    EDGE_LOG: logFile,
  });

  t.after(() => {
    edge.kill();
    upstream.close();
    fs.rmSync(tmp, { recursive: true, force: true });
  });

  const get = await request(listenPort, 'GET', '/items?token=TOKENVALUE&page=2', { cookie: 'sid=COOKIEVALUE' });
  assert.equal(get.status, 200);

  await request(controlPort, 'GET', '/mark?label=held');
  const post = await request(listenPort, 'POST', '/items/9/save', { 'content-type': 'application/x-www-form-urlencoded' }, 'password=BODYVALUE&version=3');
  assert.equal(post.status, 201);
  await request(controlPort, 'GET', '/mark?label=release');

  // GET arrival and done, held marker, POST arrival and done, release marker.
  const lines = await waitForLines(logFile, 6);
  assert.equal(lines.length, 6, 'one arrival and one done per request, plus two markers');
  const raw = fs.readFileSync(logFile, 'utf8');
  for (const secret of ['TOKENVALUE', 'COOKIEVALUE', 'BODYVALUE']) {
    assert.ok(!raw.includes(secret), `log must not contain ${secret}`);
  }

  const getArrival = lines.find((l) => l.event === 'arrival' && l.path === '/items');
  assert.deepEqual(getArrival.query_keys, ['token', 'page']);
  assert.equal(getArrival.unsafe, false);

  const postArrival = lines.find((l) => l.event === 'arrival' && l.method === 'POST');
  assert.equal(postArrival.unsafe, true);
  assert.equal(postArrival.path, '/items/9/save');
  assert.deepEqual(postArrival.query_keys, []);

  const postDone = lines.find((l) => l.event === 'done' && l.method === 'POST');
  assert.equal(postDone.status, 201);

  const held = lines.findIndex((l) => l.marker === 'held');
  const release = lines.findIndex((l) => l.marker === 'release');
  assert.ok(held >= 0 && release > held, 'markers are written in order');
  const leaks = lines
    .slice(held + 1, release)
    .filter((l) => l.event === 'arrival' && l.unsafe).length;
  assert.equal(leaks, 1, 'one unsafe arrival between the held and release markers');

  const beforeHeld = lines.slice(0, held).filter((l) => l.event === 'arrival' && l.unsafe).length;
  assert.equal(beforeHeld, 0, 'no unsafe arrival before the held marker');
});
