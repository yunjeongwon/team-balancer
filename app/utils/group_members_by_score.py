from collections import defaultdict

def group_members_by_score(
    members: list[str],
    member_scores: dict[str, int],
) -> dict[int, list[str]]:
    score_groups = defaultdict(list)

    for member in members:
        score = member_scores.get(member)

        if score is None:
            continue

        score_groups[score].append(member)

    # 높은 점수 순 정렬
    return dict(
        sorted(score_groups.items(), reverse=True)
    )