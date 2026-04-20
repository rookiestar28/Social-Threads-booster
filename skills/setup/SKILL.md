---
name: setup
description: "Initialize AK-Threads-Booster: import historical posts, normalize them into the tracker schema, auto-generate a personalized style guide, and build a concept library. Run on first use or whenever the user wants to backfill account history."
allowed-tools: Read, Write, Edit, Bash, Glob, Grep, WebFetch
---

# AK-Threads-Booster Initialization Module (M1 + M2 + M3)

You are the initialization guide for the AK-Threads-Booster system. Your job is to help the user import account history, normalize it into a stable tracker, generate a style guide, and build a concept library.

---

## Principles & Knowledge

Load `knowledge/_shared/principles.md` before running. Follow discovery order in `knowledge/_shared/discovery.md`. For `/setup` specifically:

- Always load `data-confidence.md` (to report dataset gate in the completion report)
- Load `psychology.md` when generating `style_guide.md` (Step 3)
- Load `ai-detection.md` only if the user asks for a first-pass AI-tone survey during setup

Skill-specific addendum: prefer a stable tracker schema over ad-hoc one-off parsing.

---

## Automation Scripts

The `scripts/` directory is a sibling of `skills/`. Use Glob to locate the scripts:

- Glob `**/scripts/fetch_threads.py` — Fetch posts via Meta Threads API
- Glob `**/scripts/parse_export.py` — Parse Meta account data export

These scripts require Python 3.9+ and the `requests` package for the API path.

---

## Execution Flow

### Step 1: Choose Data Import Path

**Before presenting options**, Glob for `threads_daily_tracker.json` in the working directory. If one exists, run the Path E detection heuristics first — an existing legacy file means migration, not import. Only offer Paths A–D when no tracker is present or the existing file is already v1-schema.

Present these options:

**Path A: Meta Threads API (recommended — full metrics + comments, refreshable)**

Walk the user through each step. Do not assume any prior Meta developer experience.

*A.1 Create the developer app*

1. Open https://developers.facebook.com/ and log in with the Meta account that owns the Threads profile.
2. Top nav → **My Apps** → **Create App**.
3. Use case: **Other** → Next → App type: **Business** → Next.
4. Name the app (e.g., "ak-threads-booster-personal"). Contact email is the same Meta account.

*A.2 Add the Threads product*

1. Inside the new app, go to **Dashboard** → scroll to **Add a product**.
2. Find **Threads API** → click **Set up**.
3. Under **Threads API → Use cases**, add the use cases the user needs — at minimum: `threads_basic`, `threads_content_publish`, `threads_read_replies`, `threads_manage_insights`.

*A.3 Add the account as a Threads Tester*

1. In the Threads API panel, open **Roles** (sometimes labeled **Threads Tester**).
2. Add the Threads handle (e.g., `@yourname`) as a tester.
3. Open threads.com on the account, go to **Settings → Account → Website permissions → Invitations**, and accept the tester invite. If no invite appears, re-check that the Threads handle in the developer dashboard exactly matches the account.

*A.4 Generate a short-lived user access token*

1. Back in the developer dashboard → **Threads API → User Token Generator**.
2. Confirm the 4 scopes are checked.
3. Click **Generate token**, authorize on threads.com, and copy the returned token. This token is valid for 1 hour.

*A.5 (Optional but recommended) Exchange for a long-lived token*

Long-lived tokens last 60 days and can be refreshed. To exchange, the user needs the **App Secret** from **App settings → Basic**. The `fetch_threads.py` script will perform the exchange when `--app-secret` is passed.

*A.6 Run the fetch script*

```bash
# Run from the AK-Threads-Booster directory (where scripts/ lives)
python scripts/fetch_threads.py \
  --token USER_TOKEN \
  --app-secret APP_SECRET_OPTIONAL \
  --output "<user-working-dir>/threads_daily_tracker.json"
```

Replace `<user-working-dir>` with the user's actual working directory. Ask if unsure.

*A.7 Common API errors and how to resolve them*

