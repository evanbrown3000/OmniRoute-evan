# Federated Agent System: Promotion and Expansion Plan

**Date:** 2026-11-13  
**Promotion candidate:** `agent-router-a2a-20261113-01`  
**Historical base:** `agent-router-a2a-20261112-06`

## Executive decision

Promote the historical implementation 06 as the starting point, not the reduced release workflow. Keep the new branch as a promotion candidate until an independent source-backed review is complete.

The new branch corrects a systemic lifecycle defect: provider completion was being overridden by ordinary response prose containing the word `PENDING`. Provider-declared state or an anchored `STATUS`/`STATE` line is now authoritative. The same provider task ID remains the resume key; the change does not create a duplicate primary task.

Do not merge this branch merely because the live run succeeded. First verify the workflow diff, the task receipt, and the owner-boundary integration described below.

## Verified live execution

GitHub Actions run: https://github.com/evanbrown3000/OmniRoute-evan/actions/runs/43273485410

- The previously created TaskPlanner task `a356742a-afb0-4f57-9d5d-f96a1e5634eb` was resumed by the same ID and read back as `COMPLETED`.
- Terminal evidence source: `provider-status-line`; HTTP 200; the response's unrelated discussion of pending work no longer overrides the terminal state.
- The deterministic 36% secondary branch was selected: request ID `gpt6-20261112-omniroute-federation-live-12-readback`, hash bucket 17, selected=true.
- The secondary FirstPrinciplesAnalyst task `2af10988-1ed6-48c1-b1d7-db60cc6d0afe` completed with HTTP 200.
- The secondary response was not a source-backed repository review; it explicitly said it could not inspect the live repository. Count the provider-native turn as executed, but do not treat its conclusions as verified code review.
- The external Lordevo Shop A2A call returned HTTP 200 and a completed context, `0809c313-8c79-4b23-a2b8-b7cfde90dc18`. Its response reported that the GitHub URL was blocked by `robots_disallowed`. This is a completed cross-platform transport/context receipt, not a successful source inspection.
- Browser discovery returned 30 agent records and 24 tool names. The pricing page reported $0 and no signup.
- Sanitized HAR artifact: https://github.com/evanbrown3000/OmniRoute-evan/actions/runs/43273485410
  - 45 entries.
  - 3 successful `POST https://shop.lordevo.com/mcp-http/mcp` requests (HTTP 200).
  - 1 successful `GET https://shop.lordevo.com/pricing` request (HTTP 200).
  - 0 request headers, 0 response headers, 0 cookies, and 0 captured post bodies in the sanitized HAR.
- A2A endpoint used: `https://shop.lordevo.com/a2a`. The browser HAR captures the browser-origin MCP calls; the Node-side A2A request is separately represented in the workflow's sanitized MCP trace.

The HAR is evidence of the observed HTTP route and status codes, not a complete record of all Node-side provider traffic. Keep the separate MCP trace and its request/response hashes.

## Ownership model

Keep the existing subsystem boundaries. Do not add another scheduler or a parallel durable ledger.

| Subsystem | Sole responsibility | Required evidence |
|---|---|---|
| Pipeline | Recurrence, lease ownership, retries, effect readback, cursor advancement | Lease ID, attempt ID, terminal effect readback |
| WorkEpisode | Durable assignment/turn record, parent-child handoffs, result and continuation receipts | AssignmentEpisode ID, native task ID, parent ID, state source, terminal state, artifact refs |
| B4PT0R | Provider-native execution and provider session/task lifecycle | Provider-native task/session ID and terminal readback |
| ComputerUseX | Browser session ownership, capture, sanitized HAR, browser action receipts | Browser session ID, HAR hash, observed endpoint list |
| Accounts | Encrypted credential custody and access references | Credential/access reference; never plaintext secret |
| Networks | Capability-qualified remote nodes, independent provider quotas, resource admission | Provider/account identity, capability, quota scope, health and execution receipt |
| OmniRoute | MCP/A2A routing and cross-platform agent handoffs | Agent identity, A2A context/task ID, parent-child relation |

### Target execution path

1. Pipeline claims a due item and owns its lease, retry policy, and final effect readback.
2. WorkEpisode creates or resumes the durable AssignmentEpisode using a stable idempotency key.
3. Networks selects a qualified node based on capability, region, quota, and health—not merely an account's existence.
4. Accounts resolves an `access_ref` for the selected provider. Raw credentials never enter prompts, task records, HAR files, or logs.
5. B4PT0R starts a provider-native turn and records the provider's task/session ID.
6. ComputerUseX owns browser sessions and produces sanitized HAR plus endpoint/action receipts.
7. OmniRoute performs agent-to-agent handoffs. Every child agent gets a durable child WorkEpisode linked to its parent.
8. WorkEpisode records provider state, state source, task/context IDs, response hash, and artifact references.
9. Pipeline polls or resumes the same provider task ID, reads the terminal result, reconciles side effects, then commits its cursor.

