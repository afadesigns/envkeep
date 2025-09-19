from __future__ import annotations

from pathlib import Path

from envkeep import EnvSnapshot, EnvSpec

EXAMPLE_SPEC = Path("examples/basic/envkeep.toml")
DEV_ENV = Path("examples/basic/.env.dev")


def test_validation_benchmark(benchmark) -> None:
    spec = EnvSpec.from_file(EXAMPLE_SPEC)
    snapshot = EnvSnapshot.from_env_file(DEV_ENV)
    benchmark(lambda: spec.validate(snapshot))
