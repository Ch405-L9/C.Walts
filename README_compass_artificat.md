# C.Walts v0.4 — Gate 1.2 Stabilization Plan (Canonical)

**Status:** Approved for execution. Supersedes the informal advisor exchange.
**Applies to:** `feat/natural-flow-rag-activation` @ ce4c2b3
**Controlling clock:** stable-and-correct. No gate opens with an open blocker.
**Scope discipline:** local/FOSS-first. No corpus, private, or holdout data leaves the machine. No cloud eval services.
**Gate numbering:** unchanged from the committed handoff at ce4c2b3 (Gate 2 = select 315 public · Gate 3 = author 285 custom · Gate 4 = assemble/seal · Gate 5 = calibrate/holdout-once). This document is **Gate 1.2**, a stabilization pass *before* Gate 2.

Gate 3-A is governed by Architecture Amendment A6: all 285 custom query texts
are local-only private evaluation material from creation, with local-model
generation and local owner approval only. Gate 3 remains pre-split; Gate 4
owns formal split and sealing.

## Architecture Ordering Amendment A1 — Stage 3A

Approved for the `feat/narration-generalization-v0.4` branch on 2026-08-08.
The historical Stage 3 populated-qrels exit criterion is superseded for the
current Gate 1.2 pass because no legitimate canonical non-holdout query
universe exists before Gate 2 and Gate 3. Legacy regression cases are not
requalified as benchmark queries, and an empty qrels file is not accepted.

Stage 3A therefore implements the exact frozen-96 coverage histogram, qrels
schemas, read-only deterministic candidate-pool infrastructure, qrels
validation, and synthetic/fake-only tests. Real qrels population is deferred
to Gate 4 after the complete 600-query universe exists, split validation has
passed, and the 300 calibration records are isolated from the sealed 300
holdout records. Stage 5 split verification remains mandatory before Gate 2
or Gate 3 query authoring. Gate numbering and the 600-record allocation do
not change. `CW-LIM-009` remains open.

### Architecture Scope Amendment A2 — Stage 6 blocker scopes

The explicit `blocking_scopes` field on the limitation registry is authoritative
for Stage 6+ enforcement. Historical boolean fields remain preserved verbatim
for audit compatibility. The current deferred blocker applies to
`gate2_authorization`, `calibration`, `rc_creation`, and `release_promotion`;
this scope migration does not close the blocker. Gate 2 remains prohibited while
the blocker is open, while Stages 7 and 8 may proceed independently.

### Architecture Amendment A3 — Requirements lock ownership

For C.Walts v0.4, `requirements.txt` remains the dependency source of truth and
`requirements.lock` is the frozen hash-pinned artifact. `pyproject.toml` remains
metadata/tool configuration; dependencies are not migrated into
`[project].dependencies`, and `uv.lock` is not used. uv is a compile and
verification tool only, and lock generation must preserve the tested versions.

### Architecture Amendment A4 — Chroma vulnerability containment

`PYSEC-2026-311` is a real ChromaDB vulnerability, not a false positive. The
v0.4 disposition is `mitigated_by_enforced_non_exposure`, valid only while the
project uses a contained local `PersistentClient`, explicit collection embedding
functions, explicit vector queries and writes, no Chroma network/server paths,
and project-contained persistence. The exception is exact-version and must be
invalidated when those controls or the advisory scope changes.

---

## How the disputes were settled

Both prior advisor votes agreed on five items (provenance stamping, the split verifier, cross-gate blocker enforcement, keeping 600, splitting secrets out of housekeeping). Those were never in question and are carried straight through. Independent research settled the four genuine disputes; each decision below carries a one-line reason and its strongest source. Nothing here is taken on either advisor's authority alone.

---

## Execution order

The sequence is deliberate. Determinism instrumentation comes first because it can *shrink the whole job* — if the wobble is cosmetic float noise, several downstream worries evaporate. Corpus freeze precedes query authoring because sealing a benchmark against a corpus you're still editing is the exact leakage failure Gate 1 already had to clean once. Hygiene gates run last because they're independent and shouldn't block the measurement work.

---

### STAGE 0 — Freeze and baseline (do first, ~30 min)

**0.1** Confirm clean tree, HEAD == origin, 321 tests green, `verify_restore.py --expect-from-sources` PASS at 84/84, `evaluation_case` 0. This is the known-good floor every later step is diffed against.
**0.2** Confirm the complete handoff report at ce4c2b3 is the authoritative CURRENT_STATE. If any Stage below changes architecture, the report is updated in the same commit — never left stale.

*Exit:* baseline recorded, nothing in flight.

---

### STAGE 1 — Determinism instrumentation (~1 day)

