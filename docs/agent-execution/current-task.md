# Current task

Request ID: `chatgpt-20261112-per-turn-agent-event-02`

## Objective

Design and execute the durable per-user-turn cross-platform agent handoff by extending the strongest existing implementation. Preserve the existing domain ownership and do not introduce a second scheduler, agent registry, credential vault, memory graph authority, or account inventory.

## Required investigation

1. Inspect the existing public OmniRoute A2A/MCP implementation and the current `agent-router-a2a` workflow. Distinguish a real provider-native task from a queued prompt, ordinary model completion, or workflow status.
2. Determine the smallest robust event-driven trigger that lets a new ChatGPT user turn submit a unique work request to the existing remote executor. Pipeline remains the durable work and recurrence owner; this workflow is only an execution adapter.
3. Preserve the existing A2A client, browser/HAR capture, provider readback, and task continuation rather than starting over. Identify the best historical implementation to promote.
4. Use only public repositories and public provider documentation. Do not read private repository content or secrets.

## Mandatory agent execution

1. Use AgentRouter MCP discovery to select a real agent on a distinct provider platform.
2. Trigger a fresh native task with this request ID and a bounded, substantive prompt.
3. Wait for terminal completion and independently read the provider-side result. Record the native task/conversation identifiers and actual output.
4. Have the primary agent trigger a successor on a different platform. Wait for that successor's terminal result and provider-side readback. A discovery result, queued task, Slack post, or ordinary model completion does not count.
5. Explain how the 36% successor rule can be implemented deterministically without creating accounts or multiplying schedulers.

## Constraints

- Use existing no-charge, already-authorized provider routes.
- Do not create accounts, reuse passwords, submit credentials, bypass verification, evade quotas, incur charges, initiate payments, contact people, perform outreach, or create external business commitments.
- Do not invent facts, provider results, task IDs, or completion states.
- Do not modify application source code or run internal test suites during this review.
- Do not create receipts or write private conversation content into this public repository.
- Return a top-down architecture, the exact production execution evidence, current blockers, and the single highest-value next implementation step.
