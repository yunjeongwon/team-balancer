import json

from app.utils import load_scores as ls


def test_save_upsert_round_trips(tmp_path, monkeypatch):
    fake_path = tmp_path / "scores.json"
    monkeypatch.setattr(ls, "_scores_path", lambda: fake_path)

    ls.save_scores(updates={"김": 5, "이": 3})

    assert ls.load_scores() == {"김": 5, "이": 3}


def test_save_preserves_wrapper_structure(tmp_path, monkeypatch):
    fake_path = tmp_path / "scores.json"
    monkeypatch.setattr(ls, "_scores_path", lambda: fake_path)

    ls.save_scores(updates={"김": 5})

    raw = json.loads(fake_path.read_text(encoding="utf-8"))
    assert raw == {"scores": {"김": 5}}


def test_save_is_atomic_no_tmp_left_behind(tmp_path, monkeypatch):
    fake_path = tmp_path / "scores.json"
    monkeypatch.setattr(ls, "_scores_path", lambda: fake_path)

    ls.save_scores(updates={"김": 5})

    assert fake_path.exists()
    assert not (tmp_path / "scores.json.tmp").exists()


def test_save_upsert_merges_onto_existing(tmp_path, monkeypatch):
    # 로컬 read-modify-write: 최신(예전:1) 위에 델타(새이름:5)만 얹는다.
    fake_path = tmp_path / "scores.json"
    fake_path.write_text(json.dumps({"scores": {"예전": 1}}), encoding="utf-8")
    monkeypatch.setattr(ls, "_scores_path", lambda: fake_path)

    ls.save_scores(updates={"새이름": 5})

    assert ls.load_scores() == {"예전": 1, "새이름": 5}


def test_save_delete_removes_only_targeted(tmp_path, monkeypatch):
    fake_path = tmp_path / "scores.json"
    fake_path.write_text(
        json.dumps({"scores": {"김": 5, "이": 3, "박": 1}}), encoding="utf-8"
    )
    monkeypatch.setattr(ls, "_scores_path", lambda: fake_path)

    ls.save_scores(deletes={"이"})

    assert ls.load_scores() == {"김": 5, "박": 1}
