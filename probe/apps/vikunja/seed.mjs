// Setup for the records app (Vikunja v2.8.0). Creates the frozen seed data through
// the app's own API, as user alex. This is setup, not a measured step.
//
// Run after the app has been reset to a fresh database and the user has been
// created (see NOTES.md). The script refuses to run on a database that already
// has the seed projects, so a run never starts from a half-seeded state.
//
//   node probe/apps/vikunja/seed.mjs [--base http://127.0.0.1:8300]
//
// The password is read from state/secrets.json (records.alex.password). It is
// never printed. Calls go through the records edge, so the edge log shows them
// between the setup markers.

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const SECRETS_FILE = process.env.PROBE_SECRETS || path.join(HERE, '..', '..', 'state', 'secrets.json');
const DEFAULT_BASE = 'http://127.0.0.1:8300';

export const SEED_PROJECTS = ['Work', 'Home'];
export const SEED_TASKS = [
  { title: 'Renew passport', project: 'Home' },
  { title: 'Pay council tax', project: 'Home' },
  { title: 'Call dentist', project: 'Home' },
  { title: 'Quarterly report draft', project: 'Work' },
  { title: 'Book venue', project: 'Work' },
  { title: 'Old test item', project: 'Inbox' },
];
export const SEED_LABELS = ['urgent'];

export class SeedError extends Error {}

async function call(base, token, method, urlPath, body) {
  const headers = { accept: 'application/json' };
  if (token) headers.authorization = `Bearer ${token}`;
  if (body !== undefined) headers['content-type'] = 'application/json';
  const res = await fetch(new URL(urlPath, base), {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const text = await res.text();
  let data = null;
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = text;
    }
  }
  if (!res.ok) {
    const detail = data && typeof data === 'object' ? data.detail || data.message : null;
    throw new SeedError(`${method} ${urlPath} failed: ${res.status} ${detail || res.statusText}`);
  }
  return data;
}

async function listAll(base, token, urlPath) {
  const data = await call(base, token, 'GET', `${urlPath}${urlPath.includes('?') ? '&' : '?'}per_page=100`);
  if (!data || !Array.isArray(data.items)) throw new SeedError(`GET ${urlPath} did not return the list envelope`);
  return data.items;
}

// Creates the seed data and checks it. Returns counts. Throws SeedError on any problem.
export async function seed({ base = DEFAULT_BASE, username = 'alex', password }) {
  if (!password) throw new SeedError('no password given');

  const login = await call(base, null, 'POST', '/api/v2/login', { username, password, long_token: false });
  const token = login && login.token;
  if (!token) throw new SeedError('login returned no token');

  const projects = await listAll(base, token, '/api/v2/projects');
  const titles = new Set(projects.map((p) => p.title));
  for (const title of SEED_PROJECTS) {
    if (titles.has(title)) throw new SeedError(`project ${title} already exists: database is not in seed state`);
  }
  const inbox = projects.find((p) => p.title === 'Inbox');
  if (!inbox) throw new SeedError('no Inbox project: the user was not created with its default project');

  const ids = { Inbox: inbox.id };
  for (const title of SEED_PROJECTS) {
    const created = await call(base, token, 'POST', '/api/v2/projects', { title });
    ids[title] = created.id;
  }
  for (const task of SEED_TASKS) {
    await call(base, token, 'POST', `/api/v2/projects/${ids[task.project]}/tasks`, { title: task.title });
  }
  for (const title of SEED_LABELS) {
    await call(base, token, 'POST', '/api/v2/labels', { title });
  }

  // Check the result: every seed task appears exactly once in its project.
  for (const task of SEED_TASKS) {
    const found = await listAll(base, token, `/api/v2/projects/${ids[task.project]}/tasks`);
    const matches = found.filter((t) => t.title === task.title).length;
    if (matches !== 1) throw new SeedError(`task "${task.title}" found ${matches} times after seeding`);
  }
  const labels = await listAll(base, token, '/api/v2/labels');
  const allProjects = await listAll(base, token, '/api/v2/projects');

  return {
    projects: allProjects.filter((p) => ['Inbox', ...SEED_PROJECTS].includes(p.title)).length,
    tasks: SEED_TASKS.length,
    labels: labels.filter((l) => SEED_LABELS.includes(l.title)).length,
  };
}

export function readPassword(file = SECRETS_FILE) {
  const secrets = JSON.parse(fs.readFileSync(file, 'utf8'));
  const password = secrets && secrets.records && secrets.records.alex && secrets.records.alex.password;
  if (!password) throw new SeedError(`no records.alex.password in ${path.basename(file)}`);
  return password;
}

const isMain = path.resolve(process.argv[1] || '') === fileURLToPath(import.meta.url);
if (isMain) {
  const flag = process.argv.indexOf('--base');
  const base = flag > 0 ? process.argv[flag + 1] : DEFAULT_BASE;
  seed({ base, password: readPassword() })
    .then((counts) => console.log(JSON.stringify({ seeded: counts })))
    .catch((err) => {
      console.error(err.message);
      process.exit(1);
    });
}
