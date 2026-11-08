// Setup helper: writes generated probe secrets to probe/state/secrets.json (git-ignored).
// Prints only the key names, never a value. Run once before the first start.
import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const stateDir = path.resolve(here, '..', '..', 'state');
const file = path.join(stateDir, 'secrets.json');
fs.mkdirSync(stateDir, { recursive: true });
const secrets = fs.existsSync(file) ? JSON.parse(fs.readFileSync(file, 'utf8')) : {};
secrets.records = secrets.records || {};
if (!secrets.records.jwt_secret) secrets.records.jwt_secret = crypto.randomBytes(32).toString('hex');
if (!secrets.records.alex || !secrets.records.alex.password) {
  secrets.records.alex = { password: crypto.randomBytes(18).toString('base64url') };
}
fs.writeFileSync(file, JSON.stringify(secrets, null, 2));
console.log(JSON.stringify({ wrote: 'probe/state/secrets.json', records_keys: Object.keys(secrets.records).sort() }));
