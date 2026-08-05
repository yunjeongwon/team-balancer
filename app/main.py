import sys
from pathlib import Path

# Streamlit Cloud는 레포 루트를 sys.path에 넣지 않으므로 app.* 임포트 전에 직접 추가한다.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from langgraph.types import Command
import streamlit as st
from dotenv import load_dotenv
from app.auth import require_auth
from app.constants import PLACEHOLDER_MEMBER
from app.exceptions.validation import ValidationError
from app.graph.builder import graph_builder
from app.llm.model import get_default_model_route
from app.logging_config import configure_run_logging
from app.utils.compute_team_score_sum import compute_team_score_sum
from app.utils.load_scores import load_settings
from app.utils.parse_team_request import parse_team_request
from pathlib import Path
import os
import uuid

load_dotenv()

@st.cache_resource
def get_app(graph_code_stamp: tuple[tuple[str, int], ...], model_route: str):
    return graph_builder(model_route)


MODEL_ROUTE_LABELS = {
    "omniroute": "OmniRoute",
    "gemini": "Gemini 3.5 Flash-Lite",
    "gpt": "GPT",
}


def _model_route() -> str:
    if os.environ.get("USE_GPT") == "1":
        return "gpt"
    return st.session_state.get("model_route", get_default_model_route())


def _next_model_route(model_route: str) -> str | None:
    if model_route == "omniroute":
        return "gemini"
    if model_route == "gemini":
        return "gpt"
    return None


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


def build_graph_input(team_request: str) -> dict:
    parsed_request = parse_team_request(team_request)
    return {
        "members_input": parsed_request["members_input"],
        "must_link_groups_input": parsed_request["must_link_groups_input"],
        "cannot_link_groups_input": parsed_request["cannot_link_groups_input"],
        "default_score": load_settings()["default_score"],
    }


def get_original_team_request(messages: list[dict]) -> str | None:
    """현재 세션이 보관한 최초 팀 구성 요청을 찾는다.

    InMemorySaver는 그래프 캐시가 재생성되면 비워질 수 있지만, Streamlit
    세션의 대화 기록은 남아 있을 수 있다. 이전 버전 세션도 복구할 수 있도록
    별도 세션 키가 없을 때는 대화 기록을 보조 수단으로 사용한다.
    """
    saved_request = st.session_state.get("team_request")
    if isinstance(saved_request, str) and saved_request.strip():
        return saved_request

    return next(
        (
            message["content"]
            for message in messages
            if message.get("role") == "user"
            and isinstance(message.get("content"), str)
            and "팀원" in message["content"]
        ),
        None,
    )


def build_team_message(values: dict, include_scores: bool = True) -> str:
    team_a_members = [m for m in values["team_a"] if m != PLACEHOLDER_MEMBER]
    team_b_members = [m for m in values["team_b"] if m != PLACEHOLDER_MEMBER]

    if include_scores:
        member_scores = values["member_scores"]
        # 이전 실행 상태에는 이 필드가 없을 수 있다. 점수 출처가 누락되면
        # 등록 점수가 아닌 기본 점수로 안전하게 표시한다.
        member_score_sources = values.get("member_score_sources", {})
        team_a = " ".join(
            _format_member_with_score(
                member,
                member_scores,
                member_score_sources,
                values["default_score"],
            )
            for member in team_a_members
        )
        team_b = " ".join(
            _format_member_with_score(
                member,
                member_scores,
                member_score_sources,
                values["default_score"],
            )
            for member in team_b_members
        )
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


def _format_member_with_score(
    member: str,
    member_scores: dict[str, int],
    member_score_sources: dict[str, str],
    default_score: int,
) -> str:
    score = member_scores[member]
    if score != default_score:
        return f"{member}({score})"

    source_label = "등록" if member_score_sources.get(member) == "registered" else "기본"
    return f"{member}({score} · {source_label})"


require_auth()

st.title("Team Balancer")

input_container = st.container()

with input_container:
    team_request_input = st.text_area(
        "팀 구성 입력",
        placeholder="""팀원: 강병의 김성인 박규원 박종민

분리: 박종민/김성인

묶음: 박규원-박종민""",
        height=320,
    )
    team_create_button_clicked = st.button("팀 생성")

if "awaiting_approval" not in st.session_state:
    st.session_state.awaiting_approval = False

if "config" not in st.session_state:
    st.session_state.config = None

if "messages" not in st.session_state:
    st.session_state.messages = []

if "generation_error" not in st.session_state:
    st.session_state.generation_error = None

is_retry = st.session_state.pop("pending_generate", False)
should_generate = team_create_button_clicked or is_retry

if team_create_button_clicked:
    # 새 요청은 항상 기본 경로(OmniRoute가 설정됐다면 OmniRoute)부터 시작한다.
    st.session_state.model_route = get_default_model_route()

app = get_app(graph_code_stamp(), _model_route())

fallback_notice = st.session_state.pop("fallback_notice", None)
if fallback_notice:
    st.info(fallback_notice)

if should_generate:
    st.session_state.awaiting_approval = False
    st.session_state.config = None
    st.session_state.generation_error = None

    if not team_request_input.strip():
        st.warning("팀원을 입력해주세요.")
    else:
        msg = None
        try:
            initial_graph_input = build_graph_input(team_request_input)

            st.session_state.thread_id = str(uuid.uuid4())
            configure_run_logging(st.session_state.thread_id)

            if not is_retry:
                st.session_state.messages.append({
                    "role": "user",
                    "content": team_request_input,
                })
                st.session_state.team_request = team_request_input

            msg = st.info("팀 생성 중 ..")

            config = {
                "configurable": {
                    "thread_id": st.session_state.thread_id
                }
            }

            app.invoke(
                initial_graph_input,
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
            current_route = _model_route()
            next_route = _next_model_route(current_route)
            if next_route:
                st.session_state.model_route = next_route
                st.session_state.pending_generate = True
                st.session_state.fallback_notice = (
                    f"{MODEL_ROUTE_LABELS[current_route]} 호출에 실패해 "
                    f"{MODEL_ROUTE_LABELS[next_route]}로 자동 재시도합니다."
                )
                st.rerun()
            st.session_state.generation_error = e

if st.session_state.get("generation_error") is not None:
    st.error("OmniRoute, Gemini, GPT 순차 재시도가 모두 실패했습니다. 잠시 후 다시 시도해주세요.")
    st.exception(st.session_state.generation_error)

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

            # 그래프 캐시가 새로 만들어진 경우 InMemorySaver의 체크포인트는
            # 사라질 수 있다. 그 상태에서 Command(resume)를 호출하면 새 실행이
            # input 노드부터 시작해 members_input KeyError가 난다.
            snapshot = app.get_state(st.session_state.config)
            if "members_input" not in snapshot.values:
                original_request = get_original_team_request(st.session_state.messages)
                if not original_request:
                    raise RuntimeError("기존 팀 구성 입력을 찾을 수 없습니다.")

                app.invoke(
                    build_graph_input(original_request),
                    config=st.session_state.config,
                )

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
