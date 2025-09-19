# Changelog

All notable changes to Envkeep will be documented here.

## [Unreleased]
### Added
- Allowed specs to be streamed from stdin across CLI commands via `--spec -` with guardrails against duplicate stdin consumption.
- Added JSON output for `envkeep inspect` so automation can consume variable and profile metadata.

### Changed
- Hardened `.env` parsing to preserve escaped `#` characters, honour embedded quotes, and surface unterminated strings as validation warnings.
- Centralized CLI output formatting with strict format validation and clearer TOML parse diagnostics.
- Shielded specification caches behind read-only views to prevent accidental mutation between validations.
- Updated project branding and metadata for Andreas Fahl / afadesigns ahead of the public repository launch.

### Documentation
- Clarified how to escape `#` characters and quotes in `.env` files within the getting started guide.
- Refreshed governance, conduct, and support docs with the new maintainer contact paths.

## [0.1.0] - 2025-09-19
### Added
- Initial Envkeep release with typed spec loader, validation engine, drift diffing, and CLI commands.
- Documentation site, tests, and CI workflows.
