# HAR and browser state

The Traffic Inspector now has a **HAR & browser state** tab. It records through
existing capture modes, saves the current HAR, and automatically uploads selected
original HAR/storage-state files to the private Accounts capture service. Large
files are read and uploaded in 4 MiB pieces; a final index retains original file
names, lengths, byte offsets and all part references. No whole large file is
loaded into browser memory. The UI reports success only after Accounts returns
its verified commit and manifest location.

Capture credentials are data: authorization, cookies, Set-Cookie, device headers,
token-bearing URLs and original request/response bodies must survive capture,
copy, persistence and export. Capture hooks, proxy capture, ingest, buffer,
export and the inspector display no longer mask these values. Header forwarding
policy is separate: a transport may manage Host/framing or authenticate its own
router hop without modifying the captured original headers.

There is one browser network recorder in **browser-automation**:
`passive_network_capture.NetworkCapture`. Browser engines and CDP adapters belong
there. ChatGPT-specific selectors and native HTTP live in **chatgpt-backend-api**;
LibreChat owns higher-level sessions/orchestration. OmniRoute owns routing,
Responses/v1 conversion, this UI and its HTTP/proxy capture specializations.
These are consumers and extensions of the capture boundary, not competing vaults
or browser lifecycle owners. Add provider-specific behavior in its provider
owner; add a browser transport to browser-automation; do not clone a recorder.

The server relay uses `NATIVE_CORE_CAPTURE_KEY` and optional
`ACCOUNTS_CAPTURE_URL` (default the existing cognilode.com native capture route).
The Accounts service needs `ACCOUNTS_CAPTURE_GITHUB_TOKEN` for its private repo.
Raw artifacts are **never** committed to this public OmniRoute fork.
See accounts-and-secrets `docs/browser-captures.md` for the original-byte storage
contract. Source publication does not install those bindings or deploy the UI.

`Capture integrity` is the CI check for this policy. It rejects capture
sanitizers/redactors and exercises original header/body preservation. The
optional local hook is installed with `git config core.hooksPath .githooks`.
Tests deliberately preserve credential-shaped fixture values. HTML escaping and
unrelated application error rendering are separate from capture contents.
