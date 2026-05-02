import streamlit as st
from dotenv import load_dotenv
from app.graph.builder import graph_builder

load_dotenv()

# Streamlit UI
st.title("Team Balancer")

# Input field
user_input = st.text_input("팀원 이름을 입력하세요 (띄어쓰기로 구분)")

# 버튼 클릭 시 실행
if st.button("팀 생성"):
    if not user_input.strip():
        st.warning("입력을 먼저 해주세요.")
    else:
        msg = st.info(f"입력: '{user_input}' 검증 중 ..")
        app = graph_builder()
        config = {
            "configurable": {
                "thread_id": "user-1"
            }
        }
        res = app.invoke({
            "raw_input": user_input
        }, config=config)

        print(res)

        # 작업 끝나면
        # msg.empty()

        # graph = build_graph()

        # # LangGraph 실행
        # result = graph.invoke({
        #     "raw_input": user_input
        # })

        # # 결과 출력
        # st.subheader("결과")
        # st.write(result)
