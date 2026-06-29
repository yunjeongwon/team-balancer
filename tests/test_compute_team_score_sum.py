from app.utils.compute_team_score_sum import compute_team_score_sum


def test_sums_each_members_score():
    member_scores = {"a": 5, "b": 3, "c": 4}

    assert compute_team_score_sum(["a", "b"], member_scores) == 8
    assert compute_team_score_sum(["c"], member_scores) == 4


def test_placeholder_member_is_counted_like_any_other_member():
    member_scores = {"a": 5, "(공석)": 4}

    assert compute_team_score_sum(["a", "(공석)"], member_scores) == 9
