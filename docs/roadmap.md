# AK-Threads-Booster Roadmap

> Last updated: 2026-04-21
> Purpose: convert currently identified pending gaps into a stable, ordered backlog for implementation.
> Scope source: repository analysis of current skill specs, scripts, templates, and packaging.

## Status Legend

- `backlog` - approved and waiting for implementation
- `in_progress` - currently being implemented
- `blocked` - cannot proceed until dependency is resolved
- `done` - completed and accepted
- `deferred` - intentionally postponed

## Ordering Rules

1. Finish `Now` items before opening `Next` unless a dependency forces reordering.
2. Within each bucket, implement items by ascending `Item ID`.
3. Child work should stay under the parent item instead of creating duplicate backlog entries.
4. Any future implementation plan and implementation record should reference the relevant `Item ID`.

## Now

| Item ID | Title | Status | Priority | Area | Depends On |
|---------|-------|--------|----------|------|------------|
| AKR-001 | Establish roadmap and backlog governance | done | P0 | docs / planning | - |
| AKR-017 | Align testing SOP and AGENTS rules with repo reality | done | P0 | docs / governance | - |
| AKR-002 | Programmatic `style_guide.md` generation | done | P0 | setup / analysis | - |
| AKR-003 | Programmatic `concept_library.md` generation | done | P0 | setup / analysis | AKR-002 |
| AKR-004 | Programmatic `brand_voice.md` generation | done | P0 | voice / drafting | AKR-002 |
| AKR-005 | Shared artifact generation pipeline for `/setup` | done | P0 | setup / orchestration | AKR-002, AKR-003, AKR-004 |
| AKR-006 | Shared tracker IO, backup, and mutation utilities | done | P0 | scripts / data integrity | - |
| AKR-007 | Enforce `/refresh` headless log contract in executable code | done | P0 | refresh / auditability | AKR-006 |
| AKR-008 | Enforce freshness audit log contract for `/topics` and `/draft` | done | P0 | topics / draft / auditability | AKR-006 |
| AKR-009 | Implement `/review` log-health checks and degraded-mode analysis helpers | done | P0 | review / auditability | AKR-007, AKR-008 |

## Next

| Item ID | Title | Status | Priority | Area | Depends On |
|---------|-------|--------|----------|------|------------|
| AKR-010 | Legacy tracker migration and markdown enrichment automation | backlog | P1 | setup / migration | AKR-006 |
| AKR-011 | Tracker schema validation and write guards | backlog | P1 | scripts / validation | AKR-006 |
| AKR-012 | Sample-data regression tests for scripts and generated artifacts | backlog | P1 | testing | AKR-002, AKR-003, AKR-004, AKR-006 |
| AKR-013 | Repo-local test harness and CI-parity verification flow | backlog | P1 | testing / tooling | AKR-012 |

## Later

| Item ID | Title | Status | Priority | Area | Depends On |
|---------|-------|--------|----------|------|------------|
| AKR-014 | Reduce duplicated schema scaffolding across import/update scripts | backlog | P2 | maintainability | AKR-006, AKR-011 |
| AKR-015 | Expand semantic clustering and topic classification beyond heuristics | backlog | P2 | topic freshness / NLP | AKR-012 |
| AKR-016 | Add deterministic report-generation helpers for analysis outputs | backlog | P2 | analyze / predict / review | AKR-002, AKR-003, AKR-004 |

## Backlog Details

### AKR-001 - Establish roadmap and backlog governance

- Status: `done`
- Priority: `P0`
- Problem:
  The repository had no formal roadmap or stable backlog IDs, making follow-up implementation hard to plan and track.
- Target outcome:
  A single `docs/roadmap.md` file that registers all currently known pending gaps in execution order.
- Acceptance notes:
  The roadmap exists, uses stable IDs, and groups work into `Now / Next / Later`.

### AKR-002 - Programmatic `style_guide.md` generation

- Status: `done`
- Priority: `P0`
- Problem:
  `/setup` specifies structured `style_guide.md` output, but the repository has no deterministic local generator for it.
- Target outcome:
  Add executable logic that reads `threads_daily_tracker.json` and produces `style_guide.md` from measurable post features and performance aggregates.
- Scope:
  Hook type summaries, word-count bands, ending patterns, content-type mix, emotional arc placeholders, signature phrases, confidence notes.
- Acceptance notes:
  Running the generator on sample tracker data produces a stable markdown file matching the template shape and can be re-run safely.
  Implemented by `scripts/generate_style_guide.py` with regression coverage in `tests/test_generate_style_guide.py`.

### AKR-017 - Align testing SOP and AGENTS rules with repo reality

- Status: `done`
- Priority: `P0`
- Problem:
  The repository's testing SOP and AGENTS rules were inherited from a different project shape and incorrectly assumed frontend/browser tooling plus `.planning/ROADMAP.md`.
