---
title: Overview
---

# Envkeep

Envkeep keeps multi-stage environments honest by turning `.env` files into a typed contract. Define the variables your services depend on, validate them locally or in CI, and detect drift before it escapes to production.

## Highlights
- Single source of truth in `envkeep.toml` with strict typing, defaults, and patterns.
- Validation and diffing that normalize values and redact secrets.
- CLI and Python API parity for local developer workflows and automation pipelines.
- Documentation, tests, and CI pipelines ready for production teams.

## Use Cases
- Catch missing secrets before deploys.
- Generate sanitized `.env.example` files automatically.
- Compare staging vs. production to spot unexpected drift.
- Enforce configuration policy as part of GitHub Actions or other CI systems.

## Next Steps
- Read the [Getting Started guide](guides/getting-started.md).
- Explore the [CLI reference](reference/cli.md).
- Dive into the [Python API](reference/api.md).
