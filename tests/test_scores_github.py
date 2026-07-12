import base64
import json
from unittest.mock import MagicMock, patch

from app.utils import load_scores as ls


def _fake_contents_response(scores_dict, sha="abc123"):
    content = base64.b64encode(
        json.dumps({"scores": scores_dict}, ensure_ascii=False).encode("utf-8")
    ).decode("ascii")
    return {"content": content, "sha": sha, "encoding": "base64"}


def test_get_token_prefers_env(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "env-token")
    assert ls._get_token() == "env-token"


def test_get_token_returns_none_when_absent(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    # 테스트 컨텍스트에선 st.secrets 도 unavailable → None
    assert ls._get_token() is None


def test_headers_includes_authorization_and_accept(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "abc")
    h = ls._headers()
    assert h["Authorization"] == "token abc"
    assert h["Accept"] == "application/vnd.github+json"


def test_load_github_decodes_base64_and_returns_scores(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "abc")
    fake = _fake_contents_response({"alice": 5, "bob": 3})
    with patch.object(ls, "requests") as mock_req:
        mock_req.get.return_value = MagicMock(json=MagicMock(return_value=fake))
        result = ls._load_github()
    assert result == {"alice": 5, "bob": 3}
    # 올바른 URL 과 ref 파라미터 호출 검증
    _, kwargs = mock_req.get.call_args
    assert kwargs["params"] == {"ref": "master"}
