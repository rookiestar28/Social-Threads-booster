# Freshness Audit Log Plan

> Date: 2026-04-21
> Backlog item: AKR-008

## Scope

### In scope

- Add shared helpers for `threads_freshness.log` JSON-line entry construction.
- Add a thin local CLI for appending freshness audit entries without duplicating field formatting.
- Add regression coverage and deterministic CLI E2E for the freshness log contract.

### Out of scope

- automatic `/topics` or `/draft` orchestration
- `/review` log-health summarization
- web-search execution itself

## Design Changes

### New shared module

- Add `scripts/freshness_logging.py`

Responsibilities:

- generate `run_id`
- normalize log entry structure for `topics` and `draft`
- enforce status / verdict / decision value constraints
- append JSON lines to `threads_freshness.log`

### New thin CLI

- Add `scripts/log_freshness_audit.py`

Responsibilities:

- expose the shared contract as a deterministic local command
- support both `topics` and `draft` entry shapes
- print the chosen `run_id` for chaining

## Security Implications

- log files must not include raw search result dumps or unrelated sensitive text
- only explicit short query strings should be stored
- writes stay local to the workspace or explicit target path

## Failure Modes And Rollback

- invalid status or outcome values could silently create unusable log data
- `topics` and `draft` shapes could drift if field mapping is duplicated
- CLI could create malformed JSON lines if it bypasses shared builders

Handling:

- validate status and outcome values centrally
- keep one shared append path for both skills
- fail fast on invalid combinations

Rollback:

- revert the freshness logging commit
- remove the generated `threads_freshness.log` file if it was only test data

## Test Plan

- pre-fix reproduction via a freshness logging regression test that fails before the helper/module exists
- post-fix targeted regression via the same tests
- full sweep per [tests/TEST_SOP.md](/C:/Users/Ray/Documents/我的專案/AK-Threads-booster/tests/TEST_SOP.md)
- CLI E2E per [tests/E2E_TESTING_NOTICE.md](/C:/Users/Ray/Documents/我的專案/AK-Threads-booster/tests/E2E_TESTING_NOTICE.md) and [tests/E2E_TESTING_SOP.md](/C:/Users/Ray/Documents/我的專案/AK-Threads-booster/tests/E2E_TESTING_SOP.md) using the thin audit CLI

## Acceptance Criteria

- shared helpers can append valid `topics` and `draft` freshness audit lines
- `run_id`, status, and verdict/decision fields are normalized and consistent
- the thin CLI appends contract-compliant entries to `threads_freshness.log`
- regression tests and deterministic E2E pass
