import time
import threading
from .browser.manager import BrowserManager
from .browser.chat_monitor import ChatMonitor, ChatMessage
from .llm.deepseek import DeepSeekClient
from .core.router import MessageRouter
from .core.context import ContextManager
from .core.commands import CommandHandler
from .core.character import CharacterManager, Character
from .core.skills import SkillManager, Skill
from .utils.logger import setup_logger

logger = setup_logger(__name__)


class Bot:
    def __init__(
        self,
        deepseek_client: DeepSeekClient,
        browser_manager: BrowserManager,
        context_manager: ContextManager,
        character_manager: CharacterManager | None = None,
        skill_manager: SkillManager | None = None,
        bot_name: str = "小助手",
        reply_cooldown: float = 2.0,
    ):
        self.deepseek = deepseek_client
        self.browser = browser_manager
        self.context = context_manager
        self.character_manager = character_manager
        self.skill_manager = skill_manager
        self.commands = CommandHandler(
            context_manager,
            character_manager=character_manager,
            skill_manager=skill_manager,
        )
        self.router = MessageRouter(
            bot_name=bot_name,
            reply_cooldown=reply_cooldown,
        )
        # Seed the router with current character names for @mention detection
        self._sync_router_characters()
        self.bot_name = bot_name
        self._monitors: list[ChatMonitor] = []
        self._stop_event = threading.Event()

    def _sync_router_characters(self) -> None:
        """Sync character names AND skill names from managers to the MessageRouter."""
        names = []
        if self.character_manager:
            names.extend([c.name for c in self.character_manager.list_characters()])
        # Also add skill names so they can be @mentioned too
        if self.skill_manager:
            for skill in self.skill_manager.list_skills():
                names.append(skill.name)
                # Also add any trigger words from the skill
                names.extend(skill.triggers)
        # Remove duplicates
        names = list(dict.fromkeys(names))
        logger.info(f"[_sync_router_characters] Synced names: {names}")
        self.router.set_character_names(names)

    def add_group(self, group_id: str, group_url: str, page=None) -> ChatMonitor:
        if page is None:
            page = self.browser.new_page()
        monitor = ChatMonitor(page, group_id, group_url)
        monitor.navigate()
        monitor.on_message(self._handle_message)
        self._monitors.append(monitor)
        logger.info(f"[add_group] Added group: {group_id} at {group_url}")
        return monitor

    def _get_bound_skills_for_character(self, char: Character) -> list[Skill]:
        """Get list of skills bound to the given character."""
        if not self.skill_manager or not char.bound_skills:
            return []

        bound = []
        for skill_name in char.bound_skills:
            skill = self.skill_manager.get(skill_name)
            if skill:
                bound.append(skill)
            else:
                # Try case-insensitive match
                for s in self.skill_manager.list_skills():
                    if s.name.lower() == skill_name.lower():
                        bound.append(s)
                        break
        return bound

    def _build_system_prompt(self, group_id: str, user_message: str = "", character_name: str | None = None) -> str:
        """Build the system prompt dynamically from character, skills, and custom overrides.

        Args:
            group_id: The group chat identifier.
            user_message: The user's message content (for skill matching).
            character_name: If set, use THIS character's prompt (from @mention detection).
                           Otherwise use the currently active character.
                           This could also be a skill name!
        """
        logger.info(f"[_build_system_prompt] group={group_id}, char_name={repr(character_name)}, msg={repr(user_message[:50])}")

        # 1. Determine which character to use
        char = None
        base_prompt = ""
        mentioned_skill = None

        if self.character_manager:
            if character_name:
                # Try to find the @mentioned character by key (filename) then by display name
                char = self.character_manager.get(character_name)
                if not char:
                    char = self.character_manager.get_by_name(character_name)
                if char:
                    logger.info(f"[_build_system_prompt] Found character: {char.name}")
                else:
                    # If still not found, check if it's a skill name
                    if self.skill_manager:
                        mentioned_skill = self.skill_manager.get(character_name)
                        if not mentioned_skill:
                            for s in self.skill_manager.list_skills():
                                if s.name.lower() == character_name.lower():
                                    mentioned_skill = s
                                    break
                        if mentioned_skill:
                            logger.info(f"[_build_system_prompt] Found skill: {mentioned_skill.name}")
                        if not mentioned_skill:
                            logger.warning("@mentioned character '%s' not found in character or skill managers. "
                                           "Available characters: %s",
                                           character_name,
                                           [c.name for c in self.character_manager.list_characters()])

            # Fall back to active character
            if not char:
                char = self.character_manager.active
                if char:
                    logger.info(f"[_build_system_prompt] Using active character: {char.name}")

            if char:
                base_prompt = char.build_system_prompt()

        # 2. Check for group-level custom system prompt override (from /system command)
        sys_prompt = self.commands.get_system_prompt(group_id, base_prompt or "")

        # 3. Inject skill prompts
        if self.skill_manager:
            # If a skill was @mentioned, add it first
            if mentioned_skill:
                mentioned_parts = ["\n\n## @提及的技能:"]
                mentioned_parts.append(f"\n### {mentioned_skill.name}")
                mentioned_parts.append(mentioned_skill.prompt.strip())
                sys_prompt += "\n".join(mentioned_parts)
                logger.info(f"[_build_system_prompt] Added mentioned skill: {mentioned_skill.name}")

            # Then add bound skills for the character (always inject, even without user_message)
            if char and char.bound_skills:
                bound_skills = self._get_bound_skills_for_character(char)
                if bound_skills:
                    bound_parts = ["\n\n## 该角色绑定的技能:"]
                    for skill in bound_skills:
                        bound_parts.append(f"\n### {skill.name}")
                        bound_parts.append(skill.prompt.strip())
                    sys_prompt += "\n".join(bound_parts)
                    logger.info(f"[_build_system_prompt] Added {len(bound_skills)} bound skills: {[s.name for s in bound_skills]}")

            # Then add any matched skills from the message content
            if user_message:
                skill_prompt = self.skill_manager.build_skill_prompt(user_message)
                if skill_prompt:
                    sys_prompt += skill_prompt
                    logger.info(f"[_build_system_prompt] Added matched skills from message")

        logger.info(f"[_build_system_prompt] Final system prompt length: {len(sys_prompt)} chars")
        return sys_prompt

    def _handle_message(self, msg: ChatMessage) -> None:
        logger.info(f"[_handle_message] START: group={msg.group_id}, content={repr(msg.content[:100])}")

        # ── Step 1: Let the router decide if we should reply ──
        # should_reply() ONLY decides — it does NOT execute commands.
        if not self.router.should_reply(msg):
            logger.info(f"[_handle_message] router.should_reply() returned False, ignoring")
            return

        # ── Step 2: Commands take priority — handle before anything else ──
        is_cmd = self.router.is_command(msg)
        logger.info(f"[_handle_message] router.is_command(): {is_cmd}")
        if is_cmd:
            logger.info(f"[_handle_message] Handling as command")
            reply = self.commands.handle(msg, self.router)
            if reply:
                logger.info(f"[_handle_message] Command reply generated ({len(reply)} chars), calling _send_reply()")
                self._send_reply(msg, reply)
            else:
                logger.info(f"[_handle_message] No command reply generated")
            return

        # ── Step 3: Skip own messages (defense-in-depth after router check) ──
        if msg.user_name == self.bot_name:
            logger.info(f"[_handle_message] Skipping own message (username={self.bot_name})")
            return

        # ── Step 4: Rate limit for normal (non-command) messages ──
        if not self.router.can_send_now():
            logger.info(f"[_handle_message] Rate limited, skipping")
            return

        # ── Step 5: Generate LLM reply ──
        try:
            logger.info(f"[_handle_message] Generating LLM reply")
            # Use the character that was @mentioned (from router's mention detection)
            mentioned_char = self.router.matched_character
            history = self.context.get_history(msg.group_id, msg.user_name)
            sys_prompt = self._build_system_prompt(msg.group_id, msg.content, character_name=mentioned_char)

            self.context.add_message(msg.group_id, msg.user_name, "user", msg.content)

            full_messages = history + [
                {"role": "user", "content": msg.content},
            ]

            logger.info(f"[_handle_message] Calling deepseek.chat()...")
            reply = self.deepseek.chat(full_messages, system_prompt=sys_prompt)
            logger.info(f"[_handle_message] Received LLM reply ({len(reply)} chars)")
            self.context.add_message(msg.group_id, msg.user_name, "assistant", reply)
            self._send_reply(msg, reply)
        except Exception as e:
            logger.error(f"[_handle_message] Error: {e}", exc_info=True)

    def _send_reply(self, msg: ChatMessage, reply_text: str) -> None:
        logger.info(f"[_send_reply] START: group={msg.group_id}, reply={repr(reply_text[:100])}")

        # Mark this content as sent BEFORE typing so the MutationObserver
        # won't pick it up as a new incoming message (prevents self-talk loop).
        self.router.mark_sent(msg.group_id, reply_text)

        for monitor in self._monitors:
            if monitor.group_id == msg.group_id:
                time.sleep(1)
                success = monitor.send_message(reply_text)
                if not success:
                    logger.warning("First send attempt failed for group %s, retrying...", msg.group_id)
                    time.sleep(1)
                    # Re-mark in case the first attempt partially cleared the hash
                    self.router.mark_sent(msg.group_id, reply_text)
                    monitor.send_message(reply_text)
                return
        logger.warning("No monitor found for group %s to send reply", msg.group_id)

    def start(self, groups: list[dict]) -> None:
        logger.info(f"[start] STARTING bot with {len(groups)} groups")
        self._stop_event.clear()

        self.browser.start()
        login_page = self.browser.login()

        for i, group in enumerate(groups):
            group_id = group.get("name", f"group_{i}")
            group_url = group["url"]
            if i == 0:
                monitor = self.add_group(group_id, group_url, page=login_page)
            else:
                monitor = self.add_group(group_id, group_url)
            logger.info("Bot monitoring group: %s", group_id)

        logger.info("Bot is running. Press Ctrl+C to stop.")

        try:
            while not self._stop_event.is_set():
                for monitor in self._monitors:
                    if self._stop_event.is_set():
                        break
                    try:
                        monitor.poll()
                    except Exception as e:
                        logger.error(f"[start] Poll error for {monitor.group_id}: {e}", exc_info=True)
                        time.sleep(1)
                        continue
                self._maintenance()
                time.sleep(2)
        except KeyboardInterrupt:
            self.stop()

    def _maintenance(self) -> None:
        """Periodic health checks."""
        for monitor in self._monitors:
            try:
                # Light health check — just verify the page exists
                if monitor.page.is_closed():
                    logger.warning(f"[_maintenance] Page for {monitor.group_id} closed, reloading")
                    monitor.navigate()
            except Exception as e:
                logger.warning(f"[_maintenance] Health check failed for {monitor.group_id}: {e}")
                try:
                    monitor.navigate()
                except Exception as e2:
                    logger.error(f"[_maintenance] Reload failed for {monitor.group_id}: {e2}")

    def stop(self) -> None:
        logger.info("[stop] Stopping bot...")
        self._stop_event.set()
        self.deepseek.close()
        self.browser.stop()
        logger.info("[stop] Bot stopped")
