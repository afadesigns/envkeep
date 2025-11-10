from __future__ import annotations

from pathlib import Path

import pytest

from envkeep import DiffKind, EnvSnapshot, EnvSpec

EXAMPLE_SPEC = Path("examples/basic/envkeep.toml")


def test_spec_load_and_summary() -> None:
    spec = EnvSpec.from_file(EXAMPLE_SPEC)
    summary = spec.summary()
    assert summary["version"] == 1
    assert "DATABASE_URL" in summary["variables"]
    assert "development" in summary["profiles"]


def test_validate_reports_missing_required(tmp_path: Path) -> None:
    spec = EnvSpec.from_file(EXAMPLE_SPEC)
    env_file = tmp_path / ".env"
    env_file.write_text("DATABASE_URL=postgresql://localhost:5432/dev\n", encoding="utf-8")
    snapshot = EnvSnapshot.from_env_file(env_file)
    report = spec.validate(snapshot)
    assert not report.is_success
    assert report.error_count == 1
    assert report.issues[0].variable == "API_TOKEN"


def test_diff_detects_changes(tmp_path: Path) -> None:
    spec = EnvSpec.from_file(EXAMPLE_SPEC)
    left = tmp_path / "left.env"
    right = tmp_path / "right.env"
    left.write_text(
        "\n".join(
            [
                "DATABASE_URL=postgresql://localhost/dev",
                "DEBUG=false",
                "ALLOWED_HOSTS=localhost",
                "API_TOKEN=ABCDEFGHIJKLMNOPQRSTUVWX12345678",
            ],
        ),
        encoding="utf-8",
    )
    right.write_text(
        "\n".join(
            [
                "DATABASE_URL=postgresql://localhost/dev",
                "DEBUG=true",
                "ALLOWED_HOSTS=localhost,api",
                "API_TOKEN=ABCDEFGHIJKLMNOPQRSTUVWX12345678",
            ],
        ),
        encoding="utf-8",
    )
    diff = spec.diff(EnvSnapshot.from_env_file(left), EnvSnapshot.from_env_file(right))
    assert not diff.is_clean()
    kinds = {entry.kind for entry in diff.entries}
    assert DiffKind.CHANGED in kinds


def test_diff_orders_extra_variables_case_insensitive() -> None:
    spec = EnvSpec.from_dict({"version": 1, "variables": []})
    left_snapshot = EnvSnapshot.from_text(
        "\n".join(
            [
                "beta=1",
                "Alpha=1",
            ]
        ),
        source="left",
    )
    right_snapshot = EnvSnapshot.from_text(
        "\n".join(
            [
                "Gamma=1",
                "alpha=1",
            ]
        ),
        source="right",
    )
    diff = spec.diff(left_snapshot, right_snapshot)
    missing = [entry.variable for entry in diff.entries_by_kind(DiffKind.MISSING)]
    extra = [entry.variable for entry in diff.entries_by_kind(DiffKind.EXTRA)]
    assert missing == ["Alpha", "beta"]
    assert extra == ["alpha", "Gamma"]


def test_validate_allows_extra_when_requested(tmp_path: Path) -> None:
    spec = EnvSpec.from_file(EXAMPLE_SPEC)
    env_file = tmp_path / "extra.env"
    env_file.write_text(
        "\n".join(
            [
                "DATABASE_URL=postgresql://localhost/dev",
                "DEBUG=false",
                "ALLOWED_HOSTS=localhost",
                "API_TOKEN=ABCDEFGHIJKLMNOPQRSTUVWX12345678",
                "EXTRA_VAR=value",
            ],
        ),
        encoding="utf-8",
    )
    snapshot = EnvSnapshot.from_env_file(env_file)
    report = spec.validate(snapshot, allow_extra=True)
    assert report.is_success
    report = spec.validate(snapshot, allow_extra=False)
    assert report.warning_count == 1
    assert report.issues[0].code == "extra"


def test_validate_surfaces_duplicate_keys(tmp_path: Path) -> None:
    spec = EnvSpec.from_file(EXAMPLE_SPEC)
    env_file = tmp_path / "duplicates.env"
    env_file.write_text(
        "\n".join(
            [
                "DATABASE_URL=postgresql://localhost/dev",
                "DATABASE_URL=postgresql://localhost/prod",
                "DEBUG=false",
                "API_TOKEN=ABCDEFGHIJKLMNOPQRSTUVWX12345678",
            ],
        ),
        encoding="utf-8",
    )
    snapshot = EnvSnapshot.from_env_file(env_file)
    report = spec.validate(snapshot)
    assert report.warning_count == 1
    warning = report.issues[0]
    assert warning.code == "duplicate"
    assert warning.variable == "DATABASE_URL"


def test_validate_reports_invalid_lines(tmp_path: Path) -> None:
    spec = EnvSpec.from_file(EXAMPLE_SPEC)
    env_file = tmp_path / "invalid.env"
    env_file.write_text(
        "\n".join(
            [
                "BROKEN",
                "DATABASE_URL=postgresql://localhost/dev",
                "DEBUG=false",
                "API_TOKEN=ABCDEFGHIJKLMNOPQRSTUVWX12345678",
            ],
        ),
        encoding="utf-8",
    )
    snapshot = EnvSnapshot.from_env_file(env_file)
    report = spec.validate(snapshot)
    assert report.warning_count == 1
    warning = report.issues[0]
    assert warning.code == "invalid_line"
    assert warning.variable.startswith("line")


def test_spec_rejects_duplicate_variables() -> None:
    data = {
        "version": 1,
        "variables": [
            {"name": "FOO"},
            {"name": "FOO"},
        ],
    }
    with pytest.raises(ValueError, match="duplicate variable declared: FOO"):
        EnvSpec.from_dict(data)


def test_spec_rejects_duplicate_profiles() -> None:
    data = {
        "version": 1,
        "variables": [{"name": "FOO"}],
        "profiles": [
            {"name": "same", "env_file": "a.env"},
            {"name": "same", "env_file": "b.env"},
        ],
    }
    with pytest.raises(ValueError, match="duplicate profile declared: same"):
        EnvSpec.from_dict(data)


def test_spec_maps_are_read_only() -> None:
    spec = EnvSpec.from_file(EXAMPLE_SPEC)
    variables = spec.variable_map()
    profiles = spec.profiles_by_name()
    assert "DATABASE_URL" in variables
    assert "development" in profiles
    with pytest.raises(TypeError):
        variables["NEW"] = spec.variables[0]
    with pytest.raises(TypeError):
        profiles["staging"] = spec.profiles[0]
