# Account and Credential Boundary

Social-Threads-Booster separates account identity from credential values.

Account configuration may contain:

- platform key
- platform account ID or handle
- account type
- display name
- credential source reference
- non-sensitive notes

Account configuration must not contain:

- access tokens
- refresh tokens
- client secrets
- API keys
- passwords
- cookies
- raw OAuth responses

## Local Config

Use `platform_accounts.local.json` for local account context. This file is ignored by Git.

Use `examples/platform-accounts-example.json` as the safe template. The example stores only credential references, not credential values.

## Credential Source Types

| Type | Required reference | Local availability check |
| --- | --- | --- |
| `env` | `name` | environment variable exists and is non-empty |
| `token_file` | `path` | token file exists |
| `external_ref` | `ref` | not locally resolved by default |

## Adapter Rule

Adapters may request an `AccountContext` from `scripts/account_context.py`, but they must retrieve actual secret values through their own bounded credential path. They must not read token values from account config.

