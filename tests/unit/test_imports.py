from __future__ import annotations

import textwrap
from pathlib import Path

from envkeep.cli import load_spec


def test_spec_imports_merge_variables_and_profiles(tmp_path: Path) -> None:
    base_dir = tmp_path

    # Create the imported spec file
    imported_spec_file = base_dir / "imports.toml"
    imported_spec_text = textwrap.dedent(
        """
        version = 1
        [[variables]]
        name = "IMPORTED_VAR"
        type = "string"

        [[profiles]]
        name = "imported_profile"
        env_file = ".env.imported"
        """
    )
    imported_spec_file.write_text(imported_spec_text, encoding="utf-8")

    # Create the main spec file that imports the other one
    main_spec_file = base_dir / "envkeep.toml"
    main_spec_text = textwrap.dedent(
        """
        version = 1
        imports = ["imports.toml"]

        [[variables]]
        name = "MAIN_VAR"
        type = "string"

        [[profiles]]
        name = "main_profile"
        env_file = ".env.main"
        """
    )
    main_spec_file.write_text(main_spec_text, encoding="utf-8")

    # Load the main spec
    spec = load_spec(main_spec_file)

    # Check that variables from both specs are present
    variable_names = {var.name for var in spec.variables}
    assert "MAIN_VAR" in variable_names
    assert "IMPORTED_VAR" in variable_names

    # Check that profiles from both specs are present
    profile_names = {prof.name for prof in spec.profiles}
    assert "main_profile" in profile_names
    assert "imported_profile" in profile_names


def test_spec_imports_main_overrides_imported(tmp_path: Path) -> None:
    base_dir = tmp_path

    # Create the imported spec file
    imported_spec_file = base_dir / "imports.toml"
    imported_spec_text = textwrap.dedent(
        """
        version = 1
        [[variables]]
        name = "VAR"
        type = "string"
        description = "Imported description"

        [[profiles]]
        name = "profile"
        env_file = ".env.imported"
        """
    )
    imported_spec_file.write_text(imported_spec_text, encoding="utf-8")

    # Create the main spec file that imports the other one
    main_spec_file = base_dir / "envkeep.toml"
    main_spec_text = textwrap.dedent(
        """
        version = 1
        imports = ["imports.toml"]

        [[variables]]
        name = "VAR"
        type = "string"
        description = "Main description"

        [[profiles]]
        name = "profile"
        env_file = ".env.main"
        """
    )
    main_spec_file.write_text(main_spec_text, encoding="utf-8")

    # Load the main spec
    spec = load_spec(main_spec_file)

    # Check that the main spec's variable definition overrides the imported one
    assert len(spec.variables) == 1
    assert spec.variables[0].description == "Main description"

    # Check that the main spec's profile definition overrides the imported one
    assert len(spec.profiles) == 1
    assert spec.profiles[0].env_file == ".env.main"
