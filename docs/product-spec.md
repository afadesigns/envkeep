# Envkeep Product Specification

## Problem Statement
Modern teams juggle multiple `.env` files and secrets stores across development, staging, and production. Small drifts—missing variables, stale defaults, mistyped URLs—routinely break deployments and leak secrets. Existing linters flag formatting issues but cannot guarantee that every environment matches the intended contract or that diffs are reviewed before release.

## Target Users
- **Backend engineers** shipping services that rely on environment variables for configuration.
- **Platform/DevOps engineers** responsible for enforcing configuration policy across stages.
- **Security engineers** auditing secrets hygiene in CI/CD pipelines.

## Value Proposition
Envkeep provides a single typed specification (`envkeep.toml`) that powers validation, drift detection, sanitized sample generation, and CI enforcement. It delivers confidence that every environment matches policy and that secrets stay in their proper lanes without introducing heavyweight configuration frameworks.

## Scope (MVP)
- TOML-based spec loader with versioned schema and validation of required fields, defaults, patterns, and enumerated choices.
- Environment snapshot loader supporting `.env` files and live `os.environ` ingestion.
- Validation engine producing machine-readable and human-friendly reports with severity levels.
- Drift diffing between two snapshots, highlighting missing, extra, and divergent values while redacting marked secrets.
- CLI (Typer) and mirroring Python API for `check`, `diff`, `generate`, `inspect`, and `doctor` workflows.
- CI-ready exit codes and JSON report output.
- Docs site with tutorials, API reference (mkdocstrings), and operations playbooks.

## Non-Goals
- Managing secret storage or rotation.
- Replacing infrastructure-as-code tools (e.g., Terraform, Pulumi).
- Providing opinionated deployment orchestration.
- Supporting non-file configuration backends in v0 (e.g., Vault, SSM).

## Public API Design
```python
from envkeep import EnvSpec, EnvSnapshot, ValidationReport

spec = EnvSpec.from_file("envkeep.toml")
snapshot = EnvSnapshot.from_env_file(".env")
report = spec.validate(snapshot)
if report.is_success:
    ...
diff = spec.diff(snapshot, EnvSnapshot.from_env_file(".env.prod"))
```
- `EnvSpec.from_file(path: PathLike[str]) -> EnvSpec`
- `EnvSpec.validate(snapshot, *, allow_extra: bool = False) -> ValidationReport`
- `EnvSpec.diff(left: EnvSnapshot, right: EnvSnapshot) -> DiffReport`
- `EnvSpec.generate_example(redact_secrets: bool = True) -> str`
- Reports expose structured data (`issues`, `summary`, `to_json`).

## CLI Specification
- `envkeep check [ENV_FILE] --spec envkeep.toml --format {text,json}`
- `envkeep diff FIRST_ENV SECOND_ENV --spec envkeep.toml`
- `envkeep generate --spec envkeep.toml --output .env.example`
- `envkeep inspect --spec envkeep.toml` (summaries, required variables, secrets)
- `envkeep doctor --spec envkeep.toml --profile all|NAME` (validates each profile declared in spec).

## Performance Targets & Testing
- Validate 500 variables in <120 ms on a 2022 developer laptop (baseline recorded via `benchmarks/validate_env.py`).
- Diff two 500-variable environments in <150 ms.
- No CLI command spawns more than one subprocess; memory overhead stays under 50 MB.
- Performance tests executed via `pytest -q --benchmark-only` in CI’s nightly workflow.
