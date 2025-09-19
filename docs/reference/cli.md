---
title: CLI Reference
---

# CLI Reference

Envkeep ships with a Typer-based CLI. All commands accept `--spec` (default `envkeep.toml`).

## `envkeep check`
Validate an environment file against the spec.

```
envkeep check path/to/.env --spec envkeep.toml --format json
```

Options:
- `--format text|json` (default `text`)
- `--allow-extra` to ignore undeclared variables

Exit codes:
- `0` – success
- `1` – errors found

`envkeep check` also emits warnings for duplicate key declarations so that drift is caught early.

## `envkeep diff`
Compare two environment files with normalization and secret redaction.

```
envkeep diff .env staging.env --spec envkeep.toml
```

Exit codes mirror `check` (non-zero when drift is detected).

## `envkeep generate`
Emit a sanitized `.env.example`.

```
envkeep generate --spec envkeep.toml --output .env.example --no-redact-secrets
```

Use `--no-redact-secrets` to keep default secret values in the output.
Parent directories for `--output` are created automatically.

## `envkeep inspect`
Display a summary of variables and profiles declared in the spec.

```
envkeep inspect --spec envkeep.toml
```

## `envkeep doctor`
Validate every profile declared in the spec.

```
envkeep doctor --spec envkeep.toml --profile production
```

Options:
- `--profile all|NAME` (default `all`)
- `--allow-extra` to suppress warnings for undeclared variables
- `--format text|json` (default `text`) for machine-readable summaries

Exit code aggregates results across profiles (non-zero if any profile fails).
With `--format json`, the command prints an object containing each profile report and omits the Rich table output.
