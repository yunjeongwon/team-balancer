def format_score_groups(
    score_groups: dict[int, list[str]]
) -> str:
    lines = []

    for score, members in score_groups.items():
        lines.append(
            f"{score}: {', '.join(members)}"
        )

    return "\n".join(lines)