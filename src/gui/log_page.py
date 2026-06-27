"""Log page — real-time colored log viewer with filtering and search."""

from collections import deque
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit,
    QCheckBox, QLineEdit, QPushButton, QLabel,
)
from PyQt6.QtCore import Qt, QTimer, pyqtSlot
from PyQt6.QtGui import QFont, QTextCursor, QColor

from .thread_safety import LogRecord, LOG_COLORS


class LogPage(QWidget):
    """Real-time log viewer with level filtering and search."""

    MAX_BUFFER = 10000
    BATCH_INTERVAL_MS = 100

    def __init__(self, parent=None):
        super().__init__(parent)

        # Ring buffer for re-rendering when filters change
        self._buffer: deque[LogRecord] = deque(maxlen=self.MAX_BUFFER)
        self._pending: list[LogRecord] = []

        # Filter state
        self._show_debug = False
        self._show_info = True
        self._show_warning = True
        self._show_error = True
        self._search_text = ""
        self._auto_scroll = True

        self._build_ui()

        # Batch timer: collect records for BATCH_INTERVAL_MS, then render
        self._batch_timer = QTimer(self)
        self._batch_timer.timeout.connect(self._flush_pending)
        self._batch_timer.start(self.BATCH_INTERVAL_MS)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # ── Toolbar ──
        toolbar = QHBoxLayout()

        toolbar.addWidget(QLabel("级别:"))

        self._debug_cb = QCheckBox("DEBUG")
        self._debug_cb.setChecked(False)
        self._debug_cb.toggled.connect(self._on_filter_changed)
        toolbar.addWidget(self._debug_cb)

        self._info_cb = QCheckBox("INFO")
        self._info_cb.setChecked(True)
        self._info_cb.toggled.connect(self._on_filter_changed)
        toolbar.addWidget(self._info_cb)

        self._warn_cb = QCheckBox("WARNING")
        self._warn_cb.setChecked(True)
        self._warn_cb.toggled.connect(self._on_filter_changed)
        toolbar.addWidget(self._warn_cb)

        self._err_cb = QCheckBox("ERROR")
        self._err_cb.setChecked(True)
        self._err_cb.toggled.connect(self._on_filter_changed)
        toolbar.addWidget(self._err_cb)

        toolbar.addSpacing(16)

        toolbar.addWidget(QLabel("搜索:"))
        self._search_box = QLineEdit()
        self._search_box.setPlaceholderText("输入关键词筛选...")
        self._search_box.setMaximumWidth(200)
        self._search_box.textChanged.connect(self._on_search_changed)
        toolbar.addWidget(self._search_box)

        toolbar.addStretch()

        self._autoscroll_cb = QCheckBox("自动滚动")
        self._autoscroll_cb.setChecked(True)
        self._autoscroll_cb.toggled.connect(self._on_autoscroll_toggled)
        toolbar.addWidget(self._autoscroll_cb)

        clear_btn = QPushButton("清空")
        clear_btn.setMaximumWidth(60)
        clear_btn.clicked.connect(self._clear)
        toolbar.addWidget(clear_btn)

        layout.addLayout(toolbar)

        # ── Log output ──
        self._view = QTextEdit()
        self._view.setReadOnly(True)
        self._view.setFont(QFont("Consolas", 10))
        self._view.setStyleSheet("""
            QTextEdit {
                background: #181825;
                border: 1px solid #585b70;
                border-radius: 6px;
                padding: 4px;
            }
        """)
        layout.addWidget(self._view)

    # ── Public slot ──

    @pyqtSlot(LogRecord)
    def append_log(self, record: LogRecord) -> None:
        """Receive a log record (called from LogSignal, main thread safe)."""
        self._buffer.append(record)
        self._pending.append(record)

    # ── Internal rendering ──

    def _flush_pending(self) -> None:
        """Render any pending log records in one batch."""
        if not self._pending:
            return

        records = self._pending
        self._pending = []

        for record in records:
            if not self._passes_filter(record):
                continue

            color = LOG_COLORS.get(record.level, "#cdd6f4")
            escaped = record.message.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

            html = (
                f'<span style="color:#6c7086;">{self._format_time(record.timestamp)}</span> '
                f'<span style="color:{color};font-weight:bold;">[{record.level}]</span> '
                f'<span style="color:{color};">{escaped}</span>'
            )
            self._view.append(html)

        if self._auto_scroll:
            cursor = self._view.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            self._view.setTextCursor(cursor)

    def _passes_filter(self, record: LogRecord) -> bool:
        """Check if a record passes level filter and search filter."""
        # Level filter
        if record.level == "DEBUG" and not self._show_debug:
            return False
        if record.level == "INFO" and not self._show_info:
            return False
        if record.level == "WARNING" and not self._show_warning:
            return False
        if record.level in ("ERROR", "CRITICAL") and not self._show_error:
            return False

        # Search filter
        if self._search_text and self._search_text.lower() not in record.message.lower():
            return False

        return True

    def _re_render(self) -> None:
        """Clear and re-render all buffered records (for filter changes)."""
        self._view.clear()
        for record in self._buffer:
            if self._passes_filter(record):
                color = LOG_COLORS.get(record.level, "#cdd6f4")
                escaped = record.message.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                html = (
                    f'<span style="color:#6c7086;">{self._format_time(record.timestamp)}</span> '
                    f'<span style="color:{color};font-weight:bold;">[{record.level}]</span> '
                    f'<span style="color:{color};">{escaped}</span>'
                )
                self._view.append(html)

        if self._auto_scroll:
            cursor = self._view.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            self._view.setTextCursor(cursor)

    @staticmethod
    def _format_time(timestamp: float) -> str:
        """Format a Unix timestamp as HH:MM:SS."""
        import time
        return time.strftime("%H:%M:%S", time.localtime(timestamp))

    # ── Slots ──

    def _on_filter_changed(self) -> None:
        self._show_debug = self._debug_cb.isChecked()
        self._show_info = self._info_cb.isChecked()
        self._show_warning = self._warn_cb.isChecked()
        self._show_error = self._err_cb.isChecked()
        self._re_render()

    def _on_search_changed(self, text: str) -> None:
        self._search_text = text
        self._re_render()

    def _on_autoscroll_toggled(self, checked: bool) -> None:
        self._auto_scroll = checked

    def _clear(self) -> None:
        self._buffer.clear()
        self._pending.clear()
        self._view.clear()
