import os

import streamlit as st
from dotenv import load_dotenv
from streamlit.errors import StreamlitSecretNotFoundError

load_dotenv()


def require_auth() -> None:
    """공유 비밀번호 게이트. 각 페이지 스크립트 맨 위에서 호출한다.

    인증 전에는 로그인 폼을 보여주고 st.stop() 으로 페이지 본문 렌더를 막는다.
    한 번 인증하면 session_state.authenticated 가 세션 전체에 유지돼
    다른 페이지로 이동해도 재로그인할 필요가 없다.

    APP_PASSWORD: 로컬 .env 우선, 없으면 Streamlit Secrets(prod) 사용.
    (secrets.toml 자체가 없으면 st.secrets.get 가 에러를 던지므로 env 우선)
    """
    if st.session_state.get("authenticated", False):
        return

    st.subheader("🔒 로그인")
    expected_pw = os.environ.get("APP_PASSWORD", "")
    if not expected_pw:
        try:
            expected_pw = st.secrets.get("APP_PASSWORD", "")
        except StreamlitSecretNotFoundError:
            expected_pw = ""

    with st.form("login"):
        pw = st.text_input("비밀번호를 입력하세요", type="password")
        submitted = st.form_submit_button("로그인")

    if submitted:
        if pw and pw == expected_pw:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("비밀번호가 올바르지 않습니다.")

    st.stop()
