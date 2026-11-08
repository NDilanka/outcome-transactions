// Vikunja seed build and reset (Vikunja v2.8.0, Windows binary, SQLite in WAL mode).
//
//   node probe/apps/vikunja/reset.mjs build    rebuild the seed from scratch and snapshot it
//   node probe/apps/vikunja/reset.mjs restore  stop, restore the snapshot, start, wait for the port
//   node probe/apps/vikunja/reset.mjs stop     stop the app
//
// Each command prints one JSON line. The snapshot is taken after a WAL
// checkpoint, so it holds every committed row in the main file. Copying the
// main file alone would lose the data, which sits in the WAL until checkpoint.
//
// Registration is switched on only for the build, through the environment
// override VIKUNJA_SERVICE_ENABLEREGISTRATION, so config.yml is never edited.
// The password comes from probe/state/secrets.json and is never printed.

import { spawn, execFileSync } from 'node:child_process';
import crypto from 'node:crypto';
import fs from 'node:fs';
import net from 'node:net';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { DatabaseSync } from 'node:sqlite';

import { seed, readPassword } from './seed.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const PROBE = path.resolve(HERE, '..', '..');
const DATA = path.join(HERE, 'data');
const LOGS = path.join(HERE, 'logs');
const BIN = path.join(HERE, 'bin', 'vikunja-v2.8.0-windows-4.0-amd64.exe');
const CONFIG = path.join(DATA, 'config.yml');
const DB = path.join(DATA, 'vikunja.db');
const FILES = path.join(DATA, 'files');
const SEED_DIR = path.join(DATA, 'seed');
const SEED = path.join(SEED_DIR, 'vikunja.seed.db');
const MANIFEST = path.join(SEED_DIR, 'manifest.json');
const PIDFILE = path.join(PROBE, 'state', 'vikunja.pid');
const PORT = 3456;
const BASE_VIA_EDGE = 'http://127.0.0.1:8300';
const READY_TIMEOUT_MS = 60000;

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

function alive(pid) {
  try {
    process.kill(pid, 0);
    return true;
  } catch {
    return false;
  }
}

async function stopApp() {
  if (!fs.existsSync(PIDFILE)) return false;
  const pid = Number(fs.readFileSync(PIDFILE, 'utf8').trim());
  if (alive(pid)) {
    process.kill(pid);
    const until = Date.now() + 15000;
    while (alive(pid) && Date.now() < until) await sleep(100);
    if (alive(pid)) throw new Error(`vikunja pid ${pid} did not exit`);
  }
  fs.rmSync(PIDFILE, { force: true });
  return true;
}

function portOpen() {
  return new Promise((resolve) => {
    const socket = net.connect({ host: '127.0.0.1', port: PORT });
    socket.once('connect', () => {
      socket.destroy();
      resolve(true);
    });
    socket.once('error', () => resolve(false));
  });
}

async function waitForPort() {
  const until = Date.now() + READY_TIMEOUT_MS;
  while (Date.now() < until) {
    if (await portOpen()) return true;
    await sleep(100);
  }
  throw new Error(`vikunja did not open port ${PORT} within ${READY_TIMEOUT_MS / 1000} s`);
}

function startApp(env = {}) {
  fs.mkdirSync(LOGS, { recursive: true });
  const out = fs.openSync(path.join(LOGS, 'web.out.log'), 'a');
  const err = fs.openSync(path.join(LOGS, 'web.err.log'), 'a');
  const child = spawn(BIN, ['--config', CONFIG, 'web'], {
    detached: true,
    stdio: ['ignore', out, err],
    windowsHide: true,
    env: { ...process.env, ...env },
  });
  child.unref();
  fs.writeFileSync(PIDFILE, String(child.pid));
  return child.pid;
}

// Windows can hold a file for a moment after its process exits, so retry the removal.
async function rmWithRetry(target) {
  const until = Date.now() + 10000;
  for (;;) {
    try {
      fs.rmSync(target, { recursive: true, force: true });
      return;
    } catch (err) {
      if (!['EPERM', 'EBUSY'].includes(err.code) || Date.now() > until) throw err;
      await sleep(200);
    }
  }
}

async function removeDbFiles() {
  for (const suffix of ['', '-wal', '-shm']) await rmWithRetry(DB + suffix);
}

function sha256(file) {
  return crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');
}

async function register() {
  const password = readPassword();
  const res = await fetch(`http://127.0.0.1:${PORT}/api/v2/register`, {
    method: 'POST',
    headers: { 'content-type': 'application/json', accept: 'application/json' },
    body: JSON.stringify({ username: 'alex', email: 'alex@local.test', password }),
  });
  if (res.status !== 201) throw new Error(`register returned ${res.status}`);
}

async function build() {
  const started = Date.now();
  await stopApp();
  await removeDbFiles();
  await rmWithRetry(FILES);
  await rmWithRetry(SEED_DIR);
  fs.mkdirSync(SEED_DIR, { recursive: true });

  execFileSync(BIN, ['--config', CONFIG, 'migrate'], { stdio: 'ignore' });

  startApp({ VIKUNJA_SERVICE_ENABLEREGISTRATION: 'true' });
  await waitForPort();
  await register();
  await stopApp();

  startApp();
  await waitForPort();
  const counts = await seed({ base: BASE_VIA_EDGE, password: readPassword() });
  await stopApp();

  const db = new DatabaseSync(DB);
  db.exec('PRAGMA wal_checkpoint(TRUNCATE)');
  db.close();
  await removeWalFiles();
  fs.copyFileSync(DB, SEED);
  const hash = sha256(SEED);
  fs.writeFileSync(MANIFEST, JSON.stringify({ sha256: hash, counts, built_at: new Date().toISOString() }, null, 2));
  return { command: 'build', seed_sha256: hash, counts, seconds: round((Date.now() - started) / 1000) };
}

// Remove the WAL and shared-memory files, after the checkpoint has folded them into the main file.
async function removeWalFiles() {
  for (const suffix of ['-wal', '-shm']) await rmWithRetry(DB + suffix);
}

async function restore() {
  const started = Date.now();
  if (!fs.existsSync(MANIFEST)) throw new Error('no seed snapshot: run build first');
  const manifest = JSON.parse(fs.readFileSync(MANIFEST, 'utf8'));
  await stopApp();
  if (sha256(SEED) !== manifest.sha256) throw new Error('seed snapshot does not match its manifest');
  await removeDbFiles();
  fs.copyFileSync(SEED, DB);
  if (sha256(DB) !== manifest.sha256) throw new Error('restored database does not match the snapshot');
  await rmWithRetry(FILES);
  startApp();
  await waitForPort();
  return { command: 'restore', seed_sha256: manifest.sha256, seconds: round((Date.now() - started) / 1000) };
}

function round(value) {
  return Math.round(value * 100) / 100;
}

async function main() {
  const command = process.argv[2];
  if (command === 'build') return build();
  if (command === 'restore') return restore();
  if (command === 'stop') {
    const stopped = await stopApp();
    return { command: 'stop', stopped };
  }
  throw new Error('usage: reset.mjs build|restore|stop');
}

main()
  .then((result) => console.log(JSON.stringify(result)))
  .catch((err) => {
    console.error(err.message);
    process.exit(1);
  });
