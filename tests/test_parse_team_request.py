import pytest

from app.exceptions.validation import ValidationError
from app.utils.parse_team_request import parse_team_request


def test_parses_section_based_team_request():
    result = parse_team_request(
        """
팀원:
강병의
김성인
박규원
박종민

묶음:
박규원-박종민

분리:
박종민/김성인
강병의/박규원
"""
    )

    assert result == {
        "members_input": "강병의 김성인 박규원 박종민",
        "must_link_groups_input": "박규원-박종민",
        "cannot_link_groups_input": "박종민/김성인, 강병의/박규원",
    }


def test_allows_comma_separated_group_lines():
    result = parse_team_request(
        """
팀원:
a b c d

묶음:
a-b, c-d

분리:
a/c, b/d
"""
    )

    assert result["members_input"] == "a b c d"
    assert result["must_link_groups_input"] == "a-b, c-d"
    assert result["cannot_link_groups_input"] == "a/c, b/d"


def test_parses_inline_section_headers():
    result = parse_team_request(
        """
팀원: 강병의 김성인 김형욱 박규원 박종민
묶음: 박규원-박종민
분리: 박종민/김성인
"""
    )

    assert result == {
        "members_input": "강병의 김성인 김형욱 박규원 박종민",
        "must_link_groups_input": "박규원-박종민",
        "cannot_link_groups_input": "박종민/김성인",
    }


def test_rejects_request_without_members_section():
    with pytest.raises(ValidationError, match="팀원 섹션"):
        parse_team_request(
            """
묶음:
a-b
"""
        )
