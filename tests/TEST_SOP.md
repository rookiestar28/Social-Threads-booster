# Social-Threads-Booster Test SOP

This document is the source-of-truth local verification workflow for **Social-Threads-Booster**.
Use it before push and before marking any implementation as accepted.

## Scope

- Python regression tests under `tests/test_*.py`
- Fixture-based CLI E2E for local deterministic scripts
- Repository hygiene checks via `pre-commit` when available
- Targeted manual smoke validation for credential-dependent Threads API scripts when those scripts are changed

This repository is a **skill/plugin + Python scripts** repo.
It does **not** currently have a frontend application or Playwright browser lane.

## Required Reading Order

1. `tests/TEST_SOP.md`
2. `tests/E2E_TESTING_NOTICE.md`
3. `tests/E2E_TESTING_SOP.md`

## Acceptance Rule

A change is not accepted until required checks pass and evidence is recorded.

Required minimum gate:

1. `pre-commit run detect-secrets --all-files` when `pre-commit` is available
2. `pre-commit run --all-files --show-diff-on-failure` when `pre-commit` is available
3. `python -m unittest discover -s tests -p "test_*.py"`
4. Targeted CLI E2E per `tests/E2E_TESTING_SOP.md` for every touched deterministic script

Additional gate when credential-dependent scripts are touched:

5. Record one of:
   - a targeted manual smoke run with valid credentials, or
   - an explicit verification note that secrets/tokens were unavailable and only deterministic coverage was possible

### Bugfix/Hotfix Rule (Reproduce -> Pin -> Sweep)

For bugfix/hotfix work, acceptance evidence must include:

1. pre-fix reproduction evidence
2. post-fix targeted regression evidence
3. final full-gate evidence

### Documentation-only Exception

If all touched files are documentation/planning text only and no executable behavior is affected, full test execution is optional.

## Prerequisites

- Python 3.10+
- Recommended repo-local venv:
  - Windows: `.venv`
  - WSL/Linux: `.venv-wsl` or `.venv`
- `pre-commit` available in the interpreter used for checks if hygiene checks are expected

Node.js is **not** part of the default validation path for this repo.
Do not invent a Node-based gate unless the repo later adds actual Node tooling.

## Quick Start (Current CI-parity Core)

### Windows / PowerShell

```powershell
python -m unittest discover -s tests -p "test_*.py"
```

Then run the relevant CLI E2E commands from `tests/E2E_TESTING_SOP.md`.

### Linux / WSL

```bash
python -m unittest discover -s tests -p "test_*.py"
```

Then run the relevant CLI E2E commands from `tests/E2E_TESTING_SOP.md`.

## Manual Staged Workflow

1. Detect secrets if `pre-commit` is available:

```bash
pre-commit run detect-secrets --all-files
```

2. Run all hooks if `pre-commit` is available:

```bash
pre-commit run --all-files --show-diff-on-failure
```

Important: if hooks auto-fix files, review/stage/commit those changes, then rerun until clean.

3. Run Python regression tests:

```bash
python -m unittest discover -s tests -p "test_*.py"
```

4. Run targeted CLI E2E for changed deterministic scripts:

```bash
# Follow the commands in tests/E2E_TESTING_SOP.md
```

5. If credential-dependent scripts were touched, record one of:

- a manual smoke command and result, or
- a clear statement that credentials were unavailable

## Environment Guardrails

- Keep the Python interpreter consistent across all commands.
- Do not mix global and venv-installed `pre-commit` accidentally.
- Keep all generated verification artifacts inside the repo workspace, typically under `.tmp/`.
- Treat `.tmp/` outputs as disposable verification artifacts; do not stage them.
- If a script mutates its input tracker, run it on a copy under `.tmp/` during E2E.

## Evidence Recording

Implementation records must include:

- date/time
- OS/environment
- command log reference
- pass/fail result for each required stage
- explicit note for any unavailable gate
