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
$ envkeep check examples/basic/.env.dev
Validating examples/basic/.env.dev
All checks passed.

$ envkeep diff examples/basic/.env.dev examples/basic/.env.prod
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

$ envkeep generate --output .env.example
Wrote example to .env.example
```

Tune the summary footprint with `--summary-top`: raise it to see more impacted variables or set it to `0` to hide the list entirely (available on `check`, `diff`, and `doctor`).

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
3. Validate: `envkeep check .env`
4. Diff environments: `envkeep diff .env staging.env`
5. Generate example: `envkeep generate --output .env.example`

Pipe specs directly from tooling with `--spec -` (for example, `cat envkeep.toml | envkeep check .env --spec -`) and explore metadata via `envkeep inspect --format json` when automating reviews.

See [`examples/basic`](examples/basic) for a complete spec and environment pair and [`examples/socialsense`](examples/socialsense) for a multi-profile demo with bundled `.env` fixtures.

## Configuration

`envkeep` can be configured via a `[tool.envkeep]` section in your `pyproject.toml` file. This is useful for setting project-wide defaults.

-   `spec`: Path to the `envkeep.toml` spec file.
-   `profile_base`: The base directory for resolving relative `env_file` paths in profiles.

**Example `pyproject.toml`:**

```toml
[tool.envkeep]
spec = "config/envkeep.toml"
profile_base = "config/profiles"
```

Command-line options will always override settings in `pyproject.toml`.

## Validation Rules

In addition to types, `envkeep` supports several other validation rules:

-   `choices`: A list of allowed values for a variable.
-   `pattern`: A regular expression that the variable's value must match.
-   `min_length`: The minimum allowed length for a string variable.
-   `max_length`: The maximum allowed length for a string variable.
-   `min_value`: The minimum allowed value for an `int` or `float` variable.
-   `max_value`: The maximum allowed value for an `int` or `float` variable.

**Example `envkeep.toml`:**

```toml
[[variables]]
name = "LOG_LEVEL"
choices = ["debug", "info", "warning", "error"]

[[variables]]
name = "API_KEY"
min_length = 32
max_length = 32

[[variables]]
name = "PORT"
type = "int"
min_value = 1024
max_value = 65535
```

## Shell Completion

`envkeep` supports shell completion for Bash, Zsh, and Fish. To install, run the following command for your shell:

**Bash:**
```bash
envkeep --install-completion bash >> ~/.bashrc
```

**Zsh:**
```bash
envkeep --install-completion zsh >> ~/.zshrc
```

**Fish:**
```bash
envkeep --install-completion fish >> ~/.config/fish/completions/envkeep.fish
```

You may need to restart your shell for the changes to take effect.

## Features
- Automatic `envkeep.toml` discovery by searching the current and parent directories.
- Typed spec parsing with validation for defaults, patterns, and enumerated values.
- Human-friendly and machine-readable reports (`--format text|json`).
- Rich inspection tooling to summarize variables and profiles (`envkeep inspect`, JSON-ready output plus resolved profile paths).
- Secrets-aware diffing that redacts sensitive values.
- Robust `.env` parser that understands `export` syntax, quotes, escapes, and UTF-8 BOM-prefixed files.
- Profiles support for multi-stage environments validated via `envkeep doctor`; relative profile paths resolve against the spec (override with `--profile-base`).
- Configurable summaries that bound the "top variables" lists via `--summary-top` in `check`, `diff`, and `doctor`.
- MkDocs-powered documentation with mkdocstrings API reference.
- First-class CI workflows for linting, typing, testing, docs, and release automation.

### Doctor

The `doctor` command validates profiles against the spec. You can check all profiles at once or target a specific one.

**Check all profiles:**

```bash
envkeep doctor
```

**Check a single profile:**

```bash
envkeep doctor --profile staging
```

**Performance Caching:**

To improve performance, `envkeep` caches the results of `doctor` validations. If neither the `envkeep.toml` spec nor the profile's `.env` file has changed since the last run, `envkeep` will use the cached report instead of re-validating.

To bypass this cache and force a fresh validation, use the `--no-cache` flag:

```bash
envkeep doctor --no-cache
```

### Diff

The `diff` command compares two environment files, using the spec to normalize values and identify meaningful differences. This is useful for comparing local changes against a deployed environment.

## GitHub Action

You can use `envkeep` in your GitHub Actions workflows to automatically validate environment profiles on pull requests. Create a file named `.github/workflows/envkeep.yml` with the following content:

```yaml
name: Envkeep CI

