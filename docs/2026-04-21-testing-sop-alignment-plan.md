# Testing SOP Alignment Plan

> Date: 2026-04-21
> Backlog item: AKR-017

## Scope

### In scope

- Replace inherited testing SOP content with repo-accurate guidance.
- Add the missing `tests/E2E_TESTING_NOTICE.md` and `tests/E2E_TESTING_SOP.md`.
- Update `AGENTS.md` to reference `docs/roadmap.md` and the real validation model for this repo.

### Out of scope

- executable code changes
- introducing new runtime dependencies
- changing acceptance rules for repositories other than this one

## Design Changes

- Rewrite `tests/TEST_SOP.md` around Python regression tests + fixture-based CLI E2E.
- Add repo-specific E2E definitions and command examples.
- Remove incorrect assumptions about frontend/browser/Playwright validation from `AGENTS.md`.
- Point roadmap references to `docs/roadmap.md`.

## Security Implications

- Documentation-only change.
- No secrets or external services involved.

## Failure Modes And Rollback

- Risk: incomplete removal of old assumptions.
- Mitigation: grep for stale references after editing.
- Rollback: revert the documentation changes in git.

## Test Plan

- Documentation-only exception applies.
- Validation consists of grep-based review to ensure incorrect assumptions were removed.

## Acceptance Criteria

- `tests/TEST_SOP.md` reflects the current repo workflow.
- `tests/E2E_TESTING_NOTICE.md` and `tests/E2E_TESTING_SOP.md` exist.
- `AGENTS.md` no longer requires nonexistent frontend/browser gates for this repo.
