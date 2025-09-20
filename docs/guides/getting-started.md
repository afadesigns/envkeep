---
title: Getting Started
---

# Getting Started

This guide walks through installing Envkeep, authoring a spec, and validating an environment file.

## Install

```bash
pip install envkeep
```

## Create a Spec

Create `envkeep.toml` in the root of your project:

```toml
version = 1

[[variables]]
name = "DATABASE_URL"
type = "url"
required = true
secret = true
description = "Primary Postgres DSN"

[[variables]]
name = "DEBUG"
type = "bool"
default = false
description = "Toggle debug features"
```

## Validate a `.env`

```bash
envkeep check .env --spec envkeep.toml
```

Exit code `0` indicates success. Non-zero exits mean issues were found; see the accompanying table for details.

Need to keep literal `#` characters or quotes in your values? Escape them (for example, `API_KEY=foo\#bar` or `NAME="Acme \"Beta\""`) and Envkeep will preserve the intended content while still flagging malformed or unterminated quotes as warnings during validation.

If you prefer streaming specs from other tooling, pipe them straight into the CLI with `--spec -`:

```bash
cat envkeep.toml | envkeep check .env --spec -
```

## Generate Examples

```bash
envkeep generate --spec envkeep.toml --output .env.example
```

Add `--no-redact-secrets` if you need actual default values for variables marked as secret.

## Inspect Specifications

Review variable metadata and profiles with a single command:

```bash
envkeep inspect --spec envkeep.toml
```

Need machine-readable output for automation? Switch to JSON:

```bash
envkeep inspect --spec envkeep.toml --format json | jq '.summary'
```

## Explore Examples

Browse [`examples/basic`](https://github.com/afadesigns/envkeep/tree/main/examples/basic) for a more complete spec, including patterns and profile definitions.

## Next Steps
- Wire Envkeep into CI using the [CI how-to](../how-to/ci-enforcement.md).
- Learn the [CLI commands](../reference/cli.md).
- Integrate with Python code using the [API reference](../reference/api.md).
