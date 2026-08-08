# Architecture Ordering Amendment A1: Stage 3 qrels

Date: 2026-08-08
Status: approved for Stage 3A implementation
Scope: Gate 1.2 ordering only

## Decision

Gate 1.2 Stage 3 is split into Stage 3A and a later Gate 4 activity. Stage 3A
measures the frozen 96-record corpus and implements qrels schemas, validation,
deterministic candidate pooling, holdout refusal, and synthetic tests. It does
not create real qrels. After Gate 2 selects 315 public records and Gate 3
authors 285 custom/private records, Gate 4 will validate the complete 600-query
split, seal the holdout half, expose only the 300 calibration records, and
populate and freeze calibration qrels before Gate 5.

## Superseded ordering

The original Stage 3 exit criterion required a populated qrels file for a
non-holdout set before Gate 2 and Gate 3. Repository inspection found no
canonical selected calibration query universe. The allocation manifest and
approved dataset manifest contain planning metadata, not query records. The
legacy regression cases are regression-only and are not requalified. Creating
an empty qrels file would be vacuous and would falsely imply complete judging.

This creates the cycle: Stage 3 qrels require canonical calibration queries;
canonical queries require Gate 2/3; Gate 2/3 require the Gate 1.2 exit; and the
old Gate 1.2 exit required Stage 3 qrels. A1 resolves it by deferring real qrels
population to Gate 4 without changing top-level Gate numbering or the 600
record allocation.

## Stage 3A exit criterion

The exact frozen 96 production records are each assigned once in a
one-dimensional coverage taxonomy. The read-only verifier proves 96 Chroma
records, 96 BM25 records, exact parity, zero evaluation records, deterministic
category and independence counts, and smoke-floor labels only. Qrels schemas,
candidate pooling, validation, holdout refusal, and synthetic tests pass. No
real evaluation query is authored, processed, or judged.

## Gate 4 contract

Gate 4 must have a validated 600-query universe, exactly 300 calibration
records, and a sealed 300-record holdout. Only calibration records may enter
candidate pooling and qrels generation. Holdout qrels and judgments must remain
absent, and calibration qrels must be validated and frozen before Gate 5.

Stage 5 split verification remains mandatory before Gate 2/3 query authoring.
No Gate number changes. `CW-LIM-009` remains open.
