import logging

import app.logging_config as logging_config


def test_configure_run_logging_creates_a_file_named_after_the_thread_id(tmp_path, monkeypatch):
    monkeypatch.setattr(logging_config, "LOG_DIR", tmp_path)

    logging_config.configure_run_logging("thread-abc")
    logging.getLogger("team_balancer").info("hello")

    log_file = tmp_path / "thread-abc.log"
    assert log_file.exists()
    assert "hello" in log_file.read_text(encoding="utf-8")


def test_configure_run_logging_appends_when_called_again_for_the_same_thread_id(tmp_path, monkeypatch):
    monkeypatch.setattr(logging_config, "LOG_DIR", tmp_path)
    logger = logging.getLogger("team_balancer")

    logging_config.configure_run_logging("thread-abc")
    logger.info("first")
    logging_config.configure_run_logging("thread-abc")
    logger.info("second")

    log_file = tmp_path / "thread-abc.log"
    content = log_file.read_text(encoding="utf-8")
    assert "first" in content
    assert "second" in content
