---
title: Enforce Envkeep in CI
---

# Enforce Envkeep in CI

Use Envkeep to block deployments when configuration drift is detected.

## GitHub Actions Example

```yaml
name: Config Guard
on: [push]
jobs:
  envkeep:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: |
          pip install envkeep
          envkeep check .env --spec envkeep.toml --fail-on-warnings
```

## Pre-commit Hook

Add to `.pre-commit-config.yaml`:

```yaml
  - repo: local
    hooks:
      - id: envkeep-check
        name: Envkeep check
        entry: envkeep check .env --spec envkeep.toml
        language: system
        pass_filenames: false
```

## Deployment Pipelines
- Validate staging and production env files with `envkeep doctor --profile staging --fail-on-warnings` before promoting builds.
- Store normalization reports as artifacts to audit configuration history.
- When env files are provided dynamically, pipe them into `envkeep check - --spec envkeep.toml` to avoid touching disk.
