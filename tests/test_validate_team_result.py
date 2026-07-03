from app.utils.validate_team_result import validate_team_result


def test_validates_members_are_split_exactly_once():
    result = validate_team_result(
        members=["a", "b", "c", "d"],
        team_a=["a", "b"],
        team_b=["c", "d"],
        must_link_groups=[],
        cannot_link_groups=[],
    )

    assert result.status == "PASS"


def test_fails_when_team_sizes_are_different():
    result = validate_team_result(
        members=["a", "b", "c", "d"],
        team_a=["a"],
        team_b=["b", "c", "d"],
        must_link_groups=[],
        cannot_link_groups=[],
    )

    assert result.status == "FAIL"
    assert "팀 인원 수 불일치" in result.reason


def test_fails_when_members_are_missing_or_duplicated():
    result = validate_team_result(
        members=["a", "b", "c", "d"],
        team_a=["a", "b"],
        team_b=["b", "x"],
        must_link_groups=[],
        cannot_link_groups=[],
    )

    assert result.status == "FAIL"
    assert "누락" in result.reason
    assert "중복" in result.reason
    assert "존재하지 않는 멤버" in result.reason


def test_fails_when_link_constraints_are_violated():
    result = validate_team_result(
        members=["a", "b", "c", "d"],
        team_a=["a", "c"],
        team_b=["b", "d"],
        must_link_groups=[["a", "b"]],
        cannot_link_groups=[["c", "a"]],
    )

    assert result.status == "FAIL"
    assert "must_link" in result.reason
    assert "cannot_link" in result.reason
