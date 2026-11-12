# Active execution objective — 2026-11-13

**Request ID:** `gpt6-20261113-omniroute-federation-review-02`  
**State:** active  
**Predecessor:** archived at `docs/agent-execution/history/2026-11-13-current-task-predecessor.md`

## Mission

Perform an independent, source-backed architecture review of OmniRoute and the wider federated agent system. The target is the owner-selected **Variant C: federated capability and session composition**. Preserve the best existing implementation and promote stronger historical components selectively; do not start over, build a parallel orchestrator, or mistake a queue for an executed agent turn.

## Mandatory execution for this task

1. Use the existing remote GitHub Actions browser runner to execute a real agent turn on the Agent Router platform. Do not merely enqueue a prompt.
2. Capture a fresh, sanitized HAR for the public Agent Router/MCP interaction. Identify the actual MCP endpoint, request/response methods, tool schemas, and backend API routes. Never include cookies, authorization values, private session state, or secret material in artifacts.
3. Perform a genuine cross-platform A2A handoff when a free/no-signup agent is available. Discover candidates first; select a substantive free capability, avoid paid/x402 skills, and record the endpoint, request, response, context/task identifiers, and terminal state. A queue acknowledgement is not completion. If no task ID is exposed, state that limitation explicitly and require the strongest available independent terminal readback.
4. Record whether the 36% secondary-agent branch was selected, which agent was actually invoked, and whether its provider-native turn completed. Do not claim a secondary handoff when the branch was not selected or the provider failed.
5. If a genuinely new free-tier provider account is needed to add an independent capability, identify the exact onboarding route through the Accounts and browser-session owners. Only proceed through those owners with encrypted credential custody and a verified native session. Never reuse a password, place credentials in this public repository, or leave an unverified account counted as capacity. If that route is unavailable, document the precise blocker and continue with another existing free route.

## Canonical ownership boundaries

- **Pipeline:** the single recurring-work scheduler and authority for leases, retries, stage execution and original-effect readback.
- **WorkEpisode:** durable assignment/turn identity, child assignments, handoff decisions and continuation state.
- **B4PT0R:** provider-native agent execution, authenticated provider session, exact submission, stream observation and terminal provider response.
- **ComputerUseX:** finite browser/computer interaction, provider login/session acquisition, HAR/recording and browser postcondition evidence.
- **Accounts:** account identity, credential custody, device-bound grants, revisions and recovery.
- **Networks:** physical resource graph, account/quota/egress failure domains, placement, capability qualification, reclaim and repurpose.
- **OmniRoute:** inference routing and MCP/A2A transport adapters; it must not become a second scheduler or the canonical assignment store.

Use the existing typed hosted-agent execution contract `agent.execute@1.0.0` and the existing WorkEpisode turn-action/handoff interfaces where they are already implemented. Preserve the sequence `admit → capacity → prepare → submit → observe → consume`. Do not duplicate these owners' responsibilities.

## Review scope

1. Compare `release/v3.8.54` with the strongest historical OmniRoute implementation, especially `agent-router-a2a-20261112-06`. Identify the exact improvements worth promoting and the divergence that makes a wholesale branch merge unsafe.
2. Compare the historical deterministic SHA-256 36% secondary-agent selection with the current random selection. Recommend where the durable decision belongs and how it binds to WorkEpisode identity so retries cannot change the decision.
3. Define proof of a real native agent handoff: provider-native task/context identity, accepted/running state, terminal state, response payload, and independent readback. Distinguish synchronous completion, queued work, provider failure, and a completed task.
4. Show how OmniRoute's A2A/MCP adapter participates in WorkEpisode and Pipeline without becoming a second scheduler, queue, task database, account vault, or agent loop.
5. Compare current public agent runtimes and execution platforms using public GitHub repositories and official documentation. At minimum evaluate OpenHands, Agno, LangGraph, Letta, Cloudflare Agents/Browser Rendering, Browserbase, Browserless, Daytona, E2B, Modal, Kilo and Agent Router. Distinguish recurring free allocations from one-time credits, anonymous/no-signup access from actual accounts, and model/API access from a hosted agent runtime.
6. Recommend the next genuinely useful provider/node to onboard, based on independent capability and failure-domain value—not account count alone. Include its free allocation, account prerequisites, deployment shape, credential-custody path, and how it becomes available to every compatible agent/node.
7. Define a reclaimable node contract: declared purpose, capability, provider/account, quota, cost, egress/network failure domain, source/version, health and native postcondition, lease/reclaim rules, and idempotent rebuild from modular components.
8. Explain how browser acquisition and HAR evidence flow through ComputerUseX, Accounts, Networks and Pipeline. A successful HTTP response, page load, click, screenshot, or queued prompt alone is not proof of a useful capability.

## Required deliverable

Return one recommended target architecture and an ordered migration/deployment sequence—not competing designs. Include:

- Current versus historical source-backed findings with exact paths and line references.
- The best historical implementation to promote, with the specific components to preserve.
- The first highest-leverage integration seam and the owner that should implement it.
- A durable handoff state machine and acceptance criteria.
- The free-tier provider matrix, with recurring versus one-time resources and official source links.
- Fresh HAR/backend-route evidence and the actual A2A/provider terminal readback.
- The next provider account/node recommendation and its complete onboarding/reclaim contract.
- Current blockers, alternate execution routes, and explicit unknowns. Do not infer success from HTTP 200 or a workflow conclusion alone.

## Guardrails

Use public web sources for public research and the existing project repositories for implementation evidence. Do not access, copy, or publish private credentials, cookies, personal identities, private HAR, or recovery bundles. Do not make paid purchases, send outreach, or create duplicate accounts merely to increase counts. Preserve historical artifacts and source lineage. Do not ask the owner to repeat information already present in the project context.
