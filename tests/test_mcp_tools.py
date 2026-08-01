"""MCP surface: the seven tools, their schemas, and the write gates.

Importing `mcp/server.py` runs `load_settings()` at module scope, so this file
also serves as the "server starts" check Prompt C §10 asks for before
registration — a broken config fails here rather than at `claude mcp add`.
"""

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

READ_ONLY = (
    "natural_flow_search",
    "natural_flow_analyze",
    "natural_flow_rewrite",
    "natural_flow_source_inspect",
    "natural_flow_collection_health",
)
WRITE_CAPABLE = ("natural_flow_feedback", "natural_flow_reindex")


@pytest.fixture(scope="module")
def server():
    sys.path.insert(0, str(ROOT / "src"))
    spec = importlib.util.spec_from_file_location("nfr_mcp_server", ROOT / "mcp" / "server.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_approved_tool_set_is_complete(server):
    assert set(server.TOOLS) == set(READ_ONLY) | set(WRITE_CAPABLE)


@pytest.mark.parametrize("name", READ_ONLY)
def test_read_only_tools_are_marked_read_only(server, name):
    assert server.TOOLS[name]["write"] is False


@pytest.mark.parametrize("name", WRITE_CAPABLE)
def test_write_tools_are_marked_write(server, name):
    assert server.TOOLS[name]["write"] is True


@pytest.mark.parametrize("name", WRITE_CAPABLE)
def test_write_tools_refuse_without_confirmation(server, name):
    result = server.dispatch(name, {})
    assert result["error"]["code"] == "CONFIRMATION_REQUIRED"


@pytest.mark.parametrize("name", WRITE_CAPABLE)
def test_write_tools_refuse_while_writes_disabled(server, name):
    """confirm alone is not enough — the config gate is independent."""
    result = server.dispatch(name, {"confirm": True})
    assert result["error"]["code"] == "WRITES_DISABLED"


def test_reindex_schema_defaults_to_dry_run(server):
    schema = server._schema_for("natural_flow_reindex")
    assert schema["properties"]["dry_run"]["default"] is True


@pytest.mark.parametrize("name", WRITE_CAPABLE)
def test_confirm_is_optional_in_schema_so_the_server_gate_is_reachable(server, name):
    """`confirm` in `required` would make CONFIRMATION_REQUIRED unreachable.

    A schema-conforming client could then never omit it, and the refusal would be
    enforced by client-side validation instead of by this server — which is not
    the same guarantee. Found by the fresh-session MCP acceptance run.
    """
    schema = server._schema_for(name)
    assert "confirm" in schema["properties"]
    assert "confirm" not in schema.get("required", [])


@pytest.mark.parametrize("name", READ_ONLY + WRITE_CAPABLE)
def test_every_tool_has_an_object_schema(server, name):
    schema = server._schema_for(name)
    assert schema["type"] == "object"
    assert isinstance(schema.get("properties"), dict)


def test_no_tool_accepts_a_filesystem_path_or_collection_name(server):
    """Two invariants from Prompt C §10, checked across the whole surface."""
    forbidden = {"path", "file", "filepath", "file_path", "directory", "collection",
                 "collection_name", "persistence_path"}
    for name in server.TOOLS:
        properties = set(server._schema_for(name).get("properties", {}))
        assert not (properties & forbidden), f"{name} exposes {properties & forbidden}"


def test_unknown_tool_is_refused(server):
    result = server.dispatch("natural_flow_delete_everything", {})
    assert result["error"]["code"] == "UNKNOWN_TOOL"


def test_source_inspect_rejects_a_malformed_chunk_id(server):
    result = server.dispatch("natural_flow_source_inspect", {"chunk_id": "../../etc/passwd"})
    assert result["error"]["code"] == "INVALID_PARAMS"


def test_analyze_measures_without_rewriting(server):
    dense = (
        "The implementation configuration initialization process requires validation "
        "of all environment-specific dependency resolution conditions prior to execution."
    )
    payload = server.tool_analyze(dense)
    analysis = payload["analysis"]
    assert analysis["words"] > 15
    assert analysis["longest_nominal_run"] >= 3
    assert any("noun stacking" in flag for flag in analysis["flags"])
    assert "rewrite" not in payload  # measurement only
    assert "estimated_seconds_by_register" in analysis


def test_analyze_rejects_empty_text(server):
    assert server.tool_analyze("  ")["error"]["code"] == "INVALID_PARAMS"


def test_rewrite_returns_the_original_when_preservation_fails(server):
    source = "The administrator must rotate the key within 10 minutes."
    bad = "The administrator should rotate the key soon."
    payload = server.tool_rewrite(source, candidate=bad)
    assert payload["preservation"]["passed"] is False
    assert payload["accepted_text"] == source
    assert "rejected" in payload["warning"]


def test_rewrite_accepts_a_faithful_candidate(server):
    source = "The administrator must rotate the key within 10 minutes."
    good = "Within 10 minutes, the administrator must rotate the key."
    payload = server.tool_rewrite(source, candidate=good)
    assert payload["preservation"]["passed"] is True
    assert payload["accepted_text"] == good


def test_search_labels_neighbours_and_reports_that_k_caps_ranked_only(server):
    """A caller asking for k=3 gets 3 RANKED results plus neighbour context.

    The fresh-session run read 6 results for k=3 as the cap being ignored. The
    counts and the label now make the distinction explicit in the payload.
    """
    payload = server.tool_search("breath group pacing for a technical warning", k=3)
    assert payload["strategy"]["ranked_n"] <= 3
    assert all("is_neighbor" in r for r in payload["results"])
    neighbours = [r for r in payload["results"] if r["is_neighbor"]]
    assert all(r["score"] == 0.0 for r in neighbours)
    assert payload["strategy"]["neighbor_n"] == len(neighbours)


def test_health_counts_a_loaded_lexical_index(server):
    """Counting ids on an unloaded index reported 0 for a healthy index."""
    payload = server.tool_collection_health()
    assert payload["lexical_index_error"] is None
    assert payload["lexical_index_chunks"] == payload["count"]
    assert payload["status"] == "OK"


def test_feedback_targets_a_separate_collection(server):
    """Feedback must never be able to write into the retrieval corpus."""
    assert server.FEEDBACK_COLLECTION != server.SETTINGS.collection.name
    assert server.FEEDBACK_COLLECTION in server.SETTINGS.collection.allowlisted_collections


def test_incomplete_call_is_a_caller_error_not_an_internal_one(server, monkeypatch):
    """A missing required argument must not be reported as a server fault.

    Found in the rc.2 smoke run: dispatching natural_flow_feedback with only
    confirm=true, while writes were enabled, raised TypeError inside the generic
    handler and returned INTERNAL_ERROR. That tells the caller the server broke
    when the request was simply incomplete — and it hides real internal faults
    among ordinary bad requests.
    """
    monkeypatch.setenv("NFR_ALLOW_WRITES", "true")
    payload = server.dispatch("natural_flow_feedback", {"confirm": True})
    assert payload["error"]["code"] == "INVALID_PARAMS"
    assert "chunk_id" in payload["error"]["message"]


def test_unexpected_argument_is_also_a_caller_error(server, monkeypatch):
    monkeypatch.setenv("NFR_ALLOW_WRITES", "true")
    payload = server.dispatch(
        "natural_flow_reindex", {"confirm": True, "not_a_real_parameter": 1}
    )
    assert payload["error"]["code"] == "INVALID_PARAMS"
