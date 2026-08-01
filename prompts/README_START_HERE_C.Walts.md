# C.Walts — Claude Continuation Package

## Canonical project decision

- **Project name:** `C.Walts`
- **GitHub owner:** `Ch405-L9`
- **New remote repository:** `Ch405-L9/C.Walts`
- **Remote visibility:** **PRIVATE**
- **Working implementation path:** `/home/t0n34781/projects/natural-language-flow-rag`
- **Existing collection name:** `badgr_natural_flow_v1`
- **Existing implementation policy:** Preserve Prompt C unless this package supplies a narrower, evidence-backed clarification.
- **Primary objective:** Complete the natural-language-flow and voice-delivery corpus, prove isolated ingestion and retrieval, register project-scoped MCP, smoke test, version, commit, tag, and push before owner testing.

The spelling `C.Walts` is canonical for the repository and project handoff, even if an earlier ChatGPT project label displayed `project c.waltz`.

---

# 1. Controlling execution order

Claude must read these files in order:

1. `README_START_HERE_C.Walts.md`
2. `prompts/PC_nat-lang-flow_controlled-activation.md`
3. `prompts/PD_C.Walts_media-corpus_activation.md`
4. `docs/source-analysis-and-decisions.md`
5. `corpus/raw/style_rules/market_voice_delivery_rules.md`
6. `corpus/raw/owner_examples/approved_before_after_pairs.md`
7. `corpus/raw/evaluation/audio_reference_manifest.yaml`
8. `corpus/raw/evaluation/evaluation_prompts.md`

Prompt C remains the controlling build and release directive. Prompt D is a scoped addendum covering the newly supplied media, corpus composition, market-facing voice standards, and repository decision.

Where the files conflict:

1. safety, licensing, secrets, data preservation, and compatibility controls win;
2. verified local facts win over assumptions;
3. Prompt D wins only for the media classification and corpus decisions introduced here;
4. no unrelated architecture redesign is authorized.

---

# 2. User-approved source classification

## Positive target references

The four standalone ElevenLabs MP3 files are **user-approved target-delivery references**:

- Hanna — calm and conversational;
- Jessica — controlled, clear technical delivery;
- Seán — deep and clear technical delivery;
- B. Lawson — concise professional delivery.

These recordings represent the target class: natural, deliberate, market-ready, and non-robotic. They are not automatically proof of a universal voice or pace. They are reference performances for matching delivery quality across different registers.

## Negative or contrast references

The screen recordings inside `elevenlabs_example|sample_bundle.zip` are **user-designated examples of what should not be reproduced**, particularly synthetic or explanatory delivery that sounds robotic, mechanically paced, over-enunciated, flat, or disconnected from the meaning.

Use negative media only for:

- evaluation;
- contrastive analysis;
- rejection tests;
- documentation of failure modes.

Do not ingest negative recordings as positive style exemplars.

## Excluded context-only material

A screen recording showing wireless-debugging settings is unrelated to voice-delivery quality. Exclude it from corpus ingestion and delivery scoring.

---

# 3. Critical implementation distinction

The current RAG design is text-first. Audio binaries must **not** be inserted directly into the textual Chroma collection as opaque files.

For the first production activation:

- ingest the approved textual annotations, before/after pairs, scripts, delivery descriptors, and market rules;
- retain audio files under `references/media/` as evaluation evidence;
- store audio hashes and metadata in the manifest;
- expose source references through metadata;
- do not add acoustic embeddings unless an independently tested audio-feature pipeline exists.

If Claude discovers an existing compatible acoustic-analysis module, it may produce sidecar measurements. It must not change the collection's embedding type or mix audio vectors with `nomic-embed-text` vectors.

---

# 4. Market-first rule

This corpus does **not** attempt to clone the owner's personal speaking style.

The primary standard is current professional market practice for:

- commercial voice-over;
- explainer videos;
- product demonstrations;
- technical narration;
- educational narration;
- professional brand introductions.

The owner's supplied examples may make small preference adjustments, but market-tested clarity, natural delivery, audience fit, production consistency, and message effectiveness take priority.

No single pace, voice, or slider setting is universal. Delivery must adapt to register and information density.

---

# 5. Required execution

Claude must:

1. verify every referenced file and SHA-256 hash;
2. create or connect the new **private** remote `Ch405-L9/C.Walts`;
3. preserve the existing working implementation unless incompatibility requires a narrow change;
4. copy only approved corpus text into the ingestion tree;
5. keep media and restricted/context assets out of Git unless explicitly allowlisted;
6. run ingestion dry-run;
7. prove the explicit `nomic-embed-text` collection contract in a disposable collection;
8. create and populate the isolated real collection only after the proof passes;
9. run the evaluation prompts in this package;
10. measure retrieval quality before selecting a similarity floor;
11. register MCP at project scope;
12. smoke test from a fresh Claude Code process;
13. version, commit, push, and tag at logical checkpoints;
14. deliver owner test commands only after all required smoke tests pass.

---

# 6. Repository privacy and media policy

The new repository must be private.

Default Git policy:

- commit prompts, manifests, rules, tests, and approved text examples;
- do not commit generated Chroma databases;
- do not commit caches, logs, `.env` files, or secrets;
- do not commit the 145 MB source bundle;
- do not commit audio binaries unless the owner explicitly chooses Git LFS and confirms redistribution rights;
- keep media local and reference it by manifest and checksum.

Suggested local media destination:

```text
/home/t0n34781/projects/natural-language-flow-rag/references/media/
```

Suggested repository content:

```text
README.md
prompts/
corpus/
docs/
tests/
config/
scripts/
```

---

# 7. Honest completion condition

The system is not complete merely because files exist or unit tests pass.

Completion requires:

- a populated isolated collection;
- relevant results for natural-flow queries;
- exact-term retrieval;
- preservation tests;
- successful project-scoped MCP registration;
- fresh-session smoke tests;
- pushed commits and release-candidate tag;
- documented rollback;
- no unresolved critical failures.

If source material is insufficient for a meaningful metric, Claude must say so and use a validation release rather than claim production readiness.
