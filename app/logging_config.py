import logging
from pathlib import Path

LOG_DIR = Path("logs")


def configure_run_logging(thread_id: str) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("team_balancer")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    logger.propagate = False

    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    file_handler = logging.FileHandler(LOG_DIR / f"{thread_id}.log", encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
