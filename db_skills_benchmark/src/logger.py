import logging
from rich.logging import RichHandler
from db_skills_benchmark.src.config import get_logs_dir

def setup_logger(run_timestamp: str) -> logging.Logger:
    logger = logging.getLogger("db_skills_benchmark")
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()

    console_handler = RichHandler(
        rich_tracebacks=True,
        markup=True,
        show_time=True,
        show_path=False,
    )
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter("%(message)s", datefmt="[%X]"))

    logs_dir = get_logs_dir()
    logs_dir.mkdir(parents=True, exist_ok=True)

    log_file = logs_dir / f"db_skills_benchmark_{run_timestamp}.log"
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_format = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler.setFormatter(file_format)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger

def get_logger() -> logging.Logger:
    return logging.getLogger("db_skills_benchmark")
