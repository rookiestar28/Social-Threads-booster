# Platform Adapter Review Gate

Every platform adapter implementation must include policy review evidence before acceptance.

Use `examples/platform-adapter-review-example.json` as the safe shape and validate it with:

```bash
python scripts/validate_platform_review.py --review <review-file.json>
```

## Required Evidence

Each review file must record:

- platform key
- adapter item or implementation identifier
- official docs reviewed
- capabilities reviewed and their policy status
- implementation decision for each reviewed capability
- rate-limit policy
- data-retention policy
- disallowed fallbacks
- credentialed smoke status

## Safety Rules

- Do not include secrets, tokens, cookies, private URLs, screenshots, raw private logs, or full API responses.
- Prefer explicit `credentialed validation unavailable` notes over unsafe credential handling.
- Capabilities marked `not_publicly_available` must not be implemented through scraping fallbacks.
- Capabilities marked `review_gated`, `tier_gated`, `limited`, or `unknown_verify_before_use` must fail closed until the implementation plan records exact proof.

