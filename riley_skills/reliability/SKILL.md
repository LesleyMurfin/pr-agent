---
name: Reliability by Design
description: Logging, debugging, telemetry, redundancy, retries, error handling, testing, evals.
---

# Reliability by Design (Pillar 4)

Governing Standard: BCP-REL-301, BCP-REL-302, BCP-REL-303, BCP-REL-304, BCP-REL-305.

Hunt these 8 core reliability capabilities in every review:

1. **Logging**: Structured, contextual, leveled logging (JSON/key-value). Log causation and recovery context; never swallow error reasons.
2. **Debugging**: Diagnostic hooks, correlation IDs, execution tracing, and reproducible failure artifacts to allow rapid triage without attaching a live debugger.
3. **Telemetry**: Meaningful operational metrics, request latency counters, error counts, and health signals emitted to monitoring collectors.
4. **Redundancy**: High-availability fallbacks, secondary routes, failover mechanisms, and eliminating single points of failure across infrastructure and services.
5. **Retries**: Bounded retries with exponential backoff and jitter on transient I/O or network failures; strict circuit breaking to prevent retry storms.
6. **Error Handling**: Deliberate, explicit exception handling. Catch specific failure modes, preserve stack traces (`raise ... from err`), and fail cleanly into a safe state. Never silent `except: pass`.
7. **Testing**: Comprehensive automated behavioral tests. Assert observable inputs, outputs, and boundary conditions. Require reproduction tests for all bug fixes.
8. **Evals**: Empirical evaluation harnesses for LLM/agent outputs, deterministic regression assertions, and score tracking against golden reference cases.