on:
  pull_request:
    branches: [main]

jobs:
  validate-profiles:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - name: Install envkeep
        run: pip install envkeep
      - name: Run envkeep doctor
        run: envkeep doctor --fail-on-warnings
```

This workflow will run on every pull request to the `main` branch and will fail if any of the profiles have errors or warnings.

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

## Plugin System
Envkeep supports a plugin system for fetching variables from remote backends like cloud secret managers or configuration servers.

### AWS Secrets Manager

To use the AWS Secrets Manager backend, first install the necessary dependencies:

```bash
pip install envkeep[aws]
```

Then, in your `envkeep.toml`, add a `source` attribute to any variable you want to fetch from Secrets Manager. The source format is `aws-sm:<secret-id>`, where `<secret-id>` is the name or ARN of the secret.

```toml
[[variables]]
name = "DATABASE_URL"
type = "url"
secret = true
source = "aws-sm:prod/database/url" # Fetched via the 'aws-sm' backend
```

### HashiCorp Vault

To use the HashiCorp Vault backend, first install the necessary dependencies:

```bash
pip install envkeep[vault]
```

The Vault backend authenticates using the `VAULT_ADDR` and `VAULT_TOKEN` environment variables. Make sure these are set in your environment before running `envkeep`.

In your `envkeep.toml`, add a `source` attribute with the format `vault:<mount-point>/<secret-path>`. This backend assumes you are using a KVv2 secrets engine.

```toml
[[variables]]
name = "API_KEY"
secret = true
source = "vault:kv/data/api-keys" # Fetched via the 'vault' backend
```

### Google Cloud Secret Manager

To use the Google Cloud Secret Manager backend, first install the necessary dependencies:

```bash
pip install envkeep[gcp]
```

The backend authenticates using the standard Google Cloud authentication methods (e.g., `gcloud auth application-default login`).

In your `envkeep.toml`, add a `source` attribute with the format `gcp-sm:<resource-id>`, where `<resource-id>` is the full resource name of the secret version.

```toml
[[variables]]
name = "GOOGLE_API_KEY"
secret = true
source = "gcp-sm:projects/my-project/secrets/my-api-key/versions/latest" # Fetched via the 'gcp-sm' backend
```

When you run `envkeep check`, the tool will automatically discover and invoke the plugin. Remotely fetched values take precedence over values in the local `.env` file.

See the [plugin development guide](docs/plugins.md) for details on creating your own backends.

## FAQ
**Is Envkeep a secret manager?** No. Envkeep verifies configuration contracts; storage and rotation stay with your existing tooling.

**Can I load from `os.environ` instead of files?** Yes, use `EnvSnapshot.from_process()`.

**Does Envkeep support YAML specs?** Not yet. TOML keeps dependencies minimal in v1.0.

**Will it slow down CI?** Validation of 500 variables completes in under 120 ms on a 2022 developer laptop (benchmarked via `pytest --benchmark-only`).

## Contributing
1. Fork and clone the repository.
2. Run `make install` to install development dependencies.
3. Use `make lint`, `make typecheck`, and `make test` before submitting a pull request.
4. Review [CONTRIBUTING.md](CONTRIBUTING.md) and [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

## Launch and Growth Plan
- Launch Day: publish v1.0.0 on PyPI, post to r/Python, Hacker News (Show HN), Dev.to, and LinkedIn with demo clips.
- Discoverability: add GitHub topics (`dotenv`, `configuration`, `devops`, `sre`, `python`, `security`, `cli`, `typed-settings`, `ci`, `workflow`).
- Community: seed “good first issue” tasks (spec lint rules, editor integrations) and open GitHub Discussions for Q&A.
- Credibility: publish benchmarks, migration guide, and testimonials from early adopters in docs.

## Support
Need help or commercial support? Check [SUPPORT.md](SUPPORT.md) or open a GitHub Discussion.

## License
Envkeep is available under the [MIT License](LICENSE).