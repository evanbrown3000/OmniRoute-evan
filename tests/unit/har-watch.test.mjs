import test from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, writeFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { scanHarDirectory } from "../../bin/cli/har-watch.mjs";
test("new captures import once, changed captures refresh, failures do not gate other files", async () => {
  const dir = mkdtempSync(join(tmpdir(), "omniroute-har-watch-"));
  try {
    writeFileSync(join(dir, "a.har"), "first");
    writeFileSync(join(dir, "b.har"), "second");
    const state = {};
    const calls = [];
    const importer = async (path) => {
      calls.push(path);
      return path.endsWith("a.har") ? 1 : 0;
    };
    await scanHarDirectory(dir, state, importer, 100);
    assert.equal(calls.length, 2);
    assert.equal(state["b.har"].ok, true);
    await scanHarDirectory(dir, state, importer, 200);
    assert.equal(calls.length, 2);
    writeFileSync(join(dir, "b.har"), "refreshed");
    await scanHarDirectory(dir, state, importer, 300);
    assert.equal(calls.length, 3);
    await scanHarDirectory(dir, state, importer, 300_101);
    assert.equal(calls.length, 4);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});
