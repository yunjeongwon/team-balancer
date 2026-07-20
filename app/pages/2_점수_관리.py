import sys
from pathlib import Path

# Streamlit Cloud는 레포 루트를 sys.path에 넣지 않으므로 app.* 임포트 전에 직접 추가한다.
# 페이지 스크립트는 main.py를 거치지 않고 독립 실행될 수 있어 여기에도 필요하다.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pandas as pd
import streamlit as st

from app.auth import require_auth
from app.utils.compute_score_delta import compute_score_delta
from app.utils.load_scores import load_scores, load_settings, save_scores, save_settings

require_auth()

_settings = load_settings()
default_score = _settings["default_score"]
max_score = _settings["max_score"]

st.title("점수 관리")
st.caption(
    f"선수 이름과 실력 점수(1~{max_score})를 관리합니다. 점수 셀을 눌러 수정하고, 삭제할 선수는 "
    "삭제 열을 체크한 뒤 저장하세요. 표 헤더(이름/점수)를 클릭하면 정렬됩니다."
)

# 직전 저장 결과 메시지. st.rerun() 직전의 st.success/toast 는 rerun 에 의해
# 무시되므로 session_state 로 넘겨 여기서 표시한다.
if "score_action_msg" in st.session_state:
    st.toast(st.session_state.score_action_msg, icon="✅")
    del st.session_state.score_action_msg

if "pending_adds" not in st.session_state:
    st.session_state.pending_adds = []


def _current_scores() -> dict[str, int]:
    try:
        return load_scores()
    except Exception as e:  # 파일 손상/부재
        st.error(f"scores.json 을 불러오지 못했습니다: {e}")
        st.stop()


scores = _current_scores()

# --- 추가: 접이식 폼 (배치에 참여, 즉시 저장 안 함) ---
with st.expander("선수 추가"):
    with st.form("add_form", clear_on_submit=True):
        new_name = st.text_input("이름")
        new_score = st.number_input(
            "점수", min_value=1, max_value=max_score, value=default_score, step=1
        )
        add_submitted = st.form_submit_button("추가")

    if add_submitted:
        name = new_name.strip()
        pending_names = {a["이름"] for a in st.session_state.pending_adds}
        if not name:
            st.error("이름을 입력해주세요.")
        elif name in scores:
            st.error("이미 등록된 선수입니다. 표에서 점수를 수정하세요.")
        elif name in pending_names:
            st.error("이미 추가 대기 중인 이름입니다.")
        else:
            st.session_state.pending_adds.append(
                {"이름": name, "점수": int(new_score)}
            )
            st.rerun()

# --- 편집 표: 기존 선수(이름순) + 추가 대기 행(끝에 append) ---
table_rows = [
    {"이름": name, "점수": score, "삭제": False}
    for name, score in sorted(scores.items())
]
table_rows += [
    {"이름": a["이름"], "점수": a["점수"], "삭제": False}
    for a in st.session_state.pending_adds
]
df = pd.DataFrame(table_rows, columns=["이름", "점수", "삭제"])

edited = st.data_editor(
    df,
    key="score_editor",
    num_rows="fixed",  # 정렬 유지 (dynamic/add 는 정렬 비활성)
    hide_index=True,
    disabled=["이름"],  # 이름 잠금: 오타로 새 선수가 생기는 사고 방지
    column_config={
        "이름": st.column_config.TextColumn("이름"),
        "점수": st.column_config.NumberColumn(
            "점수", min_value=1, max_value=max_score, step=1, format="%d", required=True
        ),
        "삭제": st.column_config.CheckboxColumn("삭제"),
    },
    column_order=["이름", "점수", "삭제"],
)

adds, edits, deletes = compute_score_delta(scores, edited.to_dict("records"))
has_changes = bool(adds or edits or deletes)

st.caption(f"추가 {len(adds)} · 수정 {len(edits)} · 삭제 {len(deletes)}")

save_col, revert_col = st.columns(2)
save_clicked = save_col.button(
    "저장", type="primary", disabled=not has_changes
)
revert_clicked = revert_col.button("되돌리기")

if revert_clicked:
    st.session_state.pop("score_editor", None)
    st.session_state.pending_adds = []
    st.rerun()

if save_clicked:
    try:
        with st.spinner("저장 중..."):
            save_scores(updates={**adds, **edits}, deletes=deletes)
    except Exception as e:
        # 실패 시 rerun 하지 않아 표의 편집을 보존한다.
        st.error(f"저장 중 오류가 발생했습니다: {e}")
    else:
        st.session_state.pop("score_editor", None)
        st.session_state.pending_adds = []
        st.session_state.score_action_msg = (
            f"저장되었습니다. (추가 {len(adds)} · 수정 {len(edits)} · 삭제 {len(deletes)})"
        )
        st.rerun()

st.divider()

# --- 기본 설정: 미등록자 기본 점수 / 최고 점수 (표 저장과 별개, 즉시 저장) ---
with st.expander("기본 설정"):
    with st.form("settings_form"):
        default_input = st.number_input(
            "미등록 인원에게 적용할 점수",
            min_value=1, max_value=max_score, value=default_score, step=1,
            key="default_score_input",
        )
        max_input = st.number_input(
            "최고 점수",
            min_value=1, max_value=20, value=max_score, step=1,
            key="max_score_input",
        )
        settings_submitted = st.form_submit_button("설정 저장")

    if settings_submitted:
        if default_input > max_input:
            st.error("기본 점수는 최고 점수보다 클 수 없습니다.")
        else:
            over = sorted(n for n, s in scores.items() if s > max_input)
            try:
                save_settings(
                    default_score=int(default_input), max_score=int(max_input)
                )
            except Exception as e:
                st.error(f"저장 중 오류가 발생했습니다: {e}")
            else:
                msg = f"설정이 저장되었습니다. (기본 {int(default_input)} · 최고 {int(max_input)})"
                if over:
                    msg += (
                        f" ⚠️ {len(over)}명이 최고점을 초과합니다: {', '.join(over)}"
                    )
                st.session_state.score_action_msg = msg
                st.rerun()
