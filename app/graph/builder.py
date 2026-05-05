from app.graph.nodes.evaluator_node import evaluator_node
from app.graph.nodes.input_node import input_node
from app.graph.nodes.score_fetch_node import score_fetch_node
from app.graph.nodes.team_generator_node import team_generator_node
from app.graph.state import TeamState
from langgraph.graph import START, StateGraph, END
from app.llm.model import get_model
from app.schemas.evaluation_schema import EvaluationSchema
from app.schemas.team_schema import TeamSchema
from langgraph.checkpoint.memory import InMemorySaver

def graph_builder():
    builder = StateGraph(TeamState)

    llm = get_model()
    team_generator_llm = llm.with_structured_output(TeamSchema)
    evaluator_llm = llm.with_structured_output(EvaluationSchema)

    builder.add_node("input", input_node)
    builder.add_node("score_fetch", score_fetch_node)
    builder.add_node("team_generator", lambda state: team_generator_node(state, team_generator_llm))
    builder.add_node("evaluator", lambda state: evaluator_node(state, evaluator_llm))

    builder.add_edge(START, "input")
    builder.add_edge("input", "score_fetch")
    builder.add_edge("score_fetch", "team_generator")
    builder.add_edge("team_generator", "evaluator")

    def evaluator_continue(state):
        if state["evaluation_status"] == "PASS":
            return END

        if state["evaluation_count"] >= 2:
            return END

        return "team_generator"

    builder.add_conditional_edges(
        "evaluator",
        evaluator_continue,
        ["team_generator", END]
    )

    app = builder.compile(checkpointer=InMemorySaver())

    return app