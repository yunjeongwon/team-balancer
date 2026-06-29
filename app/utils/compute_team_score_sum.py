def compute_team_score_sum(team: list[str], member_scores: dict[str, int]) -> int:
    return sum(member_scores[member] for member in team)
