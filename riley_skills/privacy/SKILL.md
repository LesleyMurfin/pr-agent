---
name: Privacy by Design
description: Data minimization, Canadian residency, strict tenant isolation, no PII leakage.
---

# Privacy by Design (Pillar 2)

Governing Standard: BCP-PRI-201, BCP-PRI-202, BCP-GOV-402, PIPEDA / Bill C-27.

- **Data Minimization**: Collect, transmit, process, and retain only data strictly necessary for the immediate function.
- **Zero PII in Logs/Traces**: Personally Identifiable Information (names, emails, phones, addresses, financial data, auth headers) must never appear in logs, error traces, telemetry, or review comments.
- **Strict Tenant & Entity Isolation**: Systems handling multiple clients or internal entities (`Lesley_Personal`, `Revive Business Solutions`, `RILEY (IP)`) must preserve strict partition boundaries. Prevent cross-tenant data bleed.
- **Canadian Data Sovereignty**: All storage and cloud operations default to Canadian regions (`northamerica-northeast1`). No sensitive data leaves Canadian sovereign boundaries without explicit authorization.
