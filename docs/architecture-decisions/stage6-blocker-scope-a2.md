# Architecture Scope Amendment A2 — Stage 6 blocker scopes

Status: approved for Stage 6 implementation on 2026-08-09.

The limitation register originally recorded policy-era booleans: the active
deferred limitation had `blocks_gate2: false`, blocked threshold calibration,
and blocked release-candidate creation. The later Gate 1.2 Stage 6 plan requires
one fail-closed blocker verifier consumed by Gate 2 authorization, calibration,
RC creation, and release promotion. Those representations describe different
policy points in the project history.

The historical booleans remain unchanged for audit and backward compatibility.
Stage 6 instead consumes the explicit `blocking_scopes` field. For
`CW-LIM-009-DENSE-COVERAGE`, the authoritative scopes are exactly:

- `gate2_authorization`
- `calibration`
- `rc_creation`
- `release_promotion`

The blocker remains `status: deferred`; this is a scope-policy migration, not a
closure. Gate 2 must remain prohibited while the blocker is open. Stages 7 and
8 may proceed independently, but an actual Gate 2 transition cannot proceed
until the authorization query returns clear. Closure must later be represented
by `status: resolved`, empty `blocking_scopes`, and auditable closure evidence;
the registry entry must not be deleted.

Stage 6 protects supported operational transition paths. It does not claim to
prevent deliberate source edits outside those paths.
