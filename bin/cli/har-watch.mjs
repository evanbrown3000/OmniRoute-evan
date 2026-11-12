import { createHash } from "node:crypto";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { writePrivateFileAtomic } from "./private-file.mjs";

/** Watch captured credentials, not provider generation: each worker owns its timer. */
export async function scanHarDirectory(directory, state, importFile, now = Date.now()) {
  const files = readdirSync(directory).filter((file) => file.endsWith(".har"));
  const results = [];
  for (const file of files) {
    const path = join(directory, file);
    if (!statSync(path).isFile()) continue;
    const hash = createHash("sha256").update(readFileSync(path)).digest("hex");
    const previous = state[file];
    if (previous?.hash === hash && (previous.ok || previous.retryAfter > now)) continue;
    try {
      const code = await importFile(path);
      state[file] = { hash, ok: code === 0, retryAfter: code === 0 ? 0 : now + 300_000 };
      results.push({ file, code });
    } catch {
      state[file] = { hash, ok: false, retryAfter: now + 300_000 };
      results.push({ file, code: 1 });
    }
  }
  return results;
}

export async function watchHarDirectory(directory, importFile) {
  const checkpoint = join(directory, ".omniroute-har-import-state.json");
  let state = {};
  try {
    state = JSON.parse(readFileSync(checkpoint, "utf8"));
  } catch {}
  let stopped = false;
  const stop = () => {
    stopped = true;
  };
  process.once("SIGTERM", stop);
  process.once("SIGINT", stop);
  try {
    while (!stopped) {
      const results = await scanHarDirectory(directory, state, importFile);
      if (results.length) {
        writePrivateFileAtomic(checkpoint, JSON.stringify(state));
        console.log(JSON.stringify({ component: "har-onboarding", results }));
      }
      await new Promise((resolve) => setTimeout(resolve, 2000));
    }
  } finally {
    process.removeListener("SIGTERM", stop);
    process.removeListener("SIGINT", stop);
  }
  return 0;
}
