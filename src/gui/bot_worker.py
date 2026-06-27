"""BotWorker — wraps the Bot lifecycle in a QObject for QThread execution.

All Playwright/browser/LLM objects are created and owned by this worker
in the background thread. The GUI never touches them directly.
Communication is one-way (worker → GUI) via Qt signals.
"""

import sys
from pathlib import Path
import yaml
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot

from .thread_safety import BotStatus
from ..llm.deepseek import DeepSeekClient
from ..browser.manager import BrowserManager
from ..core.context import ContextManager
from ..core.character import CharacterManager
from ..core.skills import SkillManager
from ..bot import Bot
from ..utils.logger import setup_logger

logger = setup_logger(__name__)


class BotWorker(QObject):
    """Manages the Bot lifecycle on a dedicated QThread.

    Signals (all delivered to the main thread via QueuedConnection):
        started:           Bot has begun the startup sequence
        stopped:           Bot has fully stopped and cleaned up
        status_changed:    BotStatus enum value changed
        error_occurred:    Fatal error message (str)
        message_received:  A group chat message was detected
        message_sent:      A reply was sent to a group
    """

    started = pyqtSignal()
    stopped = pyqtSignal()
    status_changed = pyqtSignal(BotStatus)
    error_occurred = pyqtSignal(str)
    message_received = pyqtSignal(str, str, str)   # group_id, user_name, content
    message_sent = pyqtSignal(str, str)             # group_id, reply_text

    def __init__(self, config: dict):
        super().__init__()
        self._config = config
        self._bot: Bot | None = None
        self._character_mgr: CharacterManager | None = None
        self._skill_mgr: SkillManager | None = None

    # ── Public API (called from main thread via slots) ──────────

    @pyqtSlot()
    def run(self) -> None:
        """Initialize and run the bot. Executes in the worker thread.

        Connected to QThread.started signal. This method blocks until
        the bot is stopped or a fatal error occurs.
        """
        try:
            self._status(BotStatus.STARTING)

            # ── Load config subsets ──
            deepseek_cfg = self._config.get("deepseek", {})
            bot_cfg = self._config.get("bot", {})
            browser_cfg = self._config.get("browser", {})
            context_cfg = self._config.get("context", {})
            groups_cfg = self._config.get("groups", [])

            # ── Character manager ──
            characters_dir = bot_cfg.get("characters_dir", "characters")
            default_character = bot_cfg.get("character", "default")
            self._character_mgr = CharacterManager(
                characters_dir=characters_dir,
                default_character=default_character,
            )

            # ── Skill manager ──
            skills_dir = bot_cfg.get("skills_dir", "skills")
            self._skill_mgr = SkillManager(skills_dir=skills_dir)

            # ── Core components ──
            deepseek = DeepSeekClient(
                api_key=deepseek_cfg.get("api_key", ""),
                model=deepseek_cfg.get("model", "deepseek-chat"),
                max_tokens=deepseek_cfg.get("max_tokens", 2048),
                temperature=deepseek_cfg.get("temperature", 0.7),
            )

            browser = BrowserManager(
                headless=browser_cfg.get("headless", False),
                slow_mo=browser_cfg.get("slow_mo", 100),
            )

            context_mgr = ContextManager(
                max_history_rounds=context_cfg.get("max_history_rounds", 10),
                session_timeout=context_cfg.get("session_timeout", 1800),
            )

            # ── Bot ──
            self._bot = Bot(
                deepseek_client=deepseek,
                browser_manager=browser,
                context_manager=context_mgr,
                character_manager=self._character_mgr,
                skill_manager=self._skill_mgr,
                bot_name=bot_cfg.get("name", "小助手"),
                reply_cooldown=bot_cfg.get("reply_cooldown", 2.0),
            )

            # ── Inject message callbacks for GUI signals ──
            self._inject_monitor_hooks()

            logger.info("BotWorker: starting bot...")
            self.started.emit()
            self._status(BotStatus.RUNNING)

            # Blocking call — runs until stop() is called
            self._bot.start(groups_cfg)

        except Exception as e:
            logger.error("BotWorker fatal error: %s", e, exc_info=True)
            self.error_occurred.emit(str(e))
            self._status(BotStatus.ERROR)
        finally:
            self._status(BotStatus.STOPPED)
            self.stopped.emit()
            logger.info("BotWorker: stopped")

    @pyqtSlot()
    def stop(self) -> None:
        """Request the bot to stop. Called from main thread."""
        logger.info("BotWorker: stop requested")
        self._status(BotStatus.STOPPING)
        if self._bot:
            self._bot.stop()

    @pyqtSlot(str)
    def switch_character(self, name: str) -> None:
        """Switch the active character. Called from main thread."""
        if self._character_mgr:
            char = self._character_mgr.switch(name)
            if char:
                logger.info("BotWorker: character switched to %s", char.name)

    # ── Properties for GUI read access ──

    @property
    def character_manager(self) -> CharacterManager | None:
        return self._character_mgr

    @property
    def skill_manager(self) -> SkillManager | None:
        return self._skill_mgr

    # ── Internal helpers ──

    def _status(self, status: BotStatus) -> None:
        """Emit a status change."""
        self.status_changed.emit(status)

    def _inject_monitor_hooks(self) -> None:
        """Wrap ChatMonitor callbacks to emit GUI signals.

        Hooks into Bot._handle_message and Bot._send_reply so the GUI
        can display message traffic in real time. The original behavior
        is preserved — we just add signal emission on top.
        """
        if not self._bot:
            return

        bot = self._bot

        # Hook: message received (before processing)
        original_handle = bot._handle_message

        def hooked_handle(msg):
            # Emit signal for GUI (truncate content for display)
            content_preview = msg.content[:100] if msg.content else ""
            self.message_received.emit(
                msg.group_id, msg.user_name or "未知", content_preview
            )
            # Call original handler
            return original_handle(msg)

        bot._handle_message = hooked_handle  # type: ignore[method-assign]

        # Hook: message sent
        original_send = bot._send_reply

        def hooked_send(msg, reply_text):
            content_preview = reply_text[:100] if reply_text else ""
            self.message_sent.emit(msg.group_id, content_preview)
            return original_send(msg, reply_text)

        bot._send_reply = hooked_send  # type: ignore[method-assign]
