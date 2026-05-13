from langgraph.types import Command
import streamlit as st
from dotenv import load_dotenv
from app.exceptions.validation import ValidationError
from app.graph.builder import graph_builder
import uuid

load_dotenv()

@st.cache_resource
def get_app():
    return graph_builder()

app = get_app()

st.title("Team Balancer")

input_container = st.container()

with input_container:
    members_input = st.text_input("팀원 이름 (띄어쓰기)")
    cannot_link_groups_input = st.text_input("분리 그룹 (선택) 예: a/b, c/d")
    must_link_groups_input = st.text_input("묶음 그룹 (선택) 예: a-b, c-d-e")
    team_create_button_clicked = st.button("팀 생성")

if "thread_id" not in st.session_state:
    st.session_state.thread_id = str(uuid.uuid4())

if "awaiting_approval" not in st.session_state:
    st.session_state.awaiting_approval = False

if "config" not in st.session_state:
    st.session_state.config = None

if "messages" not in st.session_state:
    st.session_state.messages = []

if team_create_button_clicked:
    st.session_state.awaiting_approval = False
    st.session_state.config = None

    if not members_input: 
        st.warning("팀원을 입력해주세요.")
    else:
        st.session_state.messages.append({
            "role": "user",
            "content": f"""
            팀원: {members_input}

            분리 그룹: {cannot_link_groups_input}

            묶음 그룹: {must_link_groups_input}
        """})

        msg = st.info("팀 생성 중 ..")

        try:
            config = {
                "configurable": {
                    "thread_id": st.session_state.thread_id
                }
            }

            app.invoke(
                {
                    "members_input": members_input,
                    "must_link_groups_input": must_link_groups_input,
                    "cannot_link_groups_input": cannot_link_groups_input,
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
                    "content": f"🔵 블루팀\n\n{' '.join(values['team_a'])}\n\n🟡 골드팀\n\n{' '.join(values['team_b'])}"
                })

            msg.empty()
        except ValidationError as e:
            msg.empty()
            st.error(str(e) + ". 입력을 수정한 후 다시 팀 생성 버튼을 눌러주세요.")
        except Exception as e:
            msg.empty()
            st.error("알 수 없는 오류가 발생했습니다. 입력을 수정한 후 다시 팀 생성 버튼을 눌러주세요.")
            st.exception(e)

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if st.session_state.awaiting_approval:
    snapshot = app.get_state(st.session_state.config)

    values = snapshot.values

    msg = st.info("팀 생성 완료. 수정 사항이 있으면 입력해주세요.")

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

        res = app.invoke(
            Command(
                resume={
                    "feedback": feedback_input
                },
            ),
            config=st.session_state.config,
        )

        msg.empty()

        snapshot = app.get_state(st.session_state.config)

        values = snapshot.values

        st.session_state.messages.append({
            "role": "assistant",
            "content": f"🔵 블루팀\n\n{' '.join(values['team_a'])}\n\n🟡 골드팀\n\n{' '.join(values['team_b'])}"
        })
        st.rerun()
