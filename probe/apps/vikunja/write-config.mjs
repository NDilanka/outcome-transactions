// Setup helper: writes apps/vikunja/data/config.yml with the keys from NOTES.md.
// The JWT secret is read from probe/state/secrets.json (run setup-secrets.mjs first) and never printed.
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const probe = path.resolve(here, '..', '..');
const data = path.join(here, 'data');
const secrets = JSON.parse(fs.readFileSync(path.join(probe, 'state', 'secrets.json'), 'utf8'));
const secret = secrets.records && secrets.records.jwt_secret;
if (!secret) throw new Error('no records.jwt_secret in probe/state/secrets.json: run setup-secrets.mjs first');

const p = (value) => value.split(path.sep).join('/');
fs.mkdirSync(path.join(data, 'files'), { recursive: true });
const yaml = `service:
  interface: "127.0.0.1:3456"
  publicurl: "http://127.0.0.1:8300/"
  secret: "${secret}"
  jwtttlshort: 600
  rootpath: "${p(data)}"
  enableregistration: false
  enablelinksharing: false
  enableemailreminders: false
database:
  type: "sqlite"
  path: "${p(path.join(data, 'vikunja.db'))}"
files:
  basepath: "${p(path.join(data, 'files'))}"
mailer:
  enabled: false
`;
fs.writeFileSync(path.join(data, 'config.yml'), yaml);
console.log(JSON.stringify({ wrote: 'apps/vikunja/data/config.yml', keys: ['service', 'database', 'files', 'mailer'] }));
