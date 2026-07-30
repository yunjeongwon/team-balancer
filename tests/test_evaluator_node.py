from app.graph.nodes.evaluator_node import evaluator_node


class _EvaluatorShouldNotRun:
    def invoke(self, _prompt):
        raise AssertionError("점수 차이가 최적값보다 크면 LLM 평가 전에 실패해야 합니다.")


def test_evaluator_rejects_a_team_split_worse_than_the_best_score_balance():
    member_scores = {"a": 7, "b": 6, "c": 5, "d": 4, "e": 3, "f": 2}

    result = evaluator_node(
        {
            "members": list(member_scores),
            "member_scores": member_scores,
            "team_a": ["a", "b", "c"],
            "team_b": ["d", "e", "f"],
            "must_link_groups": [],
            "cannot_link_groups": [],
        },
        _EvaluatorShouldNotRun(),
    )

    assert result["evaluation_status"] == "FAIL"
    assert "현재 9점 차이" in result["evaluation_reason"]
    assert "최소 점수 차이는 1점" in result["evaluation_reason"]


def test_evaluator_replaces_a_second_unbalanced_attempt_with_optimal_teams():
    member_scores = {"a": 7, "b": 6, "c": 5, "d": 4, "e": 3, "f": 2}

    result = evaluator_node(
        {
            "members": list(member_scores),
            "member_scores": member_scores,
            "team_a": ["a", "b", "c"],
            "team_b": ["d", "e", "f"],
            "must_link_groups": [],
            "cannot_link_groups": [],
            "evaluation_count": 1,
        },
        _EvaluatorShouldNotRun(),
    )

    assert result["evaluation_status"] == "PASS"
    assert result["score_diff"] == 1
    assert "코드 기반 최적 균형 조합" in result["evaluation_reason"]
