# Kilo Code agent route

## Purpose

Provide OmniRoute with a second, independently operated agent-execution route using the open-source Kilo Code CLI and Kilo AI Gateway. This route is separate from Agent Router and is intended for read-only repository review, architecture analysis, and future provider-to-provider delegation.

## Components

- Agent runtime: [Kilo Code CLI](https://github.com/Kilo-Org/kilocode), installed from the published `@kilocode/cli` package.
- Inference gateway: [Kilo AI Gateway](https://kilo.ai/docs/gateway), OpenAI-compatible at `https://ai-gateway.kilo.ai/api/v1`.
- Default free model: `minimax/minimax-m2.1:free`; `z-ai/glm-5:free` and `cohere/north-mini-code:free` are alternatives when listed by the live catalog.
- Custom agent: `.kilo/agents/omniroute-reviewer.md`.
- Remote execution: GitHub Actions hosted runner. No user laptop or local workstation is used.
- Durable execution envelope: GitHub Actions run ID. Preserve Kilo's own session ID and completion IDs separately when returned.

## Access and quota

Kilo Gateway permits unauthenticated requests for free models only. Free model IDs use the `:free` suffix. Anonymous requests are rate-limited to 200 requests per hour per source IP.

This route deliberately uses the legitimate anonymous free tier; it does not create duplicate identities, rotate egress IPs, or bypass provider rate limits. A 429 response is a quota signal: preserve the failure receipt and use an independent provider route rather than multiplying accounts or IPs.

No Kilo account, API key, password, or credential is required for this free-model route. Do not put credentials in this repository.

## Execution

Install and run the agent in a remote runner:

```bash
npm install -g @kilocode/cli
kilo run --auto \
  --agent omniroute-reviewer \
  --model kilocode/minimax/minimax-m2.1:free \
  --format json \
  "Review the supplied OmniRoute task."
```

The reviewer is read-only: edits are denied and shell access is restricted to read-only Git inspection commands. It must cite repository paths and line numbers, and it must not treat a terminal provider state as proof that the task's semantic objective was satisfied.

## Scheduling and ownership

This workflow is an execution target, not a scheduler. Pipeline remains the single owner of recurring work, leases, retries, and durable scheduling. The GitHub Actions workflow exposes `workflow_dispatch` and a branch-scoped initial push trigger; it must not define a cron schedule.

WorkEpisode should eventually store a normalized receipt containing:
- provider and model,
- provider-native Kilo session ID (when available),
- completion ID(s),
- GitHub Actions run ID,
- terminal status,
- response hash and timestamp,
- semantic quality-gate result,
- artifact reference.

GitHub Actions artifacts are evidence transport, not a replacement for WorkEpisode.

## Failure handling

- Model unavailable (e.g. 404): select another currently listed `:free` model.
- Provider 429: do not retry through additional accounts or IPs; retain the failure receipt and let Pipeline apply its retry policy or route to an independent provider.
- Provider 5xx/network error: preserve the error and use an independent provider route.
- Generic or unsupported answer: fail the semantic quality gate even if the provider session ends normally.

## Public references

- Kilo Code repository: https://github.com/Kilo-Org/kilocode
- Kilo CLI: https://kilo.ai/docs/code-with-ai/platforms/cli
- Kilo Gateway: https://kilo.ai/docs/gateway
- Anonymous free-model access and rate limits: https://kilo.ai/docs/gateway/authentication
