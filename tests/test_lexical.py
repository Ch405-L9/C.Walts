"""The notation tokens BM25 exists to protect must survive tokenization.

The save/load round-trip is tested too: the first build of this index persisted
48 chunk ids and zero token lists, because rank_bm25 does not retain its corpus.
It loaded as empty, `Retriever._lexical` swallowed the failure, and hybrid
retrieval silently ran dense-only. Nothing in the suite noticed.
"""

import pytest

from natural_flow_rag.lexical_search import LexicalIndex, LexicalIndexError, tokenize

NOTATION = ["H*", "L-L%", "ToBI", "L+H*", "H-H%", "L*+H", "H+!H*", "!H*", "H-"]


@pytest.mark.parametrize("token", NOTATION)
def test_notation_survives_tokenization(token):
    assert token in tokenize(f"the {token} accent marks prominence")


def test_case_is_also_matchable_lowercase():
    tokens = tokenize("ToBI annotation")
    assert "ToBI" in tokens and "tobi" in tokens


def test_break_index_is_two_tokens():
    tokens = tokenize("break index 4")
    assert "break" in tokens and "index" in tokens


CORPUS = [
    ("c_0", "The H* pitch accent and the L-L% boundary tone are ToBI labels."),
    ("c_1", "Pace the line by meaning; one main thought per breath group."),
    ("c_2", "A commercial read leads with the hook and closes on one call to action."),
]


def _built(tmp_path) -> LexicalIndex:
    index = LexicalIndex(tmp_path / "index.json")
    index.build([c[0] for c in CORPUS], [c[1] for c in CORPUS])
    return index


def test_saved_index_carries_its_tokens(tmp_path):
    import json

    _built(tmp_path).save()
    payload = json.loads((tmp_path / "index.json").read_text(encoding="utf-8"))
    assert len(payload["tokens"]) == len(CORPUS)
    assert all(payload["tokens"])


def test_round_trip_retrieves_exact_notation(tmp_path):
    _built(tmp_path).save()

    reloaded = LexicalIndex(tmp_path / "index.json")
    for probe in ("L-L%", "H*", "ToBI"):
        hits = reloaded.search(probe, 3)
        assert hits, f"{probe!r} retrieved nothing from a reloaded index"
        assert hits[0].chunk_id == "c_0"


def test_empty_index_is_refused_rather_than_saved(tmp_path):
    index = _built(tmp_path)
    index._tokens = [[] for _ in CORPUS]
    with pytest.raises(LexicalIndexError, match="refusing to write"):
        index.save()


def test_loading_a_tokenless_index_raises(tmp_path):
    import json

    path = tmp_path / "index.json"
    path.write_text(json.dumps({"version": 1, "chunk_ids": ["a"], "tokens": []}), encoding="utf-8")
    with pytest.raises(LexicalIndexError, match="no tokens"):
        LexicalIndex(path).search("anything", 3)
