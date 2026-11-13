import assert from 'node:assert/strict';
import { readFileSync, readdirSync, existsSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import test from 'node:test';
import { toHar } from '../src/lib/inspector/harExport.ts';
import { captureHeaders } from '../src/mitm/captureHeaders.ts';

const root = dirname(dirname(fileURLToPath(import.meta.url)));
const capturePaths = [
  'src/mitm/server.cjs', 'src/mitm/captureHeaders.ts', 'src/mitm/inspector', 'src/mitm/tproxy',
  'src/mitm/handlers', 'src/lib/inspector', 'src/lib/db/inspectorSessions.ts',
  'src/app/api/tools/traffic-inspector',
  'src/app/(dashboard)/dashboard/tools/traffic-inspector',
];
function* sources(path) {
  if (!existsSync(path)) return;
  const entries = readdirSync(path, { withFileTypes: true });
  for (const entry of entries) {
    const full = join(path, entry.name);
    if (entry.isDirectory()) yield* sources(full);
    else if (/\.(?:[cm]?[jt]sx?|py)$/.test(entry.name)) yield full;
  }
}
function violations(text) {
  // Error-display formatting does not transform captured headers or bodies.
  const code = text.replace(/\bsanitizeErrorMessage\b/g, 'formatError');
  return code.split('\n').flatMap((line, index) =>
    /\b(?:maskSecret\w*|sanitize\w*|redact\w*|scrub\w*)\s*(?:\(|:|=)|\b(?:redact|sanitize|maskSecrets)\s*\}/i.test(line)
      && !/^\s*(?:\/\/|\*|\/\*)/.test(line)
      ? [`${index + 1}: ${line.trim()}`] : []);
}
test('capture code cannot introduce sanitization, redaction or masking', () => {
  const failures = [];
  for (const relative of capturePaths) {
    const absolute = join(root, relative);
    const files = /\.[a-z]+$/i.test(relative) ? [absolute] : sources(absolute);
    for (const file of files) {
      for (const failure of violations(readFileSync(file, 'utf8'))) failures.push(`${file}: ${failure}`);
    }
  }
  assert.deepEqual(failures, [],
    'DENIED: sanitization/redaction in browser capture destroys the private state needed for authenticated HTTP.\n' + failures.join('\n'));
});
test('the policy rejects newly added capture redactors', () => {
  for (const code of ['maskSecret(value)', 'sanitizeHeaders(headers)', 'redact: true', 'scrubCookies(input)']) {
    assert.ok(violations(code).length, code);
  }
});
test('HAR retains complete headers, cookies, token-bearing URLs and both bodies', () => {
  const headers = { Authorization: 'Bearer owner-secret-test', Cookie: 'session=abc==; device=xyz',
    Host: 'chatgpt.com', 'X-Custom': 'unlisted-test-value' };
  const responseHeaders = { 'Set-Cookie': ['session=updated==; HttpOnly; Secure', 'other=two; Path=/'],
    Location: 'https://chatgpt.com/cb?token=redirect-test' };
  const requestBody = JSON.stringify({ token: 'sk-owner-test', nested: { secret: 'eyJ.owner.test' }, padding: 'x'.repeat(1048580) });
  const responseBody = 'data: {"accessToken":"private-response-test"}\n\ndata: [DONE]\n\n';
  const capture = { id: 'capture-test', timestamp: '2026-11-13T00:00:00.000Z', source: 'http-proxy',
    method: 'POST', host: 'chatgpt.com', path: '/backend-api/conversation?token=query-test&x=1&x=2',
    requestHeaders: captureHeaders(headers), responseHeaders: captureHeaders(responseHeaders),
    requestBody, responseBody, requestSize: requestBody.length, responseSize: responseBody.length,
    status: 200, totalLatencyMs: 1 };
  const entry = toHar([capture]).log.entries[0];
  for (const [name, value] of Object.entries(headers)) assert.equal(entry.request.headers.find(h => h.name === name)?.value, value);
  assert.equal(entry.request.postData.text, requestBody);
  assert.equal(entry.response.content.text, responseBody);
  assert.equal(entry.request.cookies.find(c => c.name === 'session')?.value, 'abc==');
  assert.equal(entry.response.headers.filter(h => h.name === 'Set-Cookie').length, 2);
  assert.deepEqual(entry.request.queryString.filter(q => q.name === 'x').map(q => q.value), ['1', '2']);
  assert.equal(entry.response.redirectURL, responseHeaders.Location);
  assert.equal(capture.requestBody, requestBody);
});
