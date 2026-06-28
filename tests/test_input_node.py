import pytest

from app.constants import PLACEHOLDER_MEMBER
from app.exceptions.validation import ValidationError
from app.graph.nodes.input_node import input_node


def _state(members_input, must_link="", cannot_link=""):
    return {
        "members_input": members_input,
        "must_link_groups_input": must_link,
        "cannot_link_groups_input": cannot_link,
    }


def test_collapses_repeated_spaces_instead_of_creating_blank_member():
    result = input_node(_state("a  b c"))

    assert "" not in result["members"]
    assert result["members"] == ["a", "b", "c", PLACEHOLDER_MEMBER]


def test_even_member_count_is_not_padded():
    result = input_node(_state("a b c d"))

    assert result["members"] == ["a", "b", "c", "d"]


def test_rejects_duplicate_members():
    with pytest.raises(ValidationError):
        input_node(_state("a a b"))


def test_must_link_group_with_unknown_member_is_rejected():
    with pytest.raises(ValidationError):
        input_node(_state("a b c", must_link="a-z"))
