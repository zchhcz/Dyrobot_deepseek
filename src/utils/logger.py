import logging
import sys
from pathlib import Path


def setup_logger(name: str = "dyrobot", level: int = logging.DEBUG, log_file: str = "dyrobot_debug.log") -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.propagate = False  # 防止重复输出

    if not logger.handlers:
        # 控制台输出
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_fmt = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        console_handler.setFormatter(console_fmt)
        logger.addHandler(console_handler)

        # 文件输出（DEBUG级别）
        try:
            log_path = Path(log_file)
            file_handler = logging.FileHandler(log_path, encoding="utf-8")
            file_handler.setLevel(logging.DEBUG)
            file_fmt = logging.Formatter(
                "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
            file_handler.setFormatter(file_fmt)
            logger.addHandler(file_handler)
        except Exception as e:
            print(f"Warning: Could not set up file logger: {e}", file=sys.stderr)

    return logger


def get_logger(name: str = "dyrobot") -> logging.Logger:
    return logging.getLogger(name)
