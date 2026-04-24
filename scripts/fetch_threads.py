#!/usr/bin/env python3
"""
AK-Threads-Booster: Fetch historical posts via Meta Threads API.

Usage:
    $env:THREADS_API_TOKEN="..."
    python fetch_threads.py [--output threads_daily_tracker.json]
    python fetch_threads.py --token-file .secrets/threads_token.txt [--output threads_daily_tracker.json]

Prerequisites:
    1. Create a Meta Developer App at https://developers.facebook.com/
    2. Add "Threads API" product to your app
    3. Generate a User Access Token with threads_basic, threads_content_publish,
       threads_read_replies, threads_manage_insights permissions
    4. Exchange for a long-lived token (valid 60 days)

The script will:
    - Fetch all your historical Threads posts
    - Fetch metrics (views, likes, replies, reposts, quotes) for each post
    - Fetch reply threads (comments) for each post
    - Output a tracker JSON file in Social-Threads-Booster standard format
"""

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from typing import Optional

from tracker_utils import (
    build_algorithm_signals as shared_build_algorithm_signals,
    build_empty_tracker,
    build_metric_snapshot as shared_build_metric_snapshot,
    build_post_record,
    build_posting_time_slot as shared_build_posting_time_slot,
    build_psychology_signals as shared_build_psychology_signals,
    build_review_state as shared_build_review_state,
    classify_content_type as shared_classify_content_type,
    count_paragraphs as shared_count_paragraphs,
    count_words as shared_count_words,
    parse_iso_datetime as shared_parse_iso_datetime,
    save_tracker,
    sort_posts_newest_first,
)
from credential_sources import CredentialSourceError, resolve_credential

try:
    import requests
except ImportError:
    print("Error: 'requests' package is required.")
    print("Install it with: pip install requests")
    sys.exit(1)

API_BASE = "https://graph.threads.net/v1.0"

# Threads API rate limits: 250 calls per user per hour
RATE_LIMIT_DELAY = 0.5  # seconds between API calls


def get_user_profile(token: str) -> dict:
    """Get the authenticated user's Threads profile."""
    resp = requests.get(
        f"{API_BASE}/me",
        params={"fields": "id,username", "access_token": token},
    )
    resp.raise_for_status()
    data = resp.json()
    return {
        "id": data["id"],
        "username": data.get("username", ""),
    }


def fetch_all_threads(user_id: str, token: str) -> list:
    """Fetch all threads (posts) for the user, handling pagination."""
    all_threads = []
    url = f"{API_BASE}/{user_id}/threads"
    params = {
        "fields": "id,text,timestamp,media_type,shortcode,permalink,is_reply",
        "limit": 50,
        "access_token": token,
    }

    page = 1
    while url:
        print(f"  Fetching posts page {page}...")
        resp = requests.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()

        posts = data.get("data", [])
        # Filter out replies — only keep original posts
        original_posts = [p for p in posts if not p.get("is_reply", False)]
        all_threads.extend(original_posts)

        # Handle pagination
        paging = data.get("paging", {})
        url = paging.get("next")
        params = {}  # next URL already contains params
        page += 1
        time.sleep(RATE_LIMIT_DELAY)

    return all_threads


def fetch_thread_insights(thread_id: str, token: str) -> dict:
    """Fetch metrics for a single thread."""
    metrics = {
        "views": 0,
        "likes": 0,
        "replies": 0,
        "reposts": 0,
        "quotes": 0,
    }

    try:
        resp = requests.get(
            f"{API_BASE}/{thread_id}/insights",
            params={
                "metric": "views,likes,replies,reposts,quotes",
                "access_token": token,
            },
        )
        resp.raise_for_status()
        data = resp.json().get("data", [])

        for item in data:
            name = item.get("name", "")
            if name in metrics:
                # Insights API returns values in different formats
                values = item.get("values", [{}])
                if values:
                    metrics[name] = values[0].get("value", 0)

    except requests.exceptions.HTTPError as e:
        # Some posts may not have insights available (too old, etc.)
        print(f"    Warning: Could not fetch insights for {thread_id}: {e}")

    return metrics


def fetch_thread_replies(thread_id: str, token: str) -> list:
    """Fetch replies (comments) for a single thread."""
    replies = []
    url = f"{API_BASE}/{thread_id}/replies"
    params = {
        "fields": "id,text,timestamp,username",
        "limit": 50,
        "access_token": token,
    }

    while url:
        try:
            resp = requests.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()

            for reply in data.get("data", []):
                replies.append({
                    "user": reply.get("username", ""),
                    "text": reply.get("text", ""),
                    "created_at": reply.get("timestamp", ""),
                    "likes": 0,  # Reply likes not available via basic API
                })

            paging = data.get("paging", {})
            url = paging.get("next")
            params = {}
        except requests.exceptions.HTTPError:
            break
        time.sleep(RATE_LIMIT_DELAY)

    return replies


