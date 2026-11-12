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

test("admits a completed login callback without a subsequent authenticated request", () => {
  const callback = entry("https://www.perplexity.ai/api/auth/callback/google", {});
  callback.response = {
    status: 302,
    headers: [
      {
        name: "Set-Cookie",
        value:
          "__Secure-next-auth.session-token=callback-private-token; Path=/; Secure; HttpOnly; Domain=.perplexity.ai",
      },
    ],
  };
  const rows = extract(har(callback));
  assert.equal(rows.length, 1);
  assert.equal(rows[0].provider, "perplexity-web");
  assert.equal(rows[0].apiKey, "__Secure-next-auth.session-token=callback-private-token");
});

test("joins structured session cookies issued across the same provider's login responses", () => {
  const first = entry("https://grok.com/login", {});
  first.response = {
    status: 200,
    cookies: [{ name: "sso", value: "private-read-session", domain: ".grok.com" }],
  };
  const second = entry("https://grok.com/auth/callback", {});
  second.response = {
    status: 302,
    cookies: [{ name: "sso-rw", value: "private-write-session", domain: "grok.com" }],
  };
  assert.equal(
    extract(har(first, second))[0]?.apiKey,
    "sso=private-read-session; sso-rw=private-write-session"
  );
});

test("rejects failed, masked, unrelated-domain and lookalike login responses", () => {
  const bad = [
    ["https://claude.ai/login", 401, ".claude.ai", "private-session"],
    ["https://claude.ai/login", 200, ".com", "private-session"],
    ["https://claude.ai/login", 200, ".attacker.test", "private-session"],
    ["https://claude.ai.attacker.test/login", 200, ".claude.ai", "private-session"],
    ["https://claude.ai/login", 200, ".claude.ai", "[redacted]"],
  ].map(([url, status, domain, value]) => ({
    ...entry(url, {}),
    response: { status, cookies: [{ name: "sessionKey", value, domain }] },
  }));
  for (const e of bad) assert.deepEqual(extract(har(e)), []);
});

test("a logout or expired callback does not reimport the retired session", () => {
  for (const suffix of ["Max-Age=0", "Expires=Thu, 01 Jan 1970 00:00:00 GMT"]) {
    const logout = entry("https://claude.ai/logout", {});
    logout.response = {
      status: 200,
      headers: [{ name: "set-cookie", value: `sessionKey=; Path=/; ${suffix}` }],
    };
    assert.deepEqual(
      extract(
        har(entry("https://claude.ai/api", { cookie: "sessionKey=private-session" }), logout)
      ),
      []
    );
  }
});
