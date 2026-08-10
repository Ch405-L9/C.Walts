# Known limitations — C.Walts v0.4

Tracked register of accepted limitations, deferred work, and closed ambiguities.

A limitation appears here when it is **known, measured, and not being fixed
now**. Anything recorded as `deferred` with `blocks_release_candidate: true` is a
release blocker: a release candidate may not be cut while such an entry is open,
regardless of how the evaluation suite scores. That is the only enforcement this
register has, so the field is machine-readable and asserted in
`tests/test_known_limitations.py`.

Status vocabulary:

| Status | Meaning |
|---|---|
| `deferred` | real gap, understood, scheduled for a named future phase |
| `accepted` | will not change; recorded so it is not repeatedly rediscovered |
| `resolved` | closed, with the change that closed it named |

---

## CW-LIM-009-DENSE-COVERAGE — EVAL-009 rests on a single production example

```yaml
id: CW-LIM-009-DENSE-COVERAGE
status: resolved
severity: medium
blocks_gate2: false
blocks_threshold_calibration: true
blocks_release_candidate: true
blocking_scopes:
resolved_at: 0.4.0-dev.12
resolved_by: docs/evidence/gate1_2-stage8-dense-coverage.json
blocking_scopes: []
```

Stage 6 explicit `blocking_scopes` are authoritative for current enforcement;
the historical boolean fields above remain unchanged for audit compatibility.

### Stage 8 closure evidence

The frozen Stage 8 diagnostic protocol ran twelve read-only searches across four
predefined structural probes and three complete rounds. Every probe in every
round returned qualifying accepted `approved_example` support. Each round
returned multiple independent groups and multiple distinct primary groups. The
diagnostic evidence is recorded in
`docs/evidence/gate1_2-stage8-dense-coverage.json`. No corpus, retrieval
configuration, or production index was changed.

### Statements of record

1. **EVAL-009 currently depends largely on one substantive production example.**
   The case passes, and it passes honestly — but on a single chunk.

2. **No corpus example will be added from EVAL-009's wording.** Writing a corpus
   example derived from the evaluation prompt would make the benchmark able to
   retrieve its own answer, which is precisely the defect Gate 1 removed 17
   chunks to eliminate. This prohibition binds every future phase. A case that
   is thin is a measurement problem; a case that can retrieve its own phrasing
   is not a measurement at all.

3. **The future narration/domain corpus-expansion phase must add multiple
   independently designed dense technical rewrite examples.** Independently
   designed means authored from real source material and real delivery problems,
   not back-formed from this register, from EVAL-009, or from each other.

4. **Those examples must cover different technical structures rather than
   paraphrasing one regression prompt.** Distinct structural failure modes —
   not the same nominalization chain restated. See the evidence below for what
   the corpus already covers and what it does not.

5. **The limitation closes only after retrieval diversity and regression tests
   demonstrate more than one substantive source.** Closure requires measurement:
   a retrieval run for EVAL-009-shaped queries returning substantive chunks from
   more than one independently authored example, plus regression tests asserting
   that diversity. A count of corpus files is not evidence. Adding examples
   without demonstrating they are retrieved does not close this entry.

### Evidence — measured 2026-08-02 at `0.4.0-dev.2`, 84 chunks

EVAL-009 declares three acceptable markers. Two of them resolve to **the same
single chunk**:

| Marker | Chunks in the production collection |
|---|---|
| `Pair CW-021` | 1 — `26e57adf05186f83_11`, *Pair CW-021 — Technical: dense architecture paragraph* |
| `dense architecture` | 1 — the same chunk, `26e57adf05186f83_11` |
| `Market Voice-Delivery Rules` | 5 — but all `doc_type: style_rule` |

The measured run matched `Pair CW-021` and returned five chunks, all
`approved_example`, none `style_rule`. The third marker therefore does not carry
the case in practice: the case asserts a `style_rule` primary would be wrong, so
the only marker that can pass it is the one chunk.

**The gap is narrower than "few technical examples", and naming it precisely is
what makes it fixable.** The corpus holds nine technical `approved_example`
headings:

```text
CW-001  Technical security explainer
CW-005  Technical warning
CW-018  Technical: retry and backoff behaviour
CW-019  Technical: what a feature does not do
CW-020  Technical: migration warning
CW-021  Technical: dense architecture paragraph
CW-022  Technical: permission boundary
CW-039  Technical: rewriting around exact identifiers and dates
SCR-002 Technical security explanation
```

Technical coverage is not thin. What is singular is the **dense nominalization
chain** — a sentence built from stacked abstract nouns, which is the structure
EVAL-009's query exercises. CW-021 is the only production example of it. The
other eight demonstrate different structures (warnings, boundaries, retry
semantics, identifier preservation) and do not stand in for it.

