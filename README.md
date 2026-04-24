# Social-Booster

Social-Booster is an AI-native operating system for social media creators who want to make better posting decisions from their own historical performance data.

It is not a generic post generator and it does not promise viral outcomes. The repository provides a structured skill workflow and supporting Python tools for turning a creator's platform history into a repeatable content process:

- import and normalize historical posts
- generate a style guide and concept library
- analyze drafts before publishing
- recommend topics with demand and freshness signals
- estimate likely performance ranges
- review actual outcomes and preserve learning in the tracker

The core idea is simple: every post should improve the next decision.

---

## Table of Contents

- [Why This Repository Exists](#why-this-repository-exists)
- [Core Strengths](#core-strengths)
- [How It Works](#how-it-works)
- [Main Workflows](#main-workflows)
- [Current Capabilities](#current-capabilities)
- [Generated Files](#generated-files)
- [Script Reference](#script-reference)
- [Recommended Operating Flow](#recommended-operating-flow)
- [Installation](#installation)
- [Requirements](#requirements)
- [Repository Layout](#repository-layout)
- [Testing](#testing)
- [What This Project Is Not](#what-this-project-is-not)
- [License](#license)

---

## Why This Repository Exists

Most creator tools optimize for speed. They help produce more text, but they rarely answer the harder operational questions:

- Which topic is worth posting now?
- Is this angle already stale for the account?
- Does this draft fit the creator's historical voice?
- What is the main distribution risk before publishing?
- Did the actual result confirm or weaken the original assumption?

Social-Booster is built for those decisions. It treats the creator's history as the primary source of truth, then combines structured data, agent workflows, and deterministic scripts into a closed feedback loop.

---

## Core Strengths

### Data-backed creator workflow

The system is centered on `threads_daily_tracker.json`, a canonical local tracker that stores posts, metrics, comments, snapshots, prediction records, review notes, algorithm signals, and psychology signals.

Tracker writes are guarded by schema validation and atomic persistence helpers so malformed or partial tracker JSON is rejected before it replaces user data.

### Modular skill architecture

Each workflow is isolated as a skill module:

- `/setup` for initialization and artifact generation
- `/topics` for topic recommendation
- `/draft` for new post drafting
- `/analyze` for pre-publish diagnosis
- `/predict` for performance range estimation
- `/review` for post-publish learning
- `/refresh` for tracker updates
- `/voice` for brand voice profiling

This separation keeps the system inspectable, extensible, and easier to adapt to different creator workflows.

### Deterministic data pipeline

The repository includes Python scripts for repeatable data operations:

- importing Meta exports
- fetching Threads API data
- migrating older tracker formats
- refreshing metrics snapshots
- generating setup artifacts
- rendering human-readable companion files
- annotating topic freshness and fatigue
- logging freshness and refresh health
- validating platform policy and local account configuration
- validating prediction and review helper data shapes

The agent handles judgment-heavy work. The scripts handle repeatable file and tracker operations.

### Closed-loop learning

The `/predict` and `/review` flow allows the system to compare expectations against actual performance. This makes the tracker more useful over time instead of leaving each post as an isolated event.

Prediction snapshots can be validated, rendered as range tables, stored safely, preserved in history, and later compared against actual metrics with deterministic review helpers.

### Configurable interaction style

Runtime preferences can be stored in an optional local `social_booster_config.json` file. Workflows can run in fast mode, discussion mode, or auto mode without duplicating preference semantics across `/draft`, `/analyze`, and `/review`.

### Honest operating boundaries

Social-Booster is designed to improve decision quality, not guarantee reach. It surfaces confidence levels, missing data, stale metrics, skipped freshness checks, and weak historical baselines instead of hiding uncertainty.

Audit logs are sanitized before write so token-like fields, sensitive query values, bearer tokens, and overly long private text do not leak into machine-readable logs.

---

## How It Works

```text
Data sources
  -> platform APIs, account exports, existing JSON/CSV/Markdown, or browser-assisted profile refresh

Normalization
  -> threads_daily_tracker.json

Generated knowledge assets
  -> style_guide.md
  -> concept_library.md
  -> brand_voice.md
  -> posts_by_date.md / posts_by_topic.md / comments.md

Skill workflows
  -> topics
  -> draft
  -> analyze
  -> predict
  -> review
  -> refresh

Feedback loop
  -> metrics snapshots, prediction comparison, review notes, freshness logs, refresh logs
```

---

## Main Workflows

### 1. Setup and import

`/setup` initializes the workspace by importing historical social-platform data and generating the files that downstream workflows use.

Supported input paths currently include:

- Threads Developer API
- Meta account data export
- existing structured or semi-structured files
- Chrome-assisted profile refresh through a compatible MCP runtime
- migration from an older tracker shape

Threads is the most mature implemented data path today. The architecture and policy guardrails are being shaped for broader mainstream social-platform support.

Primary scripts:

```bash
THREADS_API_TOKEN="..." python scripts/fetch_threads.py --output threads_daily_tracker.json
python scripts/parse_export.py --input META_EXPORT_PATH --output threads_daily_tracker.json
python scripts/migrate_legacy_tracker.py --input OLD_TRACKER.json --output threads_daily_tracker.json --write
python scripts/run_setup_artifacts.py --tracker threads_daily_tracker.json --output-dir .
```

For credentialed API workflows, environment variables and token files are preferred over direct CLI secrets.

### 2. Topic recommendation

`/topics` recommends 3 to 5 candidate topics by combining:

- historical performance
- comment demand
- creator reply patterns
- recent topic distribution
- semantic freshness
- external saturation checks when search is available
- concept-library extension opportunities

The goal is not to chase generic trends. The goal is to find topics that are timely, account-fit, and not already exhausted.

### 3. Draft generation

`/draft` creates a starting draft from a selected topic. It uses:

- `brand_voice.md`
- `style_guide.md`
- historical posts
- `concept_library.md`
- freshness checks
- source verification for factual claims
- optional runtime preferences from `social_booster_config.json`

Drafting is intentionally treated as a starting point. The user is expected to edit before publishing.

`brand_voice.md` includes a user-editable `Manual Refinements (user-edited)` section. Those refinements are preserved when the Brand Voice file is regenerated and take priority over generated voice observations.

### 4. Pre-publish analysis

`/analyze` is a diagnostic layer for posts the user has already written. It checks:

- algorithm red lines
- suppression risks
- hook and payoff alignment
- follower-fit versus stranger-fit
- historical style match
- share and comment potential
- AI-tone traces

By default, `/analyze` does not rewrite the whole post. It gives pointed, local changes so the user stays in control of the final voice.

### 5. Performance prediction

`/predict` estimates conservative, baseline, and optimistic 24-hour ranges using comparable historical posts.

It is designed as expectation management, not false precision. The prediction can be stored in the tracker so `/review` can compare it against real outcomes later.

The helper layer validates prediction snapshot shape, excludes unstable quote-volume prediction by default, renders range tables, creates pending placeholders for unpublished drafts, and prevents silent overwrite of existing prediction snapshots.

### 6. Post-publish review

`/review` closes the loop after publishing. It compares actual metrics against prior predictions, updates review state, records validated or weakened assumptions, and checks whether freshness or refresh automation has degraded.

Review helpers render prediction-versus-actual comparison tables, classify actual results as under, inside, or over the predicted band, and update `review_state` without changing the original `prediction_snapshot`.

### 7. Refresh and snapshots

`/refresh` and `scripts/update_snapshots.py` keep metrics and comments current.

API-backed refresh is preferred for reliability. Chrome-assisted refresh is available as a fallback when the user cannot use the API, but it depends on a compatible logged-in browser runtime.

The Chrome path has a deterministic extraction and merge seam for selector-health checks, metric parsing, snapshot append behavior, comment merging, and expired pending-placeholder cleanup. Unit tests do not require live browser state.

---

## Current Capabilities

### Brand Voice preservation and inventory

`scripts/generate_brand_voice.py` now produces a richer `brand_voice.md` with:

- preserved `Manual Refinements (user-edited)`
- recurring signature word and phrase counts
- opener and closer pattern inventory
- punctuation and rhythm markers
- language/register markers
- argumentation style inventory
- confidence labels when evidence is thin

### Runtime preferences

`scripts/workflow_preferences.py` validates optional runtime preferences for workflow behavior:

- `workflows.draft.discussion_mode`
- `workflows.draft.research_angle_expansion`
- `workflows.analyze.discussion_mode`
- `workflows.review.discussion_mode`

Local preference files are intentionally ignored by Git.

### Tracker safety

Tracker persistence now includes:

- schema validation before save
- actionable validation errors with field paths
- same-directory temp-file writes
- atomic replacement through `os.replace`
- shared metric snapshot and performance-window helpers

### Legacy migration

Legacy tracker migration is available through `scripts/migrate_legacy_tracker.py`. It supports:

- dry-run JSON summaries
- write mode with rollback backup
- migration from pre-v1 tracker shapes
- optional post archive and comment archive enrichment
- optional companion Markdown regeneration

### Platform and credential boundaries

The repository includes public knowledge and validation helpers for future multi-platform work:

- platform API policy matrix
- platform adapter review gate
- safe account-context loading
- local-only credential-source references

These helpers define guardrails without turning this repository into a hosted platform or storing credentials in tracked files.

### Audit and review support

Freshness and refresh logs are bounded JSONL logs. Helper scripts can:

- append freshness and refresh audit entries
- sanitize sensitive log content
- summarize recent log health
- record bounded draft decision tags
- compare prediction ranges against actual metrics

---

## Generated Files

After setup, the working directory usually contains:

| File | Purpose |
| --- | --- |
| `threads_daily_tracker.json` | Canonical machine-readable tracker |
| `style_guide.md` | Quantitative writing and performance patterns |
| `concept_library.md` | Concepts, analogies, repeated clusters, and underdeveloped ideas |
| `brand_voice.md` | Qualitative voice profile used by `/draft` |
| `posts_by_date.md` | Human-readable chronological post archive |
| `posts_by_topic.md` | Human-readable topic index |
| `comments.md` | Human-readable comment log |
| `threads_freshness.log` | JSONL audit log for freshness checks |
| `threads_refresh.log` | JSONL audit log for refresh runs |
| `social_booster_config.json` | Optional local runtime preferences; ignored by Git |
| `platform_accounts.local.json` | Optional local account-context file; ignored by Git |

---

## Script Reference

| Script | Function |
| --- | --- |
| `scripts/account_context.py` | Load safe platform/account context without storing inline secrets |
| `scripts/check_internal_guardrails.py` | Verify local-only protected files remain ignored and untracked |
| `scripts/chrome_refresh.py` | Testable Chrome refresh extraction and tracker-merge seam |
| `scripts/credential_sources.py` | Resolve credentials from env vars, files, or discouraged direct CLI values |
| `scripts/fetch_threads.py` | Fetch posts, metrics, and replies from the Threads API |
| `scripts/legacy_migration.py` | Core legacy tracker migration and Markdown enrichment helpers |
| `scripts/log_redaction.py` | Sanitize machine-readable audit log entries before write |
| `scripts/migrate_legacy_tracker.py` | Dry-run or write legacy tracker migration with rollback backup |
| `scripts/parse_export.py` | Convert a Meta account export into tracker format |
| `scripts/prediction_helpers.py` | Validate, render, and persist prediction snapshots |
| `scripts/update_snapshots.py` | Refresh metrics, append snapshots, and update checkpoint windows |
| `scripts/generate_style_guide.py` | Generate `style_guide.md` from the tracker |
| `scripts/generate_concept_library.py` | Generate `concept_library.md` from the tracker |
| `scripts/generate_brand_voice.py` | Generate `brand_voice.md` from the tracker |
| `scripts/run_setup_artifacts.py` | Generate the standard setup artifact bundle |
| `scripts/render_companions.py` | Render readable post, topic, and comment Markdown files |
| `scripts/review_helpers.py` | Build prediction-vs-actual review comparison tables and review-state updates |
| `scripts/review_log_health.py` | Parse and summarize refresh/freshness log health |
| `scripts/update_topic_freshness.py` | Add semantic cluster and fatigue signals to tracker posts |
| `scripts/log_freshness_audit.py` | Append freshness-check audit entries |
| `scripts/summarize_log_health.py` | Summarize refresh and freshness log health |
| `scripts/tracker_utils.py` | Shared tracker schema, validation, atomic save, snapshots, and backups |
| `scripts/validate_platform_review.py` | Validate platform adapter review evidence against policy requirements |
| `scripts/workflow_preferences.py` | Validate optional workflow runtime preferences |

---

## Recommended Operating Flow

### First-time setup

```text
/setup
/voice
```

### Before posting

```text
/topics
/draft
/analyze
/predict
```

### After posting

```text
/refresh
/review
```

---

## Installation

### Claude Code plugin install

```bash
claude install-plugin https://github.com/rookiestar28/Social-Booster
```

### Manual install

```bash
git clone https://github.com/rookiestar28/Social-Booster.git
cd Social-Booster
python -m pip install -r scripts/requirements.txt
```

Place the repository in the plugin or skill directory used by your agent runtime.

---

## Requirements

- Python 3.9+
- `requests` for the Threads API path
- a compatible AI agent runtime for the skill workflows
- optional Threads API access token for reliable refresh
- optional Chrome MCP-compatible browser runtime for browser-assisted refresh

---

## Repository Layout

```text
Social-Booster/
|- SKILL.md
|- README.md
|- skills/
|  |- setup/
|  |- refresh/
|  |- analyze/
|  |- draft/
|  |- predict/
|  |- review/
|  |- topics/
|  |- voice/
|- knowledge/
|  |- _shared/
|  |- account-credential-boundary.md
|  |- algorithm.md
|  |- ai-detection.md
|  |- chrome-selectors.md
|  |- data-confidence.md
|  |- platform_api_policy.json
|  |- platform-api-policy.md
|  |- platform-adapter-review-gate.md
|  |- psychology.md
|  |- user-fact-source-of-truth.md
|- scripts/
|- examples/
|- tests/
```

---

## Testing

Run the Python regression suite:

```bash
python -m unittest discover -s tests -p "test_*.py"
```

The tests cover tracker scaffolding, export parsing, setup artifact generation, style guide generation, concept library generation, brand voice generation, and audit-log health helpers.

The current suite also covers tracker validation and atomic persistence, legacy migration, Chrome refresh merge helpers, workflow preferences, account-context boundaries, platform review gates, prediction persistence helpers, and review comparison helpers.

---

## What This Project Is Not

Social-Booster is not:

- a hosted SaaS product
- a browser frontend
- a scheduler by itself
- a viral-post guarantee system
- a replacement for creator judgment

It is a local, data-centered skill and scripting toolkit for making better social content decisions across evolving multi-platform workflows.

---

## License

MIT License. See [LICENSE](./LICENSE).
