import re
import time
import hashlib
from ..browser.chat_monitor import ChatMessage
from ..utils.logger import setup_logger, get_logger

logger = setup_logger(__name__)

# After the bot sends a reply, the MutationObserver captures not only the
# exact message content but also sibling DOM text (sender name label,
# timestamp like "刚刚", wrapper divs, etc.). These spurious captures
# trigger further replies → infinite self-talk loop.
# Three defenses: (1) min length, (2) per-group cooldown, (3) exact-content hash.
SEND_COOLDOWN_SEC = 8.0  # 增加冷却时间，帮助消息较长，需要更长的冷却
MIN_CONTENT_LENGTH = 2

# System command prefix — ONLY @<System>:command format is supported
COMMAND_PREFIX = "@<System>:"


class MessageRouter:
    """
    Routes incoming chat messages:
      - Detect @mentions of character names (any loaded character)
      - Detect system commands (@<System>:help, etc.)
      - Filter out self-sent messages (prevents self-talk loops)
      - Deduplicate messages
      - Apply rate limiting
    """

    def __init__(
        self,
        bot_name: str = "小助手",
        reply_cooldown: float = 2.0,
        command_prefix: str = COMMAND_PREFIX,
    ):
        self.bot_name = bot_name
        self.reply_cooldown = reply_cooldown
        self.command_prefix = command_prefix
        self._last_reply_time: float = 0.0
        self._seen_ids: set[str] = set()
        self._command_processed: set[str] = set()  # 跟踪已处理的命令

        # ── Character-based mention system ──
        # The bot replies ONLY when @mentioned with a character name.
        # Different @character_name triggers different personas.
        self._character_names: list[str] = []
        # After should_reply() returns True, this holds the character name
        # that was @mentioned (or the bot_name / default character as fallback).
        self.matched_character: str | None = None

        # ── Self-talk prevention ──
        self._sent_content_hashes: set[str] = set()
        self._send_cooldown_until: dict[str, float] = {}

    # ── Character name management ────────────────────────────────────────

    def set_character_names(self, names: list[str]) -> None:
        """Update the list of character names to detect @mentions for."""
        self._character_names = list(names)
        logger.info(f"Set character names: {self._character_names}")

    # ── Self-talk prevention ─────────────────────────────────────────────

    def mark_sent(self, group_id: str, content: str) -> None:
        """Register that the bot just sent `content` to `group_id`.

        Must be called BEFORE the message is physically typed, so the
        MutationObserver's captures are all covered.
        """
        logger.info(f"[mark_sent] Group: {group_id}, Content: {repr(content[:100])}")

        # 添加完整消息的哈希
        h = hashlib.md5(content.encode()).hexdigest()
        self._sent_content_hashes.add(h)
        logger.info(f"[mark_sent] Added full hash: {h[:16]}...")

        # 对于长消息，还要添加每一行的哈希，防止消息被拆分成多个 DOM 节点
        lines = content.split('\n')
        logger.info(f"[mark_sent] Split into {len(lines)} lines")
        for i, line in enumerate(lines):
            line_stripped = line.strip()
            if line_stripped and len(line_stripped) >= MIN_CONTENT_LENGTH:
                line_h = hashlib.md5(line_stripped.encode()).hexdigest()
                self._sent_content_hashes.add(line_h)
                logger.info(f"[mark_sent] Added line[{i}] hash: {line_h[:16]}... -> {repr(line_stripped[:50])}")

        # Evict oldest half instead of clearing all (preserve recent hashes)
        if len(self._sent_content_hashes) > 200:
            old_count = len(self._sent_content_hashes)
            self._sent_content_hashes = set(list(self._sent_content_hashes)[100:])
            logger.info(f"[mark_sent] Evicted hashes: {old_count} -> {len(self._sent_content_hashes)}")

        cooldown_until = time.time() + SEND_COOLDOWN_SEC
        self._send_cooldown_until[group_id] = cooldown_until
        logger.info(f"[mark_sent] Cooldown set for group {group_id} until {cooldown_until:.1f}")

    def is_own_message(self, content: str) -> bool:
        """Check if this exact content matches something the bot just sent."""
        content_stripped = content.strip()
        logger.info(f"[is_own_message] Checking: {repr(content_stripped[:80])}")

        # 快速检查1：拦截看起来像是 Bot 输出的帮助消息片段
        bot_help_patterns = [
            "【机器人使用指南】",
            "━━━ 系统命令 ━━━",
            "━━━ 可用角色 ━━━",
            "━━━ 可用技能 ━━━",
            "━━━ 使用方法 ━━━",
            "【机器人帮助】",
            "可用命令：",
            "可用角色：",
            "可用技能：",
            "@角色名 让角色回复你",
        ]
        for pattern in bot_help_patterns:
            if pattern in content_stripped:
                logger.info(f"[is_own_message] BLOCKED by pattern '{pattern}': {repr(content_stripped[:60])}")
                return True

        # 快速检查2：不要拦截用户发出的@<System>:命令！
        # 但是要拦截 Bot 发出的帮助消息中包含的命令行（这些行以@<System>:开头）
        # 关键：用户发出的命令通常较短，或者只有一个命令；而Bot输出的帮助有描述
        if content_stripped.startswith("@<System>:"):
            # 如果这行包含了描述（有"-"分隔），那是帮助消息的一部分
            if " - " in content_stripped and len(content_stripped) > 30:
                logger.info(f"[is_own_message] BLOCKED by help command line: {repr(content_stripped[:60])}")
                return True

        # 快速检查3：拦截像"• 小助手 [当前]"或"• weather"这样的技能/角色列表项
        if (content_stripped.startswith("• ") and
            len(content_stripped) < 50 and
            not content_stripped.endswith(">")):
            logger.info(f"[is_own_message] BLOCKED by list item: {repr(content_stripped[:60])}")
            return True

        # 检查完整哈希匹配
        h = hashlib.md5(content.encode()).hexdigest()
        if h in self._sent_content_hashes:
            logger.info(f"[is_own_message] BLOCKED by hash match: {repr(content_stripped[:60])}")
            return True

        logger.info(f"[is_own_message] NOT blocked: {repr(content_stripped[:60])}")
        return False

    def _is_in_send_cooldown(self, group_id: str) -> bool:
        """Check if `group_id` is within the post-send suppression window."""
        until = self._send_cooldown_until.get(group_id, 0)
        is_in_cooldown = time.time() < until
        logger.info(f"[_is_in_send_cooldown] Group {group_id}: until={until:.1f}, is_in_cooldown={is_in_cooldown}")
        return is_in_cooldown

    # ── Main routing ─────────────────────────────────────────────────────

    def should_reply(self, msg: ChatMessage) -> bool:
        """Decide whether the bot should respond to this message.

        Sets self.matched_character when a character is @mentioned,
        so the caller can build the correct system prompt.

        NOTE: This method ONLY decides — it must NOT execute commands or
        send replies.  Command execution happens in Bot._handle_message().
        """
        self.matched_character = None
        content = msg.content.strip()
        logger.info(f"[should_reply] ==========================")
        logger.info(f"[should_reply] START: group={msg.group_id}, content={repr(content[:100])}")

        # ── Own-message check (runs before everything else) ──
        # The MutationObserver captures the bot's own outgoing messages as
        # new DOM nodes. Content hash catches exact matches; the send
        # cooldown catches DOM noise (sender label, timestamp, etc.).

        # 1. 先检查是否是帮助消息片段
        logger.info(f"[should_reply] 1. Calling is_own_message()...")
        is_own = self.is_own_message(content)
        logger.info(f"[should_reply] is_own_message() returned: {is_own}")
        if is_own:
            logger.info(f"[should_reply] BLOCKED by is_own_message(): {repr(content[:80])}")
            return False

        # 2. 再检查哈希匹配
        logger.info(f"[should_reply] 2. Checking hash...")
        quick_hash = hashlib.md5(content.encode()).hexdigest()
        hash_in_set = quick_hash in self._sent_content_hashes
        logger.info(f"[should_reply] Hash: {quick_hash[:16]}..., in set: {hash_in_set}")
        if hash_in_set:
            logger.info(f"[should_reply] BLOCKED by hash match: {repr(content[:80])}")
            return False

        # 3. 最后检查冷却期
        logger.info(f"[should_reply] 3. Checking cooldown...")
        in_cooldown = self._is_in_send_cooldown(msg.group_id)
        logger.info(f"[should_reply] in_cooldown: {in_cooldown}")
        if in_cooldown:
            logger.info(f"[should_reply] BLOCKED by send cooldown: {repr(content[:80])}")
            return False

        # Layer 1: minimum content length (DOM artifacts are tiny)
        if len(content) < MIN_CONTENT_LENGTH:
            logger.info(f"[should_reply] BLOCKED by min length: {len(content)} < {MIN_CONTENT_LENGTH}")
            return False

        # ── Commands: detect and pass through (do NOT execute here) ──
        is_cmd = self.is_command(msg)
        logger.info(f"[should_reply] is_command(): {is_cmd}")
        if is_cmd:
            cmd_id = hashlib.md5(
                f"{msg.group_id}:{content}:{msg.timestamp}".encode()
            ).hexdigest()
            if cmd_id in self._command_processed:
                logger.info(f"[should_reply] BLOCKED duplicate command: {repr(content[:50])}")
                return False
            self._command_processed.add(cmd_id)
            if len(self._command_processed) > 100:
                self._command_processed = set(list(self._command_processed)[50:])

            # Detect mention for character context (e.g. "@Yukino @<System>:help")
            matched = self._detect_mention(content)
            self.matched_character = matched or self.bot_name
            logger.info(f"[should_reply] ACCEPTED command, matched_character={self.matched_character}")
            return True

        # ── Dedup normal messages ──
        msg_hash = hashlib.md5(
            f"{msg.group_id}:{msg.user_name}:{content}".encode()
        ).hexdigest()
        if msg_hash in self._seen_ids:
            logger.info(f"[should_reply] BLOCKED duplicate normal message: {msg_hash[:16]}...")
            return False
        self._seen_ids.add(msg_hash)
        if len(self._seen_ids) > 50000:
            self._seen_ids = set(list(self._seen_ids)[25000:])

        # ── Mention detection (always on — bot only replies when @mentioned) ──
        matched = self._detect_mention(content)
        if matched:
            self.matched_character = matched
            logger.info(f"[should_reply] ACCEPTED @mention: {matched}")
            return True

        logger.info(f"[should_reply] BLOCKED: no command or mention found")
        return False

    def is_command(self, msg: ChatMessage) -> bool:
        """Check if the message is a system command.

        ONLY supports: @<System>:command
        The command can appear anywhere in the message.
        """
        content = msg.content.strip()
        # ONLY check for @<System>:command pattern
        found = re.search(re.escape(self.command_prefix), content) is not None
        logger.info(f"[is_command] Content: {repr(content[:80])}, found: {found}")
        return found

    def extract_command(self, msg: ChatMessage) -> str:
        """Extract the command text, stripping the prefix.

        ONLY supports @<System>:command format.
        Command can be anywhere in the message (e.g. "张三 @<System>:help").
        """
        content = msg.content.strip()
        # ONLY extract @<System>:command [args]
        pattern = rf"{re.escape(self.command_prefix)}\s*(\S+)(.*)$"
        match = re.search(pattern, content)
        if match:
            cmd = match.group(1)
            args = match.group(2).strip()
            result = f"{cmd} {args}" if args else cmd
            logger.info(f"[extract_command] Extracted: {repr(result)} from {repr(content[:80])}")
            return result
        return content

    def can_send_now(self) -> bool:
        now = time.time()
        if now - self._last_reply_time < self.reply_cooldown:
            logger.info(f"[can_send_now] NO: cooldown {now - self._last_reply_time:.2f} < {self.reply_cooldown}")
            return False
        self._last_reply_time = now
        return True

    # ── Mention detection ─────────────────────────────────────────────────

    def _detect_mention(self, content: str) -> str | None:
        """Check if any character name is @mentioned. Returns the matched name or None."""
        # First check if this looks like a system command — if so, skip mention detection
        # ONLY check for @<System>:... pattern
        if re.search(re.escape(self.command_prefix), content):
            logger.info(f"[_detect_mention] Skipping for command: {repr(content[:60])}")
            return None

        # Build list of names to check: character names + bot_name (fallback)
        names_to_check = list(self._character_names)
        if self.bot_name and self.bot_name not in names_to_check:
            names_to_check.append(self.bot_name)

        # Sort names by length descending to match longer names first (e.g. "雪之下雪乃" over "雪乃")
        names_to_check.sort(key=lambda x: len(x), reverse=True)

        if not names_to_check:
            logger.warning("No character names configured for @mention detection!")
            return None

        for name in names_to_check:
            if not name:
                continue
            # Look for @name anywhere in the content, not just at word boundaries
            # This handles cases like "@Yukino你好" or "@Hachiman在吗" or "@张雪峰 帮我分析"
            pattern = rf"@{re.escape(name)}"
            if re.search(pattern, content):
                logger.info(f"[_detect_mention] FOUND: {name} in {repr(content[:60])}")
                return name

        logger.info(f"[_detect_mention] No mention found: {repr(content[:60])}")
        return None
