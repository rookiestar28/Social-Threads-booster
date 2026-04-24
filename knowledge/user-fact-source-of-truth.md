# User-Fact Source of Truth

This policy applies whenever a workflow references the user's biography, work history, lived experience, chronology, relationships, location, identity, preferences, or claims about what happened to them.

## Source Priority

Use this order when sources conflict:

1. The user's explicit instruction in the current session.
2. The user's own posts, replies, tracker records, and pasted history.
3. User-edited sections of `brand_voice.md`, especially Manual Refinements when present.
4. Generated style or voice analysis as weak observational evidence.
5. Public web sources only for external facts, never to override the user's own stated personal facts.

## Required Behavior

- Preserve chronology exactly as the user stated it.
- Attribute a personal fact to the user only when it appears in user-provided material.
- Treat dates, ages, employers, family details, locations, and personal milestones as fragile.
- If user-provided sources conflict, surface the conflict and ask for confirmation.
- If a draft needs a personal fact that cannot be verified from user-provided material, mark it `[confirm with user]`.
- Use bounded references such as post ID/date or redacted summaries. Do not copy sensitive personal details into logs.

## Forbidden Behavior

- Do not infer biography from tone, topic, or audience.
- Do not reorder the user's timeline.
- Do not merge facts from different platforms into a new story unless the user already connected them.
- Do not let web search override the user's own personal account.
- Do not store private personal facts, raw post bodies, private URLs, credentials, or screenshots in audit logs.

## Skill Expectations

- `/draft`: confirm or omit personal facts before using them in generated text.
- `/analyze`: flag personal-fact drift or inconsistency without rewriting the user's submitted post.
- `/review`: when evaluating outcomes, consider flagged personal-fact conflicts as context only; never treat them as proof of a private fact.