- Target outcome:
  Replace those assumptions with rules that match this repo's actual execution model: docs + Python scripts + fixture-based CLI E2E + `docs/roadmap.md`.
- Acceptance notes:
  `tests/TEST_SOP.md`, `tests/E2E_TESTING_NOTICE.md`, `tests/E2E_TESTING_SOP.md`, and `AGENTS.md` now describe the current repo truth rather than a foreign application stack.

### AKR-003 - Programmatic `concept_library.md` generation

- Status: `done`
- Priority: `P0`
- Problem:
  `concept_library.md` is defined as a core setup artifact but is not generated by code.
- Target outcome:
  Add deterministic extraction of repeated concepts, analogies, concept clusters, and shallow-explanation candidates from tracker post text.
- Scope:
  Concept indexing, analogy capture, repeat-watch notes, markdown rendering compatible with the existing template.
- Acceptance notes:
  A repeatable generator creates `concept_library.md` from tracker input and preserves empty-section handling when data is thin.
  Implemented by `scripts/generate_concept_library.py` with regression coverage in `tests/test_generate_concept_library.py`.

### AKR-004 - Programmatic `brand_voice.md` generation

- Status: `done`
- Priority: `P0`
- Problem:
  `/voice` relies on a rich qualitative profile, but there is no executable pipeline for generating `brand_voice.md`.
- Target outcome:
  Add a reproducible generator that derives sentence structure, tone patterns, self-reference habits, humor style, taboo phrases, and quick-reference drafting cues from posts plus author replies.
- Scope:
  Evidence-backed section generation and graceful degradation when reply data is limited.
- Acceptance notes:
  The generator emits a markdown profile aligned to the example/template structure and cites source snippets or counts per section.
  Implemented by `scripts/generate_brand_voice.py` with regression coverage in `tests/test_generate_brand_voice.py`.

### AKR-005 - Shared artifact generation pipeline for `/setup`

- Status: `done`
- Priority: `P0`
- Problem:
  `/setup` currently depends on the agent stitching together multiple outputs manually instead of invoking a stable local pipeline.
- Target outcome:
  Create one setup-oriented orchestration entrypoint that runs tracker normalization, style guide generation, concept library generation, brand voice generation when requested, and companion rendering.
- Scope:
  Consistent file ordering, overwrite behavior, backup behavior, and summary output.
- Acceptance notes:
  A single command or module can produce all setup artifacts in a predictable order from a tracker input.
  Implemented by `scripts/run_setup_artifacts.py` with regression coverage in `tests/test_run_setup_artifacts.py`.

### AKR-006 - Shared tracker IO, backup, and mutation utilities

- Status: `done`
- Priority: `P0`
- Problem:
  Backup rotation, tracker loading, schema defaults, and write safety are duplicated or only partially enforced across scripts and skill specs.
- Target outcome:
  Introduce reusable utilities for tracker read/write, backup rotation, timestamp helpers, scaffold hydration, and safe mutation.
- Scope:
  Utilities shared by `predict`, `review`, `refresh`, setup generators, and future validation code.
- Acceptance notes:
  Existing scripts can call the shared layer without behavior regressions, and backup naming/retention becomes consistent.
  Implemented by `scripts/tracker_utils.py`, with `fetch_threads.py`, `parse_export.py`, and `update_snapshots.py` refactored onto the shared layer and regression coverage in `tests/test_tracker_utils.py` plus `tests/test_parse_export.py`.

### AKR-007 - Enforce `/refresh` headless log contract in executable code

- Status: `done`
- Priority: `P0`
- Problem:
  The `/refresh` skill defines strict JSON-line success/failure logging, but the repository currently implements only the API update script and not the full log contract in local code.
- Target outcome:
  Add executable helpers for success/failure log writing, reason codes, bounded failure handling, and summary generation.
- Scope:
  `threads_refresh.log` format, compact status entries, and compatibility with `/review`.
- Acceptance notes:
  Refresh-related code writes contract-compliant JSON lines for success and failure cases, and the output is machine-readable by downstream tooling.
  Implemented by `scripts/refresh_logging.py` plus `update_snapshots.py` headless logging integration, with regression coverage in `tests/test_refresh_logging.py`.

### AKR-008 - Enforce freshness audit log contract for `/topics` and `/draft`

- Status: `done`
- Priority: `P0`
- Problem:
  `/topics` and `/draft` require JSON-line freshness audit records, but this behavior is currently specified only in markdown.
- Target outcome:
  Provide shared freshness-log helpers and a small local contract for appending per-run audit entries.
- Scope:
  `run_id`, topic/candidate slug, performed/unavailable/skipped states, verdict/decision fields, and timestamp consistency.
