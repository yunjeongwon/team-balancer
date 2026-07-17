import math


def _is_blank_score(score) -> bool:
    """빈 점수 셀은 data_editor 가 None 또는 NaN 으로 돌려준다."""
    return score is None or (isinstance(score, float) and math.isnan(score))


def compute_score_delta(
    current: dict[str, int],
    rows: list[dict],
) -> tuple[dict[str, int], dict[str, int], set[str]]:
    """편집된 표 행과 현재 점수를 비교해 (추가, 수정, 삭제) 를 계산한다.

    삭제 여부는 '삭제' 플래그로만 결정한다(점수 유효성과 무관) — 점수 셀을
    비운 기존 선수가 삭제로 오인돼 사라지는 것을 막는다. 점수가 비어 있으면
    그 행은 추가/수정 델타를 만들지 않는다(기존 값 유지, 페이지 크래시 방지).
    """
    present = {r["이름"] for r in rows if not r["삭제"]}
    deletes = set(current) - present

    adds: dict[str, int] = {}
    edits: dict[str, int] = {}
    for r in rows:
        if r["삭제"] or _is_blank_score(r["점수"]):
            continue
        name = r["이름"]
        score = int(r["점수"])
        if name not in current:
            adds[name] = score
        elif current[name] != score:
            edits[name] = score
    return adds, edits, deletes
