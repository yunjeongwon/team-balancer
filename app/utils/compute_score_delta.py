def compute_score_delta(
    current: dict[str, int],
    rows: list[dict],
) -> tuple[dict[str, int], dict[str, int], set[str]]:
    """편집된 표 행과 현재 점수를 비교해 (추가, 수정, 삭제) 를 계산한다.

    rows 의 각 원소는 {"이름", "점수", "삭제"} 키를 가진다. 삭제 체크된 행은
    유지 집합(kept)에서 빠지므로, 기존 선수면 deletes 로, 추가 대기 행이면
    아무 델타도 만들지 않는다(순증감 0).
    """
    kept = {r["이름"]: int(r["점수"]) for r in rows if not r["삭제"]}
    adds = {name: score for name, score in kept.items() if name not in current}
    edits = {
        name: score
        for name, score in kept.items()
        if name in current and current[name] != score
    }
    deletes = set(current) - set(kept)
    return adds, edits, deletes
