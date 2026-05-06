from app.graph.state import TeamState
from app.utils.parse_pairs_input import parse_group_input

def input_node(state: TeamState) -> TeamState:
    members_input = state["members_input"]
    must_link_groups_input = state["must_link_groups_input"]
    cannot_link_groups_input = state["cannot_link_groups_input"]
    members = members_input.split(" ")

    if len(members) % 2 == 1:
        members.append('공석')

    must_link_groups = parse_group_input(must_link_groups_input, "-")
    cannot_link_groups = parse_group_input(cannot_link_groups_input, "/")

    message = f"입력 파싱 완료"
    print(message)

    return {
        "messages": [message],
        "members": members,
        "must_link_groups": must_link_groups,
        "cannot_link_groups": cannot_link_groups,
    }
