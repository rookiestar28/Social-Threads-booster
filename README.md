# Social-Threads-Booster

Social-Threads-Booster is an AI-native operating system for Threads creators who want to make better posting decisions from their own historical data.

It is not a generic post generator and it does not promise viral outcomes. The repository provides a structured skill workflow and supporting Python tools for turning a creator's Threads history into a repeatable content process:

- import and normalize historical posts
- generate a style guide and concept library
- analyze drafts before publishing
- recommend topics with demand and freshness signals
- estimate likely performance ranges
- review actual outcomes and preserve learning in the tracker

The core idea is simple: every post should improve the next decision.

---

## Why This Repository Exists

Most creator tools optimize for speed. They help produce more text, but they rarely answer the harder operational questions:

- Which topic is worth posting now?
- Is this angle already stale for the account?
- Does this draft fit the creator's historical voice?
- What is the main distribution risk before publishing?
- Did the actual result confirm or weaken the original assumption?

Social-Threads-Booster is built for those decisions. It treats the creator's history as the primary source of truth, then combines structured data, agent workflows, and deterministic scripts into a closed feedback loop.

---

## Core Strengths

### Data-backed creator workflow

The system is centered on `threads_daily_tracker.json`, a canonical local tracker that stores posts, metrics, comments, snapshots, prediction records, review notes, algorithm signals, and psychology signals.

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
- refreshing metrics snapshots
- generating setup artifacts
- rendering human-readable companion files
- annotating topic freshness and fatigue
- logging freshness and refresh health

The agent handles judgment-heavy work. The scripts handle repeatable file and tracker operations.

### Closed-loop learning

The `/predict` and `/review` flow allows the system to compare expectations against actual performance. This makes the tracker more useful over time instead of leaving each post as an isolated event.

### Honest operating boundaries

Social-Threads-Booster is designed to improve decision quality, not guarantee reach. It surfaces confidence levels, missing data, stale metrics, skipped freshness checks, and weak historical baselines instead of hiding uncertainty.

---

## How It Works

```text
Data sources
  -> Threads API, Meta export, existing JSON/CSV/Markdown, or Chrome-assisted profile refresh

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

`/setup` initializes the workspace by importing historical Threads data and generating the files that downstream workflows use.

Supported input paths include:

- Threads Developer API
- Meta account data export
- existing structured or semi-structured files
- Chrome-assisted profile refresh through a compatible MCP runtime
- migration from an older tracker shape

Primary scripts:

```bash
python scripts/fetch_threads.py --token YOUR_THREADS_TOKEN --output threads_daily_tracker.json
python scripts/parse_export.py --input META_EXPORT_PATH --output threads_daily_tracker.json
python scripts/run_setup_artifacts.py --tracker threads_daily_tracker.json --output-dir .
```

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

Drafting is intentionally treated as a starting point. The user is expected to edit before publishing.

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

### 6. Post-publish review

`/review` closes the loop after publishing. It compares actual metrics against prior predictions, updates review state, records validated or weakened assumptions, and checks whether freshness or refresh automation has degraded.

### 7. Refresh and snapshots

`/refresh` and `scripts/update_snapshots.py` keep metrics and comments current.

API-backed refresh is preferred for reliability. Chrome-assisted refresh is available as a fallback when the user cannot use the API, but it depends on a compatible logged-in browser runtime.

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

---

## Script Reference

| Script | Function |
| --- | --- |
| `scripts/fetch_threads.py` | Fetch posts, metrics, and replies from the Threads API |
| `scripts/parse_export.py` | Convert a Meta account export into tracker format |
| `scripts/update_snapshots.py` | Refresh metrics, append snapshots, and update checkpoint windows |
| `scripts/generate_style_guide.py` | Generate `style_guide.md` from the tracker |
| `scripts/generate_concept_library.py` | Generate `concept_library.md` from the tracker |
| `scripts/generate_brand_voice.py` | Generate `brand_voice.md` from the tracker |
| `scripts/run_setup_artifacts.py` | Generate the standard setup artifact bundle |
| `scripts/render_companions.py` | Render readable post, topic, and comment Markdown files |
| `scripts/update_topic_freshness.py` | Add semantic cluster and fatigue signals to tracker posts |
| `scripts/log_freshness_audit.py` | Append freshness-check audit entries |
| `scripts/summarize_log_health.py` | Summarize refresh and freshness log health |

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
claude install-plugin https://github.com/rookiestar28/Social-Threads-booster
```

### Manual install

```bash
git clone https://github.com/rookiestar28/Social-Threads-booster.git
cd Social-Threads-booster
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
Social-Threads-Booster/
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
|  |- algorithm.md
|  |- ai-detection.md
|  |- chrome-selectors.md
|  |- data-confidence.md
|  |- psychology.md
|- scripts/
|- templates/
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

---

## What This Project Is Not

Social-Threads-Booster is not:

- a hosted SaaS product
- a browser frontend
- a scheduler by itself
- a viral-post guarantee system
- a replacement for creator judgment

It is a local, data-centered skill and scripting toolkit for making better Threads content decisions.

---

## License

MIT License. See [LICENSE](./LICENSE).
