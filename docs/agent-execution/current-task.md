# Current agent-execution objective

Treat OmniRoute as the existing foundation, not a greenfield rewrite. Review the current source and its strongest historical implementations, then recommend the single best long-term architecture for a provider-independent agent-execution fabric.

The architecture must distinguish three different things:

1. A model inference request that returns a completion.
2. A native agent turn that actually runs on another platform and reaches a provider-native terminal state.
3. A browser-backed provider workflow with a real browser session, captured HAR, and verified backend endpoints.

Prioritize durable native agent invocation, provider-native task IDs and completion readback, browser session persistence, provider health and quota-aware failover, and one canonical graph linking providers, agent turns, browser sessions, HAR captures, and deployment evidence.

Inspect the existing A2A/MCP server, AgentBridge, CloudAgent/ACP integrations, provider-node endpoints, VNC login sessions, browser pool, provider registry, and historical branches. Promote the strongest proven implementation rather than layering a competing framework or starting over.

Research current public GitHub repositories and agent platforms, including OpenHands, Kilo Code, LangGraph, browser-use, and relevant alternatives. Compare genuinely free tiers, signup requirements, native agent capabilities, remote execution, and browser automation. Use official pricing and technical documentation, DeepWiki, and primary GitHub sources.

Actually invoke at least one independent agent on a different platform and wait for its provider-native completion/readback. A queued prompt, accepted request, HTTP acknowledgement, or model completion alone is not a completed agent turn. If an agent route fails, try a distinct supported route and report the exact result. The existing workflow's 36% additional-agent cadence should remain active.

Do not fabricate provider executions, account creation, quotas, sources, or completion states. Do not bypass identity verification, billing controls, provider quotas, or rate limits. Do not store credentials in the repository. Keep this task and all resulting public material free of private memory-corpus contents.

## Current-turn focus

For this run, review the existing cross-platform execution route and strengthen the evidence-backed long-term design. Start with the provider's real browser surface: capture the HAR for Agent Router pricing, DeepWiki, and the MCP endpoint; record actual request methods, URLs, status codes, and tool schemas without retaining secrets or unnecessary private payloads. Then invoke a discovered agent on a distinct platform through its native tool. If it returns a task identifier, wait on that same task until a terminal state; do not launch a duplicate fallback while it remains pending. If the route fails terminally, try a different supported provider. Read back the completed response and retain the HAR artifact.

Research current public GitHub agent runtimes and official free-tier documentation, prioritizing A2A, MCP, OpenHands, Browser Use, LangGraph, Agno, Letta, AI Horde, Kilo, Cloudflare Browser Run, Browserbase, Browserless, Daytona, E2B, Modal, and Blaxel. Compare agent execution, remote compute, browser sessions, free capacity, account prerequisites, and native completion evidence. Prefer existing production-capable implementations and one canonical graph authority; promote the strongest verified historical implementation rather than starting over or layering a competing scheduler.

Keep private memory data isolated. Do not create accounts, store credentials, bypass provider identity checks or quotas, use paid skills, publish commercial listings, or transfer funds. Distinguish completed native agent turns from inference completions, browser sessions, and queued acknowledgements.


## Fresh run focus — 2026-11-12

Independently review the actual agent-execution path in this repository, focusing on `.github/workflows/agent-router-a2a.yml` and the distinct surfaces documented in `docs/frameworks/A2A-SERVER.md`, `docs/frameworks/CLOUD_AGENT.md`, `docs/frameworks/AGENT_PROTOCOLS_GUIDE.md`, and `docs/guides/HEADLESS.md`. Verify which surface can create a genuine native agent turn, which only routes model completions, and how task IDs, provider-native terminal state, and result readback are evidenced. Compare the strongest existing CloudAgent, AgentBridge, A2A, and ACP paths with current public agent runtimes and official free-tier documentation. Recommend one durable execution contract that preserves current ownership boundaries and avoids a second scheduler. The workflow must dispatch at least one independent platform agent, wait for terminal completion/readback, and capture the browser HAR; if it cannot, report the exact failure rather than treating discovery or HTTP acknowledgement as completion. Do not modify repository code or claim actions that did not occur.