**Why first, why this way:** At 84 vectors with `ef_search=100`, HNSW is already effectively exhaustive — there is no recall headroom for a larger `ef` to recover, so the "raise ef_search to test if the wobble is fundamental" approach returns an uninformative null that could be *misread* as "fundamental." The correct instrument is an exact brute-force reference. Elasticsearch's own guidance, quoted in Lin's operational study, is decisive:

> *"when the size of the set... is rather small, it is usually better to rely on brute-force vector search rather than on HNSW-based vector search."*
> — Lin, *Operational Advice for Dense and Sparse Retrievers*, arXiv:2409.06464

The same paper establishes why an index restore can shift a distance at all, even at full recall:

> *"since HNSW index construction is non-deterministic, scores from each trial may differ slightly"* — and it therefore averages over five trials against a flat (exact) index as ground truth.

That is the method adopted below.

**1.1 — Build the exact NumPy oracle.** Normalized-cosine brute force over all 84 vectors. This is ground truth for everything downstream. *(Trivial and correct at this scale; exhaustive KNN is the recognized way to build ANN ground truth — Microsoft Azure AI Search docs.)*

**1.2 — Isolate embedding non-determinism.** Embed 3–5 representative strings 10× each; compare raw float bytes. Modern inference non-determinism traces to batch/reduction-order × floating-point non-associativity, so a byte-level repeat is the definitive local check:

> *"the primary reason nearly all LLM inference endpoints are nondeterministic is that the load (and thus batch-size) nondeterministically varies"*
> — Thinking Machines Lab / Horace He, *Defeating Nondeterminism in LLM Inference* (Sep 2025)

**1.3 — Two variance sweeps.** (i) fixed index, repeated queries → isolates embedding/query-path noise; (ii) rebuilt index, identical stored query vectors → isolates HNSW graph-construction tie-ordering. Report vs. oracle: recall@k, Kendall's τ on rankings, distance variance, **verdict-flip rate**.

**1.4 — Decision gate.**
- If rankings/verdicts are stable across rebuilds (τ≈1, zero flips) despite the ~0.0057 distance wobble → declare the wobble **cosmetic float noise**, log distance as a *volatile field* (Stage 4.4), done. `nomic-embed-text` stays.
- If verdicts flip across rebuilds → build the index once, hash it, freeze it, and add an explicit stable secondary sort (by `chunk_id`) to break near-ties deterministically.
- Replace `nomic-embed-text` **only** if 1.2 proves embedding non-determinism materially changes rankings/verdicts **and** a locally-runnable, commercially-usable, measurably-better model exists. Otherwise keep it.

*Exit:* the wobble has a named root cause and a disposition; no threshold is fitted here.

---

### STAGE 2 — Corpus freeze before benchmark construction (~0.5–1 day)

**Why this order:** The controlling rule across ML and IR methodology is to finalize all data-dependent decisions, then seal the test set and "forget it exists." Editing the corpus while authoring/measuring against the holdout is the retrieval analogue of fitting a scaler before the split. The reconciliation of the two advisor positions: **measure the gap, remediate against the measured gap, *then* freeze** — remediation is not blind, but it finishes before any query is sealed.

> *"partition data before learning any data-dependent parameters and forget the existence of the test set. Violating this order leads to subtle but serious problems."* — flow-classification methodology, arXiv:2601.04089

Google's holdout discipline is the same:

> *"The test split should not be seen during training, and don't use it for hyperparameter tuning."* — Google Cloud ML best practices

**2.1** Run the coverage measurement (Stage 3.1) — yes, before authoring. Coverage measurement is a *read* of the current corpus and must precede remediation.
**2.2** Remediate the single-supporting-chunk dependency behind EVAL-009 and any structural gap the histogram exposes. Source only from licence-clean pools already vetted (PLOS / eLife CC BY); no example may derive from EVAL-009's wording. *(This also removes a genuine fragility — a one-chunk case flips on a single deletion/re-embed — so it's robustness, not just hygiene.)*
**2.3** Re-index through the existing bounded dry-run → backup → verify_restore path. Freeze. After this point, any corpus change is a new benchmark *version*, not an in-place edit.

*Exit:* corpus is measured, remediated, re-indexed, and frozen. EVAL-009 no longer rests on one chunk.

---

### STAGE 3 — Proportionate coverage + minimal qrels (~0.5 day)

**Why lightweight, not a full matrix:** A one-dimensional coverage histogram is proportionate at 84 chunks / 600 queries; a full register × structure × task × preservation × source × retrieval matrix multiplies into mostly-empty cells and is enterprise gold-plating for a solo build. "3 per structure" is a **smoke-test floor, not a statistical threshold** — at n≈3 a per-category 95% CI is ≈±60%, i.e. no discriminating power. The dimension that *is* grounded is query breadth, and your 600 already clears it comfortably:

