# Envkeep Roadmap

## Completed

-   **Remote Secret Backends:** Envkeep supports fetching secrets from AWS Secrets Manager, HashiCorp Vault, and Google Cloud Secret Manager.
-   **Hierarchical Specs:** Specs can be split across multiple files using the `imports` key.
-   **GitHub Action:** A GitHub Action is available to validate profiles in pull requests.

## Planned

-   **Q1 2026:**
    -   Provide native integrations with GitLab CI via custom actions.
    -   Ship VS Code extension for inline spec validation while editing `.env` files.
    -   Publish enterprise add-ons (RBAC, audit reports).
-   **Policy-as-code enforcement:** Introduce policy-as-code enforcement for CI annotations.

## Ideas

-   **Additional Backends:** Support for other secret managers like Azure Key Vault.
-   **More Output Formats:** Add support for more output formats for the `diff` and `doctor` commands (e.g., `json`, `yaml`, `html`).
-   **Autofix:** Add a command to automatically fix common issues, like missing variables or incorrect types.
-   **Interactive Mode:** Add an interactive mode to the CLI to guide users through the process of creating a spec or fixing a profile.
-   **Pre-commit Hook:** Add a pre-commit hook to automatically run `envkeep doctor` before committing changes.