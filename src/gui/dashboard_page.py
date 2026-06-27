"""Dashboard page — bot status overview, start/stop controls, recent messages."""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QGroupBox, QListWidget, QListWidgetItem, QFrame,
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QColor

from .thread_safety import BotStatus, STATUS_INFO


class DashboardPage(QWidget):
    """Main dashboard showing bot status, controls, and recent activity."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._status: BotStatus = BotStatus.STOPPED
        self._uptime_seconds: int = 0
        self._uptime_timer = QTimer(self)
        self._uptime_timer.timeout.connect(self._tick_uptime)

        self._start_callback = None
        self._stop_callback = None

        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(16)

        # ── Header ──
        title = QLabel("dyrobot")
        title.setProperty("cssClass", "title")
        title.setFont(QFont("Microsoft YaHei", 24, QFont.Weight.Bold))
        layout.addWidget(title)

        subtitle = QLabel("抖音群聊 AI 机器人控制面板")
        subtitle.setProperty("cssClass", "subtitle")
        layout.addWidget(subtitle)

        layout.addSpacing(8)

        # ── Status Card ──
        status_group = QGroupBox("运行状态")
        status_layout = QVBoxLayout(status_group)

        # Status line: indicator + text + uptime
        status_row = QHBoxLayout()
        self._status_indicator = QLabel("●")
        self._status_indicator.setFont(QFont("Arial", 16))
        self._status_indicator.setFixedWidth(28)
        status_row.addWidget(self._status_indicator)

        self._status_label = QLabel("已停止")
        self._status_label.setFont(QFont("Microsoft YaHei", 14, QFont.Weight.Bold))
        status_row.addWidget(self._status_label)

        status_row.addStretch()

        self._uptime_label = QLabel("")
        self._uptime_label.setStyleSheet("color: #a6adc8;")
        status_row.addWidget(self._uptime_label)

        status_layout.addLayout(status_row)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("background: #45475a; max-height: 1px;")
        status_layout.addWidget(sep)

        # Control buttons
        btn_row = QHBoxLayout()
        self._start_btn = QPushButton("▶  启动机器人")
        self._start_btn.setProperty("cssClass", "success")
        self._start_btn.setMinimumHeight(44)
        self._start_btn.clicked.connect(self._on_start)
        btn_row.addWidget(self._start_btn)

        self._stop_btn = QPushButton("■  停止机器人")
        self._stop_btn.setProperty("cssClass", "danger")
        self._stop_btn.setMinimumHeight(44)
        self._stop_btn.setEnabled(False)
        self._stop_btn.clicked.connect(self._on_stop)
        btn_row.addWidget(self._stop_btn)

        status_layout.addLayout(btn_row)
        layout.addWidget(status_group)

        # ── Recent Messages ──
        msg_group = QGroupBox("最近消息")
        msg_layout = QVBoxLayout(msg_group)

        self._msg_list = QListWidget()
        self._msg_list.setAlternatingRowColors(True)
        self._msg_list.setMaximumHeight(400)
        self._msg_list.setFont(QFont("Consolas", 10))
        msg_layout.addWidget(self._msg_list)

        clear_btn = QPushButton("清空")
        clear_btn.setMaximumWidth(80)
        clear_btn.clicked.connect(self._msg_list.clear)
        msg_layout.addWidget(clear_btn, alignment=Qt.AlignmentFlag.AlignRight)

        layout.addWidget(msg_group)
        layout.addStretch()

    # ── Public API ──

    def set_callbacks(self, on_start, on_stop) -> None:
        """Register the start/stop callbacks (called by MainWindow)."""
        self._start_callback = on_start
        self._stop_callback = on_stop

    def update_status(self, status: BotStatus) -> None:
        """Update the displayed bot status."""
        self._status = status
        desc, color = STATUS_INFO.get(status, ("未知", "#6c7086"))
        self._status_label.setText(desc)
        self._status_indicator.setStyleSheet(f"color: {color};")

        # Enable/disable buttons based on status
        is_running = status in (BotStatus.RUNNING, BotStatus.STARTING)
        self._start_btn.setEnabled(status == BotStatus.STOPPED)
        self._stop_btn.setEnabled(is_running)

        # Manage uptime timer
        if status == BotStatus.RUNNING:
            self._uptime_seconds = 0
            self._uptime_timer.start(1000)
        else:
            self._uptime_timer.stop()
            if status != BotStatus.STOPPING:
                self._uptime_label.setText("")

    def append_message(self, group_id: str, user_name: str, content: str) -> None:
        """Add a received message to the feed."""
        item = QListWidgetItem(f"📩 [{group_id}] {user_name}: {content}")
        item.setForeground(QColor("#89b4fa"))
        self._msg_list.insertItem(0, item)
        self._trim_list()

    def append_sent(self, group_id: str, content: str) -> None:
        """Add a sent reply to the feed."""
        item = QListWidgetItem(f"📤 [{group_id}] Bot: {content}")
        item.setForeground(QColor("#a6e3a1"))
        self._msg_list.insertItem(0, item)
        self._trim_list()

    def _trim_list(self, max_items: int = 200) -> None:
        """Keep the message list from growing unbounded."""
        while self._msg_list.count() > max_items:
            self._msg_list.takeItem(self._msg_list.count() - 1)

    def _tick_uptime(self) -> None:
        """Update the uptime display every second."""
        self._uptime_seconds += 1
        m, s = divmod(self._uptime_seconds, 60)
        h, m = divmod(m, 60)
        if h > 0:
            self._uptime_label.setText(f"运行 {h}h {m}m {s}s")
        elif m > 0:
            self._uptime_label.setText(f"运行 {m}m {s}s")
        else:
            self._uptime_label.setText(f"运行 {s}s")

    def _on_start(self) -> None:
        if self._start_callback:
            self._start_callback()

    def _on_stop(self) -> None:
        if self._stop_callback:
            self._stop_callback()