> *"validates several of the rules-of-thumb experimenters use, such as the number of queries needed for a good experiment is at least 25 and 50 is better"*
> — Buckley & Voorhees, *Evaluating Evaluation Measure Stability*, SIGIR 2000

**3.1** Coverage histogram: distinct delivery structures/registers with ≥3 independent examples. Report per-category counts **as caveats**, never as statistically powered claims. This is the number that governs two of the four query classes and is currently unknown.
**3.2** Minimal qrels infrastructure: because no canonical non-holdout query
universe exists yet, Stage 3A defines the schema, deterministic dense+BM25
candidate-pool builder, validator, and synthetic tests only. Real qrels are
populated in Gate 4 from the 300 calibration records after split validation
and holdout sealing. The holdout remains unjudged and unavailable to candidate
generation or threshold fitting.

*Exit:* coverage number exists; qrels infrastructure passes its tests; real
qrels population is explicitly deferred to Gate 4.

---

### STAGE 4 — Reporting provenance (the actual bug) (~2–3 hrs)

**Why:** The evaluator runs a *separate raw query* for its distance fields and the report treats identical `top_headings` as identical chunk sets (five style_rule chunks share one heading). IDs prove identity; headings don't. Both advisor votes and the research agree this is the real, narrow defect.

**4.1** Stamp every returned chunk with `run_id`, `query_id`, `chunk_id`, `source_id`, `doc_type`, and **per-arm rank+score** (dense rank/score, BM25 rank/score, fused RRF rank/score). Per-arm scores aren't optional polish — Gate 5 calibration needs them and it's the same edit.
**4.2** State explicitly in the report that `max_distance` comes from a diagnostic query, **not** the verdict retrieval, and is not a calibration input.
**4.3** Version the report schema. Fields are additive; the two existing consumers read by name and keep working. Historical reports keep the old shape, untouched.
**4.4** Split volatile fields (timestamps, latency, raw sub-1e-2 distances) into a separate section so a re-run that differs only in timing is not flagged as a regression. *(This churn nearly buried the max_distance finding.)*

*Confirmed safe:* `evaluation-report.json` is regenerated each run, is not in `SHA256SUMS.current`, and is parsed only by two tests that read fields by name — additive changes don't break them.

*Exit:* report proves chunk identity by ID and never conflates diagnostic distances with verdicts.

---

### STAGE 5 — Split-integrity verifier (~1 day, the prevention)

**Why the strongest item on the board:** Gate 1 existed because evaluation material leaked into production. The holdout rules today are prose in `query_allocation.yaml` with zero enforcement — the *same class of unenforced invariant*, on a benchmark that doesn't exist yet. Build the guardrail before a single query file is authored; retrofitting it onto 600 authored queries is the re-authoring cycle we're avoiding. The idiom already exists in-repo (`verify_gate0_integrity.py`: pin a hash, refuse on drift, exit non-zero).

**5.1** `scripts/verify_eval_split.py`, expanded beyond three checks: enforce class/source quotas; unique IDs; duplicate/near-duplicate and template grouping; **no calibration↔holdout group leakage**; non-ingestion of evaluation records; holdout non-disclosure; SHA-256 hash sealing; deterministic regeneration; holdout retirement after use.
**5.2** Deterministic split by hashing a stable `query_id` (fingerprint hash) so the split regenerates on the fly and cannot silently drift.
**5.3** Adversarially test it — it must *fail* on a planted leak, a duplicate across splits, a mutated holdout hash, and an ingested eval record. A verifier that only passes proves nothing.

*Exit:* split integrity is executable, exits non-zero on violation, and is proven to catch the failures it exists to prevent. Runs before any Gate 2/3 query authoring.

---

### STAGE 6 — Cross-gate blocker enforcement (~1–2 hrs)

**Why:** `blocks_release_candidate: true` is currently asserted by a test that passes merely because the field exists. Nothing reads it. There is no RC/CI path to wire into yet — so this is a small *build*, not 30-minute wiring.

**6.1** One generic open-blocker verifier, consumed by Gate 2 authorization, calibration, RC creation, and release promotion — not RC alone. Each of those commands calls it and refuses if any blocker is open.
**6.2** Confirm live: the query returns exactly `['CW-LIM-009-DENSE-COVERAGE']` until Stage 2 closes it, then empty.

*Exit:* no gate can open over an open blocker; enforcement is consumed, not merely asserted.

---

### STAGE 7 — Security & supply-chain baseline (~1 hr, batched)

