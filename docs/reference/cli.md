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
- `--fail-on-warnings` to make any warnings exit non-zero (e.g., duplicate or invalid lines)
- `--summary-top N` (default `3`) to cap the number of top variables/codes reported in JSON and text summaries (`0` hides the lists)

Exit codes:
- `0` – success
- `1` – errors found

`envkeep check` also emits warnings for duplicate key declarations so that drift is caught early.
Pass `-` instead of a path to read the environment from `stdin` (useful in pipelines).
JSON output returns an object with `report` (including `issue_count`, `severity_totals`, per-code counts, non-empty severities, most-common codes, ordered `variables`, `variables_by_severity`, and `top_variables`) and `summary` mirroring those keys. Both payloads honour `--summary-top`, so the `most_common_codes`/`top_variables` lists shrink to at most `N` entries (or disappear when `0`).
Text output groups issues by severity with Rich tables, keeps entries alphabetised within each section, and ends with a one-line summary (`Errors`, `Warnings`, `Info`) plus an `Impacted` list of the top variables (respecting the `--summary-top` limit) derived from cached counts on `ValidationReport`.

## `envkeep diff`
Compare two environment files with normalization and secret redaction.

```
envkeep diff .env staging.env --spec envkeep.toml
```

Options:
- `--summary-top N` (default `3`) to limit top impacted variables in summaries (`0` hides the lists)

Exit codes mirror `check` (non-zero when drift is detected).
JSON output includes both the full entry list under `report` (now enriched with `is_clean`, `by_kind`, the ordered `variables` list, `non_empty_kinds`, `variables_by_kind`, and `top_variables`) and a `summary` with counts per diff kind plus an `is_clean` flag and the same variables metadata. The `top_variables` list honours `--summary-top`.
Text output renders one table per diff kind (Missing/Extra/Changed), keeps entries sorted alphabetically, and finishes with a summary line showing the per-kind totals, a comma-separated `Impacted` list of the top variables (bounded by `--summary-top`), and the total change count.

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
- `--fail-on-warnings` to fail the run if any profile reports warnings
- `--summary-top N` (default `3`) to include up to `N` top impacted variables/codes in summaries (`0` disables the lists)
- `--profile-base PATH` to override the directory used when resolving relative `env_file` entries (helpful with `--spec -` or shared specs)

Exit code aggregates results across profiles (non-zero if any profile fails).
With `--format json`, the command prints an object containing each profile report and omits the Rich table output. Each profile entry includes `report`, `summary`, and `warnings`. The per-profile summary mirrors `envkeep check` (issue counts plus `has_*` flags, `non_empty_severities`, `most_common_codes`, ordered `variables`, `variables_by_severity`, and `top_variables`), and the top-level payload exposes both an aggregated `summary` (profiles checked, missing profiles, severity totals, success flag, aggregated `non_empty_severities`, `most_common_codes`, `variables`, and `top_variables`) and a `warnings` field with deduplicated, alphabetised duplicate/extra variables along with per-profile invalid line details for automation.
When rendered as text, Envkeep prints a `Doctor Summary` block with totals for missing profiles, severities, a warnings breakdown, an alphabetical list of impacted variables, and a `Top impacted variables` line that highlights the most frequent offenders with their counts.

Profile `env_file` entries are resolved relative to the spec location (or the current working directory when streaming a spec from stdin). Override this base with `--profile-base PATH` when you want to point at another checkout or a temporary workspace. Values such as `../env/app.env` and `~/service.env` are expanded before validation, so specs remain portable across checkouts. In JSON output each profile now includes both the original `env_file` string and a `resolved_env_file` field with the absolute path Envkeep validated. See `examples/socialsense/envkeep.toml` for a larger multi-profile example that relies on the bundled `env/` directory.
