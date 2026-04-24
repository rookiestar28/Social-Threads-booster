#!/usr/bin/env python3
"""
AK-Threads-Booster: Refresh tracker metrics and append API-backed snapshots.

Usage:
    $env:THREADS_API_TOKEN="..."
    python update_snapshots.py [--tracker threads_daily_tracker.json]
    python update_snapshots.py --token-file .secrets/threads_token.txt --post-id 12345
    python update_snapshots.py --token-file .secrets/threads_token.txt --recent 5 --update-comments
    python update_snapshots.py --include-new-posts --update-comments --backup  # full daily refresh (token from $THREADS_API_TOKEN)

The script:
    - Reads an existing tracker JSON file
    - Fetches the latest metrics for selected posts via Threads API
    - Appends a snapshot entry to each selected post
    - Updates checkpoint fields (`performance_windows`) when the snapshot is near 24h / 72h / 7d
    - Optionally pulls in any new posts that aren't yet tracked (--include-new-posts)
    - Optionally backs up the tracker to `.bak-<ISO>` before writing (--backup)

The token can be supplied with THREADS_API_TOKEN or --token-file.
Direct --token remains available for compatibility, but is discouraged because
command-line secrets can appear in shell history or process listings.
"""

import argparse
import sys
import time
from pathlib import Path

try:
    from fetch_threads import (
        RATE_LIMIT_DELAY,
        exchange_long_lived_token,
        fetch_all_threads,
        fetch_thread_insights,
        fetch_thread_replies,
        get_user_profile,
    )
except ImportError as exc:
    print(f"Error: could not import helper functions from fetch_threads.py: {exc}")
    sys.exit(1)

from tracker_utils import (
    append_metric_snapshot,
    backup_tracker,
    build_metric_snapshot,
    build_post_record,
    hydrate_post_defaults,
    load_tracker,
    save_tracker,
    sort_posts_newest_first,
    utc_now_iso,
)
from refresh_logging import (
    append_refresh_log,
    build_refresh_failure_entry,
    build_refresh_success_entry,
)
from credential_sources import CredentialSourceError, resolve_credential

class RefreshRunError(Exception):
    def __init__(self, reason: str, detail: str, exit_code: int = 1):
        super().__init__(detail)
        self.reason = reason
        self.detail = detail
        self.exit_code = exit_code


def ensure_extended_fields(post: dict) -> None:
    """Backfill newer tracker scaffolds on existing posts."""
    hydrate_post_defaults(post)


def build_new_post_entry(thread: dict, token: str) -> tuple[dict, int]:
    """Build a full v1 post entry for a post that isn't yet in the tracker."""
    thread_id = thread["id"]
    text = thread.get("text", "")
    created_at = thread.get("timestamp", "")

    time.sleep(RATE_LIMIT_DELAY)
    metrics = fetch_thread_insights(thread_id, token)
    time.sleep(RATE_LIMIT_DELAY)
    replies = fetch_thread_replies(thread_id, token)

    snapshot_metrics = {
        "views": metrics.get("views", 0),
        "likes": metrics.get("likes", 0),
        "replies": metrics.get("replies", 0),
        "reposts": metrics.get("reposts", 0),
        "quotes": metrics.get("quotes", 0),
        "shares": 0,
    }

    return (
        build_post_record(
        post_id=thread_id,
        text=text,
        created_at=created_at,
        permalink=thread.get("permalink", ""),
        media_type=thread.get("media_type", "TEXT"),
        source_path="api-delta",
        data_completeness="full",
        metrics=snapshot_metrics,
        snapshots=[build_metric_snapshot(snapshot_metrics, created_at)],
        comments=replies,
        ),
        len(replies),
    )


def ingest_new_posts(tracker: dict, token: str) -> tuple[int, int]:
    """Fetch the full thread list and append any posts not yet in the tracker.

    Returns the number of newly inserted posts and replies added with those posts.
    """
    print("  Listing posts from API to find new entries...")
    user = get_user_profile(token)
    threads = fetch_all_threads(user["id"], token)
    known_ids = {str(p.get("id", "")) for p in tracker.get("posts", [])}
    new_threads = [t for t in threads if str(t["id"]) not in known_ids]

    if not new_threads:
        print("  No new posts to ingest.")
        return 0, 0

    print(f"  Found {len(new_threads)} new post(s); fetching full data...")
    replies_added = 0
    for thread in new_threads:
        entry, reply_count = build_new_post_entry(thread, token)
        tracker.setdefault("posts", []).insert(0, entry)
        replies_added += reply_count

    # Re-sort newest-first on created_at so the tracker stays ordered.
    tracker["posts"] = sort_posts_newest_first(tracker["posts"])
    return len(new_threads), replies_added