**Why gitleaks + uv.lock/pip-audit:** current FOSS consensus. Gitleaks is the default offline pre-commit secret scanner (MIT, fast, SARIF, maintained Action); `uv.lock` gives byte-reproducible installs and `pip-audit` is the official PyPA tool (Trail of Bits + Google), v2.10.0 released Dec 2025. `uv audit` (shipped ~June 2026) is a faster native option where available.

**7.1** `pre-commit` with `gitleaks` (keep the hook under ~10s or it gets bypassed) + one-time full-history sweep `gitleaks detect --log-opts="--all"`; rotate anything found.
**7.2** Commit `uv.lock`; add `uv audit` (or `pip-audit` in CI) as a gate; optionally `uv pip compile --exclude-newer "1 week"`.
**7.3** Holdout hash-seal: stdlib `hashlib` manifest + a pytest that fails on mismatch. ~30 lines, fully local — no dedicated package needed.
**7.4** Move the residual audio manifest out of the `evaluation/`-named corpus path (benign, but stop the naming collision).

*Exit:* secrets gated, dependencies locked+audited, holdout sealable and verifiable.

---

### STAGE 8 — Full revalidation (~0.5 day)

Backup + rollback rehearsal after the corpus/report changes; full regression, smoke, MCP, parity, provenance, and security sweep. A checksum alone doesn't prove a backup reopens — restore must validate Chroma, BM25, ID parity, evaluation exclusion, and both retrieval arms.

*Exit:* everything green against the Stage 0 baseline plus the new gates.

---

## Gate 1.2 exit criteria (all must hold before Gate 2 opens)

Gate 2-A freezes the public source-label policy, expected behaviors, grouping,
and deterministic selector before any canonical public record is selected.
Architecture Amendment A5 is recorded in
`docs/architecture-decisions/gate2-public-selection-a5.md`.

1. Wobble root-caused and disposed (Stage 1.4).
2. Corpus remediated, re-indexed, frozen; EVAL-009 no longer one-chunk (Stage 2).
3. Stage 3A coverage histogram and qrels infrastructure pass; real qrels are
   populated and frozen in Gate 4 from calibration records only.
4. Report proves chunk identity by ID; diagnostic distances separated from verdicts (Stage 4).
5. `verify_eval_split.py` executable and adversarially proven (Stage 5).
6. Open-blocker verifier consumed by all four gate commands; EVAL-009 blocker closed (Stage 6).
7. Secrets gated, deps locked+audited, holdout seal working (Stage 7).
8. Full revalidation green; rollback rehearsed (Stage 8).

**Estimate:** ~4–4.5 focused days. Stage 5 is the real day; Stages 4, 6, 7 are short. Duration is not a commitment — an exit criterion failing means the stage isn't done, regardless of clock.

---

## Explicitly deferred (not Gate 1.2)

- Full multi-dimensional structural coverage matrix — only if a failure later traces to an unmeasured dimension.
- Per-category statistical claims / power analysis — only if you start making them (then pool strata or target ~200/category).
- TruffleHog / CI history sweeps — only if the repo goes multi-contributor or public.
- Batch-invariant deterministic-inference engineering — only if Stage 1.2 shows embedding drift that flips verdicts.
- `ef_search` tuning — becomes load-bearing again at a larger corpus, not at 84.

---

## Sources (strongest, per decision)

- **ANN instrument choice / brute-force reference:** Lin, *Operational Advice for Dense and Sparse Retrievers: HNSW, Flat, or Inverted Indexes?*, arXiv:2409.06464 (quotes Elasticsearch on brute-force at small scale; establishes HNSW construction non-determinism + flat-index ground truth).
- **Embedding non-determinism test:** Thinking Machines Lab / Horace He, *Defeating Nondeterminism in LLM Inference*, Sep 2025.
- **ANN ground truth via exhaustive KNN:** Microsoft Azure AI Search documentation.
- **Corpus-before-testset ordering / leakage:** flow-classification methodology, arXiv:2601.04089; Google Cloud ML best practices (holdout discipline).
- **Query-count adequacy (not per-category):** Buckley & Voorhees, *Evaluating Evaluation Measure Stability*, SIGIR 2000; corroborated by Webber, Moffat & Zobel, CIKM 2008.
- **Metrics tooling:** ir_measures; pytrec_eval (Van Gysel & de Rijke, SIGIR 2018); ranx (Bassani, ECIR 2022).
- **Secrets / deps:** gitleaks docs; PyPA pip-audit (v2.10.0, Dec 2025); Astral uv.lock / uv audit docs.

Full evidence, counter-arguments, and caveats are in the companion research report.
