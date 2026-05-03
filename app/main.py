import streamlit as st
from dotenv import load_dotenv
from app.graph.builder import graph_builder

load_dotenv()

st.title("Team Balancer")

# user_input = st.text_input("팀원 이름을 입력하세요 (띄어쓰기로 구분)")
user_input = st.chat_input("팀원 이름을 입력하세요 (띄어쓰기로 구분)")

if user_input:
    with st.chat_message("human"):
        st.write(user_input)
    msg = st.info("팀 생성 중 ..")
    app = graph_builder()
    config = {
        "configurable": {
            "thread_id": "user-1"
        }
    }

    res = app.invoke(
        {"raw_input": user_input},
        config=config,
    )

    with st.chat_message("assistant"):
        st.markdown(f"🔵 블루팀\n\n{' '.join(res['team_a'])}")
        st.markdown(f"🟡 골드팀\n\n{' '.join(res['team_b'])}")

    msg.empty()
