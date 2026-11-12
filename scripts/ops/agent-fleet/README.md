# Existing recurring website workers

These are the existing deployed worker modules, retained here for review and recovery—not a second orchestration framework. They require Python 3.11+, `requests`, `filelock`, and the installed `slack-mcp-server` executable at `/app/slack-mcp-server`.

`daemon.py` accepts configuration/state directories through `COGNILODE_WORKER_CONFIG` and `COGNILODE_WORKER_STATE` (defaults `/config` and `/state`). Individual workers retain independent timers, admission identities and Slack delivery state. Fleet mode discovers registered supported HTTP connections and starts the same worker for each account, with a connection-scoped key. Existing externally managed connections must be listed to avoid duplicate workers.

The shared `/application-session/owner-instruction-source.json` binds the owner channel to its designated owner message. App/bot-origin messages and app-sent footers cannot replace that instruction automatically. Exact source text is retained; verified owner input is cached for Slack outages. A shared Slack identity without origin markers is not proof of human authorship.

Server-owned OmniRoute tools require `server_owned_tools: true` on a compatible worker, which requests non-streaming responses so the existing router tool loop executes its skills. Other workers keep their streaming path. Fleet mode enables this only for its explicit `server_owned_tool_providers` list.

Retain the configuration, owner-source binding, credential references, application-session data and per-account state when moving entry devices. Do not commit credential files or credential-bearing HAR captures. The modules do not provision vendor accounts by themselves: actual provider signup/login flows must supply valid session material before connection registration and native turn qualification.

`mail_verification.py` is an on-demand Accounts provider method, not a mailbox daemon. It references an existing owned credential without copying its password. Inventory does not probe the network. Explicit qualification checks IMAP authentication; verification reads only recent, sender/recipient-matched messages, using bounded `BODY.PEEK` reads without changing unread flags. It returns one unambiguous numeric code or `pending`, not a mailbox dump. No CAPTCHA or MFA requirement is bypassed.

The native controller CLI accepts `--install --credential-ref <existing reference>` to retain its source through the existing Accounts method registry. The default capability account is `mailbox.verification.evanbronitskiy`; this is not a new Gmail/vendor account or inference platform. Once installed, its `inventory`, `qualify` and `verification_code` operations are available through the existing `AccountProviderRuntime.run` interface. Verification requires `--sender-domain` and `--after` (the actual signup-request epoch timestamp), with optional `--code-length` (default six). The existing SMTP send record is unchanged.
