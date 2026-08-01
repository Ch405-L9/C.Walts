# CLAUDE CODE PROMPT F
## C.Walts v0.4 Gate 0 — Controlled Dataset Acquisition and Inventory

Read `README_START_HERE_C.Walts_v0.4_Gate0.md` first.

This is a bounded acquisition and inspection phase. Execute without deviation except for verified harm, licensing conflict, secret exposure, production-data risk, regression, or technical incompatibility. Stop only the affected operation, preserve safe completed work, document evidence, and continue independent safe work.

---

# 1. Immutable baseline

`v0.3.0-rc.2` is immutable.

Before any change:

```bash
cd /home/t0n34781/projects/natural-language-flow-rag
git status --porcelain
git remote -v
git branch --show-current
git rev-parse v0.3.0-rc.2
git show --no-patch --decorate v0.3.0-rc.2
```

Re-run and record:

```bash
.venv/bin/python scripts/corpus_lint.py
.venv/bin/python eval/run_evaluation.py
.venv/bin/python -m pytest tests/ -q
.venv/bin/python scripts/smoke_test.py
.venv/bin/python scripts/mcp_session_check.py
sha256sum -c docs/evidence/source-snapshots/SHA256SUMS
```

Record:

- RC2 tag SHA;
- branch SHA;
- collection count;
- BM25 count;
- embedding model and dimension;
- BADGR Harness production-store checksum;
- all test totals;
- free disk space.

Do not continue if the baseline fails or the working tree contains unexplained owner changes.

---

# 2. Branch and version

Create:

```text
branch: feat/narration-generalization-v0.4
version: 0.4.0-dev.1
```

Do not modify or retag RC2.

Update the version consistently in project metadata and changelog.

Checkpoint:

```text
chore: establish v0.4 dataset acquisition baseline
```

Run tests, secret scan, commit, and push.

---

# 3. Approved datasets only

Only these sources are authorized:

```yaml
clinc150:
  version: UCI dataset 570, data_full
  purpose:
    - near-domain unsupported candidates
    - explicit OOS candidates

massive:
  version: "1.0"
  locale: en-US
  purpose:
    - near-domain unsupported candidates
    - far out-of-domain candidates

banking77:
  version: PolyAI master snapshot acquired at execution time
  purpose:
    - far out-of-domain candidates
```

Do not acquire:

- LibriSpeech;
- LibriTTS;
- LibriTTS-R;
- Project Gutenberg;
- HWU64;
- SNIPS;
- SLURP;
- ATIS;
- BEIR datasets;
- Quora;
- Stack Exchange;
- NarrativeQA;
- ROCStories;
- WritingPrompts;
- LitBank;
- any unapproved source.

---

# 4. Storage and no-ingestion boundary

Raw downloads and extracted source files must remain under:

```text
var/eval_sources/
```

They must be Git-ignored.

Tracked outputs may include only:

- scripts;
- tests;
- source metadata;
- acquisition report;
- license conclusions;
- schemas;
- aggregate inventory with no bulk copied dataset text.

Do not write any acquired or derived evaluation record into:

```text
var/chroma/
var/bm25/
badgr_natural_flow_v1
```

Do not call the ingestion or reindex tools.

Take and record Chroma and BM25 counts before and after. They must be identical.

---

# 5. Disk and network gates

Before downloading:

```bash
df -BG /home/t0n34781/projects/natural-language-flow-rag
```

Honor the existing `writes.minimum_free_disk_gb` value. If free space is below 20 GiB:

- do not download;
- report the exact available space;
- continue static validation and dry-run work;
- stop before acquisition.

Run:

```bash
.venv/bin/python scripts/acquire_eval_sources.py --dry-run
```

Review the exact URLs, destination paths, archive members, and size caps.

Only then run:

```bash
.venv/bin/python scripts/acquire_eval_sources.py --execute
```

The tool must:

- permit HTTPS only;
- follow redirects safely;
- cap download size;
- download to a temporary file;
- calculate SHA-256 while streaming;
- use atomic rename;
- refuse archive path traversal;
- extract only allowlisted members;
- verify embedded license markers;
- record archive and extracted-file hashes;
- never overwrite silently;
- support repeatable reruns;
- emit `var/eval_sources/manifests/acquisition-manifest.json`.

