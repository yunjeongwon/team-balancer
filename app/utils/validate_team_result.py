from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class TeamValidationResult:
    status: Literal["PASS", "FAIL"]
    reason: str


def _member_team_map(team_a: list[str], team_b: list[str]) -> dict[str, str]:
    member_team = {}
    for member in team_a:
        member_team[member] = "team_a"
    for member in team_b:
        member_team[member] = "team_b"
    return member_team


def validate_team_result(
    members: list[str],
    team_a: list[str],
    team_b: list[str],
    must_link_groups: list[list[str]],
    cannot_link_groups: list[list[str]],
) -> TeamValidationResult:
    errors = []
    expected_members = set(members)
    assigned_members = team_a + team_b
    assigned_member_set = set(assigned_members)

    if len(team_a) != len(team_b):
        errors.append(f"팀 인원 수 불일치: team_a {len(team_a)}명, team_b {len(team_b)}명")

    missing_members = sorted(expected_members - assigned_member_set)
    if missing_members:
        errors.append(f"멤버 누락: {', '.join(missing_members)}")

    unknown_members = sorted(assigned_member_set - expected_members)
    if unknown_members:
        errors.append(f"존재하지 않는 멤버 포함: {', '.join(unknown_members)}")

    duplicated_members = sorted(
        member for member in assigned_member_set if assigned_members.count(member) > 1
    )
    if duplicated_members:
        errors.append(f"멤버 중복: {', '.join(duplicated_members)}")

    member_team = _member_team_map(team_a, team_b)

    for group in must_link_groups:
        teams = {member_team.get(member) for member in group}
        if len(teams) != 1 or None in teams:
            errors.append(f"must_link 위반: {', '.join(group)} 멤버가 같은 팀에 있지 않음")

    for group in cannot_link_groups:
        seen_teams = {}
        for member in group:
            team = member_team.get(member)
            if team is None:
                continue
            if team in seen_teams:
                errors.append(
                    f"cannot_link 위반: {seen_teams[team]}, {member} 멤버가 같은 팀에 있음"
                )
                break
            seen_teams[team] = member

    if errors:
        return TeamValidationResult(status="FAIL", reason="; ".join(errors))

    return TeamValidationResult(status="PASS", reason="모든 Hard Constraint를 만족합니다.")
