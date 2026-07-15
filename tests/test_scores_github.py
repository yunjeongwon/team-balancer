import base64
import json
from unittest.mock import MagicMock, patch

import pytest
import requests

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
    assert kwargs["params"] == {"ref": "scores-data"}


def test_save_github_fetches_sha_then_puts(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "abc")
    fake_get = _fake_contents_response({"alice": 5}, sha="sha-xyz")
    with patch.object(ls, "requests") as mock_req:
        mock_req.get.return_value = MagicMock(json=MagicMock(return_value=fake_get))
        mock_req.put.return_value = MagicMock(status_code=200)

        ls._save_github({"alice": 7})

    # 1) GET 호출 (sha 조회)
    assert mock_req.get.called

    # 2) PUT 호출 — 본문에 sha, branch, message, base64 content 포함
    _, kwargs = mock_req.put.call_args
    body = kwargs["json"]
    assert body["sha"] == "sha-xyz"
    assert body["branch"] == "scores-data"
    assert body["message"] == "chore(scores): update via app"
    decoded = json.loads(base64.b64decode(body["content"]).decode("utf-8"))
    assert decoded == {"scores": {"alice": 7}}


def test_load_scores_uses_github_when_token_present(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "abc")
    with patch.object(ls, "_load_github", return_value={"x": 1}) as gh, \
         patch.object(ls, "_load_local") as loc:
        assert ls.load_scores() == {"x": 1}
    assert gh.called and not loc.called


def test_load_scores_uses_local_when_no_token(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    with patch.object(ls, "_load_github") as gh, \
         patch.object(ls, "_load_local", return_value={"y": 2}) as loc:
        assert ls.load_scores() == {"y": 2}
    assert loc.called and not gh.called


def test_save_scores_uses_github_when_token_present(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "abc")
    with patch.object(ls, "_save_github") as gh, \
         patch.object(ls, "_save_local") as loc:
        ls.save_scores({"x": 1})
    assert gh.called and not loc.called


def test_save_scores_uses_local_when_no_token(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    with patch.object(ls, "_save_github") as gh, \
         patch.object(ls, "_save_local") as loc:
        ls.save_scores({"y": 2})
    assert loc.called and not gh.called


def test_load_github_propagates_http_error_on_404(monkeypatch):
    # raise_for_status 가 HTTPError 를 던지면 그대로 전파되어야 한다.
    monkeypatch.setenv("GITHUB_TOKEN", "abc")
    with patch.object(ls, "requests") as mock_req:
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = requests.HTTPError(
            "404 Client Error: Not Found"
        )
        mock_req.get.return_value = mock_resp
        with pytest.raises(requests.HTTPError):
            ls._load_github()


def test_save_github_propagates_http_error_on_409(monkeypatch):
    # PUT 의 raise_for_status 가 409 를 던지면 그대로 전파되어야 한다.
    monkeypatch.setenv("GITHUB_TOKEN", "abc")
    fake_get = _fake_contents_response({"alice": 5}, sha="sha-xyz")
    with patch.object(ls, "requests") as mock_req:
        mock_req.get.return_value = MagicMock(
            json=MagicMock(return_value=fake_get)
        )
        put_resp = MagicMock()
        put_resp.raise_for_status.side_effect = requests.HTTPError(
            "409 Server Error: Conflict"
        )
        mock_req.put.return_value = put_resp
        with pytest.raises(requests.HTTPError):
            ls._save_github({"alice": 7})


def test_load_github_raises_runtime_error_on_malformed_payload(monkeypatch):
    # content 키가 없는 malformed payload 는 RuntimeError 로 명확히 전달.
    monkeypatch.setenv("GITHUB_TOKEN", "abc")
    with patch.object(ls, "requests") as mock_req:
        mock_req.get.return_value = MagicMock(
            json=MagicMock(return_value={"sha": "abc"})
        )
        with pytest.raises(RuntimeError, match="scores.json 형식이 올바르지 않습니다"):
            ls._load_github()