| Error | Cause | Fix |
|-------|-------|-----|
| `400 Bad Request — permissions` | Missing scope | Re-generate token with all 4 scopes checked |
| `401 Unauthorized` | Token expired (1h short / 60d long) | Regenerate short token or run exchange again |
| `403 user not a tester` | Tester invite not accepted | Accept invite on threads.com Settings |
| `429 Too Many Requests` | 250 calls/user/hour limit hit | Wait an hour, or reduce `--recent N` |
| Empty `posts` list | Account has no public original posts, only replies | Expected — reply-only accounts are not supported |

**Path B: Meta account data export (no metrics, good for read-only accounts)**

*B.1 Request the export*

1. Open https://accountscenter.meta.com/info_and_permissions/dyi/ while logged in as the Threads account.
2. Click **Download or transfer information**.
3. Pick the Threads account → **Next**.
4. Choose **Some of your information** → scroll to **Threads activity** → check all Threads-related categories (posts, replies, followers if wanted).
5. Destination: **Download to device**.
6. Date range: **All time**.
7. Format: **JSON** (the script supports HTML as fallback but JSON parses cleanly).
8. Media quality: **Low** is fine — the script only reads text.
9. Submit the request. Meta takes anywhere from 15 minutes to 48 hours to prepare the archive; the user will get an email when ready.

*B.2 Download and unzip*

1. When the download email arrives, click the link and sign in again.
2. Download the zip, then fully extract it to a folder (not just browse inside the zip, or paths will not resolve).
3. Note the extracted folder's path — this becomes `USER_EXPORT_PATH`.

*B.3 Run the parser*

```bash
# Run from the AK-Threads-Booster directory (where scripts/ lives)
python scripts/parse_export.py \
  --input "USER_EXPORT_PATH" \
  --output "<user-working-dir>/threads_daily_tracker.json"
```

*B.4 Known limitations of the export path*

- No engagement metrics (views / likes / replies / reposts / shares) — they must be backfilled by `/review` checkpoints or by `/refresh` (Chrome MCP path).
- Exports are a point-in-time snapshot. To get fresh comments and metrics later, the user either repeats the export (slow, rate-limited to one request per ~3 days), or switches to the API or `/refresh` path.
- Very old posts may lack some metadata; the parser will leave those fields `null`.

**Path C: Existing data provided directly**

If the user already has JSON, CSV, spreadsheet, notes, or text files:

1. Read the provided file or files
2. Convert them into the standard tracker schema
3. Preserve any available metrics
4. Write `threads_daily_tracker.json`

At minimum, capture post text and creation date. If metrics are missing, leave them as `0` or `null` according to the schema guidance below.

**Path D: Chrome-driven profile scrape (no API, no export wait)**

If the user has the `Claude in Chrome` MCP installed and is logged into Threads in Chrome, the `/refresh` skill can scrape their profile page directly. This is the fastest path for users who cannot or will not go through the Meta developer dashboard and do not want to wait for an export.

1. Verify Chrome MCP is active in the current session.
2. Run `/refresh` with the user's Threads handle.
3. `/refresh` will create or update `threads_daily_tracker.json` with visible posts and metrics.

See `skills/refresh/SKILL.md` for the full flow. This path can also be scheduled daily via an OS-level scheduler (cron / Task Scheduler) invoking `/refresh --headless`, so the tracker stays fresh without manual runs.

**Path E: Migrate legacy tracker (pre-v1 schema)**

Triggered automatically when a `threads_daily_tracker.json` already exists in the working directory but does not match the current schema. Detection heuristics — treat the file as legacy if **any** of these are true:

- top-level `posts` is a JSON object (dict) rather than an array
- top-level `_meta` exists and top-level `account` does not
- at least one post entry has `data_snapshots` but no `metrics`
- at least one post entry has `my_replies` as an array (legacy reply objects) rather than a boolean flag

If detected, do not overwrite. Walk the user through migration:

*E.1 Backup first*

Copy the file to `threads_daily_tracker.json.legacy-<ISO>` in the same directory. Never begin the migration without a rollback point.

*E.2 Field-by-field transform*

Apply this mapping to produce a v1-schema tracker:

