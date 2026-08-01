# CLAUDE CODE PROMPT D
## C.Walts Media-Corpus Integration and Controlled Activation Addendum

Read `README_START_HERE_C.Walts.md` first.

Then execute `PC_nat-lang-flow_controlled-activation.md` with this addendum.

Do not reinterpret this package as authorization for broad acoustic-model development. The immediate build remains a text-first natural-language-flow RAG with audio references used for contrastive evaluation.

---

# A. Fixed owner decisions

The following decisions are approved and must not be reopened as preference questions:

```yaml
project_name: C.Walts
github_owner: Ch405-L9
github_repository: C.Walts
github_visibility: private
repository_strategy: new_remote
package_manager: pip
vector_backend: chromadb
embedding_provider: ollama
embedding_model: nomic-embed-text
embedding_dimension: 768
mcp_scope: project
text_collection: badgr_natural_flow_v1
audio_binary_ingestion: prohibited_for_text_collection
negative_media_as_positive_examples: prohibited
```

Change one of these only when a verified technical incompatibility or harmful consequence requires it. In that event, stop only the affected operation, present evidence, implement the narrowest safe alternative, and continue independent work.

---

# B. Required source review

Review and inventory:

```text
references/media/positive/
references/media/source_bundle/
references/transcripts/
corpus/raw/owner_examples/
corpus/raw/style_rules/
corpus/raw/evaluation/
```

Verify hashes against `checksums.sha256`.

Classify each media file as:

- `positive_target`;
- `negative_contrast`;
- `context_only`;
- `excluded`;
- `unknown_requires_review`.

Do not infer a positive label from a filename alone. Use the owner-approved manifest as the initial classification and verify media identity by hash.

---

# C. Audio-to-text handling

For this release:

1. Do not embed MP3, M4A, MP4, PDF, or ZIP bytes into `badgr_natural_flow_v1`.
2. Ingest only approved text and metadata.
3. Keep audio files as local evaluation references.
4. Store:
   - filename;
   - SHA-256;
   - duration;
   - reference class;
   - intended register;
   - known TTS settings;
   - transcript or script provenance;
   - approval status.
5. Never mix acoustic feature vectors with `nomic-embed-text` vectors.
6. If an acoustic sidecar is created, it must use a separate store and remain disabled by default.

---

# D. Corpus composition

The initial natural-flow corpus must emphasize:

1. before/after script pairs;
2. approved delivery-ready scripts;
3. market-facing delivery rules;
4. negative-pattern descriptions;
5. evaluation cases;
6. source and license metadata.

It must not be dominated by:

- CMUdict;
- pronunciation records;
- long religious texts;
- raw technical manuals;
- screen-recording transcripts;
- negative examples.

Before ingestion, report the percentage of chunks by source class. Reject a build where any auxiliary source class exceeds 40% of the initial text collection without explicit justification.

---

# E. Market-facing performance rules

Use `market_voice_delivery_rules.md` as the initial policy.

The core rules are:

- match the voice and delivery to the content;
- write for speech, not silent reading;
- keep one main thought per breath group;
- use varied but controlled sentence length;
- place emphasis on meaning-bearing words;
- avoid constant speed and uniform stress;
- avoid excessive theatricality;
- avoid generic AI-helpful intonation;
- use a clean hook and early benefit in commercial content;
- use calm precision in technical content;
- use genre-appropriate space in reflective narration;
- preserve factual meaning and exact protected terms;
- generate multiple takes and select by evaluation, not slider mythology.

Treat pace ranges as test targets, not universal laws.

---

# F. Required repository actions

Create or connect the private remote:

```text
git@github.com:Ch405-L9/C.Walts.git
```

Use GitHub CLI only if authenticated to the correct account.

Before remote creation or push:

```bash
gh auth status
git status --porcelain
git remote -v
```

If the remote does not exist and authentication is correct:

```bash
gh repo create Ch405-L9/C.Walts --private --source=. --remote=origin
```

Do not run the command if:

- another owner is authenticated;
- the repository already exists with unrelated content;
- private source files are staged;
- secret scanning fails.

Use the branch and checkpoint policy from Prompt C.

---

# G. Required validation stages

## G1. Corpus lint

Validate:

- front matter;
- unique IDs;
- accepted statuses;
- license labels;
- no secrets;
- no binary files in text corpus;
- no duplicate examples;
- no unapproved claims;
- no negative example marked positive.

## G2. Retrieval validation

Run all evaluation prompts.

Report:

- useful hit in top 5;
- exact-term hit;
- positive-source ratio;
- negative-source contamination;
- citation accuracy;
- latency;
- preservation result.

## G3. Audio-reference validation

For each positive MP3:

- verify duration and hash;
- confirm filename-derived settings are recorded as metadata, not treated as universal prescriptions;
- confirm the matching script or transcript reference;
- confirm it is excluded from Git unless Git LFS is explicitly approved.

For negative media:

- confirm it cannot appear as positive retrieval evidence;
- confirm it remains evaluation-only.

## G4. End-to-end smoke test

From a fresh Claude Code process:

1. `natural_flow_collection_health`;
2. `natural_flow_search`;
3. `natural_flow_analyze`;
4. `natural_flow_rewrite`;
5. `natural_flow_source_inspect`;
6. write-tool refusal without confirmation;
7. dry-run reindex;
8. restart;
9. health check again.

Do not output owner test instructions before this passes.

---

# H. Required version and release behavior

Follow Prompt C's version, commit, tag, and push checkpoints.

The first acceptable activated release is:

```text
v0.3.0-rc.1
```

Only tag it when:

- collection exists;
- corpus is populated;
- evaluations run;
- MCP is registered;
- smoke tests pass;
- rollback is documented;
- branch and tag are pushed.

Otherwise use a lower development version and state exactly what remains.

---

# I. Required final owner handoff

Provide:

- remote URL;
- branch;
- version;
- commit SHA;
- pushed tag;
- corpus source counts;
- collection count;
- embedding contract evidence;
- evaluation summary;
- MCP registration evidence;
- smoke-test report;
- known limitations;
- exact owner test commands;
- rollback commands.

No claim of completion is permitted when the collection is empty, MCP is unregistered, or end-to-end retrieval is untested.