def select_posts(posts: list, post_ids: list[str], recent: int, update_all: bool) -> list:
    """Select which posts should be refreshed."""
    if post_ids:
        wanted = set(post_ids)
        return [post for post in posts if str(post.get("id", "")) in wanted]

    if update_all:
        return posts

    return posts[:recent]


def merge_comments(existing: list, incoming: list) -> tuple[list, int]:
    known = {
        (
            str(comment.get("user", "")),
            str(comment.get("text", "")),
            str(comment.get("created_at", "")),
        )
        for comment in existing
    }
    merged = list(existing)
    added = 0

    for comment in incoming:
        key = (
            str(comment.get("user", "")),
            str(comment.get("text", "")),
            str(comment.get("created_at", "")),
        )
        if key in known:
            continue
        known.add(key)
        merged.append(comment)
        added += 1

    merged.sort(key=lambda comment: str(comment.get("created_at", "")), reverse=True)
    return merged, added


def refresh_post(post: dict, token: str, update_comments: bool) -> int:
    """Refresh a single post from the Threads API."""
    ensure_extended_fields(post)
    post_id = str(post.get("id", ""))
    created_at = post.get("created_at", "")
    metrics = fetch_thread_insights(post_id, token)

    snapshot_metrics = {
        "views": metrics.get("views", 0),
        "likes": metrics.get("likes", 0),
        "replies": metrics.get("replies", 0),
        "reposts": metrics.get("reposts", 0),
        "quotes": metrics.get("quotes", 0),
        "shares": post.get("metrics", {}).get("shares", 0),
    }
    captured_at = utc_now_iso()
    append_metric_snapshot(post, snapshot_metrics, captured_at=captured_at)

    replies_added = 0
    if update_comments:
        time.sleep(RATE_LIMIT_DELAY)
        merged_comments, replies_added = merge_comments(
            post.get("comments") or [],
            fetch_thread_replies(post_id, token),
        )
        post["comments"] = merged_comments

    return replies_added


def infer_failure_reason(exc: Exception) -> str:
    detail = str(exc).lower()
    if "timed out" in detail or "timeout" in detail:
        return "timeout"
    return "other"


def resolve_log_path(tracker_path: str, explicit_log_path: str | None) -> Path:
    if explicit_log_path:
        return Path(explicit_log_path).resolve()
    return Path(tracker_path).resolve().with_name("threads_refresh.log")


