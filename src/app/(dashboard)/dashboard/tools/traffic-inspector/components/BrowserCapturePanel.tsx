"use client";
import { useState } from "react";

async function encode(file: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(reader.error);
    reader.onload = () => resolve(String(reader.result).split(",", 2)[1]);
    reader.readAsDataURL(file);
  });
}
export function BrowserCapturePanel({ recording, onStart, onStop }: {
  recording: boolean; onStart: () => void; onStop: () => void;
}) {
  const [provider, setProvider] = useState("chatgpt.com");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [location, setLocation] = useState("");
  async function save(files: File[]) {
    if (!files.length || busy) return;
    setBusy(true); setMessage(""); setLocation("");
    try {
      async function upload(batch: File[]) {
        const payload = { provider, capture_id: crypto.randomUUID(), captured_at: new Date().toISOString(),
          files: await Promise.all(batch.map(async (file) => ({ name: file.name,
            media_type: file.type || "application/octet-stream", content_base64: await encode(file) }))) };
        const response = await fetch("/api/tools/traffic-inspector/browser-captures", {
          method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(payload),
        });
        const result = await response.json();
        if (!response.ok || result.ok !== true) throw new Error(result.error || `Accounts returned HTTP ${response.status}`);
        return result;
      }
      const chunkSize = 4 * 1024 * 1024;
      let result;
      if (files.length <= 16 && files.reduce((sum, file) => sum + file.size, 0) <= 5 * 1024 * 1024) {
        result = await upload(files);
      } else {
        // Read one small Blob slice at a time; large HARs never fill browser/server RAM.
        // A final index preserves original names, byte offsets and every exact stored part.
        const index = { schema: "accounts.browser-capture-parts.v1", provider,
          files: [] as { name: string; bytes: number; media_type: string; parts: unknown[] }[] };
        for (const file of files) {
          const original = { name: file.name, bytes: file.size, media_type: file.type, parts: [] as unknown[] };
          for (let offset = 0; offset < file.size || (offset === 0 && file.size === 0); offset += chunkSize) {
            const part = new File([file.slice(offset, offset + chunkSize)], `${file.name}.part-${offset}`,
              { type: "application/octet-stream" });
            const stored = await upload([part]);
            original.parts.push({ offset, bytes: part.size, repository: stored.repository,
              commit: stored.commit, manifest: stored.manifest, asset: stored.files[0] });
          }
          index.files.push(original);
        }
        result = await upload([new File([JSON.stringify(index, null, 2)], "capture-index.json", { type: "application/json" })]);
      }
      setMessage(`Saved ${files.length} original files in Accounts. Readback verified.`);
      setLocation(`https://github.com/${result.repository}/blob/${result.commit}/${result.manifest}`);
    } catch (error) { setMessage(error instanceof Error ? error.message : String(error)); }
    finally { setBusy(false); }
  }
  async function saveCurrent() {
    try {
      const response = await fetch("/api/tools/traffic-inspector/export.har", { cache: "no-store" });
      if (!response.ok) throw new Error(`Capture export returned HTTP ${response.status}`);
      await save([new File([await response.blob()], `traffic-${Date.now()}.har`, { type: "application/json" })]);
    } catch (error) { setMessage(error instanceof Error ? error.message : String(error)); }
  }
  return <section className="space-y-4 overflow-auto p-4">
    <h2 className="text-lg font-semibold">HAR &amp; browser state</h2>
    <p>Record traffic through the existing capture modes, or import an original browser HAR and storage-state files. Original cookies, authorization headers, tokens and bodies are saved to private Accounts together.</p>
    <label>Provider <input className="ml-2 rounded border p-2" value={provider}
      onChange={(event) => setProvider(event.target.value)} disabled={busy} /></label>
    <div className="flex gap-3">
      <button className="rounded border px-3 py-2" onClick={recording ? onStop : onStart}>
        {recording ? "Stop recording" : "Record traffic"}
      </button>
      <button className="rounded border px-3 py-2" disabled={busy} onClick={() => void saveCurrent()}>Save current HAR to Accounts</button>
    </div>
    <label className="block">Import original HAR / browser state — automatically saves to Accounts
      <input className="mt-2 block" type="file" multiple disabled={busy}
        onChange={(event) => { void save(Array.from(event.target.files || [])); event.target.value = ""; }} />
    </label>
    <p role="status">{busy ? "Saving original capture to Accounts…" : message}</p>
    {location && <a className="underline" href={location} target="_blank" rel="noreferrer">Open stored capture manifest</a>}
    <p>The browser capture engine is owned by browser-automation. This tab does not open, replace, log out or modify a Chrome profile.</p>
  </section>;
}
