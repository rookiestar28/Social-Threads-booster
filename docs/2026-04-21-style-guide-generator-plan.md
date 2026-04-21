# AKR-002 Style Guide Generator Plan

> Date: 2026-04-21
> Backlog item: AKR-002
> Location override: per explicit user instruction, this implementation plan is stored in `docs/` instead of `.planning/`.

## Scope

### In scope

- Add a deterministic local generator for `style_guide.md`.
- Read `threads_daily_tracker.json` and derive measurable style/performance summaries.
- Render output in the existing template shape closely enough for downstream human/agent use.
- Add regression tests using the existing example tracker.
- Document execution and verification for this item.

### Out of scope

- `concept_library.md` generation (`AKR-003`)
- `brand_voice.md` generation (`AKR-004`)
- full `/setup` orchestration (`AKR-005`)
- broad tracker refactors or shared utility extraction beyond what is strictly needed for this item

## Design Changes

### New executable component

- Add a new script: `scripts/generate_style_guide.py`

Responsibilities:

- load tracker JSON
- derive post-level feature aggregates from tracker fields and raw text
- compute performance statistics from available metrics
- estimate confidence notes from tracker coverage and sample size
- render markdown output to `style_guide.md`

### Data flow

1. Input tracker path
2. Parse posts array
3. Derive missing lightweight features when absent:
   - hook type
   - ending type
   - emotional arc
   - signature phrases / recurring phrases
4. Aggregate metrics by:
   - hook type
   - ending type
   - content type
   - emotional arc
   - word-count band
   - paragraph structure
   - topic cluster
5. Render markdown sections aligned to `templates/style-guide-template.md`
6. Write `style_guide.md`

### API / CLI

Planned command:

```powershell
python scripts/generate_style_guide.py --tracker threads_daily_tracker.json --output style_guide.md
```

Optional future-safe arguments may include `--lang`, but this item should avoid premature expansion unless needed.

## Security Implications

- Reads only local tracker JSON in the workspace.
- Writes only the requested markdown output path in the workspace.
- No network access.
- No execution of untrusted content from the tracker.

## Failure Modes And Rollback

### Failure modes

- tracker missing or invalid JSON
- tracker `posts` field not an array
- sparse metrics leading to partial sections
- multilingual text making phrase extraction noisy

### Handling

- fail fast with actionable error messages for invalid tracker structure
- degrade gracefully for thin data by emitting conservative notes rather than crashing
- keep rendering deterministic even when some sections have weak evidence

### Rollback

- if generation fails, no existing `style_guide.md` should be partially corrupted
- write through a temporary in-memory render then save once
- git commit boundary acts as the acceptance checkpoint

## Test Plan

Source references:

- `tests/TEST_SOP.md`

Observed constraint:

- `tests/E2E_TESTING_NOTICE.md` and `tests/E2E_TESTING_SOP.md` are not present in this repo as of 2026-04-21, so the repo cannot currently satisfy the full documented reading order.
- This item is a backend/script change, so validation will focus on script regression and repository hygiene. Any unavailable gate will be recorded explicitly in the implementation record.

Planned validation for this item:

1. targeted failing test first for style guide generation using fixture data
2. targeted passing test after implementation
3. Python test sweep for added tests
4. `pre-commit run detect-secrets --all-files` if available
5. `pre-commit run --all-files --show-diff-on-failure` if available

## Acceptance Criteria

- `scripts/generate_style_guide.py` exists and runs locally against the sample tracker.
- Generated markdown includes the major template sections and stable derived content.
- Thin data paths render without crashing.
- Regression tests fail before implementation and pass after implementation.
- Changes are committed with a conventional commit message that does not expose internal backlog IDs.
