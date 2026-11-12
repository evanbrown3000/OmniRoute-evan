# Federated Execution Boundary

**Status:** Proposed architecture boundary  
**Scope:** OmniRoute integration with remote native agents, browser sessions, and upstream orchestration  
**Principle:** Extend existing execution adapters; do not create a second global scheduler or durable task ledger inside the router.

## 1. Executive decision

Treat three capabilities as separate execution classes:

1. **Inference** — request/response model endpoints routed by the existing provider catalog, provider nodes, combos, quota telemetry, and circuit breakers.
2. **Native agent turns** — provider-owned asynchronous work initiated through MCP, A2A, ACP, or a Cloud Agent adapter. A provider-native task ID is mandatory.
3. **Browser sessions** — remote Chromium/CDP sessions that produce sanitized HAR and backend-request evidence. A browser session is not itself an agent task.

These classes can cooperate in one work item, but they must not share an ambiguous provider-node lifecycle. Keep the existing inference provider-node API inference-focused. Add execution adapters and typed receipts at the appropriate boundary rather than turning every agent, browser, shell, and inference resource into one polymorphic provider-node record.

The upstream orchestration layer remains the owner of recurring schedules, leases, retry policy, and durable work records. OmniRoute owns provider-specific transport, routing, and execution evidence for the capabilities it directly operates.

## 2. Current repository baseline

The current implementation already contains useful pieces; preserve and compose them:

| Existing surface | Current responsibility | Boundary to preserve |
|---|---|---|
| /api/providers and /api/provider-nodes | Inference provider catalog and compatible remote inference endpoints | Do not treat an inference endpoint as a remote shell or browser executor |
| src/lib/cloudAgent/baseAgent.ts | Provider-specific task interface: create, status, plan approval, messaging, and source listing | Extend through adapters; retain provider-native IDs |
| src/lib/a2a/taskManager.ts and A2A routes | A2A task submission, status, and result transport | Local task state is not the global work ledger |
| src/lib/vncSession/service.ts and /api/vnc-session | Container-backed VNC/CDP browser sessions | Session lifecycle and browser evidence remain distinct from agent-task lifecycle |
| Shared Playwright/browser services | Browser automation for internal workflows | Do not silently conflate these sessions with VNC/CDP sessions |

Important implementation observations in the current release:

- The A2A task manager uses an in-memory map for live task state. SQLite persistence is best-effort history, not a substitute for an upstream durable work record. The current defaults include a short live-task TTL; terminal in-memory entries are cleaned separately from retained database history.
- Cloud Agent adapters expose provider-specific task methods and persist their own local task records. Provider status synchronization is request-driven (for example, when task status is read), not a universal background scheduler.
- VNC/CDP sessions are ephemeral and process-local. Current defaults include a four-session cap, a ten-minute idle timeout, a thirty-minute maximum lifetime, and non-persistent profiles unless explicitly configured.
- The provider-nodes API is designed around compatible inference endpoints. Reusing it as a general agent/browser/shell registry would blur authentication, health, quota, and lifecycle semantics.

Relevant implementation and design references:

- docs/frameworks/A2A-SERVER.md
- docs/frameworks/CLOUD_AGENT.md
- docs/frameworks/AGENT_PROTOCOLS_GUIDE.md
- docs/architecture/QUALITY_EVIDENCE_CONTRACT.md
- docs/architecture/persistence-backend-boundary.md
- src/lib/a2a/taskManager.ts
- src/lib/db/a2aTasks.ts
- src/lib/cloudAgent/baseAgent.ts
- src/lib/vncSession/service.ts
- src/app/api/provider-nodes/route.ts

## 3. Canonical lifecycle

Use one lifecycle vocabulary across adapters while preserving the provider's native state:

DISCOVERED → QUALIFIED → ADMITTED → SUBMITTED → RUNNING / INPUT_REQUIRED → TERMINAL → READ_BACK → ACCEPTED / REJECTED

- **DISCOVERED** means a provider or capability is known. It is not usable capacity.
- **QUALIFIED** means its endpoint, authentication mode, health, quota window, concurrency, and evidence behavior have been checked.
- **ADMITTED** means the capacity owner has made it eligible for placement.
- **SUBMITTED** means the provider accepted a native request and returned a provider task ID or synchronous result.
- **RUNNING / INPUT_REQUIRED** are non-terminal states. Never launch a replacement task merely because a poll timed out.
- **TERMINAL** is the provider's own completed, failed, cancelled, or expired state.
- **READ_BACK** means a separate status/result request for the exact same provider task ID confirmed the terminal result.
- **ACCEPTED / REJECTED** is the work system's assessment. Provider completion alone does not imply useful work.

Keep two separate fields:

- provider_state: what the provider reports.
- acceptance_state: whether the result satisfies the requested task and evidence contract.

A response can be provider-completed but work-rejected because it is empty, irrelevant, malformed, or unsupported by evidence.

## 4. Native turn receipt

