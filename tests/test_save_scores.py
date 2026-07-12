import json

from app.utils import load_scores as ls


def test_save_then_load_round_trips(tmp_path, monkeypatch):
    fake_path = tmp_path / "scores.json"
    monkeypatch.setattr(ls, "_scores_path", lambda: fake_path)

    ls.save_scores({"김": 5, "이": 3})

    assert ls.load_scores() == {"김": 5, "이": 3}


def test_save_preserves_wrapper_structure(tmp_path, monkeypatch):
    fake_path = tmp_path / "scores.json"
    monkeypatch.setattr(ls, "_scores_path", lambda: fake_path)

    ls.save_scores({"김": 5})

    raw = json.loads(fake_path.read_text(encoding="utf-8"))
    assert raw == {"scores": {"김": 5}}


def test_save_is_atomic_no_tmp_left_behind(tmp_path, monkeypatch):
    fake_path = tmp_path / "scores.json"
    monkeypatch.setattr(ls, "_scores_path", lambda: fake_path)

    ls.save_scores({"김": 5})

    assert fake_path.exists()
    assert not (tmp_path / "scores.json.tmp").exists()


def test_save_overwrites_existing_scores(tmp_path, monkeypatch):
    fake_path = tmp_path / "scores.json"
    fake_path.write_text(json.dumps({"scores": {"예전": 1}}), encoding="utf-8")
    monkeypatch.setattr(ls, "_scores_path", lambda: fake_path)

    ls.save_scores({"새이름": 5})

    assert ls.load_scores() == {"새이름": 5}
