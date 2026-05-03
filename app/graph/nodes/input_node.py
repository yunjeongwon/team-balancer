from app.graph.state import TeamState

def input_node(state: TeamState) -> TeamState:
    raw_input = state["raw_input"]
    members = raw_input.split(" ")

    if len(members) % 2 == 1:
        members.append('공석')

    message = f"입력: {raw_input}\n split 완료"

    print(message)

    return {
        "messages": [message],
        "raw_input": state["raw_input"],
        "members": members,
    }