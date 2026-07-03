from app.exceptions.validation import ValidationError


SECTION_MEMBERS = "members"
SECTION_MUST_LINK = "must_link"
SECTION_CANNOT_LINK = "cannot_link"

SECTION_HEADERS = {
    "팀원": SECTION_MEMBERS,
    "묶음": SECTION_MUST_LINK,
    "분리": SECTION_CANNOT_LINK,
}


def parse_team_request(raw_text: str) -> dict[str, str]:
    sections = {
        SECTION_MEMBERS: [],
        SECTION_MUST_LINK: [],
        SECTION_CANNOT_LINK: [],
    }
    current_section = None

    for raw_line in raw_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        header, inline_content = _parse_header(line)
        if header:
            current_section = header
            if inline_content:
                sections[current_section].append(inline_content)
            continue

        if current_section is None:
            raise ValidationError("팀원 섹션을 먼저 입력해주세요.")

        sections[current_section].append(line)

    if not sections[SECTION_MEMBERS]:
        raise ValidationError("팀원 섹션을 입력해주세요.")

    return {
        "members_input": " ".join(sections[SECTION_MEMBERS]),
        "must_link_groups_input": _join_group_lines(sections[SECTION_MUST_LINK]),
        "cannot_link_groups_input": _join_group_lines(sections[SECTION_CANNOT_LINK]),
    }


def _parse_header(line: str) -> tuple[str | None, str]:
    for separator in (":", "："):
        if separator not in line:
            continue

        raw_header, inline_content = line.split(separator, 1)
        header = SECTION_HEADERS.get(raw_header.strip())
        if header:
            return header, inline_content.strip()

    return SECTION_HEADERS.get(line.strip()), ""


def _join_group_lines(lines: list[str]) -> str:
    groups = []
    for line in lines:
        groups.extend(group.strip() for group in line.split(",") if group.strip())
    return ", ".join(groups)
