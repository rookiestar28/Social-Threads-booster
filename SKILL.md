---
name: ak-threads-booster
description: "Threads growth operating system for topic selection, drafting, analysis, prediction, review, and tracker refresh based on the user's own post history."
allowed-tools: Read, Glob, Grep
---

# AK體-基於Threads演算法的優化skill

`ak-threads-booster` remains the internal skill id for routing and installation.

Use this as the single entry point for the AK Threads workflow.

This skill is for creators who want to pick stronger topics, write posts with clearer upside, and improve over time using their own Threads history.

It is not a viral-post guarantee engine. It is a decision system:

- find topic angles with real demand
- avoid obvious repetition and red lines
- draft from the user's own voice and history
- review outcomes and feed the learning back into the tracker

## Intent Routing

Classify the user's request first, then open and follow one primary module unless the task clearly needs a short sequence.

Each sub-skill is located via `Glob **/skills/<name>/SKILL.md` so resolution works regardless of where the plugin is installed. Do not assume an absolute path or environment variable.

- Setup / import / initialize / backfill history -> Glob `**/skills/setup/SKILL.md`
- Refresh tracker / update metrics / scrape own profile -> Glob `**/skills/refresh/SKILL.md`
- Analyze a finished post / inspect / AK-review a draft -> Glob `**/skills/analyze/SKILL.md`
- Draft / write / 起草 / 寫文 -> Glob `**/skills/draft/SKILL.md`
- Predict likely 24-hour performance / expectation check -> Glob `**/skills/predict/SKILL.md`
- Review actual post performance / compare against prediction -> Glob `**/skills/review/SKILL.md`
- Mine next topics / topic suggestions / 選題 -> Glob `**/skills/topics/SKILL.md`
- Build brand voice / voice analysis -> Glob `**/skills/voice/SKILL.md`

## Routing Rules

1. Do not answer from this file alone when a module exists for the request.
2. Open the matched module and follow its workflow.
3. If the user asks for a combined task, use the smallest valid sequence:
   - first-use account workflow -> setup, then voice if needed
   - write from historical data -> setup or voice first if data is missing, then draft
   - post decision flow -> analyze, then predict if the user asks for a range
   - post-publication learning flow -> review
4. Keep outputs grounded in the user's own tracker whenever available.
5. If `threads_daily_tracker.json` is missing, do not pretend the work is data-backed. Ask for fallback history or use the setup path.

## Working Data

Look in the working directory for:

- `threads_daily_tracker.json` - canonical machine-readable tracker
- `style_guide.md` - produced by `/setup`
- `concept_library.md` - produced by `/setup`
- `brand_voice.md` - produced by `/voice`, referenced by `/draft`
- `posts_by_date.md` - human-readable archive
- `posts_by_topic.md` - human-readable topic index
- `comments.md` - human-readable flat comment log
- `threads_freshness.log` - audit log for `/draft` and `/topics` freshness gates, read by `/review`
- `threads_refresh.log` - audit log for `/refresh` runs, read by `/review`

If legacy Chinese companion filenames already exist, treat them as equivalent companion files instead of forcing a rename.

If only the tracker exists, continue in tracker-only fallback mode when the chosen module allows it. If the tracker is missing, do not pretend the work is data-backed - ask for fallback history or use `/setup`.
