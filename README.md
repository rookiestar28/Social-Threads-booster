# Social-Booster

Social-Booster is a local, AI-native workflow toolkit for creators who want better posting decisions from their own historical performance data.

It is not a generic post generator and it does not promise viral outcomes. It combines agent skills with deterministic Python scripts so a creator can import history, understand patterns, draft more deliberately, estimate performance, and review actual results.

The core idea is simple: every post should improve the next decision.

---

## Table of Contents

- [What It Does](#what-it-does)
- [Main Workflows](#main-workflows)
- [Multi-Platform Support](#multi-platform-support)
- [Recent Improvements](#recent-improvements)
- [Generated Files](#generated-files)
- [Script Reference](#script-reference)
- [Recommended Flow](#recommended-flow)
- [Installation](#installation)
- [Requirements](#requirements)
- [Testing](#testing)
- [License](#license)

---

## What It Does

Social-Booster helps answer operational creator questions:

- Which topic is worth posting now?
- Is this angle already stale for the account?
- Does this draft fit the creator's historical voice?
- What is the main distribution risk before publishing?
- What performance range is realistic?
- Did the real result confirm or weaken the original assumption?

The repository currently provides:

- modular agent skills under `skills/`
- platform-neutral tracker helpers
- platform adapter contracts and read/normalize adapters
- local artifact generators for style, concepts, and brand voice
- prediction and review helper scripts
- deterministic test and CLI E2E validation

---

## Main Workflows

### `/setup`

Initializes the local workspace from supported inputs, then generates the standard working files:

- tracker JSON
- `style_guide.md`
- `concept_library.md`
- readable companion Markdown files
- optional `brand_voice.md`

Threads remains the most mature end-to-end import/refresh path, while platform-neutral tracker migration is available for broader multi-platform data.

### `/topics`

Recommends topics from:

- historical performance
- comments and audience demand
- semantic freshness and fatigue risk
- recent topic distribution
- concept-library extension opportunities
- external freshness checks when search is available

For platform-neutral trackers, topic mining is routed per platform first so incompatible metric baselines are not silently mixed.

### `/draft`

Creates a starting draft from a selected topic using:

- `brand_voice.md`
- `style_guide.md`
- historical posts
- `concept_library.md`
- freshness checks
- optional runtime preferences from `social_booster_config.json`

For non-Threads targets, `/draft` now applies platform routing first, so video-first, media-centric, forum-shaped, professional, and text-native platforms are handled differently.

### `/analyze`

Diagnoses a finished post without rewriting it by default. It checks:

- algorithm red lines
- suppression risks
- hook and payoff alignment
- follower-fit versus stranger-fit
- historical style match
- share and comment potential
- AI-tone traces

For platform-neutral trackers, analysis builds comparable sets within the target platform before using cross-platform context.

### `/predict`

Estimates conservative, baseline, and optimistic 24-hour performance ranges from comparable historical posts. Prediction snapshots can be stored safely and later compared by `/review`.

For platform-neutral trackers, predictions are platform-local first and unavailable metrics are marked unavailable instead of being inferred from another platform.

### `/review`

Compares actual results against predictions, records what was validated or weakened, and preserves learning in the tracker without overwriting the original prediction snapshot.

### `/refresh`

Updates metrics and comments where supported. API-backed refresh is preferred; browser-assisted refresh exists as a fallback for compatible local runtimes.

### `/voice`

Builds a reusable brand voice profile with preserved manual refinements, recurring phrase inventory, opener/closer patterns, rhythm markers, register markers, and confidence notes.

---

## Multi-Platform Support

Social-Booster now has a platform-neutral foundation in addition to the original Threads workflow.

Implemented platform-neutral pieces:

- `scripts/platform_schema.py` for schema-v2 platform-neutral trackers
- `scripts/platform_adapters.py` for normalized adapter domain objects
- `scripts/platform_migration.py` and `scripts/migrate_platform_tracker.py` for Threads-to-platform-neutral migration
- `scripts/capability_registry.py` and `knowledge/platform_api_policy.json` for capability and permission boundaries
- `scripts/platform_workflow_routing.py` for `/topics`, `/draft`, `/analyze`, and `/predict` routing

Implemented adapters and normalizers:

| Platform | Status |
| --- | --- |
| Threads | First-class adapter wrapping the existing Threads path |
| Instagram | Meta Graph-style read/normalize adapter |
| Facebook Pages | Meta Graph-style read/normalize adapter |
| YouTube | Data API and Analytics API split-client adapter |
| Reddit | Submission/comment normalization without invented reach metrics |
| Bluesky | AT Protocol post/reply normalization |
| Mastodon | Instance-aware status/reply normalization |
| X | Tier-gated adapter with fail-closed operation checks |
| LinkedIn | Review-gated member/organization adapter |
| Pinterest | Pin/board/media normalization with optional analytics fields |
| TikTok | Limited product-specific video normalization boundary |

Most adapters are intentionally conservative: they normalize deterministic payloads and fail closed when credentials, product access, API tier, or review approval are unavailable. Publishing and write operations are not broadly implemented unless the platform capability and access model are explicit.

---

## Recent Improvements

Recent completed work includes:

- semantic topic freshness improvements for mixed English/CJK topic extraction and clustering
- platform-neutral tracker schema, fixture corpus, migration, and adapter contract
- first-class adapters for Threads, Meta-family platforms, YouTube, Reddit, Bluesky, Mastodon, X, LinkedIn, Pinterest, and TikTok
- credential-source helpers that avoid storing or printing secrets
- capability review gates for platform-specific API access
- cross-platform routing for topic, draft, analysis, and prediction workflows
- richer brand voice generation with preserved manual refinements and countable inventory
- prediction helper validation, range rendering, placeholder persistence, and review comparison helpers
- sanitized freshness and refresh audit logs
- repo validation entrypoint and deterministic CLI E2E runner

---

## Generated Files

Common local outputs:

| File | Purpose |
| --- | --- |
| `threads_daily_tracker.json` | Legacy/current Threads-shaped tracker used by the mature Threads workflow |
| `social_posts_tracker.json` | Platform-neutral tracker output for multi-platform workflows |
| `style_guide.md` | Quantitative writing and performance patterns |
| `concept_library.md` | Concepts, analogies, recurring clusters, and underdeveloped ideas |
| `brand_voice.md` | Qualitative voice profile used mainly by `/draft` |
| `posts_by_date.md` | Human-readable chronological post archive |
| `posts_by_topic.md` | Human-readable topic index |
| `comments.md` | Human-readable comment log |
| `threads_freshness.log` | JSONL freshness-check audit log |
| `threads_refresh.log` | JSONL refresh audit log |
| `social_booster_config.json` | Optional local runtime preferences, ignored by Git |
| `platform_accounts.local.json` | Optional local account context file, ignored by Git |

Do not store credentials in tracker files, generated Markdown, logs, or config files.

---

## Script Reference

Core setup and tracker scripts:

| Script | Function |
| --- | --- |
| `scripts/fetch_threads.py` | Fetch Threads posts, metrics, and replies |
| `scripts/parse_export.py` | Convert a Meta account export into tracker format |
| `scripts/migrate_legacy_tracker.py` | Migrate older tracker shapes with rollback backup |
| `scripts/migrate_platform_tracker.py` | Convert a Threads tracker to schema-v2 platform-neutral format |
| `scripts/tracker_utils.py` | Shared tracker validation, atomic save, snapshots, and backups |
| `scripts/update_snapshots.py` | Refresh metrics, append snapshots, and update checkpoint windows |

Artifact and workflow helper scripts:

| Script | Function |
| --- | --- |
| `scripts/run_setup_artifacts.py` | Generate the standard setup artifact bundle |
| `scripts/generate_style_guide.py` | Generate `style_guide.md` |
| `scripts/generate_concept_library.py` | Generate `concept_library.md` |
| `scripts/generate_brand_voice.py` | Generate `brand_voice.md` |
| `scripts/render_companions.py` | Render readable post, topic, and comment Markdown files |
| `scripts/update_topic_freshness.py` | Add semantic freshness and fatigue signals |
| `scripts/prediction_helpers.py` | Validate, render, and persist prediction snapshots |
| `scripts/review_helpers.py` | Build prediction-vs-actual review summaries |
| `scripts/log_freshness_audit.py` | Append freshness-check audit entries |
| `scripts/summarize_log_health.py` | Summarize refresh and freshness log health |

Platform and safety scripts:

| Script | Function |
| --- | --- |
| `scripts/platform_schema.py` | Build and validate platform-neutral tracker objects |
| `scripts/platform_adapters.py` | Shared normalized adapter contract and domain objects |
| `scripts/platform_workflow_routing.py` | Build platform-aware routing plans for core workflows |
| `scripts/threads_adapter.py` | Threads platform adapter |
| `scripts/meta_adapters.py` | Instagram and Facebook Pages adapters |
| `scripts/youtube_adapter.py` | YouTube adapter |
| `scripts/reddit_adapter.py` | Reddit adapter |
| `scripts/open_network_adapters.py` | Bluesky and Mastodon adapters |
| `scripts/x_adapter.py` | X adapter |
| `scripts/linkedin_adapter.py` | LinkedIn adapter |
| `scripts/pinterest_adapter.py` | Pinterest adapter |
| `scripts/tiktok_adapter.py` | TikTok adapter |
| `scripts/account_context.py` | Load safe platform/account context |
| `scripts/credential_sources.py` | Resolve credentials from env vars or token files |
| `scripts/validate_platform_review.py` | Validate platform adapter review evidence |
| `scripts/workflow_preferences.py` | Validate optional workflow runtime preferences |
| `scripts/validate_repo.py` | Run the repository validation gate |

---

## Recommended Flow

First-time setup:

```text
/setup
/voice
```

Before posting:

```text
/topics
/draft
/analyze
/predict
```

After posting:

```text
/refresh
/review
```

---

## Installation

Claude Code plugin install:

```bash
claude install-plugin https://github.com/rookiestar28/Social-Booster
```

Manual install:

```bash
git clone https://github.com/rookiestar28/Social-Booster.git
cd Social-Booster
python -m pip install -r scripts/requirements.txt
```

Place the repository in the plugin or skill directory used by your agent runtime.

---

## Requirements

- Python 3.10+
- `requests` for API-backed paths
- a compatible AI agent runtime for the skill workflows
- optional Threads API token for the mature refresh path
- optional platform credentials for adapter smoke testing
- optional compatible browser runtime for browser-assisted refresh

---

## Testing

Run the full local validation gate:

```bash
python scripts/validate_repo.py
```

Or run only Python regression tests:

```bash
python -m unittest discover -s tests -p "test_*.py"
```

The maintained validation gate covers internal guardrails, Python regression tests, and fixture-based CLI E2E workflows. If no `.pre-commit-config.yaml` exists, pre-commit lanes are reported as skipped by the validation runner.

---

## License

MIT License. See [LICENSE](./LICENSE).
