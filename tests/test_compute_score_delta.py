from app.utils.compute_score_delta import compute_score_delta


def _row(name, score, deleted=False):
    return {"이름": name, "점수": score, "삭제": deleted}


def test_no_changes_returns_all_empty():
    current = {"김": 5, "이": 3}
    rows = [_row("김", 5), _row("이", 3)]
    adds, edits, deletes = compute_score_delta(current, rows)
    assert adds == {}
    assert edits == {}
    assert deletes == set()


def test_score_edit_only():
    current = {"김": 5, "이": 3}
    rows = [_row("김", 7), _row("이", 3)]
    adds, edits, deletes = compute_score_delta(current, rows)
    assert adds == {}
    assert edits == {"김": 7}
    assert deletes == set()


def test_add_only():
    current = {"김": 5}
    rows = [_row("김", 5), _row("신규", 4)]
    adds, edits, deletes = compute_score_delta(current, rows)
    assert adds == {"신규": 4}
    assert edits == {}
    assert deletes == set()


def test_delete_only():
    current = {"김": 5, "이": 3}
    rows = [_row("김", 5), _row("이", 3, deleted=True)]
    adds, edits, deletes = compute_score_delta(current, rows)
    assert adds == {}
    assert edits == {}
    assert deletes == {"이"}


def test_combined_add_edit_delete():
    current = {"김": 5, "이": 3, "박": 1}
    rows = [_row("김", 6), _row("이", 3, deleted=True), _row("박", 1), _row("신규", 2)]
    adds, edits, deletes = compute_score_delta(current, rows)
    assert adds == {"신규": 2}
    assert edits == {"김": 6}
    assert deletes == {"이"}


def test_pending_add_marked_deleted_is_noop():
    # 추가 대기 행을 삭제 체크하면 순증감 0: adds/edits/deletes 모두 비어야 한다.
    current = {"김": 5}
    rows = [_row("김", 5), _row("신규", 4, deleted=True)]
    adds, edits, deletes = compute_score_delta(current, rows)
    assert adds == {}
    assert edits == {}
    assert deletes == set()


def test_score_coerced_to_int():
    # data_editor 는 numpy int 를 줄 수 있으므로 int 로 강제되는지 확인.
    current = {"김": 5}
    rows = [_row("김", 7.0)]  # float 입력도 int 로
    _adds, edits, _deletes = compute_score_delta(current, rows)
    assert edits == {"김": 7}
    assert isinstance(edits["김"], int)


def test_blank_score_on_existing_player_is_noop_not_delete():
    # 점수 셀을 비운 기존 선수: 삭제되지 않고, 수정도 아니다 (기존 값 유지).
    current = {"김": 5}
    rows = [_row("김", float("nan"))]
    adds, edits, deletes = compute_score_delta(current, rows)
    assert adds == {}
    assert edits == {}
    assert deletes == set()


def test_none_score_is_treated_as_blank():
    current = {"김": 5}
    rows = [_row("김", None)]
    adds, edits, deletes = compute_score_delta(current, rows)
    assert (adds, edits, deletes) == ({}, {}, set())
