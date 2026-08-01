#!/usr/bin/env python3
"""Fresh-session MCP check — a real client, over stdio, against a new process.

    python scripts/mcp_session_check.py            # human report, exit 1 on failure
    python scripts/mcp_session_check.py --json     # machine report

`scripts/smoke_test.py` exercises the tool surface IN-PROCESS: it imports
mcp/server.py and calls `dispatch` directly. That proves the handlers work. It
does not prove the server starts, negotiates a protocol, advertises schemas, and
answers a client it has never seen — and those are exactly the failures that
show up only after registration, when the operator is furthest from a debugger.

This spawns the server as a subprocess, speaks the protocol to it, and asserts
against what comes back over the wire. Every assertion here is about the session,
not the retrieval quality, which the evaluation covers.

Writes stay disabled: the check confirms the write-capable tools REFUSE, which
is the behaviour a fresh session must have by default.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

EXPECTED_TOOLS = {
    "natural_flow_search",
    "natural_flow_analyze",
    "natural_flow_rewrite",
    "natural_flow_source_inspect",
    "natural_flow_collection_health",
    "natural_flow_feedback",
    "natural_flow_reindex",
}

results: list[dict] = []


def record(name: str, passed: bool, detail: object = "") -> bool:
    results.append({"check": name, "passed": bool(passed), "detail": detail})
    return bool(passed)


def payload_of(call) -> dict:
    """MCP returns content blocks; every tool here answers with one JSON block."""
    if not call.content:
        return {}
    return json.loads(call.content[0].text)


async def run() -> None:
    from mcp.client.stdio import stdio_client

    from mcp import ClientSession, StdioServerParameters

    # A genuinely fresh session: new interpreter, inherited-but-clean env, and
    # writes explicitly NOT enabled.
    env = {k: v for k, v in os.environ.items() if k != "NFR_ALLOW_WRITES"}

    params = StdioServerParameters(
        command=str(ROOT / ".venv" / "bin" / "python"),
        args=[str(ROOT / "mcp" / "server.py")],
        env=env,
    )

    async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
        init = await session.initialize()
        record("server initializes over stdio", True, init.serverInfo.name)

        listed = await session.list_tools()
        names = {t.name for t in listed.tools}
        record("all seven tools advertised", names == EXPECTED_TOOLS, sorted(names))
        record(
            "every tool advertises an input schema",
            all(t.inputSchema for t in listed.tools),
            [t.name for t in listed.tools if not t.inputSchema],
        )
        reindex = next(t for t in listed.tools if t.name == "natural_flow_reindex")
        record(
            "reindex advertises dry_run defaulting to true",
            reindex.inputSchema["properties"]["dry_run"]["default"] is True,
        )
        record(
            "reindex advertises the delete_stale opt-in",
            reindex.inputSchema["properties"]["delete_stale"]["default"] is False,
        )

        health = payload_of(await session.call_tool("natural_flow_collection_health", {}))
        record("collection_health reports OK", health.get("status") == "OK", health.get("status"))
        record(
            "health agrees with the lexical index",
            health.get("count") == health.get("lexical_index_chunks"),
            f"{health.get('count')} vs {health.get('lexical_index_chunks')}",
        )
        record("writes are off in a fresh session", health.get("writes_allowed") is False)

        search = payload_of(
            await session.call_tool("natural_flow_search", {"query": "What is ToBI?", "k": 5})
        )
        ranked = [r for r in search.get("results", []) if not r.get("is_neighbor")]
        record("search returns ranked results", bool(ranked), len(ranked))
        record(
            "every result carries a licence",
            all(r.get("license") for r in ranked),
            [r["chunk_id"] for r in ranked if not r.get("license")],
        )
        record(
            "the glossary answers a definitional probe",
            bool(ranked) and "Tones and Break Indices" in ranked[0].get("text", ""),
            ranked[0].get("source_title") if ranked else None,
        )

        for term in ("H*", "L-L%", "break index"):
            hit = payload_of(
                await session.call_tool("natural_flow_search", {"query": term, "k": 5})
            )
            texts = " ".join(r.get("text", "") for r in hit.get("results", []))
            record(f"exact notation {term!r} survives the round trip", term in texts)

        inspect = payload_of(
            await session.call_tool(
                "natural_flow_source_inspect", {"chunk_id": ranked[0]["chunk_id"]}
            )
        )
        record(
            "source_inspect returns provenance",
            bool(inspect.get("license")) and bool(inspect.get("source_checksum")),
            {k: inspect.get(k) for k in ("source_id", "license")},
        )

        analyze = payload_of(
            await session.call_tool(
                "natural_flow_analyze",
                {"text": "The implementation configuration initialisation process "
                         "requires validation of all environment-specific dependency "
                         "resolution conditions prior to execution."},
            )
        )
        record("analyze returns measurements", bool(analyze.get("analysis")))
        record("analyze fences retrieved guidance as untrusted",
               "UNTRUSTED" in str(analyze.get("note", "")).upper())

        rewrite = payload_of(
            await session.call_tool(
                "natural_flow_rewrite",
                {"text": "The administrator must rotate the exposed key before the "
                         "service can be re-enabled.",
                 "candidate": "The admin should probably rotate the key at some point."},
            )
        )
        record(
            "a weakened candidate is refused and the original returned",
            rewrite.get("preservation", {}).get("passed") is False
            and rewrite.get("accepted_text", "").startswith("The administrator must"),
            rewrite.get("warning"),
        )

        for tool, args in (
            ("natural_flow_feedback", {"chunk_id": ranked[0]["chunk_id"], "verdict": "useful"}),
            ("natural_flow_reindex", {}),
        ):
            no_confirm = payload_of(await session.call_tool(tool, args))
            record(
                f"{tool} refuses without confirm",
                no_confirm.get("error", {}).get("code") == "CONFIRMATION_REQUIRED",
                no_confirm.get("error"),
            )
            confirmed = payload_of(await session.call_tool(tool, {**args, "confirm": True}))
            record(
                f"{tool} refuses while writes are disabled",
                confirmed.get("error", {}).get("code") == "WRITES_DISABLED",
                confirmed.get("error"),
            )

        unknown = payload_of(await session.call_tool("natural_flow_search", {"query": ""}))
        record(
            "an empty query is a caller error, not a crash",
            unknown.get("error", {}).get("code") == "INVALID_PARAMS",
            unknown.get("error"),
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    try:
        asyncio.run(run())
    except Exception as exc:  # noqa: BLE001 — a failed session is a reportable result
        record("session completed", False, f"{type(exc).__name__}: {exc}")

    passed = sum(1 for r in results if r["passed"])
    report = {
        "checks": results,
        "passed": passed,
        "total": len(results),
        "all_passed": passed == len(results) and bool(results),
    }

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print("\nfresh-session MCP check — separate process, stdio protocol\n")
        for entry in results:
            mark = "PASS" if entry["passed"] else "FAIL"
            print(f"  {mark}  {entry['check']}")
            if not entry["passed"] and entry["detail"] != "":
                print(f"        detail: {entry['detail']}")
        print(f"\n{passed}/{len(results)} passed\n")

    out = ROOT / "docs" / "evidence" / "mcp-fresh-session.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return 0 if report["all_passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