Do not substitute Hugging Face mirrors or third-party copies.

---

# 6. Inventory

Run:

```bash
.venv/bin/python scripts/inventory_eval_sources.py
```

Expected source facts:

## CLINC150

Inventory:

- in-domain intent labels;
- split counts;
- OOS counts;
- duplicate counts;
- query-length statistics;
- candidate intent labels that may be near-domain;
- no selections yet.

## MASSIVE

Use only:

```text
1.0/data/en-US.jsonl
```

Inventory:

- scenario counts;
- intent counts;
- partition counts;
- duplicate counts;
- query-length statistics;
- candidate scenarios for near-domain and far-domain use;
- no selections yet.

Do not describe MASSIVE as a multi-intent dataset. It contains single-shot assistant interactions labeled by scenario and intent.

## Banking77

Inventory:

- 77 category names;
- train and test counts;
- duplicates;
- query-length statistics;
- no selections yet.

Write:

```text
docs/evidence/dataset-inventory-gate0.json
docs/dataset-acquisition-report-gate0.md
```

Do not include bulk dataset rows in the Markdown report.

---

# 7. Atomic-record rule

Do not chunk the datasets.

The later evaluation format is one atomic query per JSONL record.

The future schema is defined in:

```text
schemas/eval_query.schema.json
```

No selected query file is created in this phase.

---

# 8. Adversarial validation

Run or add tests proving:

- a ZIP path such as `../../escape` is rejected;
- a TAR path such as `/absolute/path` is rejected;
- a symlink member is rejected;
- an archive exceeding the cap is rejected;
- a missing embedded license is rejected;
- a wrong license marker is rejected;
- HTTP URLs are rejected;
- unapproved archive members are not extracted;
- interrupted downloads do not replace a verified existing file;
- rerun is idempotent;
- raw files remain ignored by Git;
- no secret is written to logs;
- Chroma count is unchanged;
- BM25 count is unchanged;
- BADGR Harness checksum is unchanged.

Do not weaken an existing test to make the phase pass.

---

# 9. Checkpoints

At every logical checkpoint:

1. run relevant unit tests;
2. run Ruff;
3. run `git diff --check`;
4. scan staged content for secrets and raw dataset rows;
5. verify raw archives are not staged;
6. verify Chroma and BM25 counts;
7. update `docs/execution-log.md`;
8. update `CHANGELOG.md`;
9. commit;
10. push.

Required commits:

```text
chore: establish v0.4 dataset acquisition baseline
feat: add controlled evaluation-source acquisition
test: add adversarial dataset archive validation
docs: record Gate 0 dataset inventory
```

Do not squash away failure history in the execution log.

---

# 10. Full validation before handoff

Run:

```bash
.venv/bin/python -m pytest tests/ -q
ruff check .
.venv/bin/python scripts/corpus_lint.py
.venv/bin/python eval/run_evaluation.py
.venv/bin/python scripts/smoke_test.py
.venv/bin/python scripts/mcp_session_check.py
.venv/bin/python scripts/acquire_eval_sources.py --verify
.venv/bin/python scripts/inventory_eval_sources.py --verify
```

Confirm:

- RC2 behavior has not regressed;
- production collection is unchanged;
- lexical index is unchanged;
- MCP still connects;
- acquisition manifest verifies;
- source inventory verifies;
- no raw dataset is tracked.

---

# 11. Stop condition and final report

Stop after Gate 0.

Do not:

- select the final 315 public queries;
- author the 285 custom queries;
- build calibration or holdout files;
- fit thresholds;
- modify MCP evidence status;
- acquire audiobook data;
- promote `main`;
- tag a release candidate.

Return:

- branch;
- version;
- commit SHAs;
- push status;
- dataset archive SHA-256 values;
- extracted-file SHA-256 values;
- embedded license verification;
- inventory totals;
- duplicate counts;
- candidate domain/intent lists;
- disk use;
- all test results;
- Chroma/BM25 before-and-after counts;
- BADGR Harness checksum before and after;
- every failure and correction;
- unresolved issues;
- exact paths to evidence.

The next phase will be designed only after this report is independently reviewed.
