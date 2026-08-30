import app.utils.build_balanced_teams as balanced_teams_module
from app.utils.build_balanced_teams import _score_distribution_key, build_balanced_teams
from app.utils.validate_team_result import validate_team_result

_CROWDED_TIER_MEMBERS = [
    "송준호",
    "최한성",
    "권순우",
    "김대성",
    "김성인",
    "변석모",
    "유원종",
    "이민재",
    "조환준",
    "김동혁",
    "선윤호",
    "권진현",
    "강병의",
    "김한주",
    "윤재관",
    "빵찬",
    "으게게",
    "테오",
]
_CROWDED_TIER_SCORES = {
    "송준호": 3,
    "최한성": 6,
    "권순우": 2,
    "김대성": 5,
    "김성인": 3,
    "변석모": 4,
    "유원종": 5,
    "이민재": 2,
    "조환준": 3,
    "김동혁": 4,
    "선윤호": 7,
    "권진현": 4,
    "강병의": 5,
    "김한주": 7,
    "윤재관": 4,
    "빵찬": 3,
    "으게게": 3,
    "테오": 3,
}
_CROWDED_TIER_CANNOT_LINK = [["조환준", "김성인"], ["이민재", "권순우"]]


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


def test_crowded_score_tier_tolerates_uneven_headcount():
    scores = {f"m{index}": 3 for index in range(6)}
    scores.update({"high1": 7, "high2": 7})
    even = _score_distribution_key(
        ["m0", "m1", "m2", "high1"], ["m3", "m4", "m5", "high2"], scores
    )
    uneven = _score_distribution_key(
        ["m0", "m1", "m2", "m3", "high1"], ["m4", "m5", "high2"], scores
    )
    assert even == uneven, "6명이 몰린 점수대는 3:3과 4:2를 동등하게 취급해야 한다"

    tier_split = _score_distribution_key(
        ["m0", "m1", "m2", "high1", "high2"], ["m3", "m4", "m5"], scores
    )
    assert tier_split > even, "2명뿐인 점수대는 여전히 1:1로 갈려야 한다"


def test_crowded_tier_allowance_widens_candidates_without_breaking_constraints(
    monkeypatch,
):
    captured = []

    def capture(candidates):
        captured.append(candidates)
        return candidates[0]

    monkeypatch.setattr(balanced_teams_module.random, "choice", capture)

    build_balanced_teams(
        members=_CROWDED_TIER_MEMBERS,
        member_scores=_CROWDED_TIER_SCORES,
        must_link_groups=[],
        cannot_link_groups=_CROWDED_TIER_CANNOT_LINK,
    )

    candidates = captured[0]
    three_point_members = {
        member for member, score in _CROWDED_TIER_SCORES.items() if score == 3
    }
    arrangements = {
        frozenset(set(candidate.team_a) & three_point_members)
        for candidate in candidates
    }
    # 3점층을 3:3으로 못박으면 12가지가 상한이었다.
    assert len(arrangements) > 12

    for candidate in candidates:
        assert candidate.score_diff <= 1
        assert len(candidate.team_a) == len(candidate.team_b) == 9
        assert ("선윤호" in candidate.team_a) != ("김한주" in candidate.team_a)
        validation = validate_team_result(
            members=_CROWDED_TIER_MEMBERS,
            team_a=candidate.team_a,
            team_b=candidate.team_b,
            must_link_groups=[],
            cannot_link_groups=_CROWDED_TIER_CANNOT_LINK,
        )
        assert validation.status == "PASS"


def test_randomly_selects_among_equally_optimal_teams(monkeypatch):
    selections = []

    def select_last(candidates):
        selections.append(candidates)
        return candidates[-1]

    monkeypatch.setattr(balanced_teams_module.random, "choice", select_last)

    result = build_balanced_teams(
        members=["a", "b", "c", "d"],
        member_scores={"a": 3, "b": 3, "c": 3, "d": 3},
        must_link_groups=[],
        cannot_link_groups=[],
    )

    assert len(selections) == 1
    assert len(selections[0]) > 1
    assert result == selections[0][-1]
    assert result.score_diff == 0
