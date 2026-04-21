#!/usr/bin/env python3
"""
Generate concept_library.md from a tracker JSON file.

Usage:
    python scripts/generate_concept_library.py --tracker threads_daily_tracker.json --output concept_library.md
"""

from __future__ import annotations

import argparse
import json
import itertools
import re
import sys
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path


ANALOGY_PATTERNS = (
    "像",
    "好像",
    "就是",
    "孤島",
    "低垂的果實",
)


def load_tracker(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"tracker not found: {path}")
    tracker = json.loads(path.read_text(encoding="utf-8"))
    posts = tracker.get("posts")
    if not isinstance(posts, list):
        raise ValueError("tracker posts field must be an array")
    return tracker


def parse_iso(timestamp: str | None) -> datetime | None:
    if not timestamp:
        return None
    try:
        return datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError:
        return None


def token_count(text: str) -> int:
    return len(re.findall(r"[A-Za-z0-9_+-]+|[\u4e00-\u9fff]", text or ""))


def explanation_depth(count: int, avg_word_count: float) -> str:
    if count >= 2 or avg_word_count >= 180:
        return "deep"
    if avg_word_count >= 120:
        return "medium"
    return "light"


def format_table(headers: list[str], rows: list[list[str]]) -> str:
    if not rows:
        rows = [["-"] * len(headers)]
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        padded = row + ["-"] * (len(headers) - len(row))
        lines.append("| " + " | ".join(padded[: len(headers)]) + " |")
    return "\n".join(lines)


def build_concept_index(posts: list[dict]) -> dict[str, dict]:
    index: dict[str, dict] = {}

    for post in posts:
        created_at = post.get("created_at", "")
        text = post.get("text", "") or ""
        topics = [str(topic).strip() for topic in post.get("topics") or [] if str(topic).strip()]
        word_count = token_count(text)

        for topic in topics:
            bucket = index.setdefault(
                topic,
                {
                    "count": 0,
                    "first_post": post.get("id", ""),
                    "first_date": created_at,
                    "latest_date": created_at,
                    "latest_post": post.get("id", ""),
                    "word_counts": [],
                    "related_topics": Counter(),
                },
            )
            bucket["count"] += 1
            bucket["word_counts"].append(word_count)

            first_dt = parse_iso(bucket["first_date"])
            current_dt = parse_iso(created_at)
            if current_dt and (first_dt is None or current_dt < first_dt):
                bucket["first_post"] = post.get("id", "")
                bucket["first_date"] = created_at

            latest_dt = parse_iso(bucket["latest_date"])
            if current_dt and (latest_dt is None or current_dt > latest_dt):
                bucket["latest_post"] = post.get("id", "")
                bucket["latest_date"] = created_at

            for other_topic in topics:
                if other_topic != topic:
                    bucket["related_topics"][other_topic] += 1

    return index


def extract_analogies(posts: list[dict]) -> list[dict]:
    results = []
    seen = set()
    for post in posts:
        text = post.get("text", "") or ""
        topics = [str(topic).strip() for topic in post.get("topics") or [] if str(topic).strip()]
        for line in text.splitlines():
            snippet = line.strip()
            if not snippet:
                continue
            if not any(pattern in snippet for pattern in ANALOGY_PATTERNS):
                continue
            key = (post.get("id", ""), snippet)
            if key in seen:
                continue
            seen.add(key)
            results.append(
                {
                    "analogy": snippet[:80],
                    "concept": topics[0] if topics else "uncategorized",
                    "post_id": post.get("id", ""),
                }
            )
    return results


def build_concept_clusters(posts: list[dict]) -> list[dict]:
    cluster_counts: Counter[tuple[str, ...]] = Counter()

    for post in posts:
        topics = sorted({str(topic).strip() for topic in post.get("topics") or [] if str(topic).strip()})
        for pair in itertools.combinations(topics, 2):
            cluster_counts[pair] += 1

    clusters = []
    for pair, count in cluster_counts.most_common(8):
        clusters.append(
            {
                "cluster": " + ".join(pair),
                "concepts": ", ".join(pair),
                "frequency": count,
            }
        )
    return clusters


