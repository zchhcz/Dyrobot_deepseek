"""Main window — sidebar navigation, page container, signal orchestration."""

import logging
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QStackedWidget, QPushButton, QButtonGroup, QLabel,
    QStatusBar, QMessageBox, QFrame,
)
from PyQt6.QtCore import Qt, QThread, QTimer
from PyQt6.QtGui import QFont, QIcon

from ..utils.logger import setup_logger
from .thread_safety import BotStatus, STATUS_INFO
from .log_signal import LogSignal, QtLogHandler
from .bot_worker import BotWorker
from .dashboard_page import DashboardPage
from .log_page import LogPage
from .character_page import CharacterPage
from .skill_page import SkillPage
from .settings_page import SettingsPage

logger = setup_logger(__name__)

NAV_ITEMS = [
    ("dashboard",  "📊  仪表盘"),
    ("log",        "📋  日志"),
    ("character",  "🎭  角色"),
    ("skill",      "🔧  技能"),
    ("settings",   "⚙  设置"),
]


class MainWindow(QMainWindow):
    """Top-level application window for dyrobot GUI."""

    def __init__(self, config: dict):
        super().__init__()
        self._config = config
        self._bot_status: BotStatus = BotStatus.STOPPED

        # Thread management
        self._worker_thread: QThread | None = None
        self._worker: BotWorker | None = None

        # Logging bridge
        self._log_signal = LogSignal()
        self._log_handler = QtLogHandler(self._log_signal)

        self._build_ui()
        self._install_log_handler()
        self._connect_signals()

        # Window setup
        self.setWindowTitle("dyrobot — 抖音群聊 AI 机器人")
        self.resize(1100, 720)
        self.setMinimumSize(900, 560)

    # ── UI Construction ────────────────────────────────────────

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)

        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Sidebar ──
        sidebar = self._create_sidebar()
        root.addWidget(sidebar)

        # ── Content stack ──
        self._stack = QStackedWidget()

        # Create all pages.  CharacterPage / SkillPage are created with
        # manager=None and show a placeholder internally.  When the bot
        # starts, set_manager() is called to populate them — no widget
        # swapping needed, so the pages are always at the same stack index.
        self._dashboard_page = DashboardPage()
        self._log_page = LogPage()
        self._character_page = CharacterPage(character_manager=None)
        self._skill_page = SkillPage(skill_manager=None)
        self._settings_page = SettingsPage(self._config)

        self._stack.addWidget(self._dashboard_page)   # 0
        self._stack.addWidget(self._log_page)          # 1
        self._stack.addWidget(self._character_page)    # 2
        self._stack.addWidget(self._skill_page)        # 3
        self._stack.addWidget(self._settings_page)     # 4

        root.addWidget(self._stack, 1)

        # ── Status Bar ──
        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)

        self._status_icon = QLabel("●")
        self._status_text = QLabel("已停止")
        self._status_bar.addWidget(self._status_icon)
        self._status_bar.addWidget(self._status_text)

        self._status_bar.addPermanentWidget(QWidget())  # spacer

        self._char_status = QLabel("角色: —")
        self._char_status.setStyleSheet("color: #a6adc8; padding: 0 12px;")
        self._status_bar.addPermanentWidget(self._char_status)

        self._update_status_display(BotStatus.STOPPED)

    def _create_sidebar(self) -> QWidget:
        """Build the navigation sidebar."""
        sidebar = QFrame()
        sidebar.setFixedWidth(200)
        sidebar.setStyleSheet("""
            QFrame {
                background: #181825;
                border-right: 1px solid #313244;
            }
        """)

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(0, 16, 0, 16)
        layout.setSpacing(4)

        # App branding
        brand = QLabel("  dyrobot")
        brand.setFont(QFont("Microsoft YaHei", 16, QFont.Weight.Bold))
        brand.setStyleSheet("color: #89b4fa; padding: 8px 16px 20px 16px; border: none;")
        layout.addWidget(brand)

        # Nav buttons
        self._nav_group = QButtonGroup(self)
        self._nav_group.setExclusive(True)

        for i, (key, label) in enumerate(NAV_ITEMS):
            btn = QPushButton(label)
            btn.setProperty("cssClass", "nav-btn")
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda checked, idx=i: self._stack.setCurrentIndex(idx))
            self._nav_group.addButton(btn, i)
            layout.addWidget(btn)

        layout.addStretch()

        # Version
        version = QLabel("v2.0.0")
        version.setStyleSheet("color: #45475a; font-size: 11px; padding: 8px 16px; border: none;")
        version.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(version)

        # Select first button by default
        first_btn = self._nav_group.button(0)
        if first_btn:
            first_btn.setChecked(True)

        return sidebar

    # ── Signal Wiring ──────────────────────────────────────────

    def _connect_signals(self) -> None:
        """Wire up all signals between pages, worker, and log handler."""
        # Dashboard start/stop callbacks
        self._dashboard_page.set_callbacks(
            on_start=self._start_bot,
            on_stop=self._stop_bot,
        )

        # Log signal → log page
        self._log_signal.record_received.connect(self._log_page.append_log)

        # Settings saved → notify
        self._settings_page.config_saved.connect(self._on_config_saved)

    def _wire_worker_signals(self) -> None:
        """Connect BotWorker signals to UI slots. Called after worker is created."""
        if not self._worker:
            return

        self._worker.status_changed.connect(self._on_bot_status)
        self._worker.error_occurred.connect(self._on_bot_error)
        self._worker.message_received.connect(self._dashboard_page.append_message)
        self._worker.message_sent.connect(self._dashboard_page.append_sent)

    # ── Bot Lifecycle ──────────────────────────────────────────

    def _start_bot(self) -> None:
        """Create worker, move to thread, and start."""
        if self._worker_thread is not None:
            return  # already running

        # Create worker (no parent — will be moved to thread)
        self._worker = BotWorker(self._config)
        self._wire_worker_signals()

        # Create thread
        self._worker_thread = QThread()
        self._worker.moveToThread(self._worker_thread)

        # Wire thread lifecycle
        self._worker_thread.started.connect(self._worker.run)
        self._worker.started.connect(self._init_manager_pages)  # fired AFTER all init is done
        self._worker.stopped.connect(self._on_worker_stopped)
        self._worker.error_occurred.connect(self._on_worker_stopped)

        # Start!
        self._worker_thread.start()

    def _stop_bot(self) -> None:
        """Request the bot to stop."""
        if self._worker:
            self._worker.stop()

    def _on_worker_stopped(self) -> None:
        """Clean up thread after worker stops."""
        if self._worker_thread:
            self._worker_thread.quit()
            self._worker_thread.wait(5000)  # 5s timeout
            self._worker_thread = None
            self._worker = None
        # Reset pages to placeholder state for next run
        self._character_page.set_manager(None)
        self._skill_page.set_manager(None)

    def _init_manager_pages(self) -> None:
        """Populate character/skill pages once the worker's managers are ready.

        Connected to BotWorker.started, which fires AFTER all initialization.
        Pages are never swapped — set_manager() just toggles the internal
        QStackedWidget from placeholder to content.
        """
        if not self._worker:
            return

        char_mgr = self._worker.character_manager
        skill_mgr = self._worker.skill_manager

        if char_mgr:
            self._character_page.set_manager(char_mgr, skill_mgr)
            self._character_page.character_switched.connect(self._on_character_switched)
            logger.debug("CharacterPage populated")

        if skill_mgr:
            self._skill_page.set_manager(skill_mgr)
            logger.debug("SkillPage populated")

    # ── Status Updates ─────────────────────────────────────────

    def _on_bot_status(self, status: BotStatus) -> None:
        """Handle status change from worker."""
        self._bot_status = status
        self._update_status_display(status)

        # Also notify dashboard
        self._dashboard_page.update_status(status)

    def _update_status_display(self, status: BotStatus) -> None:
        """Update the status bar indicator."""
        desc, color = STATUS_INFO.get(status, ("未知", "#6c7086"))
        self._status_icon.setStyleSheet(f"color: {color}; font-size: 14px; font-weight: bold;")
        self._status_text.setText(desc)

    def _on_bot_error(self, msg: str) -> None:
        """Show error dialog for fatal errors."""
        QMessageBox.critical(
            self, "机器人错误",
            f"机器人运行出错:\n\n{msg}\n\n请查看日志了解详情。"
        )

    def _on_character_switched(self, name: str) -> None:
        """Update status bar when character is switched."""
        self._char_status.setText(f"角色: {name}")
        # Also notify worker if it's running
        if self._worker:
            self._worker.switch_character(name)

    def _on_config_saved(self) -> None:
        """Handle config save — show brief confirmation."""
        self._status_bar.showMessage("配置已保存，重启机器人后生效", 5000)

    # ── Logging Setup ──────────────────────────────────────────

    def _install_log_handler(self) -> None:
        """Install QtLogHandler on the root logger."""
        root = logging.getLogger()
        root.addHandler(self._log_handler)
        # Also capture our module loggers
        for name in ["dyrobot", "src"]:
            logging.getLogger(name).addHandler(self._log_handler)

    def _remove_log_handler(self) -> None:
        """Remove QtLogHandler from the root logger."""
        root = logging.getLogger()
        root.removeHandler(self._log_handler)
        for name in ["dyrobot", "src"]:
            logging.getLogger(name).removeHandler(self._log_handler)

    # ── Window Events ──────────────────────────────────────────

    def closeEvent(self, event) -> None:
        """Clean shutdown when window is closed."""
        # Stop bot if running
        if self._worker:
            self._worker.stop()
            if self._worker_thread:
                self._worker_thread.quit()
                self._worker_thread.wait(5000)

        # Remove log handler
        self._remove_log_handler()

        event.accept()
