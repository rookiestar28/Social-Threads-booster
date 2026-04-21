#!/usr/bin/env python3
"""
Generate style_guide.md from a tracker JSON file.

Usage:
    python scripts/generate_style_guide.py --tracker threads_daily_tracker.json --output style_guide.md
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean
from typing import Iterable


TOKEN_RE = re.compile(r"[A-Za-z0-9_+-]+|[\u4e00-\u9fff]")
QUESTION_RE = re.compile(r"[?？]\s*$")
DIGIT_RE = re.compile(r"\d")

STOPWORDS = {
    "the", "and", "for", "that", "this", "with", "from", "your", "have", "just",
    "they", "them", "then", "than", "what", "when", "will", "into", "about", "would",
    "there", "their", "because", "while", "which", "where", "been", "were", "being",
    "also", "more", "most", "really", "very", "much", "some", "only", "like", "still",
    "dont", "does", "did", "you", "are", "was", "its", "not", "can", "all", "but",
    "why", "how", "who", "our", "out", "too", "got", "get", "had", "has", "use",
    "using", "used", "make", "made", "post", "thread", "threads",
    "的", "了", "是", "我", "你", "我們", "一個", "這個", "那個", "不是", "就是", "沒有",
    "可以", "因為", "所以", "如果", "什麼", "自己", "現在", "時候", "很多", "比較", "真的",
}


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


def non_empty_paragraphs(text: str) -> list[str]:
    return [line.strip() for line in (text or "").splitlines() if line.strip()]


def token_count(text: str) -> int:
    return len(TOKEN_RE.findall(text or ""))


def average(values: Iterable[float]) -> float:
    values = list(values)
    return mean(values) if values else 0.0


def bucket_word_count(count: int) -> str:
    if count < 150:
        return "0-149"
    if count < 200:
        return "150-199"
    if count < 250:
        return "200-249"
    if count < 300:
        return "250-299"
    if count < 350:
        return "300-349"
    return "350+"


def classify_hook_type(text: str) -> str:
    first_paragraph = non_empty_paragraphs(text)[:1]
    opening = first_paragraph[0] if first_paragraph else (text or "").strip()
    if QUESTION_RE.search(opening):
        return "question"
    if DIGIT_RE.search(opening) or any(marker in opening for marker in ("數據", "結果", "%", "LCP", "實測")):
        return "data/result"
    if any(marker in opening for marker in ("我以前", "昨天", "最近", "上禮拜", "上個月", "有人問我", "有個客戶", "做了")):
        return "story"
    if any(marker in opening for marker in ("小技巧", "解法", "做法", "步驟", "常見")):
        return "instructional"
    return "direct statement"


def classify_ending_type(text: str) -> str:
    paragraphs = non_empty_paragraphs(text)
    ending = paragraphs[-1] if paragraphs else (text or "").strip()
    if QUESTION_RE.search(ending):
        return "open question"
    if any(marker in ending for marker in ("不要", "記得", "先", "建議", "可以", "做法")):
        return "practical takeaway"
    if any(marker in ending for marker in ("重點", "答案", "本質", "不是", "而是", "反正")):
        return "summary statement"
    return "observation close"


def classify_emotional_arc(text: str, content_type: str) -> str:
    if content_type == "story":
        return "story -> turn -> lesson"
    if content_type == "tutorial":
        return "problem -> steps -> takeaway"
    if content_type == "question":
        return "question -> stance -> discussion"
    if any(marker in text for marker in ("結果", "後來", "發現")):
        return "setup -> discovery -> conclusion"
    return "observation -> argument -> conclusion"


def classify_register(text: str) -> str:
    formal_markers = sum(text.count(marker) for marker in ("然而", "因此", "此外", "綜上所述"))
    colloquial_markers = sum(text.count(marker) for marker in ("其實", "拜託", "真的", "太", "哈哈"))
    if colloquial_markers > formal_markers:
        return "colloquial"
    if formal_markers > colloquial_markers:
        return "formal"
    return "mixed"


def signature_phrases(posts: list[dict], limit: int = 5) -> list[str]:
    counts: Counter[str] = Counter()
    for post in posts:
        text = post.get("text", "")
        for token in TOKEN_RE.findall(text):
            lowered = token.lower()
            if lowered in STOPWORDS:
                continue
            if len(token) == 1 and not ("\u4e00" <= token <= "\u9fff"):
                continue
            counts[token] += 1
    return [token for token, count in counts.most_common(limit) if count > 1]


def top_topics(posts: list[dict]) -> Counter[str]:
    counter: Counter[str] = Counter()
    for post in posts:
        for topic in post.get("topics") or []:
            topic = str(topic).strip()
            if topic:
                counter[topic] += 1
    return counter


def format_table(headers: list[str], rows: list[list[str]]) -> str:
    if not rows:
        rows = [["-", "-", "-", "-", "-"][: len(headers)]]
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        normalized = row + ["-"] * (len(headers) - len(row))
        lines.append("| " + " | ".join(normalized[: len(headers)]) + " |")
    return "\n".join(lines)


def build_post_features(post: dict) -> dict:
    text = post.get("text", "") or ""
    metrics = post.get("metrics") or {}
    paragraphs = non_empty_paragraphs(text)
    content_type = str(post.get("content_type") or "unknown")
    word_count = int(post.get("word_count") or token_count(text))
    paragraph_count = int(post.get("paragraph_count") or len(paragraphs))
    return {
        "id": post.get("id", ""),
        "text": text,
        "created_at": post.get("created_at", ""),
        "content_type": content_type,
        "topics": post.get("topics") or [],
        "views": int(metrics.get("views") or 0),
        "likes": int(metrics.get("likes") or 0),
        "replies": int(metrics.get("replies") or 0),
        "shares": int(metrics.get("shares") or 0),
        "hook_type": str(post.get("hook_type") or classify_hook_type(text)),
        "ending_type": str(post.get("ending_type") or classify_ending_type(text)),
        "emotional_arc": str(post.get("emotional_arc") or classify_emotional_arc(text, content_type)),
        "word_count": word_count,
        "paragraph_count": paragraph_count,
        "register": classify_register(text),
    }


def average_metric(features: list[dict], metric: str) -> str:
    return f"{average(item[metric] for item in features):.1f}" if features else "0.0"


def hit_rate(features: list[dict], top_ids: set[str]) -> str:
    if not features:
        return "0%"
    hits = sum(1 for item in features if item["id"] in top_ids)
    return f"{(hits / len(features)) * 100:.0f}%"


def confidence_level(post_count: int) -> str:
    if post_count < 5:
        return "Directional"
    if post_count < 10:
        return "Weak"
    if post_count < 20:
        return "Usable"
    if post_count < 50:
        return "Strong"
    return "Deep"


def build_style_guide(tracker: dict) -> str:
    raw_posts = tracker.get("posts") or []
    features = [build_post_features(post) for post in raw_posts]
    if not features:
        raise ValueError("tracker contains no posts")

    sorted_by_views = sorted(features, key=lambda item: item["views"], reverse=True)
    top_quartile_count = max(1, math.ceil(len(features) * 0.25))
    top_quartile = sorted_by_views[:top_quartile_count]
    top_ids = {item["id"] for item in top_quartile}
    topic_counts = top_topics(raw_posts)

    view_reliable = sum(1 for item in features if item["views"] > 0)
    reply_reliable = sum(1 for item in features if item["replies"] > 0)
    dated = [parse_iso(item["created_at"]) for item in features]
    dated = [dt for dt in dated if dt is not None]
    time_range = (
        f"{min(dated).date().isoformat()} to {max(dated).date().isoformat()}"
        if dated
        else "unknown"
    )
    confidence = confidence_level(len(features))

    dominant_content_types = ", ".join(
        f"{name} ({count})" for name, count in Counter(item["content_type"] for item in features).most_common(3)
    )
    dominant_hook_types = ", ".join(
        f"{name} ({count})" for name, count in Counter(item["hook_type"] for item in features).most_common(3)
    )
    dominant_endings = ", ".join(
        f"{name} ({count})" for name, count in Counter(item["ending_type"] for item in features).most_common(3)
    )
    dominant_arcs = ", ".join(
        f"{name} ({count})" for name, count in Counter(item["emotional_arc"] for item in features).most_common(3)
    )
    dominant_register = ", ".join(
        f"{name} ({count})" for name, count in Counter(item["register"] for item in features).most_common(2)
    )

    hook_rows = []
    by_hook: dict[str, list[dict]] = defaultdict(list)
    for item in features:
        by_hook[item["hook_type"]].append(item)
    for hook_type, group in sorted(by_hook.items(), key=lambda pair: average(x["views"] for x in pair[1]), reverse=True):
        hook_rows.append([
            hook_type,
            str(len(group)),
            average_metric(group, "views"),
            average_metric(group, "replies"),
            hit_rate(group, top_ids),
            f"avg likes {average_metric(group, 'likes')}",
        ])

    ending_rows = []
    by_ending: dict[str, list[dict]] = defaultdict(list)
    for item in features:
        by_ending[item["ending_type"]].append(item)
    for ending_type, group in sorted(by_ending.items(), key=lambda pair: average(x["views"] for x in pair[1]), reverse=True):
        ending_rows.append([
            ending_type,
            str(len(group)),
            average_metric(group, "views"),
            average_metric(group, "replies"),
            average_metric(group, "shares"),
            f"hit rate {hit_rate(group, top_ids)}",
        ])

    content_rows = []
    by_content: dict[str, list[dict]] = defaultdict(list)
    for item in features:
        by_content[item["content_type"]].append(item)
    for content_type, group in sorted(by_content.items(), key=lambda pair: average(x["views"] for x in pair[1]), reverse=True):
        content_rows.append([
            content_type,
            str(len(group)),
            average_metric(group, "views"),
            average_metric(group, "replies"),
            average_metric(group, "shares"),
            f"avg likes {average_metric(group, 'likes')}",
        ])

    arc_rows = []
    by_arc: dict[str, list[dict]] = defaultdict(list)
    for item in features:
        by_arc[item["emotional_arc"]].append(item)
    for arc, group in sorted(by_arc.items(), key=lambda pair: average(x["views"] for x in pair[1]), reverse=True):
        arc_rows.append([
            arc,
            str(len(group)),
            average_metric(group, "views"),
            average_metric(group, "replies"),
            f"top quartile {hit_rate(group, top_ids)}",
        ])

    top_pattern_rows = [
        [
            "content types of top-quartile posts",
            str(len(top_quartile)),
            f"median views {sorted(item['views'] for item in top_quartile)[len(top_quartile) // 2]}",
            dominant_content_types or "-",
        ],
        [
            "hook mix of top-quartile posts",
            str(len(top_quartile)),
            dominant_hook_types or "-",
            dominant_endings or "-",
        ],
    ]

    hook_payoff_rows = [
        [
            "direct value delivery in first half",
            str(sum(1 for item in features if item["paragraph_count"] >= 4)),
            f"avg views {average(item['views'] for item in features if item['paragraph_count'] >= 4):.1f}",
            "longer posts often front-load a practical explanation",
        ],
        [
            "single-theme close",
            str(sum(1 for item in features if len(item['topics']) <= 4)),
            f"top quartile posts {sum(1 for item in top_quartile if len(item['topics']) <= 4)}",
            "most example posts stay centered on one main SEO problem",
        ],
    ]

    word_band_rows = []
    by_word_band: dict[str, list[dict]] = defaultdict(list)
    for item in features:
        by_word_band[bucket_word_count(item["word_count"])].append(item)
    for band, group in sorted(by_word_band.items()):
        word_band_rows.append([
            band,
            str(len(group)),
            average_metric(group, "views"),
            average_metric(group, "replies"),
            f"avg paragraphs {average(item['paragraph_count'] for item in group):.1f}",
        ])

    structure_rows = [
        [
            "single-line heavy paragraphs",
            str(sum(1 for item in features if item["paragraph_count"] >= 6)),
            f"avg views {average(item['views'] for item in features if item['paragraph_count'] >= 6):.1f}",
            "most posts use short visual beats instead of dense blocks",
        ],
        [
            "compact structure",
            str(sum(1 for item in features if item["paragraph_count"] <= 4)),
            f"avg views {average(item['views'] for item in features if item['paragraph_count'] <= 4):.1f}",
            "used less often in the sample tracker",
        ],
    ]

    def pronoun_density(pronoun: str) -> str:
        total_tokens = sum(item["word_count"] for item in features) or 1
        total_hits = sum(item["text"].count(pronoun) for item in features)
        return f"{(total_hits / total_tokens) * 100:.2f}%"

    pronoun_rows = [
        ["I / me density", pronoun_density("我"), "first-person experience is common in sample posts"],
        ["You density", pronoun_density("你"), "direct audience address appears regularly"],
        ["We density", pronoun_density("我們"), "collective framing is less common in sample posts"],
        ["Register mix", dominant_register or "-", "derived from lightweight colloquial/formal markers"],
    ]

    share_rows = []
    for item in sorted(features, key=lambda row: (row["shares"], row["replies"], row["views"]), reverse=True)[:3]:
        share_rows.append([
            f"{item['content_type']} / {item['hook_type']}",
            item["id"],
            f"shares {item['shares']}, replies {item['replies']}",
            "high-share posts combine a clear stance with applied examples",
        ])

    topic_rows = []
    for topic, count in topic_counts.most_common(8):
        topic_posts = [item for item in features if topic in item["topics"]]
        recent_frequency = sum(1 for item in features[:5] if topic in item["topics"])
        topic_rows.append([
            topic,
            str(count),
            str(recent_frequency),
            f"avg views {average_metric(topic_posts, 'views')}",
            "derived from explicit tracker topics",
        ])

    freshness_rows = []
    seen_clusters = set()
    for post in raw_posts:
        freshness = ((post.get("algorithm_signals") or {}).get("topic_freshness") or {})
        cluster = freshness.get("semantic_cluster")
        if not cluster or cluster in seen_clusters:
            continue
        seen_clusters.add(cluster)
        freshness_rows.append([
            str(cluster),
            str(freshness.get("similar_recent_posts") if freshness.get("similar_recent_posts") is not None else "-"),
            str(freshness.get("days_since_last_similar_post") if freshness.get("days_since_last_similar_post") is not None else "-"),
            str(freshness.get("freshness_score") if freshness.get("freshness_score") is not None else "-"),
            str(freshness.get("fatigue_risk") if freshness.get("fatigue_risk") is not None else "-"),
            "tracker-provided topic freshness field",
        ])
    if not freshness_rows:
        freshness_rows.append([
            "not yet annotated",
            "-",
            "-",
            "-",
            "-",
            "run scripts/update_topic_freshness.py to populate semantic freshness fields",
        ])

    best_word_band = max(by_word_band.items(), key=lambda pair: average(x["views"] for x in pair[1]))[0]
    avg_paragraphs = average(item["paragraph_count"] for item in features)
    best_posting_windows = Counter(post.get("posting_time_slot") or "unknown" for post in raw_posts).most_common(3)
    best_window_summary = ", ".join(f"{slot} ({count})" for slot, count in best_posting_windows)
    signatures = signature_phrases(raw_posts)

    lines = [
        "# Personalized Style Guide",
        "",
        "> Generated from the user's historical Threads posts.",
        f"> Last updated: `{datetime.now(UTC).date().isoformat()}`",
        "",
        "---",
        "",
        "## Data Coverage",
        "",
        f"- Historical posts analyzed: {len(features)}",
        f"- Posts with reliable view data: {view_reliable}",
        f"- Posts with reliable reply data: {reply_reliable}",
        f"- Time range covered: {time_range}",
        f"- Confidence level: {confidence}",
        "",
        "---",
        "",
        "## Style Snapshot",
        "",
        f"- Dominant content types: {dominant_content_types or '-'}",
        f"- Dominant hook types: {dominant_hook_types or '-'}",
        f"- Typical word-count range: {best_word_band}",
        f"- Typical paragraph count: {avg_paragraphs:.1f}",
        f"- Typical ending patterns: {dominant_endings or '-'}",
        f"- Typical emotional arcs: {dominant_arcs or '-'}",
        f"- Typical register: {dominant_register or '-'}",
        "",
        "---",
        "",
        "## Top-Quartile Patterns",
        "",
        format_table(
            ["Pattern", "Evidence Count", "Performance Signal", "Notes"],
            top_pattern_rows,
        ),
        "",
        "---",
        "",
        "## Hook Types",
        "",
        format_table(
            ["Hook Type", "Usage Count", "Avg Views", "Avg Replies", "Top-Quartile Hit Rate", "Notes"],
            hook_rows,
        ),
        "",
        "---",
        "",
        "## Hook Promise Fulfillment",
        "",
        format_table(
            ["Pattern", "Evidence Count", "Performance Signal", "Notes"],
            hook_payoff_rows,
        ),
        "",
        "---",
        "",
        "## Ending Patterns",
        "",
        format_table(
            ["Ending Type", "Usage Count", "Avg Views", "Avg Replies", "Share Signal", "Notes"],
            ending_rows,
        ),
        "",
        "---",
        "",
        "## Word Count And Structure",
        "",
        f"- Best-performing word-count band: {best_word_band}",
        f"- Typical paragraph-count band: {avg_paragraphs:.1f}",
        "- Notes on short-form vs long-form performance: higher-performing sample posts usually keep short paragraphs even when total length increases.",
        "",
        format_table(
            ["Structure Pattern", "Usage Count", "Performance Signal", "Notes"],
            structure_rows,
        ),
        "",
        format_table(
            ["Word Band", "Usage Count", "Avg Views", "Avg Replies", "Notes"],
            word_band_rows,
        ),
        "",
        "---",
        "",
        "## Pronoun And Register Use",
        "",
        format_table(
            ["Feature", "Baseline", "Notes"],
            pronoun_rows,
        ),
        "",
        "---",
        "",
        "## Content Types",
        "",
        format_table(
            ["Content Type", "Usage Count", "Avg Views", "Avg Replies", "Avg Shares", "Notes"],
            content_rows,
        ),
        "",
        "---",
        "",
        "## Emotional Arcs",
        "",
        format_table(
            ["Emotional Arc", "Usage Count", "Avg Views", "Avg Replies", "Notes"],
            arc_rows,
        ),
        "",
        "---",
        "",
        "## Share And DM Drivers",
        "",
        format_table(
            ["Driver", "Evidence Count", "Performance Signal", "Notes"],
            share_rows,
        ),
        "",
        "---",
        "",
        "## Topic Clusters And Repetition Pressure",
        "",
        format_table(
            ["Topic Cluster", "Usage Count", "Recent Frequency", "Performance Signal", "Notes"],
            topic_rows,
        ),
        "",
        "---",
        "",
        "## Topic Freshness Budget",
        "",
        format_table(
            ["Semantic Cluster", "Similar Recent Posts", "Days Since Last Similar Post", "Freshness Signal", "Fatigue Risk", "Notes"],
            freshness_rows,
        ),
        "",
        "---",
        "",
        "## Timing Notes",
        "",
        f"- Best posting windows: {best_window_summary or '-'}",
        "- Day-of-week effects: not strongly modeled yet; current output is descriptive only.",
        f"- Reliability of timing data: {'usable' if dated else 'weak'}",
        "",
        "---",
        "",
        "## Signature Phrases",
        "",
    ]

    if signatures:
        for phrase in signatures:
            lines.append(f"- Phrase: {phrase}")
    else:
        lines.append("- Phrase: not enough repeated phrases yet")

    lines.extend([
        "",
        "---",
        "",
        "## Confidence Notes",
        "",
        f"- Which conclusions are statistically strong: overall content-type and hook-type comparisons across {len(features)} posts.",
        "- Which conclusions are still thin-sample: timing windows, share drivers, and any section with only one or two posts in a bucket.",
        "- Missing data caveats: derived heuristics are used when tracker-enriched fields are absent.",
        "",
    ])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate style_guide.md from a tracker JSON file.")
    parser.add_argument("--tracker", required=True, help="Path to threads_daily_tracker.json")
    parser.add_argument("--output", default="style_guide.md", help="Output markdown path")
    args = parser.parse_args()

    tracker_path = Path(args.tracker).resolve()
    output_path = Path(args.output).resolve()

    try:
        tracker = load_tracker(tracker_path)
        content = build_style_guide(tracker)
    except Exception as exc:  # noqa: BLE001 - CLI should return actionable error text
        print(f"[generate_style_guide] {exc}", file=sys.stderr)
        return 1

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")
    print(f"[generate_style_guide] wrote {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
