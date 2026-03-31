#!/usr/bin/env python3
"""
AK-Threads-Booster: Parse Meta account data export into tracker format.

Usage:
    python parse_export.py --input /path/to/export/folder [--output threads_daily_tracker.json]

How to get your Meta data export:
    1. Go to https://accountscenter.meta.com/info_and_permissions/dyi/
    2. Select your Threads account
    3. Choose "Download or transfer information"
    4. Select "Some of your information" > check "Threads"
    5. Format: JSON (recommended) or HTML
    6. Create file > Download when ready

The script handles both JSON and HTML export formats from Meta.
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    from html.parser import HTMLParser
except ImportError:
    pass


def find_threads_data(export_path: str) -> dict:
    """Locate Threads data files within the Meta export directory."""
    export_dir = Path(export_path)
    result = {"format": None, "posts_file": None, "replies_file": None}

    # Common paths in Meta data export
    search_patterns = [
        # JSON format paths
        "threads/threads_and_replies.json",
        "threads/posts_and_replies.json",
        "your_threads_activity/threads_and_replies.json",
        "threads_and_replies.json",
        "threads/threads.json",
        "threads.json",
        # Nested structure
        "your_activity_across_facebook/threads/threads_and_replies.json",
    ]

    # Search for JSON files
    for pattern in search_patterns:
        candidate = export_dir / pattern
        if candidate.exists():
            result["format"] = "json"
            result["posts_file"] = str(candidate)
            print(f"  Found JSON data: {candidate}")
            break

    # If no JSON, look for HTML
    if not result["posts_file"]:
        for html_file in export_dir.rglob("*.html"):
            if "threads" in str(html_file).lower():
                result["format"] = "html"
                result["posts_file"] = str(html_file)
                print(f"  Found HTML data: {html_file}")
                break

    # If still nothing, try to find any JSON with threads content
    if not result["posts_file"]:
        for json_file in export_dir.rglob("*.json"):
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                # Check if this looks like threads data
                if isinstance(data, dict) and any(
                    k in data for k in ["threads", "text_post_threads", "thread_posts"]
                ):
                    result["format"] = "json"
                    result["posts_file"] = str(json_file)
                    print(f"  Found threads data in: {json_file}")
                    break
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue

    return result


def decode_meta_text(text: str) -> str:
    """Decode Meta's escaped Unicode in JSON exports."""
    if not text:
        return ""
    # Meta exports sometimes use escaped UTF-8 sequences
    try:
        return text.encode("latin-1").decode("utf-8")
    except (UnicodeDecodeError, UnicodeEncodeError):
        return text


def parse_json_export(file_path: str) -> list:
    """Parse JSON format Meta data export."""
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    posts = []

    # Meta export JSON structure varies; try common patterns
    threads_data = None

    if isinstance(data, list):
        threads_data = data
    elif isinstance(data, dict):
        # Try known keys
        for key in ["threads", "text_post_threads", "thread_posts",
                     "your_threads", "posts"]:
            if key in data:
                threads_data = data[key]
                break

        # If still not found, look for nested structure
        if threads_data is None:
            for key, value in data.items():
                if isinstance(value, list) and len(value) > 0:
                    if isinstance(value[0], dict) and any(
                        k in value[0] for k in ["text", "post", "content", "title"]
                    ):
                        threads_data = value
                        break

    if threads_data is None:
        print(f"  Warning: Could not find threads data structure in {file_path}")
        print(f"  Top-level keys: {list(data.keys()) if isinstance(data, dict) else 'list'}")
        return []

    for item in threads_data:
        post = extract_post_from_json(item)
        if post:
            posts.append(post)

    return posts


def extract_post_from_json(item: dict) -> dict | None:
    """Extract a post from a single JSON item in Meta export."""
    # Try to find the text content
    text = ""
    for key in ["text", "post", "content", "title"]:
        if key in item and isinstance(item[key], str):
            text = decode_meta_text(item[key])
            break
        elif key in item and isinstance(item[key], dict):
            text = decode_meta_text(item[key].get("text", item[key].get("value", "")))
            break
        elif key in item and isinstance(item[key], list):
            # Sometimes text is in a nested list
            for sub in item[key]:
                if isinstance(sub, str):
                    text = decode_meta_text(sub)
                    break
                elif isinstance(sub, dict):
                    text = decode_meta_text(sub.get("text", sub.get("value", "")))
                    break
            if text:
                break

    if not text:
        return None

    # Try to find timestamp
    timestamp = ""
    for key in ["timestamp", "created_at", "creation_timestamp", "date"]:
        if key in item:
            val = item[key]
            if isinstance(val, (int, float)):
                # Unix timestamp
                timestamp = datetime.fromtimestamp(val, tz=timezone.utc).isoformat()
            elif isinstance(val, str):
                timestamp = val
            break

    # Check if this is a reply
    is_reply = item.get("is_reply", False)
    if not is_reply:
        # Heuristic: if there's a "parent" or "in_reply_to" field, it's a reply
        is_reply = any(k in item for k in ["parent", "in_reply_to", "reply_to"])

    if is_reply:
        return None

    return {
        "id": str(item.get("id", item.get("uri", f"export_{hash(text)}"))),
        "text": text,
        "created_at": timestamp,
        "permalink": item.get("permalink", item.get("url", "")),
        "media_type": detect_media_type(item),
        "metrics": {
            "views": 0,
            "likes": 0,
            "replies": 0,
            "reposts": 0,
            "quotes": 0,
            "shares": 0,
        },
        "comments": [],
        "content_type": classify_content_type(text),
        "topics": [],
    }


