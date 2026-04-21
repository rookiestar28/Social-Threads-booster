# Review Log Health Plan

> Date: 2026-04-21
> Backlog item: AKR-009

## Scope

### In scope

- Add shared readers and summarizers for `threads_refresh.log` and `threads_freshness.log`.
- Implement grouping rules for freshness runs by `run_id`, with timestamp-minute fallback for legacy entries.
- Add a thin local CLI that emits structured log-health summaries for review flows.
- Add regression coverage and deterministic E2E for the summarizer path.

### Out of scope

- full `/review` automation
- tracker/style/concept mutation logic
- any web-search or refresh execution itself

## Design Changes

### New shared module

- Add `scripts/review_log_health.py`

Responsibilities:

- load JSON-line logs
- summarize recent freshness runs
- summarize recent refresh runs
- detect degraded mode, stale refresh state, and dominant failure reasons
- report whether the current topic slug appears in recent freshness entries

### New thin CLI

- Add `scripts/summarize_log_health.py`

Responsibilities:

- read one or both log files
- expose the structured summary as JSON for local verification and future automation chaining

## Security Implications

- log readers must tolerate malformed lines without echoing sensitive raw data into output
- summaries should surface compact operational facts, not full log payload dumps
- file access stays local to explicit log paths

## Failure Modes And Rollback

- malformed log lines could break the whole summary path
- freshness grouping could over-count runs if fallback grouping is wrong
- stale-refresh detection could drift if timestamps are parsed inconsistently

Handling:

- ignore malformed lines with a count in the summary
- group freshness runs by `run_id` first, then `ts` rounded to the minute when absent
- parse ISO timestamps centrally and compute stale windows from UTC-aware values

Rollback:

- revert the log-health helper commit
- continue using manual review judgment until the helper is restored

## Test Plan

- pre-fix reproduction via a log-health regression test that fails before the helper/module exists
- post-fix targeted regression via the same tests
- full sweep per [tests/TEST_SOP.md](/C:/Users/Ray/Documents/我的專案/AK-Threads-booster/tests/TEST_SOP.md)
- CLI E2E per [tests/E2E_TESTING_NOTICE.md](/C:/Users/Ray/Documents/我的專案/AK-Threads-booster/tests/E2E_TESTING_NOTICE.md) and [tests/E2E_TESTING_SOP.md](/C:/Users/Ray/Documents/我的專案/AK-Threads-booster/tests/E2E_TESTING_SOP.md) using synthetic local log fixtures

## Acceptance Criteria

- shared helpers compute degraded freshness-run ratios, missing current-topic freshness coverage, dominant refresh failure reasons, and stale-refresh warnings
- the thin CLI emits machine-readable summaries for local verification
- regression tests and deterministic E2E pass
