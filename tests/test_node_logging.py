import logging

import app.graph.builder as builder_mod


def test_each_node_logs_its_progress_message(fake_llm, caplog):
    app = builder_mod.graph_builder()
    config = {"configurable": {"thread_id": "t-log"}}

    with caplog.at_level(logging.INFO, logger="team_balancer"):
        app.invoke(
            {
                "members_input": "a b",
                "must_link_groups_input": "",
                "cannot_link_groups_input": "",
                "default_score": 4,
            },
            config=config,
        )

    messages = [record.message for record in caplog.records]
    assert "입력 파싱 완료" in messages
    assert "가중치 적용 완료" in messages
    assert "팀 생성 중 .." in messages
    assert "팀 생성 완료" in messages
    assert "'1번째' 검증 중 .." in messages
    assert "'1번째' 검증 완료" in messages
