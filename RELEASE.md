# Release Process

1. Update `CHANGELOG.md` with the upcoming version and date.
2. Run `make lint typecheck test docs` to ensure quality gates pass locally.
3. Bump `pyproject.toml` version and commit the change.
4. Tag the commit with `vX.Y.Z` and push the tag.
5. Create a GitHub release. The `release.yml` workflow builds wheels and publishes to PyPI using `PYPI_API_TOKEN`.
6. Announce the release across community channels (see `README.md` launch plan).
