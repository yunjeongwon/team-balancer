import pandas as pd
import streamlit as st

from app.utils.load_scores import load_scores, save_scores

st.title("점수 관리")
st.caption(
    "선수 이름과 실력 점수(1~7)를 관리합니다. 저장하면 다음 팀 생성에 반영됩니다. "
    "표 헤더(이름/점수)를 클릭하면 정렬됩니다."
)


def _current_scores() -> dict[str, int]:
    try:
        return load_scores()
    except Exception as e:  # 파일 손상/부재
        st.error(f"scores.json 을 불러오지 못했습니다: {e}")
        st.stop()


scores = _current_scores()

# --- 조회: 정렬 가능한 읽기 전용 표 ---
df = pd.DataFrame([{"이름": name, "점수": score} for name, score in scores.items()])
st.dataframe(
    df,
    hide_index=True,
    use_container_width=True,
    column_config={
        "이름": st.column_config.TextColumn("이름"),
        "점수": st.column_config.NumberColumn("점수", format="%d"),
    },
    column_order=["이름", "점수"],
)

st.divider()

# --- 추가 / 수정 ---
st.subheader("추가 / 수정")
with st.form("upsert_form"):
    name = st.text_input("이름 (이미 있으면 점수가 수정됩니다)")
    score = st.number_input("점수", min_value=1, max_value=7, step=1, value=4)
    upsert_submitted = st.form_submit_button("저장", type="primary")

if upsert_submitted:
    name = name.strip()
    if not name:
        st.error("이름을 입력해주세요.")
    else:
        action = "수정" if name in scores else "추가"
        try:
            save_scores({**scores, name: int(score)})
        except Exception as e:
            st.error(f"저장 중 오류가 발생했습니다: {e}")
        else:
            st.success(f"{name} {action}되었습니다. (점수 {int(score)})")
            st.rerun()

# --- 삭제 ---
st.subheader("삭제")
with st.form("delete_form"):
    to_delete = st.multiselect("삭제할 선수", options=sorted(scores.keys()))
    delete_submitted = st.form_submit_button("삭제")

if delete_submitted:
    if not to_delete:
        st.error("삭제할 선수를 선택해주세요.")
    else:
        targets = set(to_delete)
        try:
            save_scores({k: v for k, v in scores.items() if k not in targets})
        except Exception as e:
            st.error(f"저장 중 오류가 발생했습니다: {e}")
        else:
            st.success(f"{len(to_delete)}명 삭제되었습니다: {', '.join(to_delete)}")
            st.rerun()
