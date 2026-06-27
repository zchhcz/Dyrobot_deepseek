"""
Usage:
    python main.py              # CLI mode (original behavior)
    python main.py --gui        # GUI mode (PyQt6 control panel)
    python main.py --config path/to/config.yaml
"""

import sys
import argparse
import yaml
from pathlib import Path
from src.llm.deepseek import DeepSeekClient
from src.browser.manager import BrowserManager
from src.core.context import ContextManager
from src.core.character import CharacterManager
from src.core.skills import SkillManager
from src.bot import Bot
from src.utils.logger import setup_logger

logger = setup_logger("dyrobot.main")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="dyrobot — 抖音群聊 AI 机器人",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py                  Run in CLI mode
  python main.py --gui            Launch the GUI control panel
  python main.py --config prod.yaml   Use a custom config file
        """,
    )
    parser.add_argument(
        "--gui", action="store_true",
        help="Launch the PyQt6 GUI control panel",
    )
    parser.add_argument(
        "--config", default="config.yaml",
        help="Path to config file (default: config.yaml)",
    )
    return parser.parse_args()


def load_config(path: str) -> dict:
    config_path = Path(path)
    if not config_path.exists():
        logger.error("Config file not found: %s", path)
        sys.exit(1)
    with open(config_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def validate_config(config: dict) -> None:
    """Validate required config fields. Exits on failure."""
    deepseek_cfg = config.get("deepseek", {})
    api_key = deepseek_cfg.get("api_key", "")
    if not api_key or api_key == "sk-your-api-key-here":
        logger.error(
            "Please set your DeepSeek API key in config.yaml (deepseek.api_key)"
        )
        sys.exit(1)

    groups_cfg = config.get("groups", [])
    if not groups_cfg:
        logger.error(
            "No groups configured. Add at least one group in config.yaml (groups)"
        )
        sys.exit(1)


def run_cli(config: dict) -> None:
    """Run the bot in CLI mode (original behavior)."""
    deepseek_cfg = config.get("deepseek", {})
    bot_cfg = config.get("bot", {})
    groups_cfg = config.get("groups", [])
    browser_cfg = config.get("browser", {})
    context_cfg = config.get("context", {})

    # Initialize character manager
    characters_dir = bot_cfg.get("characters_dir", "characters")
    default_character = bot_cfg.get("character", "default")
    character_mgr = CharacterManager(
        characters_dir=characters_dir,
        default_character=default_character,
    )
    if character_mgr.active:
        logger.info("Active character: %s", character_mgr.active.name)

    # Initialize skill manager
    skills_dir = bot_cfg.get("skills_dir", "skills")
    skill_mgr = SkillManager(skills_dir=skills_dir)
    skill_count = len(skill_mgr.list_skills())
    if skill_count > 0:
        logger.info("Loaded %d skills", skill_count)

    # Initialize components
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

    bot = Bot(
        deepseek_client=deepseek,
        browser_manager=browser,
        context_manager=context_mgr,
        character_manager=character_mgr,
        skill_manager=skill_mgr,
        bot_name=bot_cfg.get("name", "小助手"),
        reply_cooldown=bot_cfg.get("reply_cooldown", 2.0),
    )

    logger.info("Starting dyrobot (CLI mode)...")
    bot.start(groups_cfg)


def run_gui(config: dict) -> None:
    """Run the bot in GUI mode (PyQt6 control panel)."""
    from PyQt6.QtWidgets import QApplication
    from src.gui.main_window import MainWindow
    from src.gui.dark_theme import get_dark_palette, DARK_STYLESHEET

    app = QApplication(sys.argv)
    app.setApplicationName("dyrobot")
    app.setOrganizationName("dyrobot")
    app.setPalette(get_dark_palette())
    app.setStyleSheet(DARK_STYLESHEET)

    logger.info("Starting dyrobot (GUI mode)...")
    window = MainWindow(config)
    window.show()

    sys.exit(app.exec())


def main() -> None:
    args = parse_args()
    config = load_config(args.config)

    # CLI mode validates immediately; GUI mode defers to user clicking Start
    if args.gui:
        run_gui(config)
    else:
        validate_config(config)
        run_cli(config)


if __name__ == "__main__":
    main()
