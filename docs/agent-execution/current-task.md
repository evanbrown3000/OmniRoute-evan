# Current agent-execution objective

Treat OmniRoute as the existing foundation. Do not rebuild the gateway, add a competing scheduler, or assume the newest branch is strongest. Compare the current and strongest historical implementations; promote only the best proven path while preserving useful fork-specific capabilities.

## Execution contract

Keep three outcomes distinct:

1. **Inference completion:** a model API returns generated text.
2. **Native agent turn:** a different platform actually executes an agent task and exposes provider-native task identity and terminal completion/readback.
3. **Browser-backed provider workflow:** a real browser session is used, its HAR is captured, and the provider's backend endpoints and request/response behavior are verified.

A queue acknowledgement, accepted request, HTTP 2xx, model completion, tool discovery, or browser page load is not proof of a native agent turn. If an asynchronous provider returns a task ID, wait on that same task until a terminal state. Do not launch duplicate fallback work while the original task remains pending. If a route fails terminally, try a distinct supported provider and report the exact result.

## Current fork/upstream state

The current `release/v3.8.54` fork was compared against `cheaper-inference/OmniRoute:release/v3.8.54`. The fork is **17 commits ahead and 21 commits behind**, with merge base `b71881de3ebb104e3e4962a603df712ffa397eb7`. Earlier divergence counts in this task are stale.

Review upstream-only changes as candidates, not as automatically authoritative. Highest-impact areas include:

- Streaming correctness: #19557 (bounded pending SSE lines and truthful stream summaries), #19205 (separate Responses payloads from metadata buffers), #19503 (executor fixes), and #19545 (direct-path cut-stream cooldown handling).
- Provider semantics and request fidelity: #19035 (Anthropic correlation IDs), #19181 (Bedrock cache points/reasoning effort), #19485 (Codex app-server usage-limit mapping), #19337 (model-import endpoint/capability provenance and vision), #19134 (independent image quota), and #19541 (tool/embedding/search handling).
- Resilience and quota boundaries: #18733 (avoid global 503s on low-stall cgroup reclaim), #19215 (terminated transport errors), and #19165 (caller API-key scope during image fallback).
- Usage and pricing correctness: #19296 (roll up usage before retention), #19501 (aggregate long-context pricing), #19570 (model pricing/alias), and #19463 (usage fixes).

Inspect actual patches and their interaction with the fork's custom A2A/agent-execution workflows. Preserve the fork's useful 17 commits. Do not merge or edit gateway source code in this review run.

## Verified implementation boundary

The source currently exposes two materially different execution paths:

- OmniRoute's local A2A `smart-routing` skill calls its own `/v1/chat/completions` endpoint and returns a text artifact plus routing metadata. The A2A task manager tracks local task lifecycle/state. This is useful gateway orchestration, but it is an inference completion—not evidence that a distinct external agent platform executed a native task.
- The CloudAgent registry contains adapters for Jules, Devin, Codex Cloud, and Cursor Cloud. Their common interface includes `createTask`, `getStatus`, `sendMessage`, `listSources`, and provider-specific approval handling. The Cursor adapter explicitly marks its API contract as awaiting live validation. Adapter code or a configured connection alone is not proof of a successful provider-native turn; verify the external task ID, terminal state, result/activity readback, and beneficiary use.
- The `agent-router-a2a.yml` workflow is a separate external route. Its browser/HAR discovery and Agent Router MCP invocation must be evaluated independently from OmniRoute's local A2A skill server.
- ACP/IDE bridges and local browser sessions may be valuable execution surfaces, but they should not be counted as hosted native-agent turns unless the remote provider itself supplies a task identity and terminal readback.
- Never move account credentials into this public repository. Use the existing account/secret custody boundary and verify only capability state needed for dispatch.

## This run: provider-first native agent review

Use the existing `.github/workflows/agent-router-a2a.yml` route. Start with its real browser surface and capture the HAR for Agent Router pricing, DeepWiki, and the MCP endpoint. Record observed request methods, URLs, status codes, discovered agent-tool names, and input schemas. Do not retain cookies, tokens, authorization headers, or private payloads.

Use the Agent Router MCP endpoint to list tools, discover agents, and actually invoke at least one native agent on a distinct platform. If a task ID is returned, poll that same task until provider-native terminal completion and read back its response. Preserve the workflow's 36% additional-agent cadence. Retain the HAR artifact and distinguish every completed turn from discovery, acknowledgement, inference, or pending work.

Review current public GitHub projects and official free-tier documentation for OpenHands, Kilo, LangGraph, Agno, Graphiti, Letta, Browser Use, Cloudflare Browser Run, Browserbase, Browserless, Daytona, E2B, Modal, Blaxel, AI Horde, n8n, and Dify. Compare native agent execution, durable remote work, browser sessions, actual free capacity, account prerequisites, and completion evidence. Prefer proven free/self-hosted routes where they fit; do not assume a free tier without current primary evidence.

Keep private memory-corpus contents out of this public repository and out of external-agent prompts. Do not create accounts, store credentials, bypass identity verification, billing controls, quotas, or rate limits, or claim any execution that did not occur. Do not run internal tests. Return one evidence-backed long-term architecture recommendation, the strongest existing implementation to promote, the exact provider execution result, and the verified browser/HAR findings.
## Current-turn fallback dispatch

The independent Cloudflare head returned unavailable without a provider-native result readback. Use the existing Agent Router/A2A workflow as the next independent route. Run it once after this update, capture the real browser HAR and backend MCP request/response details, invoke one native external agent, and poll that same task identity to terminal completion and readback. Do not duplicate a task while it remains pending; do not create accounts, reuse passwords, bypass quotas, or modify gateway source code.


## Invocation request — 2026-11-12

Request ID: `gpt6-20261112-omniroute-agent-turn-01`

Run the existing `.github/workflows/agent-router-a2a.yml` workflow for this turn. Execute its real browser/HAR capture and native Agent Router MCP sequence. Invoke at least one distinct-platform native agent; if it returns a task ID, poll that same task to a provider-native terminal state and read back the result. Preserve the existing 36% additional-agent cadence. Record the HAR artifact and exact evidence. This request is not satisfied by a push acknowledgement, queued prompt, HTTP 2xx alone, tool discovery, or inference completion.