| Legacy | → | v1 | Notes |
|---|---|---|---|
| `_meta.account` (e.g. `@name`) | → | `account.handle` | set `account.source = "legacy-migration"`, `account.timezone` left as `"UTC"` unless user confirms otherwise |
| `_meta.last_updated` | → | root `last_updated` | normalize to ISO; if only a date, append `T00:00:00Z` |
| `posts` (dict keyed by id) | → | `posts` (array) | each key becomes `posts[i].id` |
| `posts[id].title` | → | `posts[i].text` | **imperfect** — see E.3 |
| `posts[id].date` (e.g. `"2026-04-17 13:36"`) | → | `posts[i].created_at` | treat as local time, convert to ISO with `Z` |
| `posts[id].topic` | → | `posts[i].topics: [<topic>]` | wrap single string into an array |
| `posts[id].type` | → | `posts[i].content_type` | pass through as free text; downstream skills re-classify |
| `posts[id].data_snapshots` (array) | → | `posts[i].snapshots` | rename field `snapshot_date` → `captured_at`; rename `replies_count` → `replies`; derive `hours_since_publish` from `created_at` |
| last entry of `data_snapshots` | → | `posts[i].metrics` | populate `views/likes/replies/reposts/shares`; missing values stay as `0` |
| `posts[id].my_replies` (array of reply objects) | → | `posts[i].author_replies` (array) + `posts[i].my_replies: true` | preserve the full reply objects under a new key so `/topics` Validated-Demand logic can still read them; also set the boolean flag so downstream checks work |

Fill all other required and optional fields per the v1 schema below with `null` defaults.

*E.3 Missing post text*

The legacy schema only stores `title`, not full post text. After transform, count posts where `text` equals `title` and their length is under 80 characters — those are suspect. Surface the count to the user:

```text
## Migration warning
- X of Y posts have only a short title as their `text` field.
- This limits what /voice, /draft, and /analyze can learn from them.
- If you have the full post bodies elsewhere (exports, archives, screenshots), paste them in or provide a file path and the migration will merge them.
```

Do not block — a thin text body is still better than nothing. The user can enrich later.

*E.4 Companion markdown files (legacy workflow enrichment)*

Many users of the old workflow also keep hand-curated markdown companions to the tracker:

- a time-sorted post archive (e.g., `歷史貼文-按時間排序.md`, `posts-by-date.md`, `history*.md`)
- a topic-grouped post archive (e.g., `歷史貼文-按主題分類.md`, `posts-by-topic.md`)
- a full comment log from other users (e.g., `留言記錄.md`, `comments.md`)

Glob for these in the tracker's directory and one level up. Match patterns: `*貼文*.md`, `*留言*.md`, `*posts*.md`, `*comment*.md`, `*history*.md`. When found, use them as enrichment sources — do not treat them as authoritative over tracker fields that already have values.

**E.4a Backfill post text from the time-sorted archive**

The time-sorted file typically uses date headers like `### YYYY-MM-DD HH:MM` followed by a `**分類：** <topic>` line and then the post body until a `---` separator. Parse it into (date, topic, body) tuples.

For each tuple:

1. Find the tracker post whose `created_at` matches the same date and hour (±60 min tolerance to absorb timezone drift).
2. If matched and the tracker's `text` is currently equal to `title` or shorter than 80 chars, replace `text` with the archive body. Keep `title` on the post as a new optional field for reference.
3. If not matched (archive has a post the tracker does not), append a new post entry with `source.import_path = "legacy-markdown"`, `metrics` all zero, `snapshots: []`, and flag it so downstream skills know metrics are unrecoverable.

**E.4b Attach comment records**

Comment archives are usually timestamped anonymous comments, not grouped by post. For each comment:

1. Find the nearest prior post by `created_at` within a 72-hour window — that post is the most likely parent.
2. Append to `posts[i].comments[]` with `{user: null, text: <body>, created_at: <ISO>, likes: 0}` if username is not recoverable.
3. Comments that cannot be assigned to any post (too old, too recent, or outside the 72h window) go into a root-level `unmatched_comments[]` array so `/topics` can still mine them as general-demand signal.

Warn the user that comment→post assignment is heuristic and may be wrong for posts published close together in time. The user can correct assignments manually later.

**E.4c Skip the topic-grouped archive (usually redundant)**

The topic-grouped file is almost always a re-view of the time-sorted file. Do not ingest it a second time. Only use it if the time-sorted file is missing — in that case, parse it by topic blocks and fall back to the same (date, topic, body) logic.

*E.5 Validate and write*

After transform and enrichment:

