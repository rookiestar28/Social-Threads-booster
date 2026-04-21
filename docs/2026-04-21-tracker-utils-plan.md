# Shared Tracker Utilities Plan

> Date: 2026-04-21
> Backlog item: AKR-006

## Scope

### In scope

- Add a shared local utility module for tracker read/write, timestamp generation, scaffold hydration, and backup rotation.
- Refactor `scripts/fetch_threads.py`, `scripts/parse_export.py`, and `scripts/update_snapshots.py` to consume the shared utility layer.
- Add regression coverage for the shared utility contract.

### Out of scope

- refresh log contracts
- freshness audit log contracts
- review log-health helpers
- schema migration behavior beyond current list-based tracker validation

## Design Changes

### New shared module

- Add `scripts/tracker_utils.py`

Responsibilities:

- canonical UTC timestamp helper
- tracker file loading / validation
- tracker file saving
- backup rotation with stable retention behavior
- reusable post-level scaffold builders
- reusable post hydration for older tracker entries

### Script refactor targets

- `scripts/fetch_threads.py`
- `scripts/parse_export.py`
- `scripts/update_snapshots.py`

The external CLI contracts must remain unchanged.

## Security Implications

- local filesystem writes remain explicit and inside the workspace
- backup rotation must only act on files adjacent to the target tracker path
- no new network surface is introduced

## Failure Modes And Rollback

- refactor could accidentally change serialized tracker shape
- backup rotation could delete the wrong file set if filename matching is too broad
- hydration could overwrite existing enriched fields if defaults are applied incorrectly

Handling:

- keep builders field-for-field compatible with current schema
- scope backup globbing to `<tracker>.bak-*`
- use `setdefault`-style hydration instead of destructive replacement

Rollback:

- revert the utility refactor commit
- restore tracker file from the latest `.bak-*` copy if a local mutation run misbehaves

## Test Plan

- pre-fix reproduction via a targeted utility test module that fails before `tracker_utils.py` exists
- post-fix targeted regression via the same utility tests plus existing script tests
- full sweep per [tests/TEST_SOP.md](/C:/Users/Ray/Documents/我的專案/AK-Threads-booster/tests/TEST_SOP.md)
- deterministic CLI E2E per [tests/E2E_TESTING_NOTICE.md](/C:/Users/Ray/Documents/我的專案/AK-Threads-booster/tests/E2E_TESTING_NOTICE.md) and [tests/E2E_TESTING_SOP.md](/C:/Users/Ray/Documents/我的專案/AK-Threads-booster/tests/E2E_TESTING_SOP.md) for any changed deterministic script surfaces
- explicit note if `pre-commit` remains unavailable in the local environment

## Acceptance Criteria

- one shared utility module owns tracker load/save/backup/scaffold defaults
- the three refactored scripts keep their existing CLI behavior and tracker shape
- backup rotation is deterministic and bounded
- regression tests and required CLI E2E pass
