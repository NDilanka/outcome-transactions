// Tests the Vikunja seed script against an in-process fake of the v2 routes it uses.
// No app is started. The live check runs after the go-ahead.
// Run: node --test probe/tests/vikunja-seed.test.mjs

import { test } from 'node:test';
import assert from 'node:assert/strict';
import http from 'node:http';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { seed, readPassword, SeedError, SEED_TASKS } from '../apps/vikunja/seed.mjs';

const PASSWORD = 'pw-test-not-real';
const TOKEN = 'tok-test';

function problem(res, status, detail) {
  res.writeHead(status, { 'content-type': 'application/problem+json' });
  res.end(JSON.stringify({ title: 'Error', status, detail, code: 1 }));
}

function fakeVikunja(options = {}) {
  const state = {
    projects: [{ id: 1, title: 'Inbox' }],
    tasks: [],
    labels: [],
    seen: [],
    nextId: 10,
    ...options.initial,
  };
  const calls = [];
  const server = http.createServer(async (req, res) => {
    let raw = '';
    for await (const chunk of req) raw += chunk;
    const body = raw ? JSON.parse(raw) : undefined;
    const url = new URL(req.url, 'http://x');
    calls.push(`${req.method} ${url.pathname}`);
    if (req.method === 'POST' && url.pathname === '/api/v2/login') {
      if (body.password !== PASSWORD) return problem(res, 401, 'wrong password');
      res.writeHead(200, { 'content-type': 'application/json' });
      return res.end(JSON.stringify({ token: TOKEN }));
    }
    if (req.headers.authorization !== `Bearer ${TOKEN}`) return problem(res, 401, 'no token');
    const json = (status, data) => {
      res.writeHead(status, { 'content-type': 'application/json' });
      res.end(JSON.stringify(data));
    };
    const list = (items) => json(200, { items, total: items.length, page: 1, per_page: 100, total_pages: 1 });
    if (req.method === 'GET' && url.pathname === '/api/v2/projects') return list(state.projects);
    if (req.method === 'POST' && url.pathname === '/api/v2/projects') {
      const project = { id: state.nextId++, title: body.title };
      state.projects.push(project);
      return json(201, project);
    }
    const taskList = url.pathname.match(/^\/api\/v2\/projects\/(\d+)\/tasks$/);
    if (taskList && req.method === 'GET') {
      return list(state.tasks.filter((t) => t.project_id === Number(taskList[1])));
    }
    if (taskList && req.method === 'POST') {
      const task = { id: state.nextId++, title: body.title, project_id: Number(taskList[1]), done: false };
      state.tasks.push(task);
      return json(201, task);
    }
    if (req.method === 'POST' && url.pathname === '/api/v2/labels') {
      const label = { id: state.nextId++, title: body.title };
      state.labels.push(label);
      return json(201, label);
    }
    if (req.method === 'GET' && url.pathname === '/api/v2/labels') return list(state.labels);
    return problem(res, 404, `no fake route for ${req.method} ${url.pathname}`);
  });
  return new Promise((resolve) => {
    server.listen(0, '127.0.0.1', () => {
      const { port } = server.address();
      resolve({ base: `http://127.0.0.1:${port}`, state, calls, close: () => server.close() });
    });
  });
}

test('seeds a fresh database with the frozen projects, tasks and label', async (t) => {
  const app = await fakeVikunja();
  t.after(() => app.close());
  const counts = await seed({ base: app.base, password: PASSWORD });
  assert.deepEqual(counts, { projects: 3, tasks: SEED_TASKS.length, labels: 1 });
  const titles = app.state.tasks.map((task) => task.title).sort();
  assert.deepEqual(titles, SEED_TASKS.map((task) => task.title).sort());
  const home = app.state.projects.find((p) => p.title === 'Home');
  assert.equal(app.state.tasks.filter((task) => task.project_id === home.id).length, 3);
});

test('uses the v2 create verbs and never the v1 ones', async (t) => {
  const app = await fakeVikunja();
  t.after(() => app.close());
  await seed({ base: app.base, password: PASSWORD });
  assert.ok(app.calls.includes('POST /api/v2/login'));
  assert.ok(app.calls.includes('POST /api/v2/projects'));
  assert.ok(app.calls.includes('POST /api/v2/labels'));
  assert.ok(app.calls.every((c) => c.startsWith('GET ') || c.startsWith('POST ')), 'no PUT or PATCH');
});

test('a wrong password stops the seed and does not echo it', async (t) => {
  const app = await fakeVikunja();
  t.after(() => app.close());
  await assert.rejects(
    seed({ base: app.base, password: 'wrong-value' }),
    (err) => err instanceof SeedError && /401 wrong password/.test(err.message) && !err.message.includes('wrong-value'),
  );
  assert.equal(app.state.tasks.length, 0);
});

test('refuses a database that already has the seed projects', async (t) => {
  const app = await fakeVikunja({ initial: { projects: [{ id: 1, title: 'Inbox' }, { id: 2, title: 'Home' }] } });
  t.after(() => app.close());
  await assert.rejects(seed({ base: app.base, password: PASSWORD }), /not in seed state/);
  assert.equal(app.calls.filter((c) => c === 'POST /api/v2/projects').length, 0);
  assert.equal(app.calls.filter((c) => c.includes('/tasks')).length, 0, 'refused before any task call');
});

test('stops when the default Inbox project is missing', async (t) => {
  const app = await fakeVikunja({ initial: { projects: [] } });
  t.after(() => app.close());
  await assert.rejects(seed({ base: app.base, password: PASSWORD }), /no Inbox project/);
});

test('reads the password from the secrets file and fails clearly when it is absent', () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'seed-secrets-'));
  try {
    const good = path.join(dir, 'good.json');
    fs.writeFileSync(good, JSON.stringify({ records: { alex: { password: PASSWORD } } }));
    assert.equal(readPassword(good), PASSWORD);

    const bad = path.join(dir, 'bad.json');
    fs.writeFileSync(bad, JSON.stringify({ records: {} }));
    assert.throws(() => readPassword(bad), (err) => err instanceof SeedError && !err.message.includes(PASSWORD));
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }
});
