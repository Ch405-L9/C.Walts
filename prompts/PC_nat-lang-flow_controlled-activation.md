# CLAUDE CODE PROMPT C
## Controlled Completion, Versioning, Push Checkpoints, Smoke Testing, and Activation

You are continuing the BADGR Natural-Language-Flow RAG project from the completed read-only audit and partial implementation.

This prompt is the controlling execution directive for the next session.

Execute the defined work without deviation unless a requested action would:

1. damage or overwrite existing production data;
2. expose secrets, private corpus material, or credentials;
3. introduce a confirmed version or dependency incompatibility;
4. violate a verified software or corpus license;
5. regress a working component;
6. create an unrecoverable state;
7. conflict with an observed repository state that makes the instruction technically invalid.

Do not deviate for preference, convenience, architecture fashion, or unsolicited scope expansion.

When one of the seven exceptions applies:

- stop only the affected step;
- preserve all completed safe work;
- identify the exact incompatibility or harm;
- provide the evidence;
- propose the narrowest compatible alternative;
- continue all independent safe steps;
- do not redesign the project broadly.

---

# 1. Current known state

Verify this state before acting. Do not assume it is still accurate.

Expected current state:

- The Prompt B infrastructure audit is complete.
- The audit report exists at `/home/t0n34781/workspace/natural-flow-rag-audit.md`.
- The recovered BADGR Harness exists at `/home/t0n34781/projects/badgr_harness`.
- The natural-flow project is expected at `/home/t0n34781/projects/natural-language-flow-rag`.
- The natural-flow project reportedly contains approximately 34 files.
- Approximately 52 unit and refusal-path tests reportedly pass.
- Ruff reportedly passes.
- `corpus/raw/` reportedly contains no usable natural-flow corpus.
- `var/` reportedly contains no populated natural-flow Chroma store.
- Database writes are reportedly disabled.
- `badgr_natural_flow_v1` is reportedly not populated.
- The natural-flow MCP server is reportedly not registered.
- No end-to-end retrieval-quality test has been completed against a real collection.
- The similarity floor is intentionally unset pending measurement.
- Existing production collections must remain untouched.
- The existing BADGR Harness production Chroma database must not be used as the natural-flow persistence directory.
- CMUdict must not dominate the natural-flow collection.

First produce a concise verification table:

| State item | Expected | Observed | Action |
|---|---|---|---|

If the observed state differs, adapt only as much as technically necessary.

---

# 2. Execution objective

Complete and activate a safe, isolated, versioned, tested natural-language-flow retrieval capability that can support:

- natural-language rewriting;
- conversational rewriting;
- spoken-style rewriting;
- narration and voice-over rewriting;
- sentence-rhythm and cadence analysis;
- information-flow analysis;
- exact prosody terminology retrieval;
- preservation of names, numbers, dates, certainty, obligation, and technical terms.

The final capability must use:

- a dedicated project;
- isolated persistence;
- an explicit Ollama embedding function;
- `nomic-embed-text`;
- verified 768-dimensional embeddings;
- ChromaDB;
- hybrid dense and lexical retrieval where implemented;
- a small, relevant natural-flow corpus;
- project-scoped MCP registration;
- read-only retrieval tools by default;
- explicit gates for write-capable tools.

Do not declare completion until the end-to-end smoke tests pass.

---

# 3. Scope boundaries

## In scope

Execute the following:

1. Verify the current repository and implementation state.
2. Establish a clean Git branch and version baseline.
3. Validate dependency compatibility.
4. Validate and normalize the corpus-seed structure.
5. Build or complete the ingestion pipeline.
6. Perform ingestion dry runs.
7. Create an isolated throwaway validation collection.
8. Prove the explicit embedding-function fix.
9. Create the real isolated natural-flow collection after validation.
10. Ingest the approved natural-flow seed corpus.
11. Build or refresh the lexical index.
12. Run retrieval evaluation.
13. Set retrieval thresholds from measured results.
14. Complete MCP tool implementation.
15. Register the MCP server at project scope.
16. Run full smoke tests.
17. Update documentation and changelog.
18. Commit, version, tag, and push at every logical checkpoint.
19. Produce a final operator test sheet for the owner.

