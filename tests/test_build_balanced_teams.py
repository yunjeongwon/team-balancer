from app.utils.build_balanced_teams import build_balanced_teams
from app.utils.validate_team_result import validate_team_result


def test_builds_valid_teams_for_real_world_constraints():
    members = [
        "강병의",
        "김성인",
        "김형욱",
        "박규원",
        "박종민",
        "선윤호",
        "양창온",
        "윤성빈",
        "장진석",
        "정재훈",
        "조환준",
        "최한성",
        "정윤재",
        "박찬준",
        "권순우",
        "웜뱃",
        "셋텟난뉘",
        "세훈",
    ]
    member_scores = {
        "강병의": 4,
        "김성인": 3,
        "김형욱": 4,
        "박규원": 4,
        "박종민": 1,
        "선윤호": 7,
        "양창온": 6,
        "윤성빈": 6,
        "장진석": 4,
        "정재훈": 5,
        "조환준": 3,
        "최한성": 5,
        "정윤재": 4,
        "박찬준": 5,
        "권순우": 2,
        "웜뱃": 4,
        "셋텟난뉘": 4,
        "세훈": 4,
    }

    result = build_balanced_teams(
        members=members,
        member_scores=member_scores,
        must_link_groups=[["박규원", "박종민"]],
        cannot_link_groups=[["박종민", "권순우"], ["조환준", "김성인"]],
    )

    validation = validate_team_result(
        members=members,
        team_a=result.team_a,
        team_b=result.team_b,
        must_link_groups=[["박규원", "박종민"]],
        cannot_link_groups=[["박종민", "권순우"], ["조환준", "김성인"]],
    )
    assert validation.status == "PASS"
    assert len(result.team_a) == 9
    assert len(result.team_b) == 9
    assert result.score_diff == 1


def test_raises_when_constraints_make_balanced_split_impossible():
    members = ["a", "b", "c", "d"]
    member_scores = {member: 4 for member in members}

    try:
        build_balanced_teams(
            members=members,
            member_scores=member_scores,
            must_link_groups=[["a", "b", "c"]],
            cannot_link_groups=[],
        )
    except ValueError as error:
        assert "유효한 팀 조합을 찾을 수 없습니다" in str(error)
    else:
        raise AssertionError("Expected impossible constraints to raise ValueError")
