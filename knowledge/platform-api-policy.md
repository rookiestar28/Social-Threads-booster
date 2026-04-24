# Platform API Policy Matrix

This document explains how to use `knowledge/platform_api_policy.json`.

The JSON file is the source of truth for platform capability planning. Future adapters must check the relevant platform row before implementing API access, publishing, metric refresh, comment retrieval, or search behavior.

## Rules

1. Do not implement a platform operation unless the policy row marks it as supported or explicitly gated.
2. Treat `review_gated`, `tier_gated`, `limited`, and `unknown_verify_before_use` as fail-closed states until an implementation plan records proof for the exact account, API product, scope, and tier.
3. Do not use browser scraping to bypass a platform capability marked `not_publicly_available`.
4. Do not synthesize missing metrics. If a platform does not expose impressions, reach, or owned insights, report the metric as unavailable.
5. Keep user/account credentials outside tracker data, logs, fixtures, and generated reports.

## Required Adapter Plan Evidence

Every platform adapter plan must record:

- platform key from `platform_api_policy.json`
- official documentation reviewed
- requested auth scopes or account context
- capability rows used
- unavailable capabilities and fallback behavior
- whether credentialed smoke validation is available