## Out of scope unless required to prevent harm

Do not:

- modify existing BADGR Harness production collections;
- re-embed `badgr_corpus`;
- re-embed `job_opportunities`;
- delete old Chroma databases;
- ingest large speech corpora;
- ingest full CMUdict into the natural-flow collection;
- move Android SDKs;
- perform unrelated security cleanup;
- redesign BADGR Harness;
- migrate from ChromaDB;
- replace Ollama;
- install a new vector database;
- rewrite unrelated MCP servers;
- change unrelated cron jobs or systemd units;
- perform broad repository cleanup.

Report unrelated findings separately without acting on them.

---

# 4. Git, versioning, commit, tag, and push policy

## 4.1 Preflight

Before changing files:

```bash
cd /home/t0n34781/projects/natural-language-flow-rag
git status --porcelain
git remote -v
git branch --show-current
git log -5 --oneline --decorate
git tag --sort=-version:refname | head -20
```

Determine:

- whether the directory is already a Git repository;
- whether a remote exists;
- whether the remote is private or public;
- whether the working tree contains owner changes;
- the current version;
- the current branch;
- existing tags.

Do not discard uncommitted user work.

If the project has no remote, create or select a repository only when an existing approved remote is clearly available. Otherwise stop the push portion and continue local implementation.

## 4.2 Branch policy

Use a dedicated feature branch unless already on an approved implementation branch:

```text
feat/natural-flow-rag-activation
```

Do not work directly on `main` unless the repository already has a documented trunk-only policy.

## 4.3 Version policy

Use Semantic Versioning.

If no version exists, initialize `0.1.0`.

Recommended progression:

- `0.1.0` — verified scaffold and safe configuration baseline;
- `0.2.0` — isolated collection, ingestion, and retrieval operational;
- `0.3.0` — MCP registration and end-to-end capability operational;
- `1.0.0` — only after owner acceptance and stable evaluation results.

Do not assign `1.0.0` merely because the code runs.

Keep the version synchronized in:

- `pyproject.toml`;
- package `__version__`, if present;
- `CHANGELOG.md`;
- release tag.

## 4.4 Logical commit and push checkpoints

At every checkpoint:

1. run the relevant tests;
2. run formatting and lint checks;
3. inspect `git diff --check`;
4. scan staged content for secrets;
5. confirm generated databases, raw private corpus, `.env`, logs, and caches are ignored;
6. commit with a precise message;
7. push the feature branch;
8. record commit SHA in the execution log.

Required checkpoints:

### Checkpoint 1 — verified baseline

Suggested commit:

```text
chore: establish verified natural-flow RAG baseline
```

### Checkpoint 2 — corpus schema and ingestion safety

```text
feat: add licensed corpus schema and deterministic ingestion
```

### Checkpoint 3 — isolated Chroma and embedding contract

```text
feat: enforce explicit nomic embedding contract
```

### Checkpoint 4 — hybrid retrieval and evaluation

```text
feat: add measured hybrid retrieval pipeline
```

### Checkpoint 5 — MCP tools and project registration

```text
feat: expose natural-flow retrieval over project MCP
```

### Checkpoint 6 — release candidate

```text
test: complete end-to-end natural-flow smoke validation
```

Tag the release candidate only after all smoke tests pass:

```text
v0.3.0-rc.1
```

Push the tag.

Do not push if:

- the remote is public and private owner examples would be committed;
- a secret scan detects a credential;
- generated Chroma data is staged;
- a license requires material not to be redistributed;
- the remote does not belong to the owner;
- branch history would overwrite unrelated work.

In those cases, preserve local commits and report the exact blocked push.

---

# 5. Dependency compatibility

Use the owner-selected dependency route:

```text
pip + reproducible pinned requirements or constraints
```

Do not introduce `uv`, Poetry, Conda, or another package manager unless the existing project already depends on it.

