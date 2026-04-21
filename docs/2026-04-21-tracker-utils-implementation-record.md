# Shared Tracker Utilities Implementation Record

> Date: 2026-04-21
> Backlog item: AKR-006

## What Changed

- Added `scripts/tracker_utils.py` as the shared owner for:
  - UTC timestamp generation
  - tracker load/save
  - backup rotation
  - post scaffold construction
  - post default hydration
  - metric snapshot creation
  - newest-first post sorting
- Refactored `scripts/fetch_threads.py` to build tracker records through `tracker_utils.py` and save through the shared writer.
- Refactored `scripts/parse_export.py` to build tracker records through `tracker_utils.py` and save through the shared writer.
- Refactored `scripts/update_snapshots.py` to use the shared loader, saver, backup rotation, post hydration, post construction, timestamp helper, and sorting helper.
- Added `tests/test_tracker_utils.py` for shared utility regression coverage.
- Added `tests/test_parse_export.py` for minimal CLI parsing regression.
- Updated `tests/E2E_TESTING_SOP.md`, `knowledge/_shared/discovery.md`, and `docs/roadmap.md`.
- Fixed `parse_export.py` to accept UTF-8 BOM JSON input, which surfaced during PowerShell E2E validation.

## Why Changed

- Tracker IO and schema scaffolding were duplicated across multiple scripts, which made future changes risky and inconsistent.
- Backup naming and retention behavior belonged in one place, not inside a single refresh script.
- The refactor establishes a reusable data-integrity layer before log contracts and review helpers build on top of it.
- The BOM fix was required because Windows-generated JSON fixtures triggered a real cross-environment parsing failure during E2E.

## Full Verification Evidence

- Date: 2026-04-21
- Environment: Windows PowerShell, Python `3.13.9`
- Command log reference: inline command list below

### Pre-fix Reproduction Evidence

```powershell
python -m unittest tests.test_tracker_utils
```

- Result: failed before implementation because `scripts/tracker_utils.py` did not exist.

### Post-fix Targeted Regression Evidence

```powershell
python -m unittest tests.test_tracker_utils
python -m unittest tests.test_parse_export
```

- Result: both passed after implementation.

### Final Full-Gate Evidence

```powershell
Get-Command pre-commit | Select-Object -ExpandProperty Source
python -m unittest discover -s tests -p "test_*.py"
python -m py_compile scripts\tracker_utils.py scripts\fetch_threads.py scripts\parse_export.py scripts\update_snapshots.py
python scripts/parse_export.py --input .tmp\parse-export-e2e\threads-export.json --output .tmp\parse-export-e2e\tracker.json
```

- `pre-commit` availability check: unavailable in the current environment, so the hygiene lane could not be executed locally.
- Python regression sweep: passed (`9` tests, `0` failures).
- Static import/syntax verification: passed for all refactored scripts via `py_compile`.
- CLI E2E:
  - `parse_export.py`: passed on a workspace-local minimal JSON export fixture
- Credential-dependent lanes:
  - `fetch_threads.py`: not runnable end-to-end locally without valid Threads API credentials
  - `update_snapshots.py`: not runnable end-to-end locally without valid Threads API credentials

## Known Limitations

- Credential-dependent API scripts still require live token-based smoke coverage for true end-to-end proof.
- `tracker_utils.py` centralizes current schema defaults but does not yet enforce a formal schema validator; that remains later roadmap work.
- Existing deterministic generators are not yet refactored onto `tracker_utils.py`; this item only covered the import/update script layer.

## Follow-up Items

- AKR-007 should build refresh log contracts on top of the shared tracker utility layer now in place.
