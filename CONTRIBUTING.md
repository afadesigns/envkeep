# Contributing to Envkeep

Thanks for your interest in improving Envkeep! The project welcomes bug reports, feature ideas, and pull requests from the community.

## Ground Rules
- Follow the [Code of Conduct](CODE_OF_CONDUCT.md).
- Default branch is `main`; keep pull requests focused and atomic.
- Use conventional commit prefixes where practical (`feat:`, `fix:`, `docs:`).
- Document user-facing changes in [CHANGELOG.md](CHANGELOG.md).

## Development Workflow
1. Fork and clone the repository.
2. Install dependencies: `make install`.
3. Run quality checks locally:
   - `make fmt` (format code)
   - `make lint` (ruff lint)
   - `make typecheck` (mypy)
   - `make test` (pytest)
4. Add or update tests for any behavior changes.
5. Update documentation when new features or flags are introduced.
6. Submit a pull request referencing any related issues.

## Testing Strategy
- Unit tests live in `tests/unit`; integration scenarios belong in `tests/integration`.
- Performance targets are tracked in `benchmarks/` via `pytest --benchmark-only`.
- CI runs on Ubuntu, macOS, and Windows; avoid platform-specific assumptions.

## Documentation
- Docs are built with MkDocs Material. Source files live in `docs/`.
- Run `make docs` before submitting doc-heavy pull requests to ensure the site builds cleanly.

## Issue Labels
- `bug`: reproducible defects.
- `enhancement`: feature requests or improvements.
- `good first issue`: curated starters for newcomers.
- `help wanted`: maintainers actively seeking assistance.

## Thank You
Contributors will be acknowledged in release notes. We appreciate every report, test, and pull request that helps Envkeep grow.
