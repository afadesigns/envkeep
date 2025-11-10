from __future__ import annotations

import json
import shutil
from pathlib import Path
import textwrap
import time

import pytest
from typer.testing import CliRunner

from envkeep.cli import app

runner = CliRunner()


def test_doctor_cache_hit_and_miss(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    cache_dir = tmp_path / ".envkeep_cache"

    # 1. Set up spec and env file
    spec_file = tmp_path / "envkeep.toml"
    env_file = tmp_path / ".env"
    spec_text = textwrap.dedent(
        f"""
        version = 1
        [[variables]]
        name = "MY_VAR"
        type = "string"

        [[profiles]]
        name = "test"
        env_file = "{env_file.name}"
        """
    )
    spec_file.write_text(spec_text, encoding="utf-8")
    env_file.write_text("MY_VAR=value1", encoding="utf-8")

    # 2. First run: should be a cache miss and create the cache
    result1 = runner.invoke(app, ["doctor"])
    assert result1.exit_code == 0
    assert "All checks passed" in result1.stdout
    assert cache_dir.exists()
    assert len(list(cache_dir.iterdir())) == 2  # spec.hash and one profile cache

    # 3. Second run: should be a cache hit (no output from validation)
    # To prove it's a hit, we can't just check the output.
    # Instead, we'll rely on a crude but effective method for a unit test:
    # check the modification time of the cache file.
    spec_hash_mtime = (cache_dir / "spec.hash").stat().st_mtime
    time.sleep(0.01) # Ensure clock tick
    result2 = runner.invoke(app, ["doctor"])
    assert result2.exit_code == 0
    assert (cache_dir / "spec.hash").stat().st_mtime == spec_hash_mtime

    # 4. Third run: change the env file, should be a cache miss
    env_file.write_text("MY_VAR=value2", encoding="utf-8")
    result3 = runner.invoke(app, ["doctor"])
    assert result3.exit_code == 0
    # The spec hash mtime should be the same, but the profile cache is new/updated
    assert (cache_dir / "spec.hash").stat().st_mtime > spec_hash_mtime

    # 5. Fourth run: change the spec file, should invalidate everything
    spec_file.write_text(spec_text + "\n#comment", encoding="utf-8")
    result4 = runner.invoke(app, ["doctor"])
    assert result4.exit_code == 0
    assert (cache_dir / "spec.hash").stat().st_mtime > spec_hash_mtime

    # 6. Fifth run: use --no-cache flag, should not use or create cache
    shutil.rmtree(cache_dir)
    result5 = runner.invoke(app, ["doctor", "--no-cache"])
    assert result5.exit_code == 0
    assert not cache_dir.exists()
