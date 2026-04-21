# Setup Artifact Pipeline Plan

> Date: 2026-04-21
> Backlog item: AKR-005

## Scope

### In scope

- Add a single local orchestration entrypoint for setup artifacts.
- Generate `style_guide.md`, `concept_library.md`, and companion markdown files from one command.
- Optionally generate `brand_voice.md` when requested.
- Add regression coverage for the combined pipeline.

### Out of scope

- import/migration paths themselves
- refresh logging and review log analysis
- shared utility refactor beyond what is necessary for orchestration

## Design Changes

### New executable component

- Add `scripts/run_setup_artifacts.py`

Responsibilities:

- load tracker once
- render `style_guide.md`
- render `concept_library.md`
- optionally render `brand_voice.md`
- call companion rendering
- write outputs into a chosen directory in a deterministic order

### CLI

```powershell
python scripts/run_setup_artifacts.py --tracker threads_daily_tracker.json --output-dir . --include-brand-voice
```

## Security Implications

- local file reads/writes only
- no network access
- outputs stay inside the workspace

## Failure Modes And Rollback

- partial artifact writes if one downstream renderer fails
- output-dir mismatch or missing tracker

Handling:

- validate tracker before rendering
- fail fast on invalid input
- keep writes deterministic and explicit

Rollback:

- rerun generator after fixing the issue
- git commit remains acceptance boundary

## Test Plan

- pre-fix reproduction evidence via `python -m unittest tests.test_run_setup_artifacts`
- targeted post-fix regression via `python -m unittest tests.test_run_setup_artifacts`
- full sweep per [tests/TEST_SOP.md](/C:/Users/Ray/Documents/我的專案/AK-Threads-booster/tests/TEST_SOP.md), including `python -m unittest discover -s tests -p "test_*.py"`
- CLI E2E per [tests/E2E_TESTING_NOTICE.md](/C:/Users/Ray/Documents/我的專案/AK-Threads-booster/tests/E2E_TESTING_NOTICE.md) and [tests/E2E_TESTING_SOP.md](/C:/Users/Ray/Documents/我的專案/AK-Threads-booster/tests/E2E_TESTING_SOP.md) on the fixture tracker with and without `--include-brand-voice`

## Acceptance Criteria

- one command can generate setup artifacts into a target directory
- deterministic files are created in the expected locations
- optional `brand_voice.md` is controlled by a flag
- regression and CLI E2E pass
