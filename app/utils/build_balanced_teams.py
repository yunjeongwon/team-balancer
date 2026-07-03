from dataclasses import dataclass
from itertools import combinations

from app.utils.compute_team_score_sum import compute_team_score_sum
from app.utils.validate_team_result import validate_team_result


@dataclass(frozen=True)
class BalancedTeamResult:
    team_a: list[str]
    team_b: list[str]
    score_diff: int
    reason: str


def build_balanced_teams(
    members: list[str],
    member_scores: dict[str, int],
    must_link_groups: list[list[str]],
    cannot_link_groups: list[list[str]],
) -> BalancedTeamResult:
    team_size = len(members) // 2
    best_result = None
    best_sort_key = None

    for team_a_tuple in combinations(members, team_size):
        team_a = list(team_a_tuple)
        team_a_set = set(team_a)
        team_b = [member for member in members if member not in team_a_set]

        validation = validate_team_result(
            members=members,
            team_a=team_a,
            team_b=team_b,
            must_link_groups=must_link_groups,
            cannot_link_groups=cannot_link_groups,
        )
        if validation.status == "FAIL":
            continue

        team_a_score_sum = compute_team_score_sum(team_a, member_scores)
        team_b_score_sum = compute_team_score_sum(team_b, member_scores)
        score_diff = abs(team_a_score_sum - team_b_score_sum)
        score_balance_key = _score_distribution_key(team_a, team_b, member_scores)
        sort_key = (score_diff, score_balance_key, tuple(team_a))

        if best_sort_key is None or sort_key < best_sort_key:
            best_sort_key = sort_key
            best_result = BalancedTeamResult(
                team_a=team_a,
                team_b=team_b,
                score_diff=score_diff,
                reason=(
                    "코드 기반 조합 탐색으로 모든 Hard Constraint를 만족하는 팀을 생성했습니다. "
                    f"team_a_score_sum={team_a_score_sum}, team_b_score_sum={team_b_score_sum}, "
                    f"score_diff={score_diff}"
                ),
            )

    if best_result is None:
        raise ValueError("유효한 팀 조합을 찾을 수 없습니다.")

    return best_result


def _score_distribution_key(
    team_a: list[str],
    team_b: list[str],
    member_scores: dict[str, int],
) -> tuple[int, ...]:
    score_values = sorted(set(member_scores.values()), reverse=True)
    differences = []

    for score in score_values:
        team_a_count = sum(1 for member in team_a if member_scores[member] == score)
        team_b_count = sum(1 for member in team_b if member_scores[member] == score)
        differences.append(abs(team_a_count - team_b_count))

    return tuple(differences)
