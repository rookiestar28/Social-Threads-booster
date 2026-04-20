# Shared File Discovery Pattern

> Single reference for how every AK-Threads-Booster sub-skill locates knowledge files, user data, and scripts. Sub-skills read this file instead of restating the full discovery block.

---

## Knowledge files (required for most skills)

Use Glob to locate, relative to the plugin root:

- `**/knowledge/psychology.md` — social media psychology
- `**/knowledge/algorithm.md` — Meta algorithm mechanics
- `**/knowledge/ai-detection.md` — AI-tone detection patterns
- `**/knowledge/data-confidence.md` — shared data-confidence rubric
- `**/knowledge/_shared/principles.md` — consultant principles (load first)
- `**/knowledge/chrome-selectors.md` — Chrome MCP selectors (only `/refresh` needs this)

Each sub-skill only reads the files it actually needs. The required set is listed in that sub-skill's own SKILL.md under a short `Required knowledge files` line rather than a full copy of the glob list.

---

## User data files (working directory)

Glob from the user's working directory:

- `threads_daily_tracker.json` — core post history + metrics + comments
- `style_guide.md` — quantitative style reference, produced by `/setup`
- `concept_library.md` — previously-explained concepts, produced by `/setup` + `/review`
- `brand_voice.md` — qualitative voice profile, produced by `/voice`
- `threads_refresh.log` — last-run health of `/refresh` (may not exist)

Optional user-managed files (skip silently if absent):

- `*topic*`, `*idea*`, `*題材*` — user-maintained topic banks, supported by `/draft` and `/topics`

---

## Script references

Scripts live at `**/scripts/`:

- `fetch_threads.py` — Meta API import
- `parse_export.py` — Meta export import
- `update_snapshots.py` — periodic metrics refresh (API)
- `update_topic_freshness.py` — semantic cluster + freshness scoring

---

## Discovery order

When a sub-skill starts:

1. Load `_shared/principles.md` first.
2. Load any sub-skill-specific knowledge files declared in its SKILL.md.
3. Load `data-confidence.md` if the skill makes claims based on the user's history.
4. Locate user data files. Tracker is the common backbone; style/voice/concept files are upgrades.
5. If a required file is missing, degrade per the fallback rules in the sub-skill's own SKILL.md. Never invent data.
