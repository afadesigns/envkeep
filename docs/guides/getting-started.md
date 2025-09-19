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

## Generate Examples

```bash
envkeep generate --spec envkeep.toml --output .env.example
```

## Explore Examples

Browse [`examples/basic`](../../examples/basic/README.md) for a more complete spec, including patterns and profile definitions.

## Next Steps
- Wire Envkeep into CI using the [CI how-to](../how-to/ci-enforcement.md).
- Learn the [CLI commands](../reference/cli.md).
- Integrate with Python code using the [API reference](../reference/api.md).
