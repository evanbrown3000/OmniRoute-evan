import { test } from "node:test";
import assert from "node:assert/strict";
import { perplexity_webProvider } from "../../open-sse/config/providers/registry/perplexity/web/index.ts";
import { checkToolCallingRequiredButUnsupported } from "../../open-sse/handlers/chatCore/toolCallingRequiredCheck.ts";
import { filterTargetsByRequestCompatibility } from "../../open-sse/services/combo/comboStructure.ts";
import { stripUnsupportedParams } from "../../open-sse/handlers/chatCore/unsupportedParamsStrip.ts";
import { getUnsupportedParams } from "../../open-sse/config/providerRegistry.ts";
import type { ResolvedComboTarget } from "../../open-sse/services/combo/types.ts";

function buildResolvedTarget(provider: string, model: string): ResolvedComboTarget {
  return {
    kind: "model",
    stepId: `${provider}-step`,
    executionKey: `${provider}-step:0`,
    modelStr: `${provider}/${model}`,
    provider,
    providerId: null,
    connectionId: null,
    weight: 1,
    label: null,
  };
}

test("Perplexity preserves tool controls for its existing executor emulation", () => {
  assert.ok(perplexity_webProvider.models.every((model) => model.toolCalling === false));
  assert.ok(
    !perplexity_webProvider.unsupportedParams?.includes("tools"),
    "tools must reach the emulation adapter"
  );
  assert.ok(
    !perplexity_webProvider.unsupportedParams?.includes("tool_choice"),
    "tool_choice must reach the emulation adapter"
  );
  assert.ok(
    !perplexity_webProvider.unsupportedParams?.includes("parallel_tool_calls"),
    "parallel_tool_calls must reach the emulation adapter"
  );
});

test("direct requests can reach the existing emulated tool path", () => {
  const model = "pplx-sonar";
  const provider = "perplexity-web";
  const unsupported = getUnsupportedParams(provider, model);

  // 1. tools array
  const checkTools = checkToolCallingRequiredButUnsupported(
    { model, tools: [{ type: "function", function: { name: "test" } }] },
    unsupported,
    false,
    model
  );
  assert.equal(checkTools.blocked, false);
  assert.equal(checkTools.message, undefined);
});

test("combo routing retains emulated tools for the executor instead of silently discarding them", () => {
  // Real ResolvedComboTarget shape, as produced by the routing layer.
  const candidateTargets: ResolvedComboTarget[] = [
    buildResolvedTarget("openai", "gpt-4"),
    buildResolvedTarget("perplexity-web", "pplx-sonar"),
  ];

  const bodyWithTools = {
    model: "auto",
    messages: [{ role: "user", content: "hello" }],
    tools: [{ type: "function", function: { name: "test" } }],
  };

  // filterTargetsByRequestCompatibility deliberately keeps `toolCalling: "emulated"`
  // providers (web-cookie.ts, #5240) eligible even when the request carries `tools`,
  // so this pre-filter alone does NOT drop perplexity-web from the candidate list —
  // both targets stay.
  const filteredWithTools = filterTargetsByRequestCompatibility(
    candidateTargets,
    bodyWithTools,
    console
  );
  assert.equal(filteredWithTools.length, 2);
  assert.ok(filteredWithTools.some((target) => target.provider === "perplexity-web"));

  const bodyNoTools = {
    model: "auto",
    messages: [{ role: "user", content: "hello" }],
  };
  const filteredNoTools = filterTargetsByRequestCompatibility(
    candidateTargets,
    bodyNoTools,
    console
  );
  assert.equal(filteredNoTools.length, 2);

  // The executor turns definitions into its existing tool contract and parses
  // the returned calls. Dropping them here would silently disable that path.
  const unsupported = getUnsupportedParams("perplexity-web", "pplx-sonar");
  const translatedBody: Record<string, unknown> = { ...bodyWithTools };
  const { strippedParams } = stripUnsupportedParams(translatedBody, unsupported);
  assert.ok(!strippedParams.includes("tools"));
  assert.deepEqual(translatedBody.tools, bodyWithTools.tools);
});
