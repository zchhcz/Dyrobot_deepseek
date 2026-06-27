"""Command handler for in-chat bot commands.

ONLY supports command format: @<System>:command
"""

from ..browser.chat_monitor import ChatMessage
from .context import ContextManager
from .character import CharacterManager
from .skills import SkillManager
from ..utils.logger import setup_logger, get_logger

logger = setup_logger(__name__)

# Help 消息模板 — 精简版，避免超时
HELP_TEMPLATE = """【机器人使用指南】

@<System>:help - 显示帮助
@<System>:reset - 清空上下文
@<System>:status - 查看状态
@<System>:system xxx - 自定义提示词
@<System>:character list - 查看角色
@<System>:character xxx - 切换角色
@<System>:skills - 查看技能

可用角色: {characters_list}
可用技能: {skills_list}

使用: @角色名 消息内容 来让指定角色回复！"""

# 命令列表定义
COMMANDS_LIST = [
    {
        "name": "help",
        "usage": "@<System>:help",
        "description": "显示帮助",
    },
    {
        "name": "reset",
        "usage": "@<System>:reset",
        "description": "清空上下文",
    },
    {
        "name": "status",
        "usage": "@<System>:status",
        "description": "查看状态",
    },
    {
        "name": "system",
        "usage": "@<System>:system <提示词>",
        "description": "自定义提示词",
    },
    {
        "name": "character",
        "usage": "@<System>:character [list|名称]",
        "description": "切换角色",
    },
    {
        "name": "skills",
        "usage": "@<System>:skills",
        "description": "查看技能",
    },
]


