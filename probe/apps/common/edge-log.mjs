// Logging reverse proxy in front of a browser-facing app. Node 24, no dependencies.
//
// Every request is forwarded unchanged. Two JSON lines are appended to the log:
// an "arrival" line when the request reaches the edge, and a "done" line with
// the status and duration once the app has answered. Each line carries the time,
// edge name, sequence number, method, path and whether the method is unsafe. The
// query string is logged as key names only, and cookie, authorization and body
// values are never logged. A held request never reaches the edge, so every unsafe
// arrival is a request the browser policy let through. Unsafe arrivals between
// the held and release markers are the hold-leak count, and they do not depend
// on the browser's own view.
//
// A control port accepts GET /mark?label=... and writes a marker line, so the
// runner can split the log into phases (setup, held run, release) by marker
// rather than by clock.
//
// Environment:
//   EDGE_NAME      name written in each line
//   EDGE_LISTEN    port the browser uses (127.0.0.1)
//   EDGE_UPSTREAM  port of the app (127.0.0.1)
//   EDGE_LOG       path of the JSON-lines log
//   EDGE_CONTROL   port for markers (127.0.0.1)

import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';

const NAME = process.env.EDGE_NAME || 'app';
const LISTEN = Number(process.env.EDGE_LISTEN);
const UPSTREAM = Number(process.env.EDGE_UPSTREAM);
const LOG = process.env.EDGE_LOG;
const CONTROL = Number(process.env.EDGE_CONTROL || 0);
const SAFE = new Set(['GET', 'HEAD', 'OPTIONS']);

if (!LISTEN || !UPSTREAM || !LOG) {
  console.error('edge-log: EDGE_LISTEN, EDGE_UPSTREAM and EDGE_LOG are required');
  process.exit(2);
}

fs.mkdirSync(path.dirname(LOG), { recursive: true });
let seq = 0;

function write(obj) {
  fs.appendFileSync(LOG, JSON.stringify({ ts: new Date().toISOString(), edge: NAME, ...obj }) + '\n');
}

function describe(rawUrl) {
  const q = rawUrl.indexOf('?');
  const pathOnly = q === -1 ? rawUrl : rawUrl.slice(0, q);
  const keys = q === -1 ? [] : [...new URLSearchParams(rawUrl.slice(q + 1)).keys()];
  return { path: pathOnly, query_keys: keys };
}

const server = http.createServer((req, res) => {
  const id = ++seq;
  const started = process.hrtime.bigint();
  const { path: pathOnly, query_keys } = describe(req.url);
  const base = { id, method: req.method, path: pathOnly, query_keys, unsafe: !SAFE.has(req.method) };
  write({ event: 'arrival', ...base });
  const upstream = http.request(
    { host: '127.0.0.1', port: UPSTREAM, method: req.method, path: req.url, headers: req.headers },
    (ures) => {
      res.writeHead(ures.statusCode, ures.headers);
      ures.pipe(res);
      ures.on('end', () => {
        write({ event: 'done', ...base, status: ures.statusCode, ms: Number(process.hrtime.bigint() - started) / 1e6 });
      });
    },
  );
  upstream.on('error', () => {
    if (!res.headersSent) res.writeHead(502, { 'content-type': 'text/plain' });
    res.end('upstream unavailable');
    write({ event: 'done', ...base, status: 502, ms: Number(process.hrtime.bigint() - started) / 1e6 });
  });
  req.pipe(upstream);
});

server.listen(LISTEN, '127.0.0.1', () => {
  console.log(`edge ${NAME}: 127.0.0.1:${LISTEN} -> 127.0.0.1:${UPSTREAM}`);
});

if (CONTROL) {
  http.createServer((req, res) => {
    const u = new URL(req.url, 'http://127.0.0.1');
    if (u.pathname === '/mark' && req.method === 'GET') {
      const label = (u.searchParams.get('label') || 'mark').slice(0, 80);
      write({ marker: label });
      res.writeHead(204);
      res.end();
      return;
    }
    res.writeHead(404);
    res.end();
  }).listen(CONTROL, '127.0.0.1');
}
