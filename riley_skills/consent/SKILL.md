---
name: Consent by Design
description: User approval before side-effects, propose-then-confirm UX, explicit opt-in for destruction.
---

# Consent by Design (Pillar 3)

Governing Standard: BCP-GOV-401, BCP-GOV-403, BCP-OPS-121.

- **Propose-Then-Confirm UX**: Actions producing external side-effects (publishing PRs, pushing commits, sending external notifications, modifying live state) must present the proposal/diff first and require human approval.
- **Explicit Opt-In for Destruction**: Irreversible operations (data deletion, table truncation, cluster teardown) require explicit confirmation; silence or absence of error is not consent.
- **Never Auto-Merge**: PRs, issues, deployments, and production merges remain gated by policy and human verification. No autonomous merge bypasses.
- **Auditability & Traceability**: Every side-effect must record the initiating user/actor, timestamp, and explicit consent artifact.