class CommandHandler:
    def __init__(
        self,
        context_manager: ContextManager,
        character_manager: CharacterManager | None = None,
        skill_manager: SkillManager | None = None,
    ):
        self.context_manager = context_manager
        self.character_manager = character_manager
        self.skill_manager = skill_manager
        self._custom_system_prompts: dict[str, str] = {}  # group_id -> custom prompt
        self._debug_logger = get_logger("commands")

    def handle(self, msg: ChatMessage, router=None) -> str | None:
        """
        Process a command message. Returns reply text if handled, None if not a command.

        Args:
            msg: The incoming chat message.
            router: Optional MessageRouter for extracting the command.
        """
        self._debug_logger.info(f"[handle] START: group={msg.group_id}, content={repr(msg.content[:100])}")

        # Extract the command text (strip prefix)
        if router and hasattr(router, "extract_command"):
            content = router.extract_command(msg)
        else:
            content = msg.content.strip()
            # Strip @<System>: prefix
            if content.startswith("@<System>:"):
                content = content[len("@<System>:"):].strip()

        self._debug_logger.debug(f"[handle] Extracted command content: {repr(content)}")

        if not content:
            self._debug_logger.debug("[handle] No content, returning None")
            return None

        # Split into command verb and arguments
        parts = content.split(None, 1)
        cmd = parts[0].lower() if parts else ""
        args = parts[1].strip() if len(parts) > 1 else ""
        self._debug_logger.debug(f"[handle] Parsed: cmd={repr(cmd)}, args={repr(args)}")

        # help 命令 — 单独函数实现，不使用模型
        if cmd == "help":
            self._debug_logger.info("[handle] Executing HELP command")
            return self._handle_help_command()

        # reset - exact match only
        if cmd == "reset":
            self._debug_logger.info("[handle] Executing RESET command")
            self.context_manager.reset(msg.group_id, msg.user_name)
            reply = f"已清空 @{msg.user_name} 的对话上下文 ✓"
            self._debug_logger.info(f"[handle] RESET reply: {repr(reply)}")
            return reply

        # system <prompt>
        if cmd == "system":
            self._debug_logger.info(f"[handle] Executing SYSTEM command with args: {repr(args)}")
            if not args:
                reply = "用法: @<System>:system <自定义提示词>"
                self._debug_logger.info(f"[handle] SYSTEM (no args) reply: {repr(reply)}")
                return reply
            self._custom_system_prompts[msg.group_id] = args
            logger.info("Custom system prompt set for group %s", msg.group_id)
            reply = "已更新系统提示词 ✓"
            self._debug_logger.info(f"[handle] SYSTEM reply: {repr(reply)}")
            return reply

        # character [name|list]
        if cmd == "character":
            self._debug_logger.info(f"[handle] Executing CHARACTER command with args: {repr(args)}")
            reply = self._handle_character_cmd(args)
            self._debug_logger.info(f"[handle] CHARACTER reply: {repr(reply[:100])}")
            return reply

        # skills
        if cmd in ("skills", "skill"):
            self._debug_logger.info("[handle] Executing SKILLS command")
            reply = self._handle_skills_cmd()
            self._debug_logger.info(f"[handle] SKILLS reply: {repr(reply[:100])}")
            return reply

        # status - exact match only
        if cmd == "status":
            self._debug_logger.info("[handle] Executing STATUS command")
            reply = self._handle_status(msg)
            self._debug_logger.info(f"[handle] STATUS reply: {repr(reply)}")
            return reply

        self._debug_logger.debug(f"[handle] Unknown command: {repr(cmd)}, returning None")
        return None

    def _handle_help_command(self) -> str:
        """
        单独的 help 命令实现函数。
        使用固定模板，一次性发送长消息，不使用模型输出。
        """
        self._debug_logger.info("[_handle_help_command] START")

        # 1. 读取并格式化角色列表
        characters_list = ""
        if self.character_manager:
            chars = self.character_manager.list_characters()
            self._debug_logger.debug(f"[_handle_help_command] Found {len(chars)} characters")
            if chars:
                active = self.character_manager.active
                active_name = active.name if active else None
                self._debug_logger.debug(f"[_handle_help_command] Active character: {active_name}")
                char_items = []
                for char in chars:
                    marker = " [当前]" if char.name == active_name else ""
                    char_items.append(f"  • {char.name}{marker}")
                characters_list = "\n".join(char_items)
            else:
                characters_list = "  暂无角色"
        else:
            characters_list = "  角色系统未启用"

        self._debug_logger.debug(f"[_handle_help_command] characters_list:\n{characters_list}")

        # 2. 读取并格式化技能列表
        skills_list = ""
        if self.skill_manager:
            skills = self.skill_manager.list_skills()
            self._debug_logger.debug(f"[_handle_help_command] Found {len(skills)} skills")
            if skills:
                skill_items = []
                for skill in skills:
                    skill_items.append(f"  • {skill.name}")
                skills_list = "\n".join(skill_items)
            else:
                skills_list = "  暂无技能"
        else:
            skills_list = "  技能系统未启用"

        self._debug_logger.debug(f"[_handle_help_command] skills_list:\n{skills_list}")

        # 3. 使用固定模板组装帮助消息
        help_message = HELP_TEMPLATE.format(
            characters_list=characters_list,
            skills_list=skills_list,
        )

        logger.info("Generated help message, length: %d", len(help_message))
        self._debug_logger.info(f"[_handle_help_command] Generated help message ({len(help_message)} chars)")
        self._debug_logger.debug(f"[_handle_help_command] Message content:\n---\n{help_message}\n---")

        return help_message

    def _handle_character_cmd(self, arg: str) -> str:
        """Handle character command — list or switch characters.

        Args:
            arg: The argument after 'character' (e.g. 'list', 'Yukino', '张雪峰').
        """
        self._debug_logger.debug(f"[_handle_character_cmd] arg: {repr(arg)}")

        if not self.character_manager:
            return "角色系统未启用，请检查配置"

        if not arg or arg == "list":
            chars = self.character_manager.list_characters()
            if not chars:
                return "没有可用的角色"

            active = self.character_manager.active
            lines = ["可用角色:"]
            for c in chars:
                marker = " ← 当前" if active and c.name == active.name else ""
                lines.append(f"  • {c.name} ({c.description}){marker}")
            lines.append("")
            lines.append("使用 @<System>:character <名称> 切换角色")
            lines.append("或在群聊中直接 @角色名 来让对应角色回复")
            return "\n".join(lines)

        # Try to switch to the specified character
        char = self.character_manager.switch(arg)
        if char:
            return f"已切换为角色: {char.name} ✓\n{char.description}"
        else:
            available = [c.name for c in self.character_manager.list_characters()]
            return f"未找到角色: {arg}\n可用角色: {', '.join(available)}"

    def _handle_skills_cmd(self) -> str:
        """Handle skills command — list available skills."""
        if not self.skill_manager:
            return "技能系统未启用，请检查配置"

        skills = self.skill_manager.list_skills()
        if not skills:
            return "没有可用的技能"

        lines = ["可用技能 (匹配关键词自动激活):"]
        for s in skills:
            triggers_str = ", ".join(s.triggers[:5])
            if len(s.triggers) > 5:
                triggers_str += f" ...等{len(s.triggers)}个"
            lines.append(f"  • {s.name} — {s.description}")
            lines.append(f"    触发词: {triggers_str}")
        return "\n".join(lines)

    def _handle_status(self, msg: ChatMessage) -> str:
        """Handle status command."""
        history = self.context_manager.get_history(msg.group_id, msg.user_name)
        rounds = len(history) // 2
        custom = self._custom_system_prompts.get(msg.group_id)

        status_lines = [
            "状态: 运行中",
            f"当前对话轮数: {rounds}",
            f"自定义系统提示词: {'是' if custom else '否'}",
        ]

        if self.character_manager and self.character_manager.active:
            status_lines.append(f"当前角色: {self.character_manager.active.name}")

        return "\n".join(status_lines)

    def get_system_prompt(self, group_id: str, default_prompt: str) -> str:
        """Get the system prompt for a group, with fallback to default."""
        return self._custom_system_prompts.get(group_id, default_prompt)
