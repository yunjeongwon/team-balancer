from dataclasses import dataclass
from itertools import combinations
import random

from app.utils.compute_team_score_sum import compute_team_score_sum
from app.utils.validate_team_result import validate_team_result

# 인원이 많이 몰린 점수대는 실력이 비슷한 사람들이라 인원 수가 한두 명 어긋나도
# 균형에 영향이 적다. 그 층의 "정확히 반반" 강제를 풀어 조합 다양성을 확보한다.
CROWDED_SCORE_TIER_SIZE = 4
CROWDED_TIER_COUNT_ALLOWANCE = 2


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
    best_sort_key = None
    best_results = []

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
        sort_key = (score_diff, score_balance_key)

        if best_sort_key is None or sort_key < best_sort_key:
            best_sort_key = sort_key
            best_results = []

        if sort_key == best_sort_key:
            best_results.append(
                BalancedTeamResult(
                    team_a=team_a,
                    team_b=team_b,
                    score_diff=score_diff,
                    reason=(
                        "코드 기반 조합 탐색으로 모든 Hard Constraint를 만족하는 팀을 생성했습니다. "
                        f"team_a_score_sum={team_a_score_sum}, team_b_score_sum={team_b_score_sum}, "
                        f"score_diff={score_diff}"
                    ),
                )
            )

    if not best_results:
        raise ValueError("유효한 팀 조합을 찾을 수 없습니다.")

    return random.choice(best_results)


def _score_distribution_key(
    team_a: list[str],
    team_b: list[str],
    member_scores: dict[str, int],
) -> tuple[int, ...]:
    score_values = sorted(set(member_scores.values()), reverse=True)
    differences = []

    for score in score_values:
        tier_size = sum(1 for value in member_scores.values() if value == score)
        allowance = (
            CROWDED_TIER_COUNT_ALLOWANCE
            if tier_size >= CROWDED_SCORE_TIER_SIZE
            else 0
        )
        team_a_count = sum(1 for member in team_a if member_scores[member] == score)
        team_b_count = sum(1 for member in team_b if member_scores[member] == score)
        differences.append(max(abs(team_a_count - team_b_count) - allowance, 0))

    return tuple(differences)
