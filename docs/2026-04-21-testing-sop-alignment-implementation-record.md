# Testing SOP Alignment Implementation Record

> Date: 2026-04-21
> Backlog item: AKR-017

## What Changed

- Replaced `tests/TEST_SOP.md` with an AK-Threads-Booster-specific validation workflow.
- Added `tests/E2E_TESTING_NOTICE.md`.
- Added `tests/E2E_TESTING_SOP.md`.
- Updated `AGENTS.md` to align roadmap references, plan/record paths, and the validation model with the current repo.
- Added `AKR-017` to `docs/roadmap.md` and marked it done.

## Why Changed

The repository's prior testing rules were inherited from a different project shape and incorrectly assumed frontend/browser tooling plus a `.planning/ROADMAP.md` source. That made acceptance guidance inaccurate for this repo.

## Full Verification Evidence

- Date: 2026-04-21
- Environment: Windows PowerShell, local workspace
- Verification method:
  - grep scan for stale references to frontend/browser/Playwright/npm-based gates
  - manual readback of the updated SOP and AGENTS sections
- Command log reference:
  - `rg -n "frontend|Playwright|npm test|\\.planning/ROADMAP|run_full_tests|run_unittests.py|Node 18\\+" AGENTS.md tests\\TEST_SOP.md tests\\E2E_TESTING_NOTICE.md tests\\E2E_TESTING_SOP.md`
  - `Get-Content -TotalCount 120 tests\\TEST_SOP.md`
  - `Get-Content -TotalCount 140 AGENTS.md`
- Result:
  - repo-incorrect assumptions removed
  - repo-specific test documents now exist

## Known Limitations

- This change only aligns the rules; it does not itself add new executable coverage beyond the already-added Python regression lane.
- Future Node/frontend tooling would require another SOP update before becoming part of the acceptance gate.

## Follow-up Items

- Continue with `AKR-002` and later backlog items under the updated repo-specific SOP.
