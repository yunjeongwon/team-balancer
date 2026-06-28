from app.exceptions.validation import ValidationError
from app.graph.state import TeamState
from app.utils.parse_pairs_input import parse_group_input

def input_node(state: TeamState) -> TeamState:
    members_input = state["members_input"]
    must_link_groups_input = state["must_link_groups_input"]
    cannot_link_groups_input = state["cannot_link_groups_input"]

    # members_input => members
    members = members_input.split()

    member_set = set(members)
    if len(member_set) != len(members):
        raise ValidationError("중복된 팀원이 존재합니다.")

    # 짝수 맞추기
    if len(members) % 2 == 1:
        members.append('EMPTY')

    # groups_input => groups
    must_link_groups = parse_group_input(must_link_groups_input, "-")
    cannot_link_groups = parse_group_input(cannot_link_groups_input, "/")
    
    # validation
    for group in must_link_groups + cannot_link_groups:
        for member in group:
            if member not in member_set:
                raise ValidationError(
                f"존재하지 않는 팀원이 포함되어 있습니다: {member}"
            )

    message = f"입력 파싱 완료"
    print(message)

    return {
        "messages": [message],
        "members": members,
        "must_link_groups": must_link_groups,
        "cannot_link_groups": cannot_link_groups,
    }