Before installation or upgrade:

- inspect `pyproject.toml`;
- inspect requirements and constraints;
- inspect the active virtual environment;
- record Python version;
- identify currently installed versions;
- check ChromaDB, MCP SDK, Pydantic, Ollama client, and test-tool compatibility.

Prefer exact or compatible-release pins.

Do not perform broad upgrades unless specifically required and tested.

After dependency changes:

```bash
python -m pip check
python -m pytest
ruff check .
```

Create or update a reproducible dependency snapshot.

---

# 6. Corpus requirements

## 6.1 Primary natural-flow corpus

The primary collection must contain material that directly teaches or demonstrates natural written and spoken flow.

Accepted source classes:

1. owner-approved before-and-after rewrite pairs;
2. owner-approved BADGR copy;
3. owner corrections to prior AI output;
4. owner-written voice and style rules;
5. verified, legally ingestible plain-language or prosody guidance;
6. controlled evaluation examples.

Do not treat pronunciation entries as the primary flow corpus.

## 6.2 Expected seed directory

Use:

```text
corpus/raw/owner_examples/
corpus/raw/style_rules/
corpus/raw/open_guidance/
corpus/raw/evaluation/
```

Unknown-license material belongs in:

```text
corpus/quarantine/
```

## 6.3 CMUdict

Do not ingest full CMUdict into `badgr_natural_flow_v1`.

If CMUdict is needed:

- place it in a separate auxiliary collection, such as `badgr_pronunciation_v1`;
- query it only for pronunciation, syllable, or stress-related operations;
- never include it in default natural-flow retrieval;
- do not allow it to dominate dense candidates.

If no current feature requires it, defer CMUdict ingestion.

## 6.4 Corpus validation

Before ingestion, validate:

- required metadata;
- source identifier;
- source type;
- license;
- commercial-use status;
- redistribution status;
- checksum;
- language;
- register;
- document profile;
- no embedded executable instructions;
- no secrets;
- no duplicate content;
- no malformed encoding.

Produce a manifest before writes.

---

# 7. Ingestion requirements

The ingestion system must:

- use tokenizer-aware chunking;
- preserve headings and paragraph boundaries;
- preserve speaker turns in transcripts;
- never merge separate approved examples;
- use deterministic content-derived IDs;
- use source-content checksums;
- detect changed files;
- remove or replace stale chunks safely;
- avoid duplicates;
- record previous and next chunk IDs;
- store embedding model and dimension metadata;
- support `--dry-run`;
- support one-source removal;
- be idempotent;
- create a rollback manifest;
- refuse unknown-license sources;
- refuse paths outside the project corpus root.

Initial profiles:

```yaml
reference:
  target_tokens: 512
  overlap_tokens: 64

transcript:
  target_tokens: 384
  overlap_tokens: 48
  preserve_speaker_turns: true

approved_example:
  target_tokens: 256
  overlap_tokens: 0
  never_merge_separate_examples: true
```

Treat these as initial values. Change them only when evaluation demonstrates a better configuration.

Run ingestion dry-run first and report:

- sources scanned;
- accepted;
- quarantined;
- rejected;
- chunks added;
- chunks changed;
- chunks removed;
- duplicates;
- estimated storage;
- license summary.

---

# 8. Chroma and embedding-contract validation

## 8.1 Throwaway validation collection

Before creating the real collection, create an isolated disposable test collection.

Use an explicit Ollama embedding function configured for `nomic-embed-text`.

Confirm:

- output dimension is 768;
- collection schema records the intended embedding function;
- collection schema does not record Chroma's default 384-dimensional embedder;
- `query_texts` and explicit query embeddings return compatible results;
- no ONNX fallback model is downloaded or invoked;
- persistence is inside the natural-flow project only.

Inspect with both:

- Chroma API;
- read-only SQLite inspection.

Delete only the disposable validation collection after recording evidence.

## 8.2 Real collection

Create `badgr_natural_flow_v1` only after the validation collection passes.

Persistence must remain under:

