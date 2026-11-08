// Tests for the webmail stub's SMTP client, against an in-process fake SMTP
// server. No Mailpit, no browser. Run: node --test probe/tests/smtp-client.test.mjs

import test from 'node:test';
import assert from 'node:assert/strict';
import net from 'node:net';
import { smtpSend, HttpError } from '../apps/mail/webmail.mjs';

// Fake SMTP server. `state.refuseOn` names a command verb (e.g. 'RCPT') that
// gets a 550 reply. Every command and every DATA body is recorded.
async function fakeSmtp() {
  const state = { refuseOn: null, commands: [], messages: [] };
  const sockets = new Set();
  const server = net.createServer((sock) => {
    sockets.add(sock);
    sock.on('close', () => sockets.delete(sock));
    sock.on('error', () => {});
    let buf = '';
    let inData = false;
    let data = '';
    sock.write('220 fake.local ESMTP\r\n');
    sock.on('data', (chunk) => {
      buf += chunk.toString('utf8');
      let i;
      while ((i = buf.indexOf('\r\n')) !== -1) {
        const line = buf.slice(0, i);
        buf = buf.slice(i + 2);
        if (inData) {
          if (line === '.') {
            inData = false;
            state.messages.push(data);
            data = '';
            sock.write('250 queued\r\n');
          } else {
            data += line + '\r\n';
          }
          continue;
        }
        state.commands.push(line);
        const verb = line.split(' ')[0].toUpperCase();
        if (state.refuseOn === verb) {
          sock.write('550 refused\r\n');
        } else if (verb === 'EHLO') {
          sock.write('250-fake.local\r\n250-SIZE 10240000\r\n250 OK\r\n');
        } else if (verb === 'DATA') {
          inData = true;
          sock.write('354 go ahead\r\n');
        } else if (verb === 'QUIT') {
          sock.write('221 bye\r\n');
          sock.end();
        } else {
          sock.write('250 OK\r\n');
        }
      }
    });
  });
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
  return {
    state,
    port: server.address().port,
    close: () =>
      new Promise((resolve) => {
        for (const s of sockets) s.destroy();
        server.close(resolve);
      }),
  };
}

const base = { fromName: 'Alex Reed', fromAddress: 'alex@local.test', to: 'bob@example.test' };

test('delivers one message with the expected SMTP sequence', async () => {
  const smtp = await fakeSmtp();
  try {
    await smtpSend({ ...base, subject: 'Hello', body: 'First line\nSecond line\n', host: '127.0.0.1', port: smtp.port });
    assert.deepEqual(smtp.state.commands, [
      'EHLO webmail.local.test',
      'MAIL FROM:<alex@local.test>',
      'RCPT TO:<bob@example.test>',
      'DATA',
      'QUIT',
    ]);
    assert.equal(smtp.state.messages.length, 1);
    const data = smtp.state.messages[0];
    assert.match(data, /^From: Alex Reed <alex@local\.test>\r\n/);
    assert.match(data, /\r\nTo: bob@example\.test\r\n/);
    assert.match(data, /\r\nSubject: Hello\r\n/);
    assert.match(data, /\r\n\r\nFirst line\r\nSecond line\r\n$/);
  } finally {
    await smtp.close();
  }
});

test('dot-stuffs body lines that start with a dot', async () => {
  const smtp = await fakeSmtp();
  try {
    await smtpSend({ ...base, subject: 'Dots', body: '.hidden line\nafter\n', host: '127.0.0.1', port: smtp.port });
    const data = smtp.state.messages[0];
    assert.match(data, /\r\n\.\.hidden line\r\n/);
    assert.match(data, /\r\nafter\r\n$/);
  } finally {
    await smtp.close();
  }
});

test('encodes a non-ASCII subject as RFC 2047 base64', async () => {
  const smtp = await fakeSmtp();
  try {
    const subject = 'Café agenda';
    await smtpSend({ ...base, subject, body: 'x', host: '127.0.0.1', port: smtp.port });
    const header = smtp.state.messages[0].split('\r\n').find((l) => l.startsWith('Subject: '));
    const match = header.match(/^Subject: =\?UTF-8\?B\?(.+)\?=$/);
    assert.ok(match, `unexpected subject header: ${header}`);
    assert.equal(Buffer.from(match[1], 'base64').toString('utf8'), subject);
  } finally {
    await smtp.close();
  }
});

test('refuses header values with line breaks before connecting', async () => {
  await assert.rejects(
    smtpSend({ ...base, subject: 'Hi\r\nBcc: eve@example.test', body: 'x', host: '127.0.0.1', port: 9 }),
    (err) => err instanceof HttpError && err.status === 422,
  );
});

test('reports a refused recipient as a 502 and sends nothing after it', async () => {
  const smtp = await fakeSmtp();
  smtp.state.refuseOn = 'RCPT';
  try {
    await assert.rejects(
      smtpSend({ ...base, subject: 'Hi', body: 'x', host: '127.0.0.1', port: smtp.port }),
      (err) => err instanceof HttpError && err.status === 502 && /550/.test(err.message),
    );
    assert.equal(smtp.state.messages.length, 0);
    assert.ok(!smtp.state.commands.includes('DATA'));
  } finally {
    await smtp.close();
  }
});

test('reports an unreachable server as a 502', async () => {
  const smtp = await fakeSmtp();
  const port = smtp.port;
  await smtp.close();
  await assert.rejects(
    smtpSend({ ...base, subject: 'Hi', body: 'x', host: '127.0.0.1', port }),
    (err) => err instanceof HttpError && err.status === 502,
  );
});
