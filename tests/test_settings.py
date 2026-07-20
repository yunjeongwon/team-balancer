import base64
import json
from unittest.mock import MagicMock, patch

from app.constants import DEFAULT_SCORE, MAX_SCORE
from app.utils import load_scores as ls


def test_load_settings_falls_back_to_constants_when_absent(tmp_path, monkeypatch):
    fake_path = tmp_path / "scores.json"
    fake_path.write_text(json.dumps({"scores": {"김": 5}}), encoding="utf-8")
    monkeypatch.setattr(ls, "_scores_path", lambda: fake_path)

    assert ls.load_settings() == {"default_score": DEFAULT_SCORE, "max_score": MAX_SCORE}


def test_load_settings_partial_falls_back_per_key(tmp_path, monkeypatch):
    fake_path = tmp_path / "scores.json"
    fake_path.write_text(
        json.dumps({"scores": {}, "settings": {"default_score": 2}}), encoding="utf-8"
    )
    monkeypatch.setattr(ls, "_scores_path", lambda: fake_path)

    assert ls.load_settings() == {"default_score": 2, "max_score": MAX_SCORE}


def test_load_settings_missing_file_falls_back(tmp_path, monkeypatch):
    monkeypatch.setattr(ls, "_scores_path", lambda: tmp_path / "nope.json")

    assert ls.load_settings() == {"default_score": DEFAULT_SCORE, "max_score": MAX_SCORE}


def test_save_settings_local_preserves_scores(tmp_path, monkeypatch):
    fake_path = tmp_path / "scores.json"
    fake_path.write_text(json.dumps({"scores": {"김": 5}}), encoding="utf-8")
    monkeypatch.setattr(ls, "_scores_path", lambda: fake_path)

    ls.save_settings(default_score=3, max_score=7)

    raw = json.loads(fake_path.read_text(encoding="utf-8"))
    assert raw == {"scores": {"김": 5}, "settings": {"default_score": 3, "max_score": 7}}


def test_save_scores_local_preserves_settings(tmp_path, monkeypatch):
    fake_path = tmp_path / "scores.json"
    fake_path.write_text(
        json.dumps(
            {"scores": {"김": 5}, "settings": {"default_score": 3, "max_score": 7}}
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(ls, "_scores_path", lambda: fake_path)

    ls.save_scores(updates={"이": 2})

    raw = json.loads(fake_path.read_text(encoding="utf-8"))
    assert raw["settings"] == {"default_score": 3, "max_score": 7}
    assert raw["scores"] == {"김": 5, "이": 2}


def test_save_scores_github_preserves_settings(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "abc")
    full = {"scores": {"alice": 5}, "settings": {"default_score": 3, "max_score": 7}}
    content = base64.b64encode(
        json.dumps(full, ensure_ascii=False).encode("utf-8")
    ).decode("ascii")
    fake = {"content": content, "sha": "sha-1", "encoding": "base64"}
    with patch.object(ls, "requests") as mock_req:
        mock_req.get.return_value = MagicMock(json=MagicMock(return_value=fake))
        mock_req.put.return_value = MagicMock(status_code=200)
        ls.save_scores(updates={"bob": 2})

    _, kwargs = mock_req.put.call_args
    decoded = json.loads(base64.b64decode(kwargs["json"]["content"]).decode("utf-8"))
    assert decoded["settings"] == {"default_score": 3, "max_score": 7}
    assert decoded["scores"] == {"alice": 5, "bob": 2}


def test_save_settings_github_preserves_scores(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "abc")
    full = {"scores": {"alice": 5}, "settings": {"default_score": 4, "max_score": 7}}
    content = base64.b64encode(
        json.dumps(full, ensure_ascii=False).encode("utf-8")
    ).decode("ascii")
    fake = {"content": content, "sha": "sha-1", "encoding": "base64"}
    with patch.object(ls, "requests") as mock_req:
        mock_req.get.return_value = MagicMock(json=MagicMock(return_value=fake))
        mock_req.put.return_value = MagicMock(status_code=200)
        ls.save_settings(default_score=2, max_score=6)

    _, kwargs = mock_req.put.call_args
    decoded = json.loads(base64.b64decode(kwargs["json"]["content"]).decode("utf-8"))
    assert decoded["scores"] == {"alice": 5}
    assert decoded["settings"] == {"default_score": 2, "max_score": 6}
    assert kwargs["json"]["sha"] == "sha-1"
