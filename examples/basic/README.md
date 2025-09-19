# Basic Example

This example pairs `envkeep.toml` with local and production `.env` files to demonstrate core features.

## Files
- `envkeep.toml` – Spec with four variables and two profiles.
- `.env.dev` – Developer defaults.
- `.env.prod` – Production defaults.

## Try It
```
envkeep check examples/basic/.env.dev --spec examples/basic/envkeep.toml
envkeep diff examples/basic/.env.dev examples/basic/.env.prod --spec examples/basic/envkeep.toml
```
