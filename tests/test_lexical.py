"""The notation tokens BM25 exists to protect must survive tokenization."""

import pytest

from natural_flow_rag.lexical_search import tokenize

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