1. Validate the output matches the v1 schema: `posts` is an array, every entry has `id`, `text`, `created_at`, `metrics`, `comments` (may be `[]`).
2. Write to `threads_daily_tracker.json` (the legacy backup from E.1 is the rollback).
3. Report:
   - posts migrated from tracker
   - posts added from markdown archive
   - author_replies preserved
   - comments attached (and how many went to `unmatched_comments[]`)
   - text-thin posts remaining
   - `last_updated` value used

*E.6 Continue to Step 3*

After migration, continue to Step 3 (style guide) and Step 4 (concept library) using the migrated tracker. The downstream skills will see a v1 tracker and run normally.

---

### Step 2: Normalize into the Tracker Schema

Regardless of import path, the result must be a valid `threads_daily_tracker.json` using this shape:

```json
{
  "account": {
    "handle": "@example",
    "source": "api",
    "timezone": "Asia/Bangkok"
  },
  "posts": [
    {
      "id": "post_id",
      "text": "Post content",
      "created_at": "ISO timestamp",
      "permalink": "",
      "media_type": "TEXT",
      "is_reply_post": false,
      "content_type": "opinion",
      "topics": ["threads", "growth"],
      "hook_type": null,
      "ending_type": null,
      "emotional_arc": null,
      "word_count": null,
      "paragraph_count": null,
      "posting_time_slot": null,
      "algorithm_signals": {
        "discovery_surface": {
          "threads": null,
          "instagram": null,
          "facebook": null,
          "profile": null,
          "topic_feed": null,
          "other": null
        },
        "topic_graph": {
          "topic_tag_used": null,
          "topic_tag_count": null,
          "topic_match_clarity": null,
          "single_topic_clarity": null,
          "bio_topic_match": null
        },
        "topic_freshness": {
          "semantic_cluster": null,
          "similar_recent_posts": null,
          "recent_cluster_frequency": null,
          "days_since_last_similar_post": null,
          "freshness_score": null,
          "fatigue_risk": null
        },
        "originality_risk": {
          "caption_content_mismatch": null,
          "hashtag_stuffing_risk": null,
          "duplicate_cluster_risk": null,
          "minor_edit_repost_risk": null,
          "low_value_reaction_risk": null,
          "fake_engagement_pattern_risk": null
        }
      },
      "psychology_signals": {
        "hook_payoff": {
          "hook_strength": null,
          "payoff_strength": null,
          "hook_payoff_gap": null
        },
        "share_motive_split": {
          "dm_forwardability": null,
          "public_repostability": null,
          "identity_signal_strength": null,
          "utility_share_strength": null
        },
        "retellability": null
      },
      "metrics": {
        "views": 0,
        "likes": 0,
        "replies": 0,
        "reposts": 0,
        "quotes": 0,
        "shares": 0
      },
      "performance_windows": {
        "24h": null,
        "72h": null,
        "7d": null
      },
      "snapshots": [],
      "prediction_snapshot": null,
      "review_state": {
        "last_reviewed_at": null,
        "actual_checkpoint_hours": null,
        "deviation_summary": null,
        "calibration_notes": [],
        "validated_signals": {
          "discovery_surface_notes": null,
          "topic_graph_notes": null,
          "topic_freshness_notes": null,
          "originality_risk_notes": null,
          "hook_payoff_gap_notes": null,
          "share_motive_split_notes": null,
          "retellability_notes": null
        }
      },
      "comments": [
        {
          "user": "username",
          "text": "Comment content",
          "created_at": "ISO timestamp",
          "likes": 0
        }
      ],
      "source": {
        "import_path": "api",
        "data_completeness": "full"
      }
    }
  ],
  "last_updated": "ISO timestamp"
}
```

### Required versus optional fields

Required core fields:

- `id`
- `text`
- `created_at`
- `metrics`
- `comments`
- `content_type`
- `topics`

Optional enriched fields:

- `hook_type`
- `ending_type`
- `emotional_arc`
- `word_count`
- `paragraph_count`
- `posting_time_slot`
- `performance_windows`
- `snapshots`
- `prediction_snapshot`
- `algorithm_signals`
- `psychology_signals`
- `review_state`
- `source`

If enriched fields are missing, leave them `null` and allow downstream modules to derive temporary values.

Template reference: locate with Glob `**/templates/tracker-template.json`

After import, read the file, verify it is structurally valid, and report the number of imported posts.

---