def detect_media_type(item: dict) -> str:
    """Detect media type from export data."""
    if "media" in item or "attachments" in item:
        media = item.get("media", item.get("attachments", []))
        if isinstance(media, list) and media:
            first = media[0] if isinstance(media[0], dict) else {}
            uri = first.get("uri", first.get("url", ""))
            if any(ext in uri.lower() for ext in [".mp4", ".mov", "video"]):
                return "VIDEO"
            if any(ext in uri.lower() for ext in [".jpg", ".png", ".jpeg", "image"]):
                return "IMAGE"
            return "IMAGE"
    return "TEXT"


def classify_content_type(text: str) -> str:
    """Basic content type classification."""
    if not text:
        return "other"
    if "?" in text or "？" in text:
        if text.strip().endswith(("?", "？")):
            return "question"
    if any(m in text for m in ["1.", "2.", "3.", "一、", "二、", "第一", "步驟"]):
        return "tutorial"
    if any(m in text for m in ["數據", "data", "%", "成長", "增長"]):
        return "data-insight"
    if any(m in text for m in ["我的經驗", "我之前", "那時候", "故事"]):
        return "story"
    return "opinion"


class ThreadsHTMLParser(HTMLParser):
    """Parse Meta HTML export format for Threads posts."""

    def __init__(self):
        super().__init__()
        self.posts = []
        self.current_text = ""
        self.current_timestamp = ""
        self.in_content = False
        self.in_timestamp = False
        self.depth = 0

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        cls = attrs_dict.get("class", "")

        if "pam" in cls or "content" in cls.lower():
            self.in_content = True
            self.current_text = ""
        if "timestamp" in cls.lower() or "date" in cls.lower():
            self.in_timestamp = True
            self.current_timestamp = ""

    def handle_endtag(self, tag):
        if self.in_content and tag in ("div", "p"):
            if self.current_text.strip():
                self.posts.append({
                    "text": self.current_text.strip(),
                    "timestamp": self.current_timestamp,
                })
            self.in_content = False
        if self.in_timestamp:
            self.in_timestamp = False

    def handle_data(self, data):
        if self.in_content:
            self.current_text += data
        if self.in_timestamp:
            self.current_timestamp = data.strip()


def parse_html_export(file_path: str) -> list:
    """Parse HTML format Meta data export."""
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    parser = ThreadsHTMLParser()
    parser.feed(content)

    posts = []
    for item in parser.posts:
        text = item["text"]
        if not text:
            continue

        posts.append({
            "id": f"export_{hash(text)}",
            "text": text,
            "created_at": item.get("timestamp", ""),
            "permalink": "",
            "media_type": "TEXT",
            "metrics": {
                "views": 0,
                "likes": 0,
                "replies": 0,
                "reposts": 0,
                "quotes": 0,
                "shares": 0,
            },
            "comments": [],
            "content_type": classify_content_type(text),
            "topics": [],
        })

    return posts


def build_tracker(posts: list) -> dict:
    """Build the standard tracker JSON."""
    # Sort by date, newest first
    posts.sort(key=lambda p: p.get("created_at", ""), reverse=True)

    return {
        "posts": posts,
        "last_updated": datetime.now(timezone.utc).isoformat(),
    }


def main():
    parser = argparse.ArgumentParser(
        description="Parse Meta data export into AK-Threads-Booster tracker format"
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Path to Meta data export folder (or specific JSON/HTML file)",
    )
    parser.add_argument(
        "--output",
        default="threads_daily_tracker.json",
        help="Output file path (default: threads_daily_tracker.json)",
    )
    args = parser.parse_args()

    input_path = args.input

    print("[1/3] Locating Threads data in export...")

    # Check if input is a file or directory
    if os.path.isfile(input_path):
        ext = os.path.splitext(input_path)[1].lower()
        if ext == ".json":
            file_info = {"format": "json", "posts_file": input_path}
        elif ext in (".html", ".htm"):
            file_info = {"format": "html", "posts_file": input_path}
        else:
            print(f"Error: Unsupported file format: {ext}")
            sys.exit(1)
    else:
        file_info = find_threads_data(input_path)

    if not file_info["posts_file"]:
        print("Error: Could not find Threads data in the export.")
        print("Make sure you exported Threads data from Meta Account Center.")
        print("Expected: a JSON or HTML file containing your Threads posts.")
        sys.exit(1)

    print(f"[2/3] Parsing {file_info['format'].upper()} export...")

    if file_info["format"] == "json":
        posts = parse_json_export(file_info["posts_file"])
    else:
        posts = parse_html_export(file_info["posts_file"])

    if not posts:
        print("Error: No posts found in the export file.")
        print("The file might be empty or in an unexpected format.")
        sys.exit(1)

    print(f"  Found {len(posts)} posts")

    print("[3/3] Building tracker...")
    tracker = build_tracker(posts)

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(tracker, f, ensure_ascii=False, indent=2)

    print(f"\nDone! Saved {len(tracker['posts'])} posts to {args.output}")
    print("Note: Meta data export does not include engagement metrics.")
    print("Metrics will be populated as you use /review after publishing.")
    print(f"\nNext step: Run /setup in Claude Code to generate your style guide and concept library.")


if __name__ == "__main__":
    main()
