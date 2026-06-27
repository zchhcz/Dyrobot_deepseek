"""Thread-safety primitives and shared data types for the dyrobot GUI.

These types are passed across thread boundaries via Qt signals,
so they must use simple built-in types (str, int, float, bool, dict, list).
"""

from dataclasses import dataclass, field
from enum import Enum, auto


class BotStatus(Enum):
    """Bot lifecycle states."""
    STOPPED = auto()
    STARTING = auto()
    RUNNING = auto()
    STOPPING = auto()
    ERROR = auto()


@dataclass
class LogRecord:
    """A single log entry, safe to pass across Qt signal boundaries."""
    timestamp: float
    level: str
    logger_name: str
    message: str


@dataclass
class GroupStats:
    """Per-group monitoring statistics."""
    group_id: str = ""
    message_count: int = 0
    last_message: str = ""
    online: bool = True


# Log level → QColor name mapping (used by LogPage for syntax-highlighting)
LOG_COLORS: dict[str, str] = {
    "DEBUG":    "#6c7086",   # gray
    "INFO":     "#cdd6f4",   # white
    "WARNING":  "#f9e2af",   # yellow
    "ERROR":    "#f38ba8",   # red
    "CRITICAL": "#f38ba8",   # red (bold)
}

# BotStatus → description + color mapping
STATUS_INFO: dict[BotStatus, tuple[str, str]] = {
    BotStatus.STOPPED:  ("已停止", "#f38ba8"),   # red
    BotStatus.STARTING: ("启动中", "#f9e2af"),   # yellow
    BotStatus.RUNNING:  ("运行中", "#a6e3a1"),   # green
    BotStatus.STOPPING: ("停止中", "#f9e2af"),   # yellow
    BotStatus.ERROR:    ("错误",   "#f38ba8"),   # red
}
