import test from "node:test";
import assert from "node:assert/strict";
import {
  onboardWebsiteAccount,
  type WebsiteAccountStore,
} from "../../src/lib/skills/onboardWebsiteAccount.ts";

function fixture() {
  const rows: Array<Record<string, unknown> & { id: string; name: string }> = [];
  const store: WebsiteAccountStore = {
    list: async () => rows,
    create: async (data) => {
      const row = { ...data, id: String(rows.length + 1), name: String(data.name) };
      rows.push(row);
      return row;
    },
    update: async (id, data) => {
      const row = rows.find((r) => r.id === id)!;
      Object.assign(row, data);
      return row;
    },
  };
  return { rows, store };
}
const input = {
  provider: "kimi-web",
  account_alias: "new-account",
  credential: "actual-website-session",
  model: "k3",
};

test("agent can register another authenticated platform without receiving management keys", async () => {
  const { rows, store } = fixture();
  const result = await onboardWebsiteAccount(input, { apiKeyId: "agent-key" }, store);
  assert.equal(result.status, "registered");
  assert.equal(rows.length, 1);
  assert.equal(rows[0].provider, "kimi-web");
  assert.equal(JSON.stringify(result).includes(input.credential), false);
});
test("concurrent onboarding of the same account refreshes one connection", async () => {
  const { rows, store } = fixture();
  const results = await Promise.all(
    [1, 2].map(() => onboardWebsiteAccount(input, { apiKeyId: "agent-key" }, store))
  );
  assert.equal(rows.length, 1);
  assert.deepEqual(
    results.map((r) => r.status),
    ["registered", "refreshed"]
  );
});
test("does not admit no-auth or paid API providers or fabricated masked material", async () => {
  const { rows, store } = fixture();
  await assert.rejects(
    onboardWebsiteAccount(
      { ...input, provider: "duckduckgo-web" },
      { apiKeyId: "agent-key" },
      store
    )
  );
  await assert.rejects(
    onboardWebsiteAccount({ ...input, provider: "openai" }, { apiKeyId: "agent-key" }, store)
  );
  await assert.rejects(
    onboardWebsiteAccount({ ...input, credential: "[redacted]" }, { apiKeyId: "agent-key" }, store)
  );
  assert.equal(rows.length, 0);
});
