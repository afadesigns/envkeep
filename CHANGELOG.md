# Changelog

All notable changes to Envkeep will be documented here.

## [Unreleased]
### Added
- Allowed specs to be streamed from stdin across CLI commands via `--spec -` with guardrails against duplicate stdin consumption.
- Added JSON output for `envkeep inspect` so automation can consume variable and profile metadata.
- Added `--profile-base` to `envkeep doctor` for overriding the directory used to resolve relative profile paths, especially when specs are streamed from stdin.
- Bundled runnable Socialsense `.env` fixtures under `examples/socialsense/env/` to demonstrate multi-profile validation without extra checkouts.
- Extended `envkeep inspect --format json` profile entries with a `resolved_env_file` field that exposes the absolute path Envkeep validated.

### Changed
- Hardened `.env` parsing to preserve escaped `#` characters, honour embedded quotes, and surface unterminated strings as validation warnings.
- Centralized CLI output formatting with strict format validation and clearer TOML parse diagnostics.
- Shielded specification caches behind read-only views to prevent accidental mutation between validations.
- Updated project branding and metadata for Andreas Fahl / afadesigns ahead of the public repository launch.
- Relative profile `env_file` values now resolve against the spec directory by default; use `--profile-base` when a different root is required.
- Text-mode `envkeep doctor` reports now surface a "Resolved profile paths" section showing both the declared and absolute environment file locations.

### Documentation
- Clarified how to escape `#` characters and quotes in `.env` files within the getting started guide.
- Refreshed governance, conduct, and support docs with the new maintainer contact paths.

## [0.1.0] - 2025-09-19
### Added
- Initial Envkeep release with typed spec loader, validation engine, drift diffing, and CLI commands.
- Documentation site, tests, and CI workflows.
