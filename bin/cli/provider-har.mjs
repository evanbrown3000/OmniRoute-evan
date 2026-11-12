/** Extract authenticated website connections from private browser HAR captures. */
export const HAR_IMPORT_REVISION = 2;

const PROVIDERS = [
  { id: "claude-web", hosts: ["claude.ai"], cookie: ["sessionKey"], model: "claude-sonnet-5" },
  {
    id: "perplexity-web",
    hosts: ["www.perplexity.ai", "perplexity.ai"],
    cookie: ["__Secure-next-auth.session-token"],
    model: "pplx-sonar",
  },
  { id: "grok-web", hosts: ["grok.com", "www.grok.com"], cookie: ["sso", "sso-rw"], model: "fast" },
  { id: "deepseek-web", hosts: ["chat.deepseek.com"], bearer: true, model: "deepseek-chat" },
  { id: "kimi-web", hosts: ["www.kimi.ai", "www.kimi.com", "kimi.com"], bearer: true, model: "k3" },
];

function usable(value) {
  return (
    typeof value === "string" &&
    value.length > 8 &&
    !/\*\*\*|\[redacted\]|<redacted>|\[masked\]/i.test(value)
  );
}

function responseCookies(response) {
  if (!(response?.status >= 200 && response.status < 400)) return [];
  const cookies = [...(response.cookies || [])];
  for (const header of response.headers || []) {
    if (header.name?.toLowerCase() !== "set-cookie" || typeof header.value !== "string") continue;
    const [pair, ...attributes] = header.value.split(";");
    const at = pair.indexOf("=");
    if (at < 1) continue;
    const cookie = { name: pair.slice(0, at).trim(), value: pair.slice(at + 1).trim() };
    for (const attribute of attributes) {
      const split = attribute.indexOf("=");
      if (split < 0) continue;
      const key = attribute.slice(0, split).trim().toLowerCase();
      if (["domain", "expires", "max-age"].includes(key)) {
        cookie[key] = attribute.slice(split + 1).trim();
      }
    }
    cookies.push(cookie);
  }
  return cookies;
}

export function extractWebProviderConnectionsFromHar(har, account = "owner") {
  if (!Array.isArray(har?.log?.entries)) throw new Error("HAR log.entries is required");
  if (!/^[A-Za-z0-9_.-]{1,100}$/.test(account)) throw new Error("Invalid account alias");
  const found = new Map();
  const cookieJars = new Map();
  for (const entry of har.log.entries) {
    let url;
    try {
      url = new URL(entry?.request?.url);
    } catch {
      continue;
    }
    if (url.protocol !== "https:") continue;
    const provider = PROVIDERS.find((p) => p.hosts.includes(url.hostname));
    if (!provider) continue;
    const headers = Object.fromEntries(
      (entry.request.headers || [])
        .filter((h) => typeof h.name === "string" && typeof h.value === "string")
        .map((h) => [h.name.toLowerCase(), h.value])
    );
    let credential;
    if (provider.bearer) {
      credential = /^Bearer\s+(.+)$/i.exec(headers.authorization || "")?.[1];
    } else {
      const cookie =
        headers.cookie ||
        (entry.request.cookies || []).map((c) => `${c.name}=${c.value}`).join("; ");
      const pairs = cookieJars.get(provider.id) || new Map();
      cookieJars.set(provider.id, pairs);
      for (const part of cookie.split(";")) {
        const at = part.indexOf("=");
        if (at > 0) pairs.set(part.slice(0, at).trim(), part.slice(at + 1).trim());
      }
      for (const issued of responseCookies(entry.response)) {
        if (typeof issued.name !== "string" || typeof issued.value !== "string") continue;
        const domain = String(issued.domain || url.hostname)
          .replace(/^\./, "")
          .toLowerCase();
        if (
          !provider.hosts.includes(domain) ||
          !(url.hostname === domain || url.hostname.endsWith("." + domain))
        )
          continue;
        const maxAge = issued["max-age"];
        const retired =
          issued.value === "" ||
          (maxAge !== undefined
            ? Number(maxAge) <= 0
            : issued.expires && Date.parse(issued.expires) <= Date.now());
        if (retired) pairs.delete(issued.name);
        else if (usable(issued.value)) pairs.set(issued.name, issued.value);
      }
      if (provider.cookie.every((name) => usable(pairs.get(name)))) {
        credential = [...pairs].map(([name, value]) => `${name}=${value}`).join("; ");
      } else found.delete(provider.id);
    }
    if (!usable(credential)) continue;
    found.set(provider.id, {
      provider: provider.id,
      name: `${account} ${provider.id}`,
      apiKey: credential,
      defaultModel: provider.model,
      providerSpecificData: { onboardingAccountAlias: account, onboardingMethod: "private-har" },
    });
  }
  return [...found.values()];
}