- Acceptance notes:
  Code paths used by topic/draft automation can append valid `threads_freshness.log` entries without duplicating formatting logic.
  Implemented by `scripts/freshness_logging.py` and `scripts/log_freshness_audit.py`, with regression coverage in `tests/test_freshness_logging.py`.

### AKR-009 - Implement `/review` log-health checks and degraded-mode analysis helpers

- Status: `done`
- Priority: `P0`
- Problem:
  `/review` specifies health analysis over `threads_freshness.log` and `threads_refresh.log`, but there is no local parser/helper layer to support that logic.
- Target outcome:
  Add reusable log readers and summarizers that compute degraded-run ratios, missing freshness gates, dominant refresh failures, and stale-refresh warnings.
- Scope:
  Grouping by `run_id`, fallback grouping rules, recent-window summaries, and review-facing text helpers.
- Acceptance notes:
  A local helper can load the logs and return structured summaries that match the review spec's required checks.
  Implemented by `scripts/review_log_health.py` and `scripts/summarize_log_health.py`, with regression coverage in `tests/test_review_log_health.py`.

### AKR-010 - Legacy tracker migration and markdown enrichment automation

- Status: `backlog`
- Priority: `P1`
- Problem:
  Path E migration in `/setup` is detailed, but there is no dedicated migration script implementing the backup, transform, and markdown-enrichment workflow.
- Target outcome:
  Add an executable migration path for pre-v1 trackers and optional enrichment from legacy markdown companions.
- Scope:
  Legacy schema detection, backup creation, field mapping, archive parsing, comment attachment heuristics, validation, and summary reporting.
- Acceptance notes:
  A legacy tracker plus optional markdown files can be upgraded into the current tracker schema without manual field surgery.

### AKR-011 - Tracker schema validation and write guards

- Status: `backlog`
- Priority: `P1`
- Problem:
  Tracker shape is defined in docs and templates, but writes are not protected by a dedicated validation layer.
- Target outcome:
  Add schema validation and fail-fast checks before writing tracker mutations.
- Scope:
  Required fields, list-vs-dict shape checks, metrics defaults, comments defaults, and artifact-level validation before render.
- Acceptance notes:
  Invalid tracker mutations are rejected before write, with actionable error messages.

### AKR-012 - Sample-data regression tests for scripts and generated artifacts

- Status: `backlog`
- Priority: `P1`
- Problem:
  The repo has examples but no automated regression layer proving script behavior against sample data.
- Target outcome:
  Add tests for tracker rendering, topic-freshness annotation, setup artifact generation, and migration behavior using repo-local fixtures.
- Scope:
  Deterministic sample trackers, output assertions, and regression coverage for representative edge cases.
- Acceptance notes:
  Tests fail on contract drift and pass on stable expected output from fixtures.

### AKR-013 - Repo-local test harness and CI-parity verification flow

- Status: `backlog`
- Priority: `P1`
- Problem:
  The repository currently lacks the local validation harness and CI-parity structure expected for dependable changes.
- Target outcome:
  Add a documented, repo-local test entrypoint for the script layer plus supporting configuration for repeatable validation.
- Scope:
  Python test runner choice, fixture organization, script invocation coverage, and a clear local command path.
- Acceptance notes:
  Contributors can run one local validation flow and verify core script contracts before merging.

### AKR-014 - Reduce duplicated schema scaffolding across import/update scripts

- Status: `backlog`
- Priority: `P2`
- Problem:
  Post scaffold construction is repeated across `fetch_threads.py`, `parse_export.py`, and `update_snapshots.py`.
- Target outcome:
  Consolidate repeated tracker/post scaffold logic into shared factories.
- Scope:
  Common defaults, empty signal blocks, review state construction, and post bootstrap behavior.
- Acceptance notes:
  Script duplication is reduced without changing external output format.

### AKR-015 - Expand semantic clustering and topic classification beyond heuristics

- Status: `backlog`
- Priority: `P2`
- Problem:
  Topic clustering currently relies on lightweight heuristics. It is useful, but still coarse for multilingual and nuance-heavy content.
- Target outcome:
  Improve clustering quality, topic labeling, and content-type inference while preserving offline/local operation where possible.
- Scope:
  Better tokenization, optional language-aware handling, improved cluster labels, and more robust similarity tuning.
- Acceptance notes:
  Cluster quality improves on sample data without breaking current tracker fields or requiring online services by default.

### AKR-016 - Add deterministic report-generation helpers for analysis outputs

- Status: `backlog`
- Priority: `P2`
- Problem:
  High-level report structures for analyze/predict/review are well specified, but there are no local helper layers to normalize repeated report assembly logic.
- Target outcome:
  Add helper modules that turn structured inputs into consistent report sections and summaries.
- Scope:
  Reference-strength rendering, prediction tables, review comparison tables, and standard warning blocks.
- Acceptance notes:
  Downstream modules can reuse shared formatting logic while keeping final judgment with the agent.
