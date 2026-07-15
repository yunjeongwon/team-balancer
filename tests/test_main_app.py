from streamlit.testing.v1 import AppTest

from app.constants import PLACEHOLDER_MEMBER
from app.schemas.team_schema import TeamSchema


def _app():
    """require_auth() 가 st.stop() 으로 본문 렌더를 막으므로 인증된 상태로 시작한다."""
    at = AppTest.from_file("app/main.py")
    at.session_state["authenticated"] = True
    at.run()
    return at


def _generate(at, members_text):
    at.text_area[0].input(
        f"""
팀원:
{members_text}
"""
    ).run()
    at.button[0].click().run()


def _generate_structured(at, request_text):
    at.text_area[0].input(request_text).run()
    at.button[0].click().run()


def test_each_new_generation_gets_a_fresh_thread_id(fake_llm):
    at = _app()

    _generate(at, "a b")
    thread_1 = at.session_state["thread_id"]

    _generate(at, "c d e f")
    thread_2 = at.session_state["thread_id"]

    assert thread_1 != thread_2


def test_structured_textarea_request_reaches_graph(fake_llm):
    at = _app()

    _generate_structured(
        at,
        """
팀원:
a
b
c
d

묶음:
a-b

분리:
a/c
""",
    )

    assert at.session_state["awaiting_approval"] is True


def test_empty_placeholder_member_is_not_shown_to_the_user(fake_llm):
    fake_llm.team_responses = [
        TeamSchema(team_a=["a", PLACEHOLDER_MEMBER], team_b=["b", "c"], score_diff=0, reason="fake")
    ]

    at = _app()
    _generate(at, "a b c")

    rendered = at.chat_message[-1].markdown[0].value
    assert PLACEHOLDER_MEMBER not in rendered


def test_generated_result_shows_member_scores_and_team_totals(fake_llm):
    at = _app()
    _generate(at, "a b")

    rendered = at.chat_message[-1].markdown[0].value
    assert "🔵 블루팀 (총점: 4)" in rendered
    assert "🟡 골드팀 (총점: 4)" in rendered
    assert "a(4)" in rendered
    assert "b(4)" in rendered
    assert "4점" not in rendered


def test_confirm_adds_scoreless_result_without_changing_previous_message(fake_llm):
    at = _app()
    _generate(at, "a b")

    scored_result = at.chat_message[-1].markdown[0].value

    at.button[1].click().run()

    assert at.chat_message[-2].markdown[0].value == scored_result
    assert "총점: 4" in at.chat_message[-2].markdown[0].value
    assert "a(4)" in at.chat_message[-2].markdown[0].value

    rendered = at.chat_message[-1].markdown[0].value
    assert "총점" not in rendered
    assert "(4)" not in rendered
    assert "🔵 블루팀" in rendered
    assert "🟡 골드팀" in rendered


def test_fail_status_is_surfaced_to_the_user(fake_llm):
    fake_llm.team_responses = [
        TeamSchema(team_a=["a"], team_b=["b", "c", "d"], score_diff=0, reason="invalid")
    ]

    at = _app()
    _generate(at, "a b c d")

    at.chat_input[0].set_value("다시 섞어줘").run()

    rendered = at.chat_message[-1].markdown[0].value
    assert "검증 실패" in rendered
    assert "팀 인원 수 불일치" in rendered


def test_feedback_reaches_the_prompt_as_plain_text_not_a_dict(fake_llm):
    at = _app()
    _generate(at, "a b")

    at.chat_input[0].set_value("a와 b는 같은 팀으로").run()

    retry_prompt_text = fake_llm.team_prompts[-1][-1].content
    assert "a와 b는 같은 팀으로" in retry_prompt_text
    assert "{'feedback'" not in retry_prompt_text
