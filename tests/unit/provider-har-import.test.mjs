import test from "node:test";
import assert from "node:assert/strict";
import { extractWebProviderConnectionsFromHar as extract } from "../../bin/cli/provider-har.mjs";
const entry = (url, headers) => ({
  request: { url, headers: Object.entries(headers).map(([name, value]) => ({ name, value })) },
});
const har = (...entries) => ({ log: { entries } });
test("imports several authenticated HTTP platforms without browser generation", () => {
  const rows = extract(
    har(
      entry("https://claude.ai/api/organizations", { Cookie: "sessionKey=private-session-value" }),
      entry("https://chat.deepseek.com/api/v0/user", {
        Authorization: "Bearer private-deepseek-token",
      }),
      entry("https://www.kimi.com/apiv2/chat", { authorization: "Bearer private-kimi-token" })
    ),
    "evan"
  );
  assert.deepEqual(
    rows.map((r) => r.provider),
    ["claude-web", "deepseek-web", "kimi-web"]
  );
  assert.equal(rows[1].apiKey, "private-deepseek-token");
  assert.equal(rows[0].name, "evan claude-web");
});
test("does not accept lookalike hosts, no-auth routes or masked credentials", () => {
  assert.deepEqual(
    extract(
      har(
        entry("https://chat.deepseek.com.attacker.test/api", {
          authorization: "Bearer private-secret",
        }),
        entry("https://duck.ai/chat", {}),
        entry("https://claude.ai/api", { cookie: "sessionKey=[redacted]" })
      )
    ),
    []
  );
});
test("requires both Grok session cookies", () => {
  assert.equal(
    extract(har(entry("https://grok.com/api", { cookie: "sso=private-session" }))).length,
    0
  );
  assert.equal(
    extract(
      har(
        entry("https://grok.com/api", {
          cookie: "sso=private-session; sso-rw=private-write-session",
        })
      )
    ).length,
    1
  );
});
test("latest usable credential wins and aliases separate accounts", () => {
  const h = har(
    entry("https://chat.deepseek.com/api", { authorization: "Bearer old-private-token" }),
    entry("https://chat.deepseek.com/api", { authorization: "Bearer new-private-token" })
  );
  assert.equal(extract(h)[0].apiKey, "new-private-token");
  assert.notEqual(extract(h, "one")[0].name, extract(h, "two")[0].name);
  assert.throws(() => extract({}), /entries/);
});