def build_concept_library(tracker: dict) -> str:
    posts = tracker.get("posts") or []
    if not posts:
        raise ValueError("tracker contains no posts")

    concept_index = build_concept_index(posts)
    analogies = extract_analogies(posts)
    clusters = build_concept_clusters(posts)

    explained_rows = []
    lightly_explained_rows = []
    for concept, info in sorted(concept_index.items(), key=lambda item: (-item[1]["count"], item[0])):
        avg_words = sum(info["word_counts"]) / max(1, len(info["word_counts"]))
        depth = explanation_depth(info["count"], avg_words)
        related_topics = ", ".join(topic for topic, _ in info["related_topics"].most_common(3)) or "-"
        notes = f"mentions {info['count']} time(s), avg length {avg_words:.0f} tokens"
        explained_rows.append(
            [
                concept,
                str(info["first_post"]),
                str(parse_iso(info["first_date"]).date() if parse_iso(info["first_date"]) else info["first_date"]),
                depth,
                related_topics,
                notes,
            ]
        )
        if depth == "light":
            lightly_explained_rows.append(
                [
                    concept,
                    str(parse_iso(info["latest_date"]).date() if parse_iso(info["latest_date"]) else info["latest_date"]),
                    depth,
                    "only appears once or in a short explanation",
                ]
            )

    analogy_counter = Counter(item["analogy"] for item in analogies)
    analogy_rows = []
    for item in analogies:
        analogy_rows.append(
            [
                item["analogy"],
                item["concept"],
                item["post_id"],
                "high" if analogy_counter[item["analogy"]] > 1 else "low",
                "explicit comparison phrase found in source text",
            ]
        )

    cluster_rows = [
        [item["cluster"], item["concepts"], str(item["frequency"]), "topic co-occurrence across tracker posts"]
        for item in clusters
    ]

    deeply_explained = [concept for concept, info in concept_index.items() if explanation_depth(info["count"], sum(info["word_counts"]) / max(1, len(info["word_counts"]))) == "deep"]
    repeated_analogies = [analogy for analogy, count in analogy_counter.items() if count > 1]
    future_links = [concept for concept, info in concept_index.items() if info["count"] == 1][:5]

    lines = [
        "# Concept Library",
        "",
        "> Tracks concepts the user has already explained to the audience.",
        f"> Last updated: `{datetime.now(UTC).date().isoformat()}`",
        "",
        "---",
        "",
        "## Coverage",
        "",
        f"- Historical posts scanned: {len(posts)}",
        f"- Concepts indexed: {len(concept_index)}",
        f"- Analogies indexed: {len(analogies)}",
        "",
        "---",
        "",
        "## Explained Concepts",
        "",
        format_table(
            ["Concept", "First Post", "First Date", "Explanation Depth", "Related Topics", "Notes"],
            explained_rows,
        ),
        "",
        "---",
        "",
        "## Concepts That Were Only Lightly Explained",
        "",
        format_table(
            ["Concept", "Latest Mention", "Depth", "Why It Is Still Incomplete"],
            lightly_explained_rows,
        ),
        "",
        "---",
        "",
        "## Used Analogies",
        "",
        format_table(
            ["Analogy", "Concept", "First Post", "Reuse Risk", "Notes"],
            analogy_rows,
        ),
        "",
        "---",
        "",
        "## Concept Clusters",
        "",
        format_table(
            ["Cluster", "Concepts Included", "Frequency", "Notes"],
            cluster_rows,
        ),
        "",
        "---",
        "",
        "## Repeat-Watch Notes",
        "",
        f"- Concepts already deeply explained: {', '.join(sorted(deeply_explained)[:8]) if deeply_explained else '-'}",
        f"- Analogies that are becoming repetitive: {', '.join(repeated_analogies[:5]) if repeated_analogies else '-'}",
        f"- Concepts that can be linked into future posts: {', '.join(future_links) if future_links else '-'}",
        "- Semantic clusters that are nearing fatigue: use `scripts/update_topic_freshness.py` to attach explicit fatigue signals when needed.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate concept_library.md from a tracker JSON file.")
    parser.add_argument("--tracker", required=True, help="Path to threads_daily_tracker.json")
    parser.add_argument("--output", default="concept_library.md", help="Output markdown path")
    args = parser.parse_args()

    tracker_path = Path(args.tracker).resolve()
    output_path = Path(args.output).resolve()

    try:
        tracker = load_tracker(tracker_path)
        content = build_concept_library(tracker)
    except Exception as exc:  # noqa: BLE001 - CLI should fail with actionable text
        print(f"[generate_concept_library] {exc}", file=sys.stderr)
        return 1

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")
    print(f"[generate_concept_library] wrote {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
