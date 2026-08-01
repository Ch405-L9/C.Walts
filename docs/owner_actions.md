# Owner Actions

## Before Claude begins

You only need to:

1. Ensure the project repository is backed up and GitHub access works.
2. Ensure Ollama and the current C.Walts MCP server remain operational.
3. Keep the Anthropic API key local and untracked.
4. Confirm at least 20 GiB of free disk space.

You do not manually download, unzip, label, chunk, or embed these datasets.

## After Claude finishes Gate 0

Return to ChatGPT:

- `docs/dataset-acquisition-report-gate0.md`;
- `docs/evidence/dataset-inventory-gate0.json`;
- Claude's final terminal report;
- branch, commits, and push status;
- any failure log.

ChatGPT will then prepare the exact public-record selection rules and the custom-query authoring phase.

## Later owner role

The owner will perform private blind acceptance tests only after:

- the public and custom sets are built;
- the calibration set has been used;
- task-specific thresholds are frozen;
- the holdout is sealed;
- all automated tests pass.
