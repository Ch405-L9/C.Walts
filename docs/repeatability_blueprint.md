# Repeatability Blueprint

The purpose of this phase is to establish a reusable pattern for future MCP, RAG, and local-model projects.

## Standard lifecycle

```text
Research
→ source approval
→ immutable baseline
→ versioned branch
→ dry-run
→ controlled acquisition
→ checksum and license verification
→ aggregate inventory
→ adversarial review
→ tests
→ commit and push
→ independent review
→ selection and transformation
→ calibration
→ locked holdout
→ smoke testing
→ owner acceptance
→ release
```

## Deterministic work versus model work

Use deterministic scripts for:

- downloads;
- checksums;
- safe archive extraction;
- license-marker verification;
- record counts;
- duplicate detection;
- schema validation;
- group leakage checks;
- train/calibration/holdout allocation;
- metric calculation;
- release gates.

Use AI models for:

- research synthesis;
- classification proposals;
- narration-domain design;
- candidate query authoring;
- adversarial case generation;
- failure analysis.

AI-generated work is not promoted automatically. It requires deterministic validation and owner or reviewer approval.

## Failure record

Every failed check must record:

- exact command;
- exact failure;
- affected files;
- root cause;
- correction;
- tests added;
- commit SHA;
- whether the failure changed the design.

Do not delete evidence merely because the final run passes.

## Evaluation-data rule

Evaluation queries are test inputs, not knowledge.

They stay outside production retrieval. A holdout that influences development is retired into regression history and replaced.
