# Brand Voice Generator Plan

> Date: 2026-04-21
> Backlog item: AKR-004

## Scope

### In scope

- Add a deterministic local generator for `brand_voice.md`.
- Analyze historical posts and inferred author replies from the tracker.
- Produce sectioned qualitative output with evidence snippets.
- Add regression coverage using the example tracker fixture.

### Out of scope

- deep LLM-authored stylistic interpretation beyond local heuristics
- full `/setup` orchestration
- replacing `/voice`'s higher-level judgment role entirely

## Design Changes

### New executable component

- Add `scripts/generate_brand_voice.py`

Responsibilities:

- infer the author handle when possible
- analyze posts + author replies for sentence, tone, emotional, humor, address, and rhythm patterns
- collect supporting evidence snippets
- render markdown aligned to the repo's `brand_voice.md` example shape

### Data flow

1. Input tracker path
2. Parse posts
3. Infer author replies from `account.handle`, `author_replies`, or repeated reply handle patterns
4. Derive heuristic voice features
5. Select representative evidence snippets
6. Render markdown and write `brand_voice.md`

## Security Implications

- Reads only local tracker data.
- Writes only local markdown output in the workspace.
- No network access or secret handling.

## Failure Modes And Rollback

- tracker missing or malformed
- weak or absent author-reply data limiting reply-tone analysis
- heuristic tone classification being lower-confidence on sparse datasets

Handling:

- fail fast on invalid tracker structure
- degrade explicitly when reply evidence is thin
- keep output deterministic and evidence-backed

Rollback:

- in-memory render before final write
- git commit remains the acceptance boundary

## Test Plan

Source references:

- `tests/TEST_SOP.md`
- `tests/E2E_TESTING_SOP.md`

Planned validation:

1. targeted failing CLI regression test
2. targeted passing regression test after implementation
3. Python regression sweep
4. CLI E2E using the example tracker
5. explicit note if `pre-commit` remains unavailable

## Acceptance Criteria

- `scripts/generate_brand_voice.py` exists and runs locally.
- Generated markdown includes the major brand voice sections plus a quick reference summary.
- Output cites evidence snippets or counted observations.
- Regression tests fail before implementation and pass after implementation.
