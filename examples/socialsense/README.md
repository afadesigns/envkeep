# Socialsense Example

This directory contains a runnable multi-profile Envkeep specification that demonstrates how teams can validate several environment files at once.

- `envkeep.toml` declares the variables and two profiles (`database` and `integration-tests`).
- `env/` bundles `.env` fixtures that mimic local and CI configuration for the Socialsense service.

Try the workflows:

```bash
uv run envkeep doctor --spec examples/socialsense/envkeep.toml
uv run envkeep doctor --spec examples/socialsense/envkeep.toml --profile-base /tmp/other-checkout --profile database
uv run envkeep doctor --spec examples/socialsense/envkeep.toml --format json | jq '.summary.profile_base_dir, .profiles[] | {profile, resolved_env_file}'
```

The text report ends with a "Resolved profile paths" block that lists the original `env_file` values alongside the absolute paths Envkeep validated, so you always know which files were inspected.
