# Temporary read-only agent review request

Review the current provider-routing and cross-agent execution architecture in this repository.

Focus on:
- Provider adapters, authentication boundaries, and model/provider routing.
- A provider-native way to trigger an external agent turn and verify completion rather than treating queue acceptance as execution.
- Free-tier providers, tool-calling capability, rate limits, and fallback behavior.
- Remote execution and browser-session patterns, including capture and validation of provider-native network evidence.
- Durable recurring automation versus one-off remote sessions.

Use the repository's actual code and documentation. Return concrete findings with exact paths and symbols. This is a read-only review: do not modify files, create branches, open pull requests, add credentials, or run tests. Do not infer that a provider is usable unless the repository contains evidence for the route.
