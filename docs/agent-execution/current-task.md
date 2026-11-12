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