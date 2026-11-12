# OmniRoute federation evidence-custody and provider architecture review — turn 12

Request ID: gpt6-20261113-omniroute-evidence-custody-01
TARGET_AGENT: softwareengineeringexpert
SECONDARY_AGENT: researchagent
EXPECTED_36_PERCENT_BUCKET: 30

## Objective

Continue the existing OmniRoute foundation. Improve the reliability of provider-native execution evidence and select the strongest existing architecture to promote. Do not rebuild the gateway or create a competing scheduler.

## Required live execution

1. Use the existing GitHub-hosted Playwright workflow and Agent Router MCP endpoint. Capture the real browser HAR, MCP endpoint, HTTP methods/statuses, advertised tool names, and input schemas. Keep the HAR sanitized: no cookies, authorization headers, tokens, query values, or raw request/response bodies. Delete the raw HAR after sanitization.
2. Primary: invoke `softwareengineeringexpert` to inspect the public OmniRoute repository and compare `release/v3.8.54`, `agent-router-a2a-20261112-04`, `agent-router-a2a-20261112-05`, and `agent-router-a2a-20261113-01`. Determine which implementation has the strongest native-task lifecycle, resumability, secondary-agent gating, and evidence custody. Branches have diverged; do not recommend wholesale merging without a file-level basis.
3. Investigate the previous run #75 artifact result: the workflow wrote a sanitized HAR index, MCP trace, and native-task receipt, but GitHub Actions reported only one uploaded file. Identify the path/runner boundary responsible and verify that the shared-workspace evidence bundle now contains all required files.
4. Compute the secondary-agent selection from this request ID. If the deterministic 36% bucket qualifies, invoke `researchagent` only after primary terminal success. Give it an independent research task and require its own native task ID, provider-declared terminal state, and final readback. Never treat a secondary as a primary fallback. If the primary remains pending, resume that exact task ID and do not launch a duplicate.
5. Trigger the separate Lordevo Shop A2A endpoint using only its free preflight capability for the public repository URL. Do not invoke paid skills, initiate x402, request a wallet, create an account, or submit payment. Record returned state and context ID; an acknowledgement alone is not completion.
6. Preserve provider names, native task IDs, terminal states, final readbacks, selection bucket, MCP trace hashes, sanitized HAR index, evidence manifest, and artifact inventory.

## Architecture review

Assess the durable composition:
- WorkEpisode owns immutable execution identity and provider-native completion receipts.
- Pipeline is the single owner of recurrence, leases, retries, idempotency, and effect readback.
- Networks owns provider/node admission, health, capacity, placement, and failure domains.
- Accounts owns encrypted credential custody and scoped account bindings.
- ComputerUseX owns browser execution, sanitized HAR evidence, and artifact pointers.
- B4PT0R owns provider-hosted website-session transport.
- OmniRoute remains the inference gateway and MCP/A2A routing layer.

Specify a provider adapter contract that includes discovery, capability/schema retrieval, submission, native task ID, wait/resume, terminal-state readback, cancellation, quota/cost, health, and evidence export. Distinguish accepted/queued work from completed provider-native execution.

## External research

Use public GitHub repositories and current official documentation. Assess OpenHands, Agno/AgentOS, LangGraph, Letta, Graphiti, the A2A protocol, Browser Use, Cloudflare Workers/Browser Rendering, Browserbase, Browserless, Daytona, E2B, Modal, n8n, and Dify.

Separate:
- open-source agent runtime versus hosted agent platform;
- inference API versus provider-native agent execution;
- remote compute versus browser-session hosting;
- recurring free capacity versus one-time credits;
- no-signup access versus account-required access;
- advertised quota versus durable production capacity.

Prefer proven existing free routes. Recommend new provider enrollment only where it adds a distinct failure domain and measurable recurring capacity.

## Security and execution constraints

- No account creation, password reuse, credential collection/disclosure, private-memory access, paid provisioning, quota/rate-limit/billing/identity circumvention, or wallet operations.
- Do not use the owner's personal computer.
- No email, outreach, product listings, offers, internal tests, or application-source changes in this review.
- Limit external-agent prompts to public repository facts and this architecture summary.

## Required conclusion

Recommend one long-term federated architecture and the strongest historical implementation to promote. State exactly which changes should be selectively promoted, what remains blocked, and which owner integration is required to persist receipts into WorkEpisode and return recurrence ownership to Pipeline.