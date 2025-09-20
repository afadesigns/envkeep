---
title: Validate Multi-profile Environments
---

# Validate Multi-profile Environments

Run Envkeep's doctor workflow against several environment files at once to ensure they stay in sync with the specification.

## Use the Socialsense sample spec

The repository ships a multi-profile example at `examples/socialsense/envkeep.toml`. The spec declares multiple profiles whose `env_file` entries target the bundled `examples/socialsense/env/` directory so you can run validations without checking out any external projects.

```bash
uv run envkeep doctor --spec examples/socialsense/envkeep.toml
```

Envkeep resolves every profile path relative to the spec directory and expands user home markers such as `~/service.env`. When you need to point at a different checkout (for example, CI workspaces), supply `--profile-base /path/to/checkout` to override the resolution root.

## Target specific profiles

Limit validation to one profile when you only need to audit a subset.

```bash
uv run envkeep doctor --spec examples/socialsense/envkeep.toml --profile database
```

Combine the `--profile` flag with `--fail-on-warnings` to fail CI on duplicate variables, invalid lines, or missing entries even when there are no hard errors.

## Capture machine-readable reports

For automated pipelines, switch to JSON output and consume the per-profile summary payload.

```bash
uv run envkeep doctor --spec examples/socialsense/envkeep.toml --format json \
  | jq '.summary, .profiles[] | {profile, env_file: .env_file, resolved_env_file: .resolved_env_file}'
```

The aggregated summary mirrors `envkeep check`, providing severity totals, affected variables, and top offenders for dashboards or alerting systems. Individual profile payloads expose a `resolved_env_file` field so downstream tooling receives absolute locations regardless of how the spec references the profiles.