def classify_content_type(text: str) -> str:
    """Basic content type classification based on text patterns."""
    return shared_classify_content_type(text)


def count_words(text: str) -> int:
    """Estimate word count from whitespace-separated tokens."""
    return shared_count_words(text)


def count_paragraphs(text: str) -> int:
    """Count non-empty paragraphs."""
    return shared_count_paragraphs(text)


def build_posting_time_slot(timestamp: str) -> Optional[str]:
    """Convert an ISO timestamp into a coarse posting-time bucket."""
    return shared_build_posting_time_slot(timestamp)


def parse_iso_datetime(timestamp: str) -> Optional[datetime]:
    """Parse an ISO timestamp into a datetime."""
    return shared_parse_iso_datetime(timestamp)


def build_metric_snapshot(metrics: dict, created_at: str, captured_at: Optional[str] = None) -> dict:
    """Create a metrics snapshot entry for the tracker."""
    return shared_build_metric_snapshot(metrics, created_at, captured_at=captured_at)


def build_algorithm_signals() -> dict:
    """Create an empty algorithm-signals scaffold for a post."""
    return shared_build_algorithm_signals()


def build_psychology_signals() -> dict:
    """Create an empty psychology-signals scaffold for a post."""
    return shared_build_psychology_signals()


def build_review_state() -> dict:
    """Create an empty review-state scaffold for a post."""
    return shared_build_review_state()


def build_tracker(threads: list, token: str, account_handle: str = "") -> dict:
    """Build the tracker JSON from fetched threads."""
    posts = []
    total = len(threads)

    for i, thread in enumerate(threads, 1):
        thread_id = thread["id"]
        text = thread.get("text", "")

        print(f"  Processing post {i}/{total}: {text[:40]}...")

        # Fetch metrics
        time.sleep(RATE_LIMIT_DELAY)
        metrics = fetch_thread_insights(thread_id, token)

        # Fetch replies
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
        post = build_post_record(
            post_id=thread_id,
            text=text,
            created_at=thread.get("timestamp", ""),
            permalink=thread.get("permalink", ""),
            media_type=thread.get("media_type", "TEXT"),
            source_path="api",
            data_completeness="full",
            metrics=snapshot_metrics,
            snapshots=[build_metric_snapshot(snapshot_metrics, thread.get("timestamp", ""))],
            comments=replies,
        )
        posts.append(post)

    return build_empty_tracker(
        account_handle=account_handle,
        source="api",
        timezone_name="UTC",
        posts=sort_posts_newest_first(posts),
    )


def exchange_long_lived_token(short_token: str, app_secret: str) -> str:
    """Exchange a short-lived token for a long-lived token (60 days)."""
    resp = requests.get(
        f"{API_BASE}/access_token",
        params={
            "grant_type": "th_exchange_token",
            "client_secret": app_secret,
            "access_token": short_token,
        },
    )
    resp.raise_for_status()
    data = resp.json()
    print(f"  Long-lived token obtained. Expires in {data.get('expires_in', 'unknown')} seconds.")
    return data["access_token"]


def main():
    parser = argparse.ArgumentParser(
        description="Fetch Threads historical posts via Meta Threads API"
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
        "--output",
        default="threads_daily_tracker.json",
        help="Output file path (default: threads_daily_tracker.json)",
    )
    args = parser.parse_args()

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
        print(f"Error: {exc}")
        sys.exit(1)

    if token_source.warning:
        print(token_source.warning, file=sys.stderr)
    if app_secret_source.warning:
        print(app_secret_source.warning, file=sys.stderr)
    if not token_source.value:
        print("Error: no API token. Set $THREADS_API_TOKEN, pass --token-file, or use --token.")
        sys.exit(1)

    token = token_source.value

    # Exchange for long-lived token if app secret provided
    if app_secret_source.value:
        print("[1/4] Exchanging for long-lived token...")
        token = exchange_long_lived_token(token, app_secret_source.value)
    else:
        print("[1/4] Using provided token (skip long-lived exchange)")

    # Get user profile
    print("[2/4] Fetching user profile...")
    profile = get_user_profile(token)
    user_id = profile["id"]
    print(f"  User ID: {user_id}")
    if profile["username"]:
        print(f"  Username: @{profile['username']}")

    # Fetch all threads
    print("[3/4] Fetching all historical posts...")
    threads = fetch_all_threads(user_id, token)
    print(f"  Found {len(threads)} original posts")

    if not threads:
        print("No posts found. Check your token permissions.")
        sys.exit(1)

    # Build tracker with metrics and replies
    print("[4/4] Fetching metrics and replies for each post...")
    handle = f"@{profile['username']}" if profile["username"] else ""
    tracker = build_tracker(threads, token, account_handle=handle)

    # Write output
    save_tracker(args.output, tracker)

    print(f"\nDone! Saved {len(tracker['posts'])} posts to {args.output}")
    print(f"Next step: Run /setup in Claude Code to generate your style guide and concept library.")


if __name__ == "__main__":
    main()