def run_refresh(args: argparse.Namespace) -> dict:
    try:
        token_source = resolve_credential(
            label="Threads API token",
            direct_value=args.token,
            direct_source_name="--token",
            env_var="THREADS_API_TOKEN",
            file_path=args.token_file,
        )
        app_secret_source = resolve_credential(
            label="Threads app secret",
            direct_value=args.app_secret,
            direct_source_name="--app-secret",
            env_var="THREADS_APP_SECRET",
            file_path=args.app_secret_file,
        )
    except CredentialSourceError as exc:
        raise RefreshRunError("other", str(exc)) from exc

    if token_source.warning:
        print(token_source.warning, file=sys.stderr)
    if app_secret_source.warning:
        print(app_secret_source.warning, file=sys.stderr)
    if not token_source.value:
        raise RefreshRunError("other", "no API token. Set $THREADS_API_TOKEN, pass --token-file, or use --token.")

    token = token_source.value
    if app_secret_source.value:
        print("[1/4] Exchanging for long-lived token...")
        token = exchange_long_lived_token(token, app_secret_source.value)
    else:
        print("[1/4] Using provided token (skip long-lived exchange)")

    print("[2/5] Loading tracker...")
    try:
        tracker = load_tracker(args.tracker)
    except Exception as exc:  # noqa: BLE001 - CLI should return actionable error text
        raise RefreshRunError("other", str(exc)) from exc

    posts = tracker.get("posts", [])
    if not isinstance(posts, list):
        raise RefreshRunError("other", "tracker posts field is not an array")

    new_post_count = 0
    replies_added = 0
    if args.include_new_posts:
        print("[3/5] Checking for new posts via API...")
        new_post_count, replies_added = ingest_new_posts(tracker, token)
        posts = tracker.get("posts", [])
    else:
        print("[3/5] Skipping new-post discovery (pass --include-new-posts to enable)")

    if not posts:
        raise RefreshRunError("other", "tracker contains no posts to refresh")

    selected_posts = select_posts(posts, args.post_id, args.recent, args.all)
    if not selected_posts:
        raise RefreshRunError("other", "no matching posts found in the tracker")

    print(f"[4/5] Refreshing metrics on {len(selected_posts)} post(s)...")
    for idx, post in enumerate(selected_posts, 1):
        post_id = str(post.get("id", ""))
        summary = post.get("text", "")[:40].replace("\n", " ")
        print(f"  [{idx}/{len(selected_posts)}] {post_id}: {summary}...")
        replies_added += refresh_post(post, token, update_comments=args.update_comments)
        time.sleep(RATE_LIMIT_DELAY)

    tracker["last_updated"] = utc_now_iso()

    print("[5/5] Writing tracker...")
    if args.backup:
        try:
            backup_path = backup_tracker(args.tracker)
        except Exception as exc:  # noqa: BLE001 - backup failures need their own reason code
            raise RefreshRunError("backup_failed", str(exc)) from exc
        if backup_path:
            print(f"  Backup written to {backup_path}")

    save_tracker(args.tracker, tracker)
    print(
        f"Done. Refreshed {len(selected_posts)} post(s)"
        f"{f', ingested {new_post_count} new' if new_post_count else ''} in {args.tracker}"
    )

    return {
        "posts_scraped": len(selected_posts) + new_post_count,
        "new_posts": new_post_count,
        "updated_posts": len(selected_posts),
        "replies_added": replies_added,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Refresh tracker metrics and append snapshots via Threads API"
    )
    parser.add_argument(
        "--token",
        default=None,
        help="Threads API access token. Prefer $THREADS_API_TOKEN or --token-file.",
    )
    parser.add_argument(
        "--token-file",
        default=None,
        help="Path to a file containing the Threads API access token.",
    )
    parser.add_argument(
        "--app-secret",
        default=None,
        help="App secret for long-lived token exchange. Prefer $THREADS_APP_SECRET or --app-secret-file.",
    )
    parser.add_argument(
        "--app-secret-file",
        default=None,
        help="Path to a file containing the app secret for long-lived token exchange.",
    )
    parser.add_argument(
        "--tracker",
        default="threads_daily_tracker.json",
        help="Path to the tracker JSON file",
    )
    parser.add_argument(
        "--post-id",
        action="append",
        default=[],
        help="Specific post id to refresh (can be passed multiple times)",
    )
    parser.add_argument(
        "--recent",
        type=int,
        default=10,
        help="Refresh the most recent N posts when no --post-id is given",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Refresh all posts in the tracker",
    )
    parser.add_argument(
        "--update-comments",
        action="store_true",
        help="Refresh replies/comments for selected posts as well",
    )
    parser.add_argument(
        "--include-new-posts",
        action="store_true",
        help="Also fetch and insert any new posts not yet in the tracker (daily-refresh mode)",
    )
    parser.add_argument(
        "--backup",
        action="store_true",
        help="Write a .bak-<ISO> copy of the tracker before saving (keeps 5 most recent)",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Write contract-compliant refresh logs instead of prompting for user interaction",
    )
    parser.add_argument(
        "--log-file",
        default=None,
        help="Refresh log path (default: alongside the tracker as threads_refresh.log)",
    )
    args = parser.parse_args()
    log_path = resolve_log_path(args.tracker, args.log_file)

    try:
        result = run_refresh(args)
    except RefreshRunError as exc:
        if args.headless:
            try:
                append_refresh_log(
                    log_path,
                    build_refresh_failure_entry(
                        reason=exc.reason,
                        detail=exc.detail,
                        mode="api",
                    ),
                )
            except Exception as log_exc:  # noqa: BLE001 - preserve original failure
                print(f"Error: {exc.detail}")
                print(f"Refresh logging also failed: {log_exc}")
                sys.exit(exc.exit_code)

        print(f"Error: {exc.detail}")
        sys.exit(exc.exit_code)
    except Exception as exc:  # noqa: BLE001 - CLI should still log bounded failure output
        reason = infer_failure_reason(exc)
        detail = str(exc)
        if args.headless:
            try:
                append_refresh_log(
                    log_path,
                    build_refresh_failure_entry(
                        reason=reason,
                        detail=detail,
                        mode="api",
                    ),
                )
            except Exception as log_exc:  # noqa: BLE001 - preserve original failure
                print(f"Error: {detail}")
                print(f"Refresh logging also failed: {log_exc}")
                sys.exit(1)

        print(f"Error: {detail}")
        sys.exit(1)

    if args.headless:
        append_refresh_log(
            log_path,
            build_refresh_success_entry(
                **result,
                mode="api",
            ),
        )


if __name__ == "__main__":
    main()
