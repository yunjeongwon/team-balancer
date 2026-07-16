"""Streamlit Cloud처럼 레포 루트가 sys.path에 없는 환경에서도 진입점 스크립트의
app.* 임포트가 성립하는지 검증한다.

- python -I: cwd와 PYTHONPATH를 sys.path에 넣지 않는다 (Cloud에는 PYTHONPATH가 없음)
- runpy.run_path: streamlit 부트스트랩처럼 스크립트가 있는 폴더만 sys.path에 추가한다

2026-07-16 배포 장애 회귀 테스트: 로컬은 README의 PYTHONPATH=. 로 임포트가 성립했지만
Cloud에서는 ModuleNotFoundError: No module named 'app' 으로 죽었다.
"""

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

ENTRY_SCRIPTS = [
    "app/main.py",
    "app/pages/2_점수_관리.py",
]


@pytest.mark.parametrize("script", ENTRY_SCRIPTS)
def test_entry_script_imports_without_repo_root_on_syspath(script):
    result = subprocess.run(
        [sys.executable, "-I", "-c", f"import runpy; runpy.run_path({script!r})"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert "ModuleNotFoundError" not in result.stderr, result.stderr
