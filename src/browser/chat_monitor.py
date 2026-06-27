import hashlib
import time
from dataclasses import dataclass
from typing import Callable
from playwright.sync_api import Page, Frame, Error as PlaywrightError
from ..utils.logger import setup_logger, get_logger

logger = setup_logger(__name__)


@dataclass
class ChatMessage:
    group_id: str
    user_name: str
    content: str
    timestamp: float
    msg_id: str = ""

    def __hash__(self):
        return hash(self.msg_id or f"{self.group_id}_{self.user_name}_{self.content}_{self.timestamp}")


# Douyin chat selectors — tune these when DOM changes.
SELECTORS = {
    "chat_input": '[contenteditable="true"]',
    "chat_input_fallback": 'div[class*="editor"]',
    "send_btn": 'button[class*="send"]',
    "send_btn_fallback": 'text=发送',
    "chat_iframe": 'iframe[src*="chat"], iframe[src*="im"]',
}


class ChatMonitor:
    def __init__(self, page: Page, group_id: str, group_url: str):
        self.page = page                  # Main Page — always retains this for wait_for_timeout
        self._frame: Frame = page.main_frame  # Active frame — may be an iframe
        self.group_id = group_id
        self.group_url = group_url
        self._seen_ids: set[str] = set()
        self._message_callback: Callable[[ChatMessage], None] | None = None
        self._observer_injected = False
        self._debug_logger = get_logger("chat_monitor")

    def navigate(self) -> None:
        logger.info("Navigating to group chat: %s", self.group_url)
        self._debug_logger.debug(f"[{self.group_id}] Navigating to: {self.group_url}")
        self._observer_injected = False
        self.page.goto(self.group_url, wait_until="domcontentloaded", timeout=30000)
        self._wait_for_stable_page()

        # Check if chat is inside an iframe
        iframe = self.page.locator(SELECTORS["chat_iframe"]).first
        if iframe.count():
            frame = iframe.content_frame()
            if frame:
                logger.info("Chat inside iframe, using iframe context")
                self._frame = frame
            else:
                self._frame = self.page.main_frame
        else:
            self._frame = self.page.main_frame

        logger.info("Group chat page loaded (frame URL: %s)", self._frame.url)
        self._debug_logger.debug(f"[{self.group_id}] Page loaded, frame URL: {self._frame.url}")

    def _wait_for_stable_page(self) -> None:
        """Wait for the SPA to finish client-side navigation."""
        initial_url = self.page.url
        deadline = time.time() + 10
        while time.time() < deadline:
            self.page.wait_for_timeout(1000)
            current_url = self.page.url
            if current_url != initial_url:
                logger.info("Page navigated: %s -> %s", initial_url[:60], current_url[:60])
                initial_url = current_url
                continue
            self.page.wait_for_timeout(1000)
            break

    def on_message(self, callback: Callable[[ChatMessage], None]) -> None:
        self._message_callback = callback

    def _inject_observer(self) -> bool:
        js_code = """() => {
            if (!window.__dyrobot_observer_injected) {
                window.__dyrobot_messages = [];
                var SKIP_TAGS = new Set(['SCRIPT','STYLE','LINK','META','NOSCRIPT','IFRAME','SVG','PATH']);
                var observer = new MutationObserver(function(mutations) {
                    for (var mi = 0; mi < mutations.length; mi++) {
                        var nodes = mutations[mi].addedNodes;
                        for (var i = 0; i < nodes.length; i++) {
                            var node = nodes[i];
                            if (node.nodeType !== 1) continue;
                            if (SKIP_TAGS.has(node.tagName)) continue;
                            var text = (node.textContent || '').trim();
                            if (!text || text.length > 5000) continue;
                            if (text.indexOf('%7B') === 0 || text.indexOf('if (') === 0 || (text.indexOf('.') === 0 && text.indexOf('{') !== -1)) continue;
                            window.__dyrobot_messages.push({text: text, time: Date.now()});
                        }
                    }
                });
                observer.observe(document.body, {childList: true, subtree: true});
                window.__dyrobot_observer_injected = true;
            }
        }"""
        try:
            self._frame.evaluate(js_code)
            self._observer_injected = True
            self._debug_logger.debug(f"[{self.group_id}] Observer injected successfully")
            return True
        except PlaywrightError as e:
            if "context was destroyed" in str(e) or "detached Frame" in str(e):
                logger.warning("Observer injection failed: page context changed, will retry")
                self._observer_injected = False
                return False
            raise
        return True

    def poll(self) -> list[ChatMessage]:
        if not self._observer_injected:
            if not self._inject_observer():
                return []

        try:
            raw_messages = self._frame.evaluate("""() => {
                var msgs = window.__dyrobot_messages || [];
                window.__dyrobot_messages = [];
                return msgs;
            }""")

            if raw_messages:
                logger.info(f"[{self.group_id}] Raw captured from JS: {len(raw_messages)} messages")
                for i, raw in enumerate(raw_messages):
                    text = raw.get("text", "")
                    logger.info(f"[{self.group_id}]  Raw[{i}]: {repr(text)}")

            new_messages = []
            for raw in raw_messages:
                text = raw.get("text", "").strip()

                if text:
                    logger.info(f"[{self.group_id}] Processing: {repr(text)}")

                if not text:
                    continue

                # 检查是否有效
                is_valid = self._is_valid_chat_text(text)
                if not is_valid:
                    logger.info(f"[{self.group_id}] Filtered by _is_valid_chat_text: {repr(text[:100])}")
                    continue

                msg_id = hashlib.md5(text.encode()).hexdigest()[:16]
                if msg_id in self._seen_ids:
                    self._debug_logger.debug(f"[{self.group_id}] Duplicate msg_id: {msg_id}")
                    continue
                self._seen_ids.add(msg_id)
                if len(self._seen_ids) > 10000:
                    self._seen_ids.clear()

                msg = ChatMessage(
                    group_id=self.group_id,
                    user_name="",
                    content=text,
                    timestamp=raw.get("time", 0) / 1000.0,
                    msg_id=msg_id,
                )
                new_messages.append(msg)
                self._debug_logger.info(f"[{self.group_id}] ACCEPTED message: {repr(text[:100])}")

            for msg in new_messages:
                logger.info("[%s] NEW: %s", self.group_id, msg.content[:80])
                if self._message_callback:
                    try:
                        self._debug_logger.debug(f"[{self.group_id}] Calling message_callback for: {repr(msg.content[:100])}")
                        self._message_callback(msg)
                    except Exception as e:
                        logger.error("Error in message callback: %s", e)
                        self._debug_logger.error(f"[{self.group_id}] Callback error: {e}", exc_info=True)

            return new_messages
        except PlaywrightError as e:
            if "context was destroyed" in str(e) or "detached Frame" in str(e):
                logger.warning("Poll failed: page context changed, will re-inject observer")
                self._observer_injected = False
                return []
            logger.error("Playwright error in poll: %s", e)
            self._debug_logger.error(f"[{self.group_id}] Playwright error: {e}", exc_info=True)
            return []
        except Exception as e:
            logger.error("Error in poll: %s", e)
            self._debug_logger.error(f"[{self.group_id}] Error: {e}", exc_info=True)
            return []

    @staticmethod
    def _is_valid_chat_text(text: str) -> bool:
        if text.startswith("if (") or text.startswith("window.") or text.startswith("function"):
            return False
        if text.startswith(".") and ("{" in text and "}" in text):
            return False
        if text.startswith("%7B") or "%22" in text[:20]:
            return False
        noise = {"抖音聊天", "进入全屏", "直播加载中", "登录后免费畅享高清视频"}
        if text in noise:
            return False
        if text.startswith(".") and "font-family" in text:
            return False

        # 最小化过滤，让 router来处理重复和自说自话的判断
        # 只过滤明显的噪音
        text_stripped = text.strip()
        if not text_stripped:
            return False

        # 注意：不过滤用户输入的命令！让 router 来处理
        return True

    def _find_input(self):
        for sel in [SELECTORS["chat_input"], SELECTORS["chat_input_fallback"]]:
            el = self._frame.locator(sel).first
            if el.count():
                return el
        return None

    def _find_send_btn(self):
        for sel in [SELECTORS["send_btn"], SELECTORS["send_btn_fallback"]]:
            el = self._frame.locator(sel).first
            if el.count():
                return el
        return None

    def send_message(self, text: str) -> bool:
        self._debug_logger.info(f"[{self.group_id}] SENDING message: {repr(text[:100])}")
        try:
            input_el = self._find_input()
            if not input_el:
                logger.error("[%s] Chat input not found", self.group_id)
                self._debug_logger.error(f"[{self.group_id}] Chat input not found!")
                return False

            # ── Phase 1: Focus and clear input ──
            input_el.click()
            self.page.wait_for_timeout(300)

            # Multiple ways to clear the input
            for attempt in range(3):
                try:
                    input_el.fill("")
                except Exception:
                    pass
                self.page.wait_for_timeout(100)
                try:
                    self.page.keyboard.press("Control+A")
                    self.page.wait_for_timeout(50)
                    self.page.keyboard.press("Backspace")
                    self.page.wait_for_timeout(100)
                except Exception:
                    pass
                # Verify input is empty
                try:
                    current = input_el.text_content() or ""
                    if not current.strip():
                        break
                except Exception:
                    break

            # ── Phase 2: Type message ──
            input_el.type(text, delay=50)
            self.page.wait_for_timeout(500)

            # ── Phase 3: Send — try multiple methods ──
            sent = False

            # Method A: Send button
            send_btn = self._find_send_btn()
            if send_btn:
                try:
                    send_btn.click()
                    self.page.wait_for_timeout(500)
                    sent = True
                    self._debug_logger.debug(f"[{self.group_id}] Sent via send button")
                except Exception:
                    pass

            # Method B: Enter key on page
            if not sent:
                try:
                    self.page.keyboard.press("Enter")
                    self.page.wait_for_timeout(500)
                    sent = True
                    self._debug_logger.debug(f"[{self.group_id}] Sent via page Enter")
                except Exception:
                    pass

            # Method C: Enter key on frame
            if not sent:
                try:
                    self._frame.keyboard.press("Enter")
                    self.page.wait_for_timeout(500)
                    sent = True
                    self._debug_logger.debug(f"[{self.group_id}] Sent via frame Enter")
                except Exception:
                    pass

            # ── Phase 4: Verify — check if input was cleared (message sent) ──
            if sent:
                try:
                    remaining = input_el.text_content() or ""
                    if remaining.strip():
                        logger.warning("[%s] Input not cleared after send, retrying with Enter", self.group_id)
                        self.page.keyboard.press("Enter")
                        self.page.wait_for_timeout(500)
                except Exception:
                    pass

            if sent:
                logger.info("[%s] Sent: %s", self.group_id, text[:80])
                self._debug_logger.info(f"[{self.group_id}] SEND SUCCESSFUL: {repr(text[:100])}")
            else:
                logger.error("[%s] All send methods failed for: %s", self.group_id, text[:80])
                self._debug_logger.error(f"[{self.group_id}] SEND FAILED!")

            return sent
        except Exception as e:
            logger.error("[%s] Error sending message: %s", self.group_id, e)
            self._debug_logger.error(f"[{self.group_id}] Send error: {e}", exc_info=True)
            return False