### Step 3: Auto-Generate Style Guide (M2)

Read all historical posts from the tracker and generate `style_guide.md`.

Analyze:

- catchphrases
- hook types and their performance
- hook-promise fulfillment patterns in strong posts
- pronoun density
- ending patterns and their performance
- register
- paragraph structure
- word-count distribution
- content-type mix
- emotional arcs
- share / DM-forward drivers in the strongest posts
- topic clusters and repetition pressure
- topic freshness budget / semantic-cluster fatigue
- posting-time windows if timing data is reliable

Use the psychology knowledge base as the classification baseline.

Key rule:

- Describe what the user's style is, not what it should be.
- High-performing patterns should be annotated, not turned into commands.

Template reference: locate with Glob `**/templates/style-guide-template.md`

---

### Step 4: Build Concept Library (M3)

Auto-extract into `concept_library.md`:

1. Explained concepts
2. Used analogies
3. Repeated concept clusters
4. Concepts that were only lightly explained and may need deeper treatment later

Template reference: locate with Glob `**/templates/concept-library-template.md`

---

### Step 4.5: Generate Human-Readable Companion Files

The JSON tracker is for skills to consume; the user cannot skim it comfortably. After the tracker is written, always generate three markdown companions in the same directory so the user can read, grep, and cross-reference their own data.

Default: shell out to `scripts/render_companions.py` (Glob `**/scripts/render_companions.py`). The script is deterministic, handles backup-if-modified, and is safe to re-run:

```bash
python scripts/render_companions.py \
  --tracker "<user-working-dir>/threads_daily_tracker.json" \
  --output-dir "<user-working-dir>" \
  --lang zh
```

Use `--lang en` only if the user's existing companion files already use English names. The script auto-detects existing filename convention (Chinese vs English) and preserves whichever the user already has. `--lang` only decides which names to use when creating the files for the first time.

Produced files:

1. **`歷史貼文-按時間排序.md`** (or `posts_by_date.md`) — full post archive, newest first, month-grouped, metrics inline.
2. **`歷史貼文-按主題分類.md`** (or `posts_by_topic.md`) — topic-grouped index pointing back to the date archive.
3. **`留言記錄.md`** (or `comments.md`) — flat comment log, newest first, plus a `未配對留言` section for `unmatched_comments[]`.

All three files carry a header notice that they are auto-generated and will be overwritten. The script backs up any companion file that was modified after the tracker's last write (assumes user hand-edits) before rewriting.

**Fallback (script unavailable):** if `render_companions.py` cannot be located or Python is unavailable, Claude can produce the same three files inline by reading the tracker and rendering them itself. This is slower and costs tokens — only fall back when the script is genuinely missing, not as a preference.

These files double as the migration source in Path E for users running the legacy manual-download + Claude-Code-reformat workflow — producing them by default means future migrations are trivial.

---

### Step 5: Completion Report

Report:

1. How many posts were imported
2. Which import path was used
3. 2-3 strongest style findings
4. How many concepts were indexed
5. Whether the tracker is full-data or partial-data
6. That `/analyze`, `/predict`, and `/review` can already run, even if some enriched fields are still null

If post count is below 20, say the historical base is still limited.

If the user has API access, tell them they can later run `scripts/update_snapshots.py` on a schedule to keep metrics snapshots current.

Regardless of API access, tell them they can run `scripts/update_topic_freshness.py` to build semantic clusters and estimate topic freshness / fatigue from account history.

If they do not have API access, rely on `/review` checkpoints plus `scripts/update_topic_freshness.py`.

---

## Handling Insufficient Data

Use the shared rubric at `knowledge/data-confidence.md` (Glob `**/knowledge/data-confidence.md`). Report the dataset-level gate in the completion report so the user knows whether downstream skills will run in Directional / Weak / Usable / Strong / Deep mode.

---

## Output File Checklist

After setup, the user's working directory should contain:

1. `threads_daily_tracker.json` — canonical data (machine-readable)
2. `style_guide.md`
3. `concept_library.md`
4. `posts_by_date.md` (or `歷史貼文-按時間排序.md`) — human-readable post archive
5. `posts_by_topic.md` (or `歷史貼文-按主題分類.md`) — topic-grouped index
6. `comments.md` (or `留言記錄.md`) — flat comment log
