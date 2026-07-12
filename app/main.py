from langgraph.types import Command
import streamlit as st
from streamlit.errors import StreamlitSecretNotFoundError
from dotenv import load_dotenv
from app.constants import PLACEHOLDER_MEMBER
from app.exceptions.validation import ValidationError
from app.graph.builder import graph_builder
from app.logging_config import configure_run_logging
from app.utils.compute_team_score_sum import compute_team_score_sum
from app.utils.parse_team_request import parse_team_request
from pathlib import Path
import os
import uuid

load_dotenv()

@st.cache_resource
def get_app(graph_code_stamp: tuple[tuple[str, int], ...]):
    return graph_builder()


def graph_code_stamp() -> tuple[tuple[str, int], ...]:
    project_root = Path(__file__).resolve().parent.parent
    graph_files = [
        "app/graph/builder.py",
        "app/graph/nodes/input_node.py",
        "app/graph/nodes/score_fetch_node.py",
        "app/graph/nodes/team_generator_node.py",
        "app/graph/nodes/evaluator_node.py",
        "app/graph/nodes/human_approval_node.py",
        "app/utils/build_balanced_teams.py",
        "app/utils/validate_team_result.py",
    ]

    return tuple(
        (file_path, (project_root / file_path).stat().st_mtime_ns)
        for file_path in graph_files
    )


def build_team_message(values: dict, include_scores: bool = True) -> str:
    team_a_members = [m for m in values["team_a"] if m != PLACEHOLDER_MEMBER]
    team_b_members = [m for m in values["team_b"] if m != PLACEHOLDER_MEMBER]

    if include_scores:
        member_scores = values["member_scores"]
        team_a = " ".join(_format_member_with_score(member, member_scores) for member in team_a_members)
        team_b = " ".join(_format_member_with_score(member, member_scores) for member in team_b_members)
        team_a_title = f"🔵 블루팀 (총점: {compute_team_score_sum(team_a_members, member_scores)})"
        team_b_title = f"🟡 골드팀 (총점: {compute_team_score_sum(team_b_members, member_scores)})"
    else:
        team_a = " ".join(team_a_members)
        team_b = " ".join(team_b_members)
        team_a_title = "🔵 블루팀"
        team_b_title = "🟡 골드팀"

    message = f"{team_a_title}\n\n{team_a}\n\n{team_b_title}\n\n{team_b}"

    if values.get("evaluation_status") == "FAIL":
        message += f"\n\n⚠️ 검증 실패 (자동 재시도 한도 도달)\n{values.get('evaluation_reason', '')}"

    return message


def _format_member_with_score(member: str, member_scores: dict[str, int]) -> str:
    return f"{member}({member_scores[member]})"


app = get_app(graph_code_stamp())

# --- 비밀번호 게이트 (shared password) ---
# APP_PASSWORD: 로컬 .env 우선, 없으면 Streamlit Secrets(prod) 사용.
# (secrets.toml 자체가 없으면 st.secrets.get 가 에러를 던지므로 env 우선)
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.title("Team Balancer")
    expected_pw = os.environ.get("APP_PASSWORD", "")
    if not expected_pw:
        try:
            expected_pw = st.secrets.get("APP_PASSWORD", "")
        except StreamlitSecretNotFoundError:
            expected_pw = ""
    pw = st.text_input("비밀번호를 입력하세요", type="password")
    if st.button("로그인"):
        if pw and pw == expected_pw:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("비밀번호가 올바르지 않습니다.")
    st.stop()

st.title("Team Balancer")

input_container = st.container()

with input_container:
    team_request_input = st.text_area(
        "팀 구성 입력",
        placeholder="""팀원:
강병의
김성인
박규원
박종민

묶음:
박규원-박종민

분리:
박종민/김성인""",
        height=320,
    )
    team_create_button_clicked = st.button("팀 생성")

if "awaiting_approval" not in st.session_state:
    st.session_state.awaiting_approval = False

if "config" not in st.session_state:
    st.session_state.config = None

if "messages" not in st.session_state:
    st.session_state.messages = []

if team_create_button_clicked:
    st.session_state.awaiting_approval = False
    st.session_state.config = None

    if not team_request_input.strip():
        st.warning("팀원을 입력해주세요.")
    else:
        msg = None
        try:
            parsed_request = parse_team_request(team_request_input)

            st.session_state.thread_id = str(uuid.uuid4())
            configure_run_logging(st.session_state.thread_id)

            st.session_state.messages.append({
                "role": "user",
                "content": team_request_input,
            })

            msg = st.info("팀 생성 중 ..")

            config = {
                "configurable": {
                    "thread_id": st.session_state.thread_id
                }
            }

            app.invoke(
                {
                    "members_input": parsed_request["members_input"],
                    "must_link_groups_input": parsed_request["must_link_groups_input"],
                    "cannot_link_groups_input": parsed_request["cannot_link_groups_input"],
                    "default_score": 4,
                },
                config=config,
            )

            snapshot = app.get_state(config)

            if snapshot.next:
                st.session_state.awaiting_approval = True
                st.session_state.config = config

                values = snapshot.values
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": build_team_message(values),
                })

            msg.empty()
        except ValidationError as e:
            if msg:
                msg.empty()
            st.error(str(e) + ". 입력을 수정한 후 다시 팀 생성 버튼을 눌러주세요.")
        except Exception as e:
            if msg:
                msg.empty()
            st.error("알 수 없는 오류가 발생했습니다. 입력을 수정한 후 다시 팀 생성 버튼을 눌러주세요.")
            st.exception(e)

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if st.session_state.awaiting_approval:
    msg = st.info("팀 생성 완료. 수정 사항이 있으면 입력해주세요.")

    if st.button("이대로 확정"):
        snapshot = app.get_state(st.session_state.config)
        values = snapshot.values
        st.session_state.messages.append({
            "role": "assistant",
            "content": build_team_message(values, include_scores=False),
        })

        st.session_state.awaiting_approval = False
        st.rerun()

    feedback_input = st.chat_input(
        "예: 김철수와 박영희는 같은 팀으로",
    )

    if feedback_input:
        st.session_state.messages.append({
            "role": "user",
            "content": feedback_input,
        })

        msg.empty()
        msg = st.info("수정 반영 중 ..")

        try:
            configure_run_logging(st.session_state.thread_id)
            app.invoke(
                Command(resume=feedback_input),
                config=st.session_state.config,
            )

            snapshot = app.get_state(st.session_state.config)
            values = snapshot.values

            st.session_state.messages.append({
                "role": "assistant",
                "content": build_team_message(values),
            })
        except Exception as e:
            msg.empty()
            st.error("수정 반영 중 오류가 발생했습니다. 다시 시도해주세요.")
            st.exception(e)
        else:
            msg.empty()
            st.rerun()
