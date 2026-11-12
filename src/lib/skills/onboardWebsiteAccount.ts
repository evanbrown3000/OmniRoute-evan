import { z } from "zod";

export const websiteAccountSchema = z
  .object({
    provider: z.enum(["claude-web", "perplexity-web", "deepseek-web", "kimi-web", "grok-web"]),
    account_alias: z.string().regex(/^[A-Za-z0-9_.-]{1,100}$/),
    credential: z.string().min(9).max(100_000),
    model: z.string().min(1).max(200),
    recovery_url: z.string().url().optional(),
  })
  .strict();

type Connection = Record<string, unknown> & { id: string; name: string };
export interface WebsiteAccountStore {
  list(provider: string): Promise<Connection[]>;
  create(data: Record<string, unknown>): Promise<Connection>;
  update(id: string, data: Record<string, unknown>): Promise<Connection>;
}

const lockKey = Symbol.for("omniroute.websiteAccountRegistration");
const holder = globalThis as typeof globalThis & { [lockKey]?: Map<string, Promise<unknown>> };
const pending = (holder[lockKey] ??= new Map());

async function defaultStore(): Promise<WebsiteAccountStore> {
  const db = await import("../db/providers");
  return {
    list: async (provider) => (await db.getProviderConnections({ provider })) as Connection[],
    create: async (data) => (await db.createProviderConnection(data)) as Connection,
    update: async (id, data) => (await db.updateProviderConnection(id, data)) as Connection,
  };
}

/** Register real website credentials; fleet admission owns qualification and recurrence. */
export async function onboardWebsiteAccount(
  input: Record<string, unknown>,
  context: { apiKeyId: string },
  store?: WebsiteAccountStore
): Promise<Record<string, unknown>> {
  const parsed = websiteAccountSchema.parse(input);
  if (/\*\*\*|\[redacted\]|<redacted>/i.test(parsed.credential)) {
    throw new Error("An actual authenticated website credential is required");
  }
  const name = `${parsed.account_alias} ${parsed.provider}`;
  const key = `${parsed.provider}:${parsed.account_alias}`;
  const task = (pending.get(key) || Promise.resolve())
    .catch(() => undefined)
    .then(async () => {
      const owner = store || (await defaultStore());
      const matches = (await owner.list(parsed.provider)).filter((row) => row.name === name);
      if (matches.length > 1) throw new Error("Account alias matches more than one connection");
      const previous = matches[0];
      const priorData = previous?.providerSpecificData;
      const providerSpecificData = {
        ...(priorData && typeof priorData === "object" ? priorData : {}),
        onboardingAccountAlias: parsed.account_alias,
        onboardedByKey: context.apiKeyId,
        onboardingMethod: "agent-skill",
        ...(parsed.recovery_url ? { recoveryUrl: parsed.recovery_url } : {}),
      };
      const update = {
        apiKey: parsed.credential,
        defaultModel: parsed.model,
        providerSpecificData,
      };
      const connection = previous
        ? await owner.update(previous.id, update)
        : await owner.create({
            ...update,
            name,
            provider: parsed.provider,
            authType: "apikey",
            isActive: true,
          });
      return {
        status: previous ? "refreshed" : "registered",
        connection_id: connection.id,
        provider: parsed.provider,
        account_alias: parsed.account_alias,
        next_step:
          "Independent fleet worker will qualify an actual turn and publish its result to Slack",
      };
    });
  pending.set(key, task);
  try {
    return await task;
  } finally {
    if (pending.get(key) === task) pending.delete(key);
  }
}
