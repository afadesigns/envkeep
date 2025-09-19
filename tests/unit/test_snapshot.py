from __future__ import annotations

import textwrap
from pathlib import Path

from envkeep.snapshot import EnvSnapshot


def test_env_snapshot_parses_comments(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        textwrap.dedent(
            """
            # comment line
            API_URL=https://example.com # trailing comment
            QUOTED="value with spaces"
            MULTI=foo\\nbar
            """
        ),
        encoding="utf-8",
    )
    snapshot = EnvSnapshot.from_env_file(env_file)
    assert snapshot.get("API_URL") == "https://example.com"
    assert snapshot.get("QUOTED") == "value with spaces"
    assert snapshot.get("MULTI") == "foo\nbar"
    assert snapshot.duplicate_keys() == ()


def test_env_snapshot_supports_export_and_preserves_escapes(tmp_path: Path) -> None:
    env_file = tmp_path / "export.env"
    env_file.write_text(
        textwrap.dedent(
            """
            export SECRET="line\\nnext"
            export SECRET="override"
            PLAIN=value
            MALFORMED
            """
        ),
        encoding="utf-8",
    )
    snapshot = EnvSnapshot.from_env_file(env_file)
    assert snapshot.get("SECRET") == "override"
    assert snapshot.get("PLAIN") == "value"
    assert snapshot.duplicate_keys() == ("SECRET",)
    assert snapshot.malformed_lines() == ((5, "MALFORMED"),)


def test_env_snapshot_duplicate_keys_preserve_order(tmp_path: Path) -> None:
    env_file = tmp_path / "duplicates.env"
    env_file.write_text(
        textwrap.dedent(
            """
            FIRST=1
            SECOND=2
            FIRST=3
            SECOND=4
            THIRD=5
            """
        ),
        encoding="utf-8",
    )
    snapshot = EnvSnapshot.from_env_file(env_file)
    assert snapshot.duplicate_keys() == ("FIRST", "SECOND")
