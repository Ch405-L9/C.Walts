# Architecture Amendment A3: Requirements Lock

For C.Walts v0.4, `requirements.txt` remains the dependency source of truth.
`requirements.lock` is the frozen, hash-pinned dependency artifact. `pyproject.toml`
continues to hold project metadata and tool configuration only; dependencies are
not migrated into `[project].dependencies`. `uv.lock` is not used.

uv is a compile and verification tool, not the dependency ownership layer. Lock
generation must preserve the currently tested package versions and must not
opportunistically upgrade unrelated packages. A future Stage 7 implementation
must validate the lock against the exact tested environment before committing it.
