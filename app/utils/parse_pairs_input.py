def parse_group_input(groups_input: str, delimiter: str) -> list[list[str]]:
    groups = []
    for group in groups_input.split(","):
        group = group.strip()
        if not group:
            continue

        members = [m.strip() for m in group.split(delimiter) if m.strip()]
        if len(members) >= 2:
            groups.append(members)
    
    return groups