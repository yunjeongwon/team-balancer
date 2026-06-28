import app.graph.builder as builder_mod


def test_graph_builder_compiles_with_expected_nodes(fake_llm):
    app = builder_mod.graph_builder()
    graph = app.get_graph()

    assert set(graph.nodes) == {
        "__start__",
        "__end__",
        "input",
        "score_fetch",
        "team_generator",
        "evaluator",
        "human_approval",
    }
