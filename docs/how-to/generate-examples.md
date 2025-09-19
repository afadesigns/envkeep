---
title: Generate Examples
---

# Generate Sanitized .env Files

Envkeep can produce shareable `.env.example` files from your spec.

## Basic Usage

```bash
envkeep generate --spec envkeep.toml --output .env.example
```

Secrets marked with `secret = true` are redacted by default. Use `--no-redact-secrets` to keep default values (for internal repos only).

## Multiple Profiles

Generate examples per profile by overriding the output path:

```bash
envkeep generate --spec envkeep.toml --output .env.staging.example
```

## Automation
- Run `envkeep generate` in CI and commit the result to ensure shared examples stay up to date.
- Pair with `git diff --exit-code` to block merges when generated files diverge.