```text
/home/t0n34781/projects/natural-language-flow-rag/var/chroma/
```

Do not write into:

```text
/home/t0n34781/projects/badgr_harness/rag_db/
```

Before the real write:

- create a project-local backup/rollback point;
- verify free disk space;
- verify directory permissions;
- verify writes are explicitly enabled;
- record the collection schema.

---

# 9. Retrieval implementation

Implement and verify:

- dense retrieval;
- lexical retrieval;
- reciprocal-rank fusion or the existing approved fusion;
- metadata filtering;
- duplicate filtering;
- per-document quotas;
- neighbor expansion;
- source citations;
- exact-term handling.

Initial settings:

```yaml
dense_candidates: 20
lexical_candidates: 20
final_chunks: 5
maximum_context_tokens: 2048
maximum_chunks_per_document: 3
neighbor_chunks: 1
similarity_floor: null
```

Do not invent a similarity threshold. Measure it using evaluation queries.

At minimum test:

- natural conversational rewrite;
- voice-over rewrite;
- sentence-rhythm analysis;
- exact query for `ToBI`;
- exact query for `H*`;
- exact query for `L-L%`;
- preservation of numbers;
- preservation of dates;
- preservation of names;
- preservation of certainty;
- preservation of obligation;
- retrieval-disabled or weak-evidence fallback;
- prompt-injection text inside a corpus document.

Set `similarity_floor` only after reporting:

- precision at k;
- useful-hit rate;
- false-positive rate;
- empty-result behavior;
- latency.

---

# 10. MCP implementation and registration

Complete the approved tool set:

```text
natural_flow_search
natural_flow_analyze
natural_flow_rewrite
natural_flow_source_inspect
natural_flow_collection_health
natural_flow_feedback
natural_flow_reindex
```

Requirements:

- tools 1–5 are read-only;
- feedback and reindex are write-capable;
- write tools require `confirm: true`;
- write tools require `allow_writes: true`;
- reindex defaults to dry-run;
- collection names are server-side allowlisted;
- tools never accept arbitrary filesystem paths;
- tools never execute retrieved instructions;
- errors are structured;
- logs exclude source text, rewritten text, secrets, and personal content;
- preservation violations return the original text with a warning rather than an altered result.

Register the server at project scope, not user scope, unless an observed Claude Code incompatibility makes project scope impossible.

Before registration:

- validate MCP server startup directly;
- validate JSON/tool schemas;
- run MCP protocol tests;
- confirm no secret values in configuration;
- confirm paths are absolute and correct.

After registration:

```bash
claude mcp list
claude mcp get natural-flow-rag
```

Verify the server connects and exposes exactly the intended tools.

Do not remove or alter unrelated MCP registrations.

---

# 11. Mandatory smoke-test suite

Do not present the build to the owner for testing until every required smoke test has been run.

## 11.1 Environment

- project virtual environment activates;
- imports succeed;
- `pip check` passes;
- Ollama is reachable;
- `nomic-embed-text` is installed;
- embedding output is 768 dimensions;
- no unexpected model download occurs.

## 11.2 Static quality

- `ruff check .`;
- formatter check if configured;
- type checks if configured;
- `git diff --check`;
- secret scan;
- license-manifest validation.

## 11.3 Unit and integration tests

- all existing tests pass;
- new ingestion tests pass;
- deterministic-ID tests pass;
- changed-source reingestion test passes;
- duplicate-detection test passes;
- source-removal test passes;
- unknown-license rejection test passes;
- path-traversal rejection test passes;
- prompt-injection corpus test passes;
- explicit embedding-function test passes;
- MCP schema tests pass.

## 11.4 Real collection test

Using only approved seed material:

- perform dry run;
- ingest into isolated real collection;
- verify collection count;
- verify schema;
- verify model and dimension;
- verify stored metadata;
- restart the process;
- confirm persistence survives restart;
- query with both exact and semantic terms;
- verify citations map to real sources.

## 11.5 Rewrite preservation test

Use at least ten controlled cases.