A queued prompt, discovered model, account, browser URL, or open session is not an executed agent turn. Count a turn only after provider-native task identity and terminal readback exist.

## Promotion and integration sequence

1. **Promote the lifecycle semantics first.** Review and merge the provider-state-only classifier from this branch. Preserve same-ID resume, terminal failure states, and deterministic secondary selection.
2. **Bind WorkEpisode.** Use its existing AssignmentEpisode/application ports. Persist the primary task ID, secondary child task ID, A2A context ID, state source, terminal state, and artifact references. Do not create a competing task ledger in OmniRoute.
3. **Bind Pipeline.** Make the existing Pipeline runner the sole recurring scheduler and lease/retry owner. It should invoke GitHub Actions or another execution target, store the run ID in WorkEpisode, and commit only after effect readback.
4. **Move browser ownership to ComputerUseX.** GitHub Actions Playwright is a useful execution target and currently produces evidence, but CUX should own session lifecycle and HAR capture through its public interface.
5. **Make cross-platform handoff recursive.** After the selected secondary completes, discover an external agent by capability, send a bounded context summary, persist the A2A context/task ID, and poll it to terminal state. The current Lordevo call is a preflight and must not be mistaken for a substantive source review.
6. **Qualify independent nodes.** Require a real provider-native execution receipt before promoting a node into the capacity pool. Track independent account/quota scope separately from model availability.
7. **Remove duplicate recurrence only after cutover.** The current GitHub Actions schedule is an interim fallback. Once Pipeline dispatch is live and verified, remove the workflow's cron schedule so recurrence has one owner.

## Free-tier and open-source expansion candidates

These are capability candidates, not a mandate to create accounts. Check live quotas and model availability at onboarding; never rotate accounts or IPs to evade provider limits.

| Candidate | Useful capability | Recommended role |
|---|---|---|
| [Cloudflare Agents SDK](https://github.com/cloudflare/agents) | Open-source stateful agent runtime built around Cloudflare's platform primitives | Candidate always-on remote agent node; keep Pipeline as scheduler |
| [OpenHands](https://github.com/All-Hands-AI/OpenHands) | Open-source coding agent and hosted cloud workflow | Independent coding/review node; hosted free usage and model costs must be measured separately |
| [Agno](https://github.com/agno-agi/agno) | Open-source multi-agent runtime and AgentOS | Self-hosted agent node where an additional provider account is not required |
| [LangGraph](https://github.com/langchain-ai/langgraph) | Open-source stateful agent graph and checkpointing | Use inside a provider worker when useful; do not make it a second scheduler |
| [Kilo Code](https://github.com/Kilo-Org/kilocode) | Native coding-agent CLI and free-model gateway | Independent agent route; select models from the live free catalog and respect rate limits |
| [Browserbase](https://www.browserbase.com/pricing) / [Browserless](https://www.browserless.io/pricing) | Remote browser sessions and automation | Browser execution providers, not agent orchestration or recurring schedulers |
| [Lordevo Shop MCP/A2A](https://shop.lordevo.com/pricing) | Observed $0/no-signup MCP and A2A entry point; 30 discovered agent records and 24 tool names in this run | Lightweight external A2A/browser route; source inspection was blocked by robots on the tested GitHub URL |

OpenHands, Agno, Cloudflare Agents, and LangGraph are public GitHub projects. The hosted plans, free quotas, and inference charges are separate from their open-source code. Prefer self-hostable runtimes when they add a distinct capability without adding another account or scheduler.

## Account and credential policy

- Do not create an account on every turn. Create one only when it adds a distinct provider capability, independent quota scope, or durable execution environment.
- Account onboarding must be idempotent and capability-driven.
- Never reuse one password across services. The password shared in the initiating prompt must be treated as exposed; do not reuse it.
- Never commit decrypted credentials or put a decryption key beside ciphertext. Store secrets in the Accounts encrypted custody path and pass only access references to workloads.
- Do not create duplicate accounts or rotate identities to bypass free-tier, IP, or API rate limits.

## Revenue lane status

No bounty or contract was completed, no revenue was earned, and no Coinbase transfer occurred in this execution. Continue only against an existing posted bounty/contract, with no unsolicited outreach and no new product/offer creation. A payout destination must be connected through an authorized, auditable route before any transfer; do not report an unearned or unverified amount as revenue.

## Source repositories

- WorkEpisode: https://github.com/evanbrown3000/work-episode
- Pipeline framework/harness: https://github.com/evanbrown3000/pipeline-framework-and-pipeline-harness
- B4PT0R/provider execution: https://github.com/evanbrown3000/b4pt0r
- ComputerUseX/browser capture: https://github.com/evanbrown3000/computerusex
- Accounts and secrets: https://github.com/evanbrown3000/accounts-and-secrets
- Networks and federation: https://github.com/evanbrown3000/networks-and-federation
- OmniRoute promotion candidate: https://github.com/evanbrown3000/OmniRoute-evan/tree/agent-router-a2a-20261113-01

