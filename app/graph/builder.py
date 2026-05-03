from app.graph.nodes.formatter_node import formmater_node
from app.graph.nodes.input_node import input_node
from app.graph.nodes.score_fetch_node import score_fetch_node
from app.graph.nodes.team_generator_node import team_generator_node
from app.graph.state import TeamState
from langgraph.graph import START, StateGraph, END
from app.llm.model import get_model
from app.schemas.team_schema import TeamSchema
from langgraph.checkpoint.memory import InMemorySaver

def graph_builder():
    builder = StateGraph(TeamState)

    llm = get_model()
    structured_llm = llm.with_structured_output(TeamSchema)

    builder.add_node("input", input_node)
    builder.add_node("score_fetch", score_fetch_node)
    builder.add_node("team_generator", lambda state: team_generator_node(state, structured_llm))
    # builder.add_node("formmater", lambda state: formmater_node(state, llm))

    builder.add_edge(START, "input")
    builder.add_edge("input", "score_fetch")
    builder.add_edge("score_fetch", "team_generator")
    builder.add_edge("team_generator", END)

    app = builder.compile(checkpointer=InMemorySaver())

    return app