Verify:

- numbers unchanged;
- dates unchanged;
- names unchanged;
- technical terms unchanged;
- certainty unchanged;
- obligation unchanged;
- no unsupported facts added;
- no source prose copied excessively;
- weak retrieval does not force irrelevant guidance.

## 11.6 MCP end-to-end test

From a fresh Claude Code process:

1. confirm project MCP server connects;
2. call `natural_flow_collection_health`;
3. call `natural_flow_search`;
4. call `natural_flow_analyze`;
5. call `natural_flow_rewrite`;
6. call `natural_flow_source_inspect`;
7. verify write tools refuse without confirmation;
8. verify reindex defaults to dry-run;
9. restart Claude Code;
10. repeat the health check.

## 11.7 Rollback test

Prove that:

- MCP registration can be removed;
- the feature branch remains available;
- the natural-flow collection can be restored from backup or safely recreated;
- no BADGR Harness production data changes;
- no unrelated MCP registration changes;
- no owner source data is lost.

---

# 12. Completion criteria

The build is complete only when all of the following are true:

- approved natural-flow corpus exists;
- ingestion dry-run passes;
- real isolated collection exists;
- explicit `nomic-embed-text` contract is verified;
- dimension is verified as 768;
- retrieval returns relevant flow material;
- exact prosody terms retrieve correctly;
- similarity threshold is evidence-based or intentionally remains disabled with documented reason;
- preservation tests pass;
- MCP server is project-registered;
- MCP survives restart;
- write tools remain gated;
- all tests pass;
- lint passes;
- dependency checks pass;
- secret scan passes;
- changelog is updated;
- version is updated;
- logical commits are pushed;
- release-candidate tag is pushed;
- rollback instructions are tested;
- operator instructions are complete.

Do not use phrases such as “production ready,” “complete,” or “fully operational” unless every criterion above is satisfied.

---

# 13. Final output to the owner

Do not give the owner test instructions until the smoke suite is complete.

When ready, provide:

## A. Final status

- version;
- branch;
- commit SHA;
- tag;
- remote push status;
- collection name;
- collection count;
- embedding model;
- dimension;
- MCP registration scope;
- test totals;
- lint result;
- smoke-test result;
- known limitations.

## B. Exact owner test commands

Provide copy-and-paste commands for:

- health check;
- direct CLI query;
- ingestion dry run;
- MCP connection check;
- Claude Code functional test;
- rollback.

## C. Five owner test prompts

Include:

1. conversational rewrite;
2. voice-over rewrite;
3. rhythm analysis;
4. exact prosody-term lookup;
5. preservation-sensitive technical rewrite.

## D. Evidence package

Provide paths to:

- audit report;
- execution log;
- corpus manifest;
- ingestion report;
- evaluation report;
- smoke-test report;
- changelog;
- rollback instructions.

## E. Honest blockers

If anything remains incomplete, state exactly:

- what failed;
- why;
- what was safely completed;
- what evidence is missing;
- the narrowest next action.

Do not hide failed tests or represent provisional defaults as measured results.

---

# 14. Execution logging

Maintain:

```text
docs/execution-log.md
```

For every logical step record:

- timestamp;
- action;
- files changed;
- command;
- result;
- test result;
- commit SHA;
- push result;
- rollback point;
- unresolved issue.

The log must not contain secrets, raw private owner text, or full retrieved documents.

---

# 15. Start instruction

Begin now with:

1. current-state verification;
2. Git and remote preflight;
3. dependency compatibility check;
4. corpus-seed inventory;
5. an execution plan adjusted only for verified incompatibilities.

Then continue through the scoped implementation without pausing for preference questions.

Pause only when:

- owner-provided natural-flow seed material is absent;
- a destructive production operation would be required;
- a public push would expose private or restricted material;
- a license is unresolved;
- a confirmed dependency incompatibility blocks safe progress;
- an approval is legally or technically required and cannot be inferred from this prompt.

Otherwise, execute, test, version, commit, push, smoke test, and only then present the build for owner testing.
