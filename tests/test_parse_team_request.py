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


def test_allows_inline_members_with_an_empty_group_section():
    result = parse_team_request(
        """
팀원: 송준호 김형욱 최한성 강병의 권순우 김상래 김성인 변석모 윤재관 정윤재 홍철민 조환준 김준 김재광 선윤호 안경하세요 둘둘 마포주민

분리: 김성인/조환준

묶음:
"""
    )

    assert result == {
        "members_input": "송준호 김형욱 최한성 강병의 권순우 김상래 김성인 변석모 윤재관 정윤재 홍철민 조환준 김준 김재광 선윤호 안경하세요 둘둘 마포주민",
        "must_link_groups_input": "",
        "cannot_link_groups_input": "김성인/조환준",
    }


def test_rejects_request_without_members_section():
    with pytest.raises(ValidationError, match="팀원 섹션"):
        parse_team_request(
            """
묶음:
a-b
"""
        )
