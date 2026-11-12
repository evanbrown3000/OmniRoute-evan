/** Extract authenticated website connections from private browser HAR captures. */
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

export function extractWebProviderConnectionsFromHar(har, account = "owner") {
  if (!Array.isArray(har?.log?.entries)) throw new Error("HAR log.entries is required");
  if (!/^[A-Za-z0-9_.-]{1,100}$/.test(account)) throw new Error("Invalid account alias");
  const found = new Map();
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
      const pairs = new Map(
        cookie.split(";").map((part) => {
          const at = part.indexOf("=");
          return [part.slice(0, at).trim(), part.slice(at + 1).trim()];
        })
      );
      if (provider.cookie.every((name) => usable(pairs.get(name)))) credential = cookie;
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
