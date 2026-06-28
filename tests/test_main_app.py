from streamlit.testing.v1 import AppTest

from app.constants import PLACEHOLDER_MEMBER
from app.schemas.evaluation_schema import EvaluationSchema
from app.schemas.team_schema import TeamSchema


def _generate(at, members_text):
    at.text_input[0].input(members_text).run()
    at.button[0].click().run()


def test_each_new_generation_gets_a_fresh_thread_id(fake_llm):
    at = AppTest.from_file("app/main.py")
    at.run()

    _generate(at, "a b")
    thread_1 = at.session_state["thread_id"]

    _generate(at, "c d e f")
    thread_2 = at.session_state["thread_id"]

    assert thread_1 != thread_2


def test_empty_placeholder_member_is_not_shown_to_the_user(fake_llm):
    fake_llm.team_responses = [
        TeamSchema(team_a=["a", PLACEHOLDER_MEMBER], team_b=["b", "c"], score_diff=0, reason="fake")
    ]

    at = AppTest.from_file("app/main.py")
    at.run()
    _generate(at, "a b c")

    rendered = at.chat_message[-1].markdown[0].value
    assert PLACEHOLDER_MEMBER not in rendered


def test_fail_status_is_surfaced_to_the_user(fake_llm):
    fake_llm.eval_responses = [
        EvaluationSchema(status="FAIL", reason="cannot_link 위반: a, b가 같은 팀")
    ]

    at = AppTest.from_file("app/main.py")
    at.run()
    _generate(at, "a b")

    rendered = at.chat_message[-1].markdown[0].value
    assert "검증 실패" in rendered
    assert "cannot_link 위반: a, b가 같은 팀" in rendered


def test_feedback_reaches_the_prompt_as_plain_text_not_a_dict(fake_llm):
    at = AppTest.from_file("app/main.py")
    at.run()
    _generate(at, "a b")

    at.chat_input[0].set_value("a와 b는 같은 팀으로").run()

    retry_prompt_text = fake_llm.team_prompts[-1][-1].content
    assert "a와 b는 같은 팀으로" in retry_prompt_text
    assert "{'feedback'" not in retry_prompt_text
