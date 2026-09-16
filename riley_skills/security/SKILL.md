---
name: Security by Design
description: Zero-trust, least privilege, fail-closed defaults, zero leaked credentials, input sanitization.
---

# Security by Design (Pillar 1)

Governing Standard: BCP-SEC-701, BCP-OPS-129, BCP-OPS-130, BCP-STD-016, BCP-REL-309.

- **Zero Hardcoded Secrets**: Reject any API keys, tokens, passwords, private keys, or credentials in code, config, commit history, or logs. Secrets must be loaded from secure environments/files (e.g. `~/.config/secrets.env`), never embedded in code.
- **Fail-Closed Defaults**: Authorization, policy evaluation, or validation failures must immediately halt execution. Never fall back to permissive or unauthenticated defaults.
- **Least Privilege & Scoping**: Access tokens, service accounts, and tool capabilities must be restricted to the minimal required permissions and narrowest resource scope.
- **Zero Injection Surface**: Reject string concatenation or shell interpolation for unvalidated user inputs, paths, or query fragments. Always use parameter arrays or typed objects.
- **Safe Subprocesses & Dependencies**: Pin dependencies to immutable digests/versions. Avoid `shell=True` and verify executable paths.
