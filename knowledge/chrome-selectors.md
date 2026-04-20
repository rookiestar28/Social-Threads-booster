# Chrome Selectors for Threads Profile Scrape

> Single source of truth for the DOM selectors `/refresh` uses against threads.com. Threads changes its DOM regularly. When `/refresh` fails a health check, update this file and re-run — no code edits needed in SKILL.md.

---

## Version

- **selectors_version**: 1
- **last_verified**: 2026-04-18
- **verified_against**: threads.com desktop web

Bump `selectors_version` when any selector below changes. `/refresh` writes this number into the tracker's refresh log so a drift can be detected.

---

## Selectors

| Purpose | Selector | Notes |
|---------|----------|-------|
| Post card container | `[data-pressable-container="true"]` | Wraps each post on a profile page. Used for scroll-to-end detection. |
| Post permalink anchor | `a[href*="/post/"]` within the card | First match per card. Permalink slug = last path segment. |
| Post text body | `[data-testid="post-text"], div[dir="auto"] > span` | First selector preferred. Fallback to the `dir="auto"` span if the testid is missing. |
| "See more" expand button | `button[aria-expanded="false"]` whose text is `See more` or `顯示更多` | Click before reading text. |
| Timestamp | `time[datetime]` within the card | Read `datetime` attribute for absolute ISO. |
| Metric row | `[role="group"][aria-label*="Like"]` | Parent of like/comment/repost/share buttons. |
| Like count button | `button[aria-label*="Like"]` in metric row | Count is in `aria-label` (e.g., `Like, 42`) or visible text. |
| Reply count button | `button[aria-label*="Repl"]` | Matches both `Reply` and `Replies`. |
| Repost count button | `button[aria-label*="Repost"]` | |
| Share count button | `button[aria-label*="Share"]` | May be absent on older posts. |
| View count | `span[aria-label*="view"]` | Not on every post. |
| Logged-in user avatar | `a[href="/@<handle>"]` in top nav | Used to verify which account is logged in. |
| Login wall indicator | `a[href="/login"]` present AND no `[data-pressable-container]` on page | If both, we are signed out. |

---

## Health check

Before scraping, `/refresh` must:

1. Navigate to the target profile.
2. Wait up to 3 seconds.
3. Count `[data-pressable-container="true"]`.
4. If count is 0 and the login-wall indicator is present → login wall, abort.
5. If count is 0 and no login-wall indicator → DOM drift, abort with `selector_health_failed`. Tell the user to update this file.
6. If count ≥ 1, proceed.

---

## Number parsing

Threads abbreviates counts. Parse these suffixes:

| Input | Output |
|-------|--------|
| `1.2K` | 1200 |
| `34K` | 34000 |
| `1.5M` | 1500000 |
| `2B` | 2000000000 |

Localized variants must also be handled:

- `1,2千`, `1.2万`, `1.2億` (zh)
- `1,2 mil`, `1,2 mi` (pt)

Reject any token that parses to `NaN` — store the post with metrics set to the last-known tracker value rather than a wrong number.
