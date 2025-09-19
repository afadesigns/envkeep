# Maintenance Plan

## Release Cadence
- Patch releases: as needed for bug fixes, ideally within 72 hours of report.
- Minor releases: every 6 weeks with grouped enhancements.
- Major releases: twice per year, following RFCs for breaking changes.

## Contributor Workflow
- Issues triaged twice weekly; labels applied for scope and priority.
- Pull requests require lint, type check, and test evidence in the description.
- Merged changes must include changelog entries unless internal-only.

## Quality Gates
- CI matrix across Linux, macOS, Windows with Python 3.11 and 3.12.
- Nightly cron job runs `pytest --benchmark-only` and `mkdocs build --strict` to detect regressions.
- Dependabot alerts reviewed weekly; security fixes prioritized immediately.

## Community Stewardship
- Host monthly office hours (recorded) to capture roadmap feedback.
- Publish quarterly retrospective posts summarizing metrics, highlights, and next steps.
- Encourage contributors with swag credits at 5 merged PRs.

## Documentation Upkeep
- Sync README quickstart with docs at every release.
- Run link checker (`mkdocs build --strict`) before tagging releases.
- Update API reference via mkdocstrings rebuild as part of release workflow.
