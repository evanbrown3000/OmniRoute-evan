import test from "node:test";
import assert from "node:assert/strict";

// The internal ingest endpoint receives raw bodies/headers from the standalone
// proxy (server.cjs) over the token-gated loopback. Original credentials must
// survive in the capture. The token must be set
// BEFORE the route module is first imported so getIngestToken() caches it.
const INGEST_TOKEN = "test-ingest-token-1234567890";
process.env.INSPECTOR_INTERNAL_INGEST_TOKEN = INGEST_TOKEN;

const INGEST_URL = "http://localhost:20128/api/tools/traffic-inspector/internal/ingest";

test("ingest preserves bearer tokens and original bodies", async () => {
  const { POST } = await import("@/app/api/tools/traffic-inspector/internal/ingest/route");
  const { globalTrafficBuffer } = await import("@/mitm/inspector/buffer");
  globalTrafficBuffer.clear();

  const SECRET = "sk-supersecret-DEADBEEF0123456789";
  const entry = {
    id: "33333333-3333-4333-8333-333333333333",
    source: "agent-bridge",
    agent: "antigravity",
    timestamp: "2026-06-19T00:00:00.000Z",
    method: "POST",
    host: "daily-cloudcode-pa.googleapis.com",
    path: "/v1internal:streamGenerateContent",
    requestHeaders: {
      authorization: `Bearer ${SECRET}`,
      "content-type": "application/json",
    },
    requestBody: `{"auth":"Bearer ${SECRET}"}`,
    requestSize: 40,
    responseHeaders: { "content-type": "text/event-stream" },
    responseBody: null,
    responseSize: 0,
    status: 200,
    mappedModel: "glm-5.2",
    sourceModel: "gemini-2.5-pro",
  };

  const res = await POST(
    new Request(INGEST_URL, {
      method: "POST",
      headers: { "content-type": "application/json", authorization: `Bearer ${INGEST_TOKEN}` },
      body: JSON.stringify(entry),
    })
  );

  assert.equal(res.status, 200);

  const list = globalTrafficBuffer.list();
  assert.equal(list.length, 1);
  // The captured entry must be present (source/model preserved)...
  assert.equal(list[0].source, "agent-bridge");
  assert.equal(list[0].mappedModel, "glm-5.2");
  // The complete captured header and body survive unchanged.
  const stored = JSON.stringify(list[0]);
  assert.ok(stored.includes(SECRET));
  assert.equal(list[0].requestHeaders.authorization, entry.requestHeaders.authorization);
  assert.equal(list[0].requestBody, entry.requestBody);

  globalTrafficBuffer.clear();
});

test("ingest rejects a wrong token with 403 (and does not buffer)", async () => {
  const { POST } = await import("@/app/api/tools/traffic-inspector/internal/ingest/route");
  const { globalTrafficBuffer } = await import("@/mitm/inspector/buffer");
  globalTrafficBuffer.clear();

  const res = await POST(
    new Request(INGEST_URL, {
      method: "POST",
      headers: { "content-type": "application/json", authorization: "Bearer wrong-token" },
      body: JSON.stringify({ id: "x" }),
    })
  );

  assert.equal(res.status, 403);
  assert.equal(globalTrafficBuffer.list().length, 0);
});

test("ingest preserves capture labels and defaults absent optional bodies", async () => {
  const { POST } = await import("@/app/api/tools/traffic-inspector/internal/ingest/route");
  const { globalTrafficBuffer } = await import("@/mitm/inspector/buffer");
  for (const agent of ["unknown", "ghe-copilot"]) {
    globalTrafficBuffer.clear();
    const entry = {
      id: "33333333-3333-4333-8333-333333333333",
      source: "agent-bridge",
      agent,
      timestamp: "2026-09-21T00:00:00.000Z",
      method: "POST",
      host: "localhost",
      path: "/fixture",
      requestHeaders: {},
      requestSize: 0,
      responseHeaders: {},
      responseSize: 0,
      status: 200,
    };
    const response = await POST(
      new Request(INGEST_URL, {
        method: "POST",
        headers: { "content-type": "application/json", authorization: `Bearer ${INGEST_TOKEN}` },
        body: JSON.stringify(entry),
      })
    );
    assert.equal(response.status, 200);
    const [stored] = globalTrafficBuffer.list();
    assert.equal(stored.agent, agent);
    assert.equal(stored.requestBody, null);
    assert.equal(stored.responseBody, null);
  }
  globalTrafficBuffer.clear();
});
