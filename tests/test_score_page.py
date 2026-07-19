import json

from streamlit.testing.v1 import AppTest

from app.utils import load_scores as ls

PAGE = "app/pages/2_점수_관리.py"


def _seed(tmp_path, monkeypatch, scores):
    fake_path = tmp_path / "scores.json"
    fake_path.write_text(
        json.dumps({"scores": scores}, ensure_ascii=False), encoding="utf-8"
    )
    monkeypatch.setattr(ls, "_scores_path", lambda: fake_path)
    return fake_path


def _run(tmp_path, monkeypatch, scores):
    _seed(tmp_path, monkeypatch, scores)
    at = AppTest.from_file(PAGE)
    at.session_state["authenticated"] = True
    at.run()
    return at


def _button(at, label):
    return next(b for b in at.button if b.label == label)


def _num(at, key):
    return next(n for n in at.number_input if n.key == key)


def test_add_form_rejects_empty_name(tmp_path, monkeypatch):
    at = _run(tmp_path, monkeypatch, {"김동영": 7})
    _button(at, "추가").click().run()
    assert any("이름을 입력해주세요" in e.value for e in at.error)


def test_add_form_rejects_existing_name(tmp_path, monkeypatch):
    at = _run(tmp_path, monkeypatch, {"김동영": 7})
    at.text_input[0].set_value("김동영").run()
    _button(at, "추가").click().run()
    assert any("이미 등록된 선수" in e.value for e in at.error)


def test_add_form_rejects_duplicate_pending(tmp_path, monkeypatch):
    at = _run(tmp_path, monkeypatch, {"김동영": 7})
    at.text_input[0].set_value("신규").run()
    _button(at, "추가").click().run()
    at.text_input[0].set_value("신규").run()
    _button(at, "추가").click().run()
    assert any("이미 추가 대기 중" in e.value for e in at.error)


def test_add_then_save_persists(tmp_path, monkeypatch):
    fake_path = _seed(tmp_path, monkeypatch, {"김동영": 7})
    at = AppTest.from_file(PAGE)
    at.session_state["authenticated"] = True
    at.run()

    at.text_input[0].set_value("신규").run()  # 점수는 기본값 3(=default_score)
    _button(at, "추가").click().run()
    _button(at, "저장").click().run()

    saved = json.loads(fake_path.read_text(encoding="utf-8"))["scores"]
    assert saved == {"김동영": 7, "신규": 3}


def test_revert_clears_pending(tmp_path, monkeypatch):
    at = _run(tmp_path, monkeypatch, {"김동영": 7})
    at.text_input[0].set_value("신규").run()
    _button(at, "추가").click().run()
    assert at.session_state["pending_adds"] == [{"이름": "신규", "점수": 3}]

    _button(at, "되돌리기").click().run()
    assert at.session_state["pending_adds"] == []


def test_save_button_disabled_when_no_changes(tmp_path, monkeypatch):
    at = _run(tmp_path, monkeypatch, {"김동영": 7})
    assert _button(at, "저장").disabled is True


def test_save_failure_preserves_pending(tmp_path, monkeypatch):
    at = _run(tmp_path, monkeypatch, {"김동영": 7})
    at.text_input[0].set_value("신규").run()
    _button(at, "추가").click().run()
    assert at.session_state["pending_adds"] == [{"이름": "신규", "점수": 3}]

    def _boom(*args, **kwargs):
        raise RuntimeError("network down")

    # 페이지는 매 rerun 마다 `from app.utils.load_scores import save_scores` 를
    # 재실행하므로 원본 모듈의 save_scores 를 패치하면 다음 run 에서 반영된다.
    monkeypatch.setattr(ls, "save_scores", _boom)

    _button(at, "저장").click().run()

    assert any("저장 중 오류" in e.value for e in at.error)
    # 실패 시 rerun/정리 없이 편집이 보존되어야 한다.
    assert at.session_state["pending_adds"] == [{"이름": "신규", "점수": 3}]


def test_settings_save_persists(tmp_path, monkeypatch):
    fake_path = _seed(tmp_path, monkeypatch, {"김동영": 7})
    at = AppTest.from_file(PAGE)
    at.session_state["authenticated"] = True
    at.run()

    _num(at, "default_score_input").set_value(2).run()
    _num(at, "max_score_input").set_value(6).run()
    _button(at, "설정 저장").click().run()

    raw = json.loads(fake_path.read_text(encoding="utf-8"))
    assert raw["settings"] == {"default_score": 2, "max_score": 6}
    assert raw["scores"] == {"김동영": 7}  # scores 보존


def test_settings_rejects_default_above_max(tmp_path, monkeypatch):
    fake_path = _seed(tmp_path, monkeypatch, {"김동영": 7})
    at = AppTest.from_file(PAGE)
    at.session_state["authenticated"] = True
    at.run()

    _num(at, "max_score_input").set_value(2).run()
    _num(at, "default_score_input").set_value(5).run()
    _button(at, "설정 저장").click().run()

    assert any("기본 점수는 최고 점수보다" in e.value for e in at.error)
    raw = json.loads(fake_path.read_text(encoding="utf-8"))
    assert "settings" not in raw  # 저장되지 않음


def test_number_inputs_reflect_stored_settings(tmp_path, monkeypatch):
    fake_path = tmp_path / "scores.json"
    fake_path.write_text(
        json.dumps(
            {"scores": {"김동영": 5}, "settings": {"default_score": 3, "max_score": 5}}
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(ls, "_scores_path", lambda: fake_path)
    at = AppTest.from_file(PAGE)
    at.session_state["authenticated"] = True
    at.run()

    assert _num(at, "default_score_input").value == 3
    assert _num(at, "max_score_input").value == 5
