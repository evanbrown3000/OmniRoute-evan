import test from "node:test";
import assert from "node:assert/strict";
import { captureHeaders } from "../../src/mitm/captureHeaders.ts";

test("capture retains all original header names and credentials", () => {
  const original = { Cookie: "session=short; csrf=also-short", Authorization: "Bearer sk-owner-test",
    Host: "chatgpt.com", "proxy-authorization": "Basic original-test", "content-length": "12" };
  assert.deepEqual(captureHeaders(original), original);
});
test("duplicate response cookies remain individually recoverable", () => {
  const cookies = ["session=abc==; HttpOnly", "csrf=original; Secure"];
  assert.deepEqual(captureHeaders({ "Set-Cookie": cookies }), { "Set-Cookie": cookies.join("\n") });
});
test("undefined headers are absent; present empty values remain", () => {
  assert.deepEqual(captureHeaders({ missing: undefined, empty: "" }), { empty: "" });
});
