def format_team(team: list[str] | None) -> str:
    if not team:
        return "None"

    return ", ".join(team)