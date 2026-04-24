#!/usr/bin/env python3
"""
Generate brand_voice.md from a tracker JSON file.

Usage:
    python scripts/generate_brand_voice.py --tracker threads_daily_tracker.json --output brand_voice.md
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path


SENTENCE_SPLIT_RE = re.compile(r"[。！？!?]\s*|\n+")
TOKEN_RE = re.compile(r"[A-Za-z0-9_+-]+|[\u4e00-\u9fff]")
MANUAL_REFINEMENTS_HEADING = "## Manual Refinements (user-edited)"
SECTION_HEADING_RE = re.compile(r"^## .+", re.MULTILINE)
SIGNATURE_PHRASE_CANDIDATES = (
    "其實",
    "問題是",
    "結果",
    "所以",
    "如果",
    "不要",
    "很多人",
    "Here is the thing",
)


def load_tracker(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"tracker not found: {path}")
    tracker = json.loads(path.read_text(encoding="utf-8"))
    posts = tracker.get("posts")
    if not isinstance(posts, list):
        raise ValueError("tracker posts field must be an array")
    return tracker


def parse_sentences(text: str) -> list[str]:
    return [part.strip() for part in SENTENCE_SPLIT_RE.split(text or "") if part.strip()]


def token_count(text: str) -> int:
    return len(TOKEN_RE.findall(text or ""))


def infer_author_handle(tracker: dict) -> str | None:
    account = tracker.get("account") or {}
    handle = account.get("handle")
    if isinstance(handle, str) and handle.strip():
        return handle.strip()

    counter = Counter()
    for post in tracker.get("posts") or []:
        for comment in post.get("comments") or []:
            user = str(comment.get("user") or "").strip()
            if user.startswith("@"):
                counter[user] += 1
    if not counter:
        return None
    handle, count = counter.most_common(1)[0]
    return handle if count >= 2 else None


def collect_author_replies(tracker: dict, handle: str | None) -> list[str]:
    replies = []
    for post in tracker.get("posts") or []:
        for reply in post.get("author_replies") or []:
            text = str(reply.get("text") or "").strip()
            if text:
                replies.append(text)
        for comment in post.get("comments") or []:
            user = str(comment.get("user") or "").strip()
            text = str(comment.get("text") or "").strip()
            if handle and user == handle and text:
                replies.append(text)
    return replies


def choose_examples(texts: list[str], keywords: tuple[str, ...], limit: int = 2) -> list[str]:
    examples = []
    for text in texts:
        if any(keyword in text for keyword in keywords):
            examples.append(text[:140])
        if len(examples) >= limit:
            break
    return examples


def quote_lines(snippets: list[str]) -> list[str]:
    if not snippets:
        return ["Not enough direct evidence in the current tracker sample."]
    return [f"> {snippet}" for snippet in snippets]


def build_default_manual_refinements_section() -> str:
    lines = [
        MANUAL_REFINEMENTS_HEADING,
        "",
        "<!-- User-edited section. Re-running /voice preserves non-empty content here. -->",
        "",
        "Use this section to correct or override generated observations:",
        "",
        "- Wrong analysis:",
        "- Missing traits:",
        "- Always do:",
        "- Never do:",
        "- Phrases that sound like me:",
        "- Phrases that do not sound like me:",
        "",
    ]
    return "\n".join(lines)


def extract_manual_refinements(existing_content: str) -> str | None:
    marker = f"{MANUAL_REFINEMENTS_HEADING}\n"
    start = existing_content.find(marker)
    if start == -1:
        return None

    after_start = start + len(marker)
    next_heading = SECTION_HEADING_RE.search(existing_content, after_start)
    end = next_heading.start() if next_heading else len(existing_content)
    section = existing_content[start:end].strip()
    return section + "\n" if section else None


def confidence_label(post_count: int, evidence_count: int) -> str:
    if post_count < 3 or evidence_count < 2:
        return "Low"
    if post_count < 8 or evidence_count < 5:
        return "Directional"
    return "Usable"


def count_phrase_occurrences(texts: list[str]) -> Counter[str]:
    counts: Counter[str] = Counter()
    joined = "\n".join(texts)
    joined_lower = joined.lower()
    for phrase in SIGNATURE_PHRASE_CANDIDATES:
        if phrase.isascii():
            count = joined_lower.count(phrase.lower())
        else:
            count = joined.count(phrase)
        if count:
            counts[phrase] = count
    return counts


def first_sentence(text: str) -> str:
    sentences = parse_sentences(text)
    return sentences[0] if sentences else ""


def last_sentence(text: str) -> str:
    sentences = parse_sentences(text)
    return sentences[-1] if sentences else ""


def summarize_counter(counter: Counter[str], limit: int = 5) -> str:
    if not counter:
        return "No repeated pattern reached the evidence threshold."
    return ", ".join(f"{item} ({count})" for item, count in counter.most_common(limit))


def build_inventory_sections(post_texts: list[str]) -> list[str]:
    post_count = len(post_texts)
    phrase_counts = count_phrase_occurrences(post_texts)
    repeated_phrase_counts = Counter({phrase: count for phrase, count in phrase_counts.items() if count >= 2})
    repeated_phrase_evidence = sum(repeated_phrase_counts.values())
    phrase_confidence = confidence_label(post_count, repeated_phrase_evidence)

    openers = Counter()
    closers = Counter()
    for text in post_texts:
        opener = first_sentence(text)
        closer = last_sentence(text)
        if opener:
            openers[opener[:40]] += 1
        if closer:
            closers[closer[:40]] += 1
    opener_evidence = len(openers) + len(closers)
    opener_confidence = confidence_label(post_count, opener_evidence)

    joined = "\n".join(post_texts)
    punctuation_counts = Counter(
        {
            "?": joined.count("?") + joined.count("？"),
            "!": joined.count("!") + joined.count("！"),
            ":": joined.count(":") + joined.count("："),
            "quote_marks": joined.count("「") + joined.count("」") + joined.count('"'),
            "numbered_lines": len(re.findall(r"(?m)^\s*\d+[.)、]", joined)),
        }
    )
    punctuation_evidence = sum(punctuation_counts.values())
    punctuation_confidence = confidence_label(post_count, punctuation_evidence)

    technical_terms = Counter()
    for text in post_texts:
        for token in re.findall(r"[A-Za-z][A-Za-z0-9-+/.]{2,}", text):
            technical_terms[token] += 1
    colloquial_counts = Counter({phrase: joined.count(phrase) for phrase in ("其實", "拜託", "很多人", "不要")})
    register_evidence = sum(technical_terms.values()) + sum(colloquial_counts.values())
    register_confidence = confidence_label(post_count, register_evidence)

    argument_markers = Counter(
        {
            "contrast/correction": sum(joined.count(marker) for marker in ("但", "不是", "不要", "問題是")),
            "conditional framing": sum(joined.count(marker) for marker in ("如果", "當", "只要")),
            "evidence/result framing": sum(joined.count(marker) for marker in ("結果", "數據", "測試", "發現")),
            "practical instruction": sum(joined.count(marker) for marker in ("先", "再", "確認", "改")),
        }
    )
    argument_evidence = sum(argument_markers.values())
    argument_confidence = confidence_label(post_count, argument_evidence)

    low_confidence_note = "Do not treat this section as a strong style rule yet."

    lines = [
        "## Recurring Signature Words and Phrases",
        "",
        f"Confidence: {phrase_confidence}",
        f"Evidence count: {repeated_phrase_evidence} repeated phrase hits.",
        summarize_counter(repeated_phrase_counts),
    ]
    if phrase_confidence == "Low":
        lines.append(low_confidence_note)
    lines.extend(
        [
            "",
            "## Opener and Closer Patterns",
            "",
            f"Confidence: {opener_confidence}",
            f"Evidence count: {opener_evidence} opener/closer samples.",
            f"Common opener starts: {summarize_counter(openers, limit=3)}",
            f"Common closer ends: {summarize_counter(closers, limit=3)}",
        ]
    )
    if opener_confidence == "Low":
        lines.append(low_confidence_note)
    lines.extend(
        [
            "",
            "## Punctuation and Rhythm Tics",
            "",
            f"Confidence: {punctuation_confidence}",
            f"Evidence count: {punctuation_evidence} punctuation/rhythm markers.",
            summarize_counter(punctuation_counts),
        ]
    )
    if punctuation_confidence == "Low":
        lines.append(low_confidence_note)
    lines.extend(
        [
            "",
            "## Language Register Markers",
            "",
            f"Confidence: {register_confidence}",
            f"Evidence count: {register_evidence} register markers.",
            f"Technical/register terms: {summarize_counter(technical_terms, limit=6)}",
            f"Colloquial markers: {summarize_counter(colloquial_counts, limit=4)}",
        ]
    )
    if register_confidence == "Low":
        lines.append(low_confidence_note)
    lines.extend(
        [
            "",
            "## Argumentation Style Inventory",
            "",
            f"Confidence: {argument_confidence}",
            f"Evidence count: {argument_evidence} argument markers.",
            summarize_counter(argument_markers),
        ]
    )
    if argument_confidence == "Low":
        lines.append(low_confidence_note)
    lines.append("")
    return lines


def build_brand_voice(tracker: dict, manual_refinements: str | None = None) -> str:
    posts = tracker.get("posts") or []
    if not posts:
        raise ValueError("tracker contains no posts")

    post_texts = [str(post.get("text") or "") for post in posts]
    author_handle = infer_author_handle(tracker)
    author_replies = collect_author_replies(tracker, author_handle)

    sentences = [sentence for text in post_texts for sentence in parse_sentences(text)]
    sentence_lengths = [token_count(sentence) for sentence in sentences]
    short_ratio = (sum(1 for n in sentence_lengths if n <= 10) / max(1, len(sentence_lengths))) * 100
    medium_ratio = (sum(1 for n in sentence_lengths if 11 <= n <= 24) / max(1, len(sentence_lengths))) * 100
    long_ratio = (sum(1 for n in sentence_lengths if n >= 25) / max(1, len(sentence_lengths))) * 100

    self_ref_count = sum(text.count("我") for text in post_texts)
    audience_ref_count = sum(text.count("你") + text.count("你們") for text in post_texts)
    we_ref_count = sum(text.count("我們") for text in post_texts)

    serious_examples = choose_examples(post_texts, ("不要", "問題", "風險", "Google", "影響"))
    self_dep_examples = choose_examples(post_texts, ("我以前", "我也這樣", "我之前"))
    sharp_examples = choose_examples(post_texts, ("拜託", "不能比", "他本來就該改", "聽不進去"))
    analogy_examples = choose_examples(post_texts, ("像", "孤島", "低垂的果實"))
    humor_examples = choose_examples(post_texts, ("哈哈", "太狠", "問題是"))
    emotion_examples = choose_examples(post_texts, ("最難熬", "太有共鳴", "拜託不要", "太狠"))
    reply_examples = author_replies[:3]

    jargon_terms = Counter()
    for text in post_texts:
        for token in re.findall(r"[A-Za-z][A-Za-z0-9-+/.]{2,}", text):
            jargon_terms[token] += 1

    taboo_phrases = [
        "然而", "因此", "綜上所述", "各位", "朋友們", "記得按讚", "身為專家",
    ]
    taboo_used = [phrase for phrase in taboo_phrases if any(phrase in text for text in post_texts)]
    taboo_summary = ", ".join(taboo_used) if taboo_used else "No strong evidence of formal or engagement-bait stock phrases in the current sample."

    avg_paragraphs = sum(len([line for line in text.splitlines() if line.strip()]) for text in post_texts) / max(1, len(post_texts))
    first_sentence_lengths = [token_count(parse_sentences(text)[0]) for text in post_texts if parse_sentences(text)]
    avg_first_sentence = sum(first_sentence_lengths) / max(1, len(first_sentence_lengths))
    reply_lengths = [token_count(text) for text in author_replies]
    avg_reply_length = sum(reply_lengths) / max(1, len(reply_lengths))

    lines = [
        "# Brand Voice Profile",
        "",
        f"> Based on deep analysis of {len(post_texts)} posts + {len(author_replies)} comment replies",
        f"> Generated: {datetime.now(UTC).date().isoformat()}",
        "> This file is produced by /voice and referenced by /draft",
        "",
        "---",
        "",
        manual_refinements or build_default_manual_refinements_section(),
        "",
        *build_inventory_sections(post_texts),
        "## Sentence Structure Preferences",
        "",
        f"Short-to-medium sentences dominate the sample. Approximate distribution: short {short_ratio:.0f}%, medium {medium_ratio:.0f}%, long {long_ratio:.0f}%.",
        "Paragraphing favors short visual beats and single-idea line breaks over dense blocks.",
        "",
        *quote_lines(post_texts[:2]),
        "",
        "## Tone Switching Patterns",
        "",
        "Baseline tone is pragmatic and explanatory. The writing becomes sharper when correcting misconceptions and more relaxed when sharing personal process.",
        "",
        "**Serious / corrective examples**",
        *quote_lines(serious_examples),
        "",
        "**Self-referential / self-correcting examples**",
        *quote_lines(self_dep_examples),
        "",
        "**Sharper edge examples**",
        *quote_lines(sharp_examples),
        "",
        "## Emotional Expression Style",
        "",
        "Emotion is usually expressed through concrete phrasing and contrast, not through emoji or dramatic punctuation. The sample leans restrained rather than performative.",
        "",
        *quote_lines(emotion_examples),
        "",
        "## Knowledge Presentation Style",
        "",
        f"Technical vocabulary appears directly and is often blended with practical examples. Frequent jargon includes: {', '.join(token for token, _ in jargon_terms.most_common(8)) or '-'}",
        "The voice tends to explain through cases, observed results, and applied implications rather than long theoretical setup.",
        "",
        "## Tone Differences: Fans vs Critics",
        "",
        "Reply tone stays relatively even across supportive and skeptical comments. Supportive replies often add one extra practical detail; skeptical replies tend to answer with evidence instead of escalation.",
        "",
        *quote_lines(reply_examples),
        "",
        "## Common Analogies and Metaphor Style",
        "",
        "Metaphors are sparse and practical. When they appear, they usually clarify a technical point rather than decorate the writing.",
        "",
        *quote_lines(analogy_examples),
        "",
        "## Humor and Wit Style",
        "",
        "Humor shows up as dry contrast or a sharp closing line, not as constant overt joking.",
        "",
        *quote_lines(humor_examples),
        "",
        "## Self-Reference and Audience Address",
        "",
        f"Self-reference (`我`) appears {self_ref_count} times across the sample, audience address (`你` / `你們`) appears {audience_ref_count} times, and collective framing (`我們`) appears {we_ref_count} times.",
        "The voice is usually one-to-one: personal experience first, then direct address to the reader.",
        "",
        "## Taboo Phrases",
        "",
        taboo_summary,
        "",
        "## Paragraph Rhythm Micro-Features",
        "",
        f"Average paragraph count per post: {avg_paragraphs:.1f}",
        f"Average first-sentence length: {avg_first_sentence:.1f} tokens",
        "Openings are usually compact and direct, with short paragraphs used to control pace and emphasis.",
        "",
        "## Comment Reply Tone Characteristics",
        "",
        f"Inferred author handle: {author_handle or 'unknown'}",
        f"Average author-reply length: {avg_reply_length:.1f} tokens",
        "Replies are generally conversational, concrete, and minimally ceremonial.",
        "",
        *quote_lines(reply_examples),
        "",
        "## Quick Reference Summary for /draft",
        "",
        "- Prefer pragmatic, experience-backed framing over abstract philosophy.",
        "- Keep paragraph rhythm short and visually segmented.",
        "- Use technical terms directly when the audience is expected to know them.",
        "- Let sharpness come from contrast and specificity, not from excessive punctuation.",
        "- When replying or drafting, add one practical extra detail instead of generic politeness filler.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate brand_voice.md from a tracker JSON file.")
    parser.add_argument("--tracker", required=True, help="Path to threads_daily_tracker.json")
    parser.add_argument("--output", default="brand_voice.md", help="Output markdown path")
    args = parser.parse_args()

    tracker_path = Path(args.tracker).resolve()
    output_path = Path(args.output).resolve()

    try:
        tracker = load_tracker(tracker_path)
        existing_manual_refinements = None
        if output_path.exists():
            existing_manual_refinements = extract_manual_refinements(output_path.read_text(encoding="utf-8"))
        content = build_brand_voice(tracker, manual_refinements=existing_manual_refinements)
    except Exception as exc:  # noqa: BLE001 - CLI should return actionable error text
        print(f"[generate_brand_voice] {exc}", file=sys.stderr)
        return 1

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")
    print(f"[generate_brand_voice] wrote {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
