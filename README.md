# Envkeep

[![CI](https://github.com/afadesigns/envkeep/actions/workflows/ci.yml/badge.svg)](https://github.com/afadesigns/envkeep/actions/workflows/ci.yml)
[![Release](https://github.com/afadesigns/envkeep/actions/workflows/release.yml/badge.svg)](https://github.com/afadesigns/envkeep/actions/workflows/release.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Docs](https://img.shields.io/badge/docs-latest-brightgreen.svg)](https://afadesigns.github.io/envkeep)

Typed environment specifications, drift detection, and CLI tooling for teams who rely on `.env` files. Envkeep keeps every environment stage aligned without adopting a heavyweight configuration framework.

## Why Envkeep?
- Typed guarantees with strict types, patterns, and enumerated choices defined once in `envkeep.toml`.
- Drift detection that normalizes values before diffing and respects secret redaction.
- Secrets hygiene that highlights undeclared variables and generates sanitized `.env.example` files.
- Library and CLI parity so CI pipelines and local workflows share the same engine.
- Cross-platform support validated on Linux, macOS, and Windows.

## Demo
```
$ envkeep check examples/basic/.env.dev --spec examples/basic/envkeep.toml
Validating examples/basic/.env.dev
All checks passed.

$ envkeep diff examples/basic/.env.dev examples/basic/.env.prod --spec examples/basic/envkeep.toml
Diffing examples/basic/.env.dev -> examples/basic/.env.prod
Changed
┏━━━━━━━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━┓
┃ Variable      ┃ Change  ┃ Left                ┃ Right           ┃
┡━━━━━━━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━┩
│ ALLOWED_HOSTS │ CHANGED │ localhost,api.local │ app.example.com │
│ API_TOKEN     │ CHANGED │ ***                 │ ***             │
│ DATABASE_URL  │ CHANGED │ ***                 │ ***             │
│ DEBUG         │ CHANGED │ true                │ false           │
└───────────────┴─────────┴─────────────────────┴─────────────────┘
Changed: 4 · Impacted: ALLOWED_HOSTS, API_TOKEN, DATABASE_URL
Total differences: 4
```

## Quickstart
1. Install: `pip install envkeep`
2. Create `envkeep.toml`:
   ```toml
   version = 1

   [[variables]]
   name = "DATABASE_URL"
   type = "url"
   required = true
   secret = true
   description = "Primary Postgres DSN"
   ```
3. Validate: `envkeep check .env --spec envkeep.toml`
4. Diff environments: `envkeep diff .env staging.env --spec envkeep.toml`
5. Generate example: `envkeep generate --spec envkeep.toml --output .env.example`

Pipe specs directly from tooling with `--spec -` (for example, `cat envkeep.toml | envkeep check .env --spec -`) and explore metadata via `envkeep inspect --format json` when automating reviews.

See [`examples/basic`](examples/basic) for a complete spec and environment pair.

## Features
- Typed spec parsing with validation for defaults, patterns, and enumerated values.
- Human-friendly and machine-readable reports (`--format text|json`).
- Rich inspection tooling to summarize variables and profiles (`envkeep inspect`, JSON-ready output).
- Secrets-aware diffing that redacts sensitive values.
- Profiles support for multi-stage environments validated via `envkeep doctor`.
- MkDocs-powered documentation with mkdocstrings API reference.
- First-class CI workflows for linting, typing, testing, docs, and release automation.

## Architecture
- `envkeep.toml` defines variables, metadata, and environment profiles.
- The core library normalizes values, produces validation reports, and renders diffs.
- The Typer CLI wraps the library for local and CI usage.
- Tests (pytest plus pytest-benchmark) protect correctness and performance targets.

## Roadmap Highlights
- Remote secret backends (Vault, AWS SSM) as optional providers.
- IDE integrations for inline validation while editing `.env` files.
- GitHub and GitLab Actions wrappers to enforce Envkeep in CI.
See [ROADMAP.md](ROADMAP.md) for the full backlog.

## FAQ
**Is Envkeep a secret manager?** No. Envkeep verifies configuration contracts; storage and rotation stay with your existing tooling.

**Can I load from `os.environ` instead of files?** Yes, use `EnvSnapshot.from_process()`.

**Does Envkeep support YAML specs?** Not yet. TOML keeps dependencies minimal in v0.1.

**Will it slow down CI?** Validation of 500 variables completes in under 120 ms on a 2022 developer laptop (benchmarked via `pytest --benchmark-only`).

## Contributing
1. Fork and clone the repository.
2. Run `make install` to install development dependencies.
3. Use `make lint`, `make typecheck`, and `make test` before submitting a pull request.
4. Review [CONTRIBUTING.md](CONTRIBUTING.md) and [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

## Launch and Growth Plan
- Launch Day: publish v0.1.0 on PyPI, post to r/Python, Hacker News (Show HN), Dev.to, and LinkedIn with demo clips.
- Discoverability: add GitHub topics (`dotenv`, `configuration`, `devops`, `sre`, `python`, `security`, `cli`, `typed-settings`, `ci`, `workflow`).
- Community: seed “good first issue” tasks (spec lint rules, editor integrations) and open GitHub Discussions for Q&A.
- Credibility: publish benchmarks, migration guide, and testimonials from early adopters in docs.

## Support
Need help or commercial support? Check [SUPPORT.md](SUPPORT.md) or open a GitHub Discussion.

## License
Envkeep is available under the [MIT License](LICENSE).
