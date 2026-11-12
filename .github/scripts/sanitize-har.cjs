"use strict";

// Reusable HAR minimizer for production browser evidence.
// Retain endpoint shape, methods, status and timing; never retain cookies,
// header values, query values, request bodies, response bodies or page titles.

const fs = require("node:fs");
const crypto = require("node:crypto");

function safeUrl(raw) {
  try {
    const url = new URL(String(raw || ""));
    const queryNames = [...new Set([...url.searchParams.keys()])].slice(0, 80);
    url.username = "";
    url.password = "";
    url.search = "";
    url.hash = "";
    url.pathname = url.pathname
      .split("/")
      .map((part) => (/^[A-Za-z0-9_-]{40,}$/.test(part) || part.length > 100 ? "[redacted]" : part))
      .join("/");
    return {
      url: url.toString(),
      queryString: queryNames.map((name) => ({ name: name.slice(0, 120), value: "[redacted]" })),
    };
  } catch {
    return { url: "[redacted-url]", queryString: [] };
  }
}

function safeHeaders(headers) {
  if (!Array.isArray(headers)) return [];
  return headers
    .filter((header) => header && typeof header.name === "string")
    .slice(0, 160)
    .map((header) => ({ name: header.name.slice(0, 160), value: "[redacted]" }));
}

function sanitizeEntry(entry, counters) {
  const request = entry?.request || {};
  const response = entry?.response || {};
  const safeRequestUrl = safeUrl(request.url);
  const safeRedirect = response.redirectURL ? safeUrl(response.redirectURL).url : "";

  counters.cookiesRemoved += (request.cookies?.length || 0) + (response.cookies?.length || 0);
  counters.requestBodiesRemoved += request.postData ? 1 : 0;
  counters.responseBodiesRemoved += response.content?.text ? 1 : 0;
  counters.headerValuesRedacted += (request.headers?.length || 0) + (response.headers?.length || 0);

  const clean = {
    startedDateTime: entry?.startedDateTime,
    time: Number.isFinite(entry?.time) ? entry.time : -1,
    request: {
      method: String(request.method || "GET").slice(0, 24),
      url: safeRequestUrl.url,
      httpVersion: String(request.httpVersion || "").slice(0, 32),
      headers: safeHeaders(request.headers),
      queryString: safeRequestUrl.queryString,
      cookies: [],
      headersSize: Number.isFinite(request.headersSize) ? request.headersSize : -1,
      bodySize: Number.isFinite(request.bodySize) ? request.bodySize : -1,
    },
    response: {
      status: Number.isInteger(response.status) ? response.status : 0,
      statusText: String(response.statusText || "").slice(0, 120),
      httpVersion: String(response.httpVersion || "").slice(0, 32),
      headers: safeHeaders(response.headers),
      cookies: [],
      content: {
        size: Number.isFinite(response.content?.size) ? response.content.size : -1,
        mimeType: String(response.content?.mimeType || "application/octet-stream").slice(0, 120),
        ...(Number.isFinite(response.content?.compression) ? { compression: response.content.compression } : {}),
      },
      redirectURL: safeRedirect,
      headersSize: Number.isFinite(response.headersSize) ? response.headersSize : -1,
      bodySize: Number.isFinite(response.bodySize) ? response.bodySize : -1,
    },
    cache: {},
    timings: {
      blocked: Number.isFinite(entry?.timings?.blocked) ? entry.timings.blocked : -1,
      dns: Number.isFinite(entry?.timings?.dns) ? entry.timings.dns : -1,
      connect: Number.isFinite(entry?.timings?.connect) ? entry.timings.connect : -1,
      send: Number.isFinite(entry?.timings?.send) ? entry.timings.send : -1,
      wait: Number.isFinite(entry?.timings?.wait) ? entry.timings.wait : -1,
      receive: Number.isFinite(entry?.timings?.receive) ? entry.timings.receive : -1,
      ssl: Number.isFinite(entry?.timings?.ssl) ? entry.timings.ssl : -1,
    },
  };

  if (typeof entry?.pageref === "string") clean.pageref = entry.pageref.slice(0, 120);
  if (typeof entry?._resourceType === "string") clean._resourceType = entry._resourceType.slice(0, 40);
  return clean;
}

function sanitizeHarFile(filePath) {
  if (typeof filePath !== "string" || !filePath) throw new TypeError("har_path_required");
  const parsed = JSON.parse(fs.readFileSync(filePath, "utf8"));
  if (!parsed || typeof parsed !== "object" || !parsed.log || !Array.isArray(parsed.log.entries)) {
    throw new TypeError("valid_har_log_entries_required");
  }

  const counters = {
    cookiesRemoved: 0,
    requestBodiesRemoved: 0,
    responseBodiesRemoved: 0,
    headerValuesRedacted: 0,
  };
  const originalEntries = parsed.log.entries;
  const cleanEntries = originalEntries.map((entry) => sanitizeEntry(entry, counters));
  const endpoints = [...new Set(cleanEntries.map((entry) => {
    try {
      const url = new URL(entry.request.url);
      return entry.request.method + " " + url.host + url.pathname + " -> " + entry.response.status;
    } catch {
      return entry.request.method + " [redacted-url] -> " + entry.response.status;
    }
  }))].sort();

  parsed.log.entries = cleanEntries;
  if (Array.isArray(parsed.log.pages)) {
    parsed.log.pages = parsed.log.pages.map((page) => ({
      startedDateTime: page.startedDateTime,
      id: typeof page.id === "string" ? page.id.slice(0, 120) : "",
      pageTimings: {
        onContentLoad: Number.isFinite(page.pageTimings?.onContentLoad) ? page.pageTimings.onContentLoad : -1,
        onLoad: Number.isFinite(page.pageTimings?.onLoad) ? page.pageTimings.onLoad : -1,
      },
    }));
  }
  parsed.log.comment = undefined;

  const output = JSON.stringify(parsed);
  fs.writeFileSync(filePath, output + "\n", { encoding: "utf8", mode: 0o600 });
  try { fs.chmodSync(filePath, 0o600); } catch {}
  const digest = crypto.createHash("sha256").update(output + "\n").digest("hex");
  return {
    schema: "cognilode.har.sanitized.v1",
    entry_count: cleanEntries.length,
    endpoint_count: endpoints.length,
    endpoints,
    sha256: digest,
    file_bytes: Buffer.byteLength(output + "\n"),
    redactions: counters,
    retained: ["method", "host", "path", "query_parameter_names", "header_names", "status", "mime_type", "timings"],
    removed: ["cookie_values", "header_values", "query_values", "request_bodies", "response_bodies", "page_titles", "page_urls", "comments"],
  };
}

async function finalizeHarCapture({ context, browser, filePath }) {
  let closeError = null;
  if (context && typeof context.close === "function") {
    try { await context.close(); } catch (error) { closeError = error; }
  }
  if (browser && typeof browser.close === "function") {
    try { await browser.close(); } catch (error) { closeError = closeError || error; }
  }
  if (closeError) {
    throw new Error("browser_capture_finalize_failed: " + String(closeError).slice(0, 300));
  }
  if (typeof filePath !== "string" || !fs.existsSync(filePath)) {
    throw new Error("har_missing_after_context_close: " + String(filePath || ""));
  }
  return sanitizeHarFile(filePath);
}

module.exports = { sanitizeHarFile, finalizeHarCapture };
