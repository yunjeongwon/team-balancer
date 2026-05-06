def format_groups(groups: list[list[str]]) -> str:
    if not groups:
        return "없음"

    lines = []

    for idx, group in enumerate(groups, start=1):
        lines.append(
            f"Group {idx}: {', '.join(group)}"
        )

    return "\n".join(lines)