Every native agent turn should produce a compact, append-only receipt. Do not put prompts, response bodies, cookies, API keys, or browser post bodies in the receipt.

    {
      "schema_version": "1",
      "work_id": "upstream-work-id",
      "attempt_id": "stable-attempt-id",
      "transport": "mcp|a2a|acp|cloud-agent",
      "provider_id": "provider-or-platform",
      "agent_id": "provider-native-agent",
      "provider_task_id": "native-task-id",
      "context_id": "provider-context-id",
      "tool_name": "native-tool-name",
      "idempotency_key": "work-id:attempt-id:provider-id",
      "submitted_at": "RFC3339",
      "provider_state": "submitted|working|input_required|completed|failed|cancelled|expired",
      "terminal_at": "RFC3339-or-null",
      "readback": {
        "method": "get_task|wait_for_task|provider_status",
        "read_at": "RFC3339-or-null",
        "confirmed_state": "provider-state-or-null",
        "result_sha256": "sha256-or-null"
      },
      "acceptance": {
        "state": "pending|accepted|rejected",
        "reason_codes": [],
        "matched_task_anchors": []
      },
      "evidence": [
        {
          "kind": "sanitized_har|request_index|mcp_trace|provider_artifact",
          "uri": "controlled-artifact-reference",
          "sha256": "sha256",
          "redacted": true
        }
      ],
      "usage": {},
      "http_status": 200,
      "error_class": null
    }

The durable upstream work record is authoritative. OmniRoute's local A2A/Cloud Agent persistence may support local UI and transport recovery, but it must not become a second scheduler or a competing source of truth.

## 5. Idempotency, retries, and provider failures

Use a stable idempotency key derived from the upstream work ID, attempt ID, and provider identity. Persist the returned provider task ID before polling.

1. If a provider returns a task ID, poll and read back that exact ID.
2. If the provider reports RUNNING, PENDING, or INPUT_REQUIRED, retain the task ID and do not submit a replacement.
3. On HTTP 429, preserve Retry-After, quota window, and provider identity. Route retry/failover decisions to the upstream scheduler.
4. On HTTP 5xx or transport timeout, distinguish “submission unknown” from “submission rejected.” Read back by idempotency key or provider task ID before retrying.
5. Only retry after a provider-terminal failure, explicit cancellation, or a reconciled expired lease. Never convert a missing response into success.
6. A secondary agent may run when policy selects it, but it receives its own child attempt and receipt. It must not overwrite the primary task's identity or status.
7. A completed response must pass task-specific relevance and output-shape checks before it is accepted. Record matched anchors or reason codes, not the full private prompt.

## 6. Browser session and HAR evidence

A browser session has its own lifecycle:

REQUESTED → ALLOCATED → CONNECTED → CAPTURED → SANITIZED → CLOSED

The session receipt should contain:

- Browser provider and session ID.
- Start/end timestamps and terminal session status.
- CDP endpoint reference (never a reusable bearer token).
- Sanitized HAR URI and SHA-256.
- Backend-request index URI and SHA-256.
- For each indexed request: method, origin, redacted path, status, MIME type, and duration.

The sanitized evidence bundle may contain a HAR, endpoint index, MCP trace, native task receipt, and a manifest. It must exclude authorization headers, cookies, set-cookie headers, query strings, fragments, request/response bodies, and token-like path segments. Keep raw HAR only in ephemeral runner storage long enough to sanitize it; do not publish it as a workflow artifact.

A browser provider's concurrency limit is not proof of free allowance. Admission must separately verify plan, quota period, remaining capacity, session maximum, retention, and whether the provider requires an account or API key.

## 7. Capability and credential boundaries

Maintain separate registries or typed adapters for:

- Inference endpoints.
- Native agent runtimes and A2A/MCP/ACP transports.
- Browser/CDP providers.
- Remote shell and sandbox providers.

Each capability record should include provider identity, capability set, region, health probe, max concurrency, quota period, last verified time, evidence support, and an opaque credential reference. Never store credential values in Git, logs, HAR, artifacts, or task prompts.

An account is an identity, not execution capacity. Creating another account does not prove that a new quota, browser session, runtime, or agent turn is available. Prefer qualifying existing accounts and accountless/free endpoints first; only onboard another provider identity when the inventory proves a missing capability and the provider reports usable capacity.

## 8. Protocol and runtime choices

- Use **A2A** for agent-to-agent task exchange and provider-native task lifecycle; use **MCP** for tool discovery and invocation. They complement rather than replace one another.
- Treat **OpenWOP** as a useful workflow-contract reference for idempotency, replay, resume, and event evidence. Do not introduce it as a second scheduler or durable ledger.
- **OpenHands Agent Server** is a candidate remote worker runtime. Its separate Automation Server owns scheduling and dispatching; use the worker API only if the existing upstream scheduler remains authoritative.
- **LangGraph** or **Agno** may be evaluated as per-agent worker runtimes when self-hosted capacity is justified. Do not deploy their orchestration/scheduling layer as a competing global control plane.

## 9. Acceptance criteria for production federation

A provider integration is production-qualified only when all of the following are demonstrated with a real provider:

- Discovery returns a documented capability and exact provider identity.
- Admission verifies quota, concurrency, health, authentication, and retention.
- Submission returns a native task/session identity.
- The same identity is read back independently to a provider-terminal state.
- A task-specific acceptance check distinguishes useful work from generic or irrelevant text.
- The receipt and sanitized evidence bundle have verifiable hashes.
- A pending task cannot be duplicated by timeout, retry, or a second agent.
- Credential values never appear in source, logs, HAR, or artifacts.
- The upstream scheduler and durable work record remain the sole owners of recurrence, leases, retries, and final work status.

## 10. Rollout order

1. Standardize the receipt and idempotency contract without changing existing provider adapters.
2. Map existing Cloud Agent and A2A adapters to the contract and preserve their native IDs.
3. Add upstream receipt/readback integration; retain local persistence only for local transport/UI needs.
4. Add browser-provider adapters that return sanitized HAR and endpoint-index references.
5. Connect capability admission to the external capacity registry; do not broaden the inference provider-node schema by default.
6. Qualify each new remote runtime against the production acceptance criteria before placing recurring work on it.

This path expands OmniRoute's federation while retaining the boundaries and working implementations already present.
