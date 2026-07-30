import app.graph.nodes.score_fetch_node as score_fetch_mod


def test_score_fetch_preserves_registered_and_default_score_sources(monkeypatch):
    monkeypatch.setattr(score_fetch_mod, "load_scores", lambda: {"등록된": 3})

    result = score_fetch_mod.score_fetch_node(
        {"members": ["등록된", "미등록"], "default_score": 3}
    )

    assert result["member_scores"] == {"등록된": 3, "미등록": 3}
    assert result["member_score_sources"] == {
        "등록된": "registered",
        "미등록": "default",
    }