So the corpus-expansion phase should not add "more technical examples". It should
add several genuinely different dense-structure sources — for example
nominalization chains, stacked prepositional qualifiers, embedded conditional
clauses, and passive agentless constructions — each authored independently.

### Why it is deferred rather than fixed

Gate 1 identified this and was explicitly forbidden from adding corpus material.
Gate 1.1 is likewise bounded: §4 records and classifies, it does not authorize
corpus changes, evaluation-query authoring, or retuning EVAL-009's markers. The
fix belongs to the corpus-expansion phase, which is where authored material is
reviewed and approved.

### Why it blocks calibration and a release candidate but not Gate 2

- `blocks_gate2: false` — Gate 2 does not depend on this case's breadth.
- `blocks_threshold_calibration: true` — a similarity threshold fitted while one
  case rests on a single chunk is fitted to that chunk. The threshold would be
  tuned to a corpus accident rather than to the retrieval behaviour it is meant
  to govern.
- `blocks_release_candidate: true` — a release candidate asserts the evaluation
  suite measures what it claims. A case carried by one example measures the
  presence of that example.

---

## CW-LIM-RC2-COUNT — the rc.2 owner report states 101 chunks

```yaml
id: CW-LIM-RC2-COUNT
status: accepted
classification: accepted historical record
severity: informational
blocks_gate2: false
blocks_threshold_calibration: false
blocks_release_candidate: false
blocking_scopes: []
```

`docs/owner-test-report-rc2.md` states the corpus grew "from 48 chunks to 101"
(lines 30 and 295). That was true at `v0.3.0-rc.2`. The collection now holds 84,
after Gate 1 removed 17 `evaluation_case` chunks.

**Accepted as a historical record and deliberately not rewritten.** An owner test
report records what an owner was shown on a date. Editing its numbers to match
the present would falsify a delivery record and destroy the ability to audit what
was accepted and when. The current count is derived, never quoted — see
`scripts/verify_restore.py` and `docs/rollback.md`.

Distinct from `CW-LIM-ROLLBACK-COUNTS` below: this is the 101 figure, and it
appears only in this owner report.

---

## CW-LIM-ROLLBACK-COUNTS — the rc.2 rollback rehearsal states 48 and 97 chunks

```yaml
id: CW-LIM-ROLLBACK-COUNTS
status: accepted
classification: accepted historical evidence
severity: informational
blocks_gate2: false
blocks_threshold_calibration: false
blocks_release_candidate: false
blocking_scopes: []
```

`docs/history/rollback-rc2.md` records a restore that returned the vector store to
**48** chunks while the lexical index still described **97**, and the `DEGRADED`
health status that caught it.

**Accepted as historical evidence and preserved verbatim.** These numbers are not
stale documentation to be refreshed — they are the measurement of a real failure
mode, and they are the reason the active procedure restores both stores together
and refuses a backup it has not verified. Rewriting them to 84 would delete the
evidence and leave the procedure looking arbitrary.

The document carries a header stating it is frozen and must not be followed, and
the active `docs/rollback.md` contains no production count at all. Gate 1.1 §3.

> **Correction carried forward.** The Gate 1 close recorded this and the entry
> above as a single item, claiming `docs/rollback.md` described 101 chunks. It
> never contained that number. The 101 figure and the 48/97 figures are in two
> different documents and are two different entries here, which is why they are
> listed separately.

---

## CW-LIM-EVAL-PATH — a production corpus path was named "evaluation"

```yaml
id: CW-LIM-EVAL-PATH
status: resolved
classification: resolved by the Gate 1.1 rename
severity: low
resolved_at: 0.4.0-dev.2
resolved_by: cdb670d
blocks_gate2: false
blocks_threshold_calibration: false
blocks_release_candidate: false
blocking_scopes: []
```

The negative-pattern corpus lived at `corpus/raw/evaluation/negative/`. The
material was never evaluation material — it is corpus text describing delivery to
avoid — but a production-ingestible directory named "evaluation" invited exactly
the confusion Gate 1 spent a phase undoing.

**Resolved at Gate 1.1 §2** by `git mv` to `corpus/raw/negative_patterns/`. The
move was provably inert: chunk ids derive from source id and content, not from
the path, so the single chunk kept id `9c1e63263b4b8373_0` and only `source_path`
changed. A dry run reported stale 0 / would-add 0 / identical id sets before any
write. Chroma and BM25 both held at 84 with exact id-set parity, and no production
`source_path` contains "evaluation".

Asserted by `tests/test_negative_pattern_path.py`, including live proof that
negative material stays out of positive rewrite retrieval and remains reachable
for an explicit "what to avoid" request.

Residual, deliberately out of scope: `corpus/raw/evaluation/` still exists holding
only `audio_reference_manifest.yaml`, which is not loader-supported, is declared
by no source, and is therefore not ingestible. A test asserts that is all that
remains.
