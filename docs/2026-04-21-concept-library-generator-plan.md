# Concept Library Generator Plan

> Date: 2026-04-21
> Backlog item: AKR-003

## Scope

### In scope

- Add a deterministic local generator for `concept_library.md`.
- Read `threads_daily_tracker.json` and derive reusable concept-level summaries.
- Extract concept clusters and lightweight analogy signals from post text.
- Add regression tests using the example tracker.

### Out of scope

- `brand_voice.md` generation (`AKR-004`)
- full `/setup` orchestration (`AKR-005`)
- deep semantic NLP or embedding-based extraction

## Design Changes

### New executable component

- Add `scripts/generate_concept_library.py`

Responsibilities:

- load tracker JSON
- infer concepts primarily from `topics[]` and repeated post-level themes
- identify first mention and latest mention per concept
- classify explanation depth heuristically
- extract analogy candidates from explicit comparison patterns
- derive recurring concept clusters from co-occurring topics
- render markdown aligned to `templates/concept-library-template.md`

### Data flow

1. Input tracker path
2. Parse posts array
3. Build concept index from tracker topics
4. Enrich each concept with:
   - first post/date
   - latest mention
   - frequency
   - related topics
   - explanation depth
5. Extract analogy candidates from text patterns
6. Build concept clusters from repeated topic co-occurrence
7. Render markdown and write `concept_library.md`

## Security Implications

- Reads only local tracker JSON.
- Writes only local markdown output in the workspace.
- No network or secret handling.

## Failure Modes And Rollback

- tracker missing or invalid
- sparse `topics[]` reducing concept quality
- analogy extraction producing low-signal results

Handling:

- fail fast on invalid tracker structure
- degrade gracefully with sparse but deterministic output when topic coverage is thin
- prefer explicit tracker topics over invented concept labels

Rollback:

- render in memory before final write
- git commit boundary remains the acceptance checkpoint

## Test Plan

Source references:

- `tests/TEST_SOP.md`
- `tests/E2E_TESTING_SOP.md`

Planned validation:

1. targeted failing regression test for the new CLI generator
2. targeted passing regression test after implementation
3. Python regression sweep
4. CLI E2E using the example tracker
5. record `pre-commit` unavailability explicitly if still absent

## Acceptance Criteria

- `scripts/generate_concept_library.py` exists and runs locally.
- Generated markdown includes coverage, explained concepts, lightly explained concepts, analogies, concept clusters, and repeat-watch notes.
- Generator is deterministic for the example tracker fixture.
- Regression tests fail before implementation and pass after implementation.
