from app.graph.state import TeamState

def input_node(state: TeamState) -> TeamState:
    raw_input = state["raw_input"]
    members = raw_input.split(" ")

    if len(members) % 2 == 1:
        members.append('공석')

    return {
        "raw_input": state["raw_input"],
        "members": members,
    }