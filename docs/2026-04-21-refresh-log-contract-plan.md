# Refresh Log Contract Plan

> Date: 2026-04-21
> Backlog item: AKR-007

## Scope

### In scope

- Add executable helpers for `threads_refresh.log` JSON-line writing.
- Integrate the log contract into `scripts/update_snapshots.py` for headless API refresh runs.
- Add regression coverage for both success-format helpers and headless failure-path logging.

### Out of scope

- Chrome MCP scrape implementation
- `/review` log-health analysis
- freshness audit log contracts

## Design Changes

### New shared module

- Add `scripts/refresh_logging.py`

Responsibilities:

- canonical refresh success entry rendering
- canonical refresh failure entry rendering
- append JSON lines to the chosen log file
- stable reason-code normalization for the current executable surface

### Script changes

- Extend `scripts/update_snapshots.py` with:
  - `--headless`
  - `--log-file`
  - failure logging on bounded early exits
  - success logging after a completed refresh write

## Security Implications

- log output must not write secrets such as API tokens
- failure details must stay short and operational, not dump stack traces into logs
- log writes remain local to the workspace or explicit target path

## Failure Modes And Rollback

- headless failure could exit before logging
- log-writing failures could mask the original refresh failure
- success counts could drift from actual update results if computed in the wrong stage

Handling:

- wrap the CLI entrypoint in one place so failures can be logged before exit
- keep log-writing best-effort but explicit
- compute success counters from the same refresh state used for persistence

Rollback:

- revert the refresh logging commit
- remove or rotate the generated `threads_refresh.log` file if needed

## Test Plan

- pre-fix reproduction via a headless logging regression test that fails before the helper/module exists
- post-fix targeted regression via the same logging tests
- full sweep per [tests/TEST_SOP.md](/C:/Users/Ray/Documents/我的專案/AK-Threads-booster/tests/TEST_SOP.md)
- CLI E2E per [tests/E2E_TESTING_NOTICE.md](/C:/Users/Ray/Documents/我的專案/AK-Threads-booster/tests/E2E_TESTING_NOTICE.md) and [tests/E2E_TESTING_SOP.md](/C:/Users/Ray/Documents/我的專案/AK-Threads-booster/tests/E2E_TESTING_SOP.md) for any deterministic failure-path coverage that can run without credentials
- explicit note that credentialed refresh success E2E remains unavailable without a live Threads token

## Acceptance Criteria

- headless refresh failures append contract-compliant JSON lines to `threads_refresh.log`
- successful refresh runs can emit contract-compliant success lines through the shared helper
- `update_snapshots.py` preserves its existing non-headless CLI behavior
- regression tests and available local E2E pass
