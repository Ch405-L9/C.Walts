# Architecture Amendment A5: Public Benchmark Selection Freeze

For canonical Gate 2, public records are selected from a tracked source-label policy committed before canonical selection. Gate 2 v1 is `public_verbatim` only and performs no model or LLM rewriting.

The policy fixes source-label classification, expected behavior, grouping, quotas, and public IDs before any 315-record selection. It may not be changed after selection is observed without a new architect-reviewed policy revision.

Selection is independent of C.Walts retrieval scores, responses, thresholds, and failures. Query text remains private evaluation data, and Gate 2 output remains pre-split. Gate 4 owns split and holdout assignment.
