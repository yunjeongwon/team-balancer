import streamlit as st
from dotenv import load_dotenv
from app.graph.builder import graph_builder

load_dotenv()

st.title("Team Balancer")

input_container = st.container()

with input_container:
    members_input = st.text_input("팀원 이름 (띄어쓰기)")
    cannot_link_groups_input = st.text_input("분리 그룹 (선택) 예: a/b, c/d")
    must_link_groups_input = st.text_input("묶음 그룹 (선택) 예: a-b, c-d-e")
    button_clicked = st.button("팀생성")

if button_clicked:
    if not members_input: 
        st.warning("팀원을 입력해주세요.")
    else:
        with st.chat_message("human"):
            st.write(f"팀원: {members_input}")
            st.write(f"분리 그룹: {cannot_link_groups_input}")
            st.write(f"묶음 그룹: {must_link_groups_input}")

        msg = st.info("팀 생성 중 ..")
        app = graph_builder()
        config = {
            "configurable": {
                "thread_id": "user-1"
            }
        }

        res = app.invoke(
            {
                "members_input": members_input,
                "must_link_groups_input": must_link_groups_input,
                "cannot_link_groups_input": cannot_link_groups_input,
            },
            config=config,
        )

        with st.chat_message("assistant"):
            st.markdown(f"🔵 블루팀\n\n{' '.join(res['team_a'])}")
            st.markdown(f"🟡 골드팀\n\n{' '.join(res['team_b'])}")

        msg.empty()
        st.info("팀 생성 완료")
