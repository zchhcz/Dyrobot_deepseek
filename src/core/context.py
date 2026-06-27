import time
from threading import Lock
from ..utils.logger import setup_logger

logger = setup_logger(__name__)


class ContextManager:
    """
    Manages per-group, per-user conversation history.
    Data structure: {group_id: {user_id: [{"role": ..., "content": ..., "timestamp": ...}]}}
    """

    def __init__(self, max_history_rounds: int = 10, session_timeout: int = 1800):
        self.max_history_rounds = max_history_rounds
        self.session_timeout = session_timeout
        self._store: dict[str, dict[str, list[dict]]] = {}
        self._lock = Lock()

    def add_message(self, group_id: str, user_id: str, role: str, content: str) -> None:
        with self._lock:
            if group_id not in self._store:
                self._store[group_id] = {}
            if user_id not in self._store[group_id]:
                self._store[group_id][user_id] = []

            self._store[group_id][user_id].append({
                "role": role,
                "content": content,
                "timestamp": time.time(),
            })

            # Trim to max_history_rounds * 2 messages (user + assistant per round)
            max_msgs = self.max_history_rounds * 2
            if len(self._store[group_id][user_id]) > max_msgs:
                self._store[group_id][user_id] = self._store[group_id][user_id][-max_msgs:]

    def get_history(self, group_id: str, user_id: str) -> list[dict]:
        """Return messages in OpenAI-compatible format [{role, content}]."""
        with self._lock:
            self._cleanup_expired(group_id)
            user_msgs = self._store.get(group_id, {}).get(user_id, [])
            return [{"role": m["role"], "content": m["content"]} for m in user_msgs]

    def reset(self, group_id: str, user_id: str | None = None) -> None:
        with self._lock:
            if group_id not in self._store:
                return
            if user_id:
                self._store[group_id].pop(user_id, None)
                logger.info("Reset context for user %s in group %s", user_id, group_id)
            else:
                self._store[group_id].clear()
                logger.info("Reset all contexts in group %s", group_id)

    def _cleanup_expired(self, group_id: str) -> None:
        """Remove expired user sessions within a group."""
        now = time.time()
        if group_id not in self._store:
            return
        expired = []
        for uid, msgs in self._store[group_id].items():
            if not msgs:
                expired.append(uid)
                continue
            last_ts = msgs[-1]["timestamp"]
            if now - last_ts > self.session_timeout:
                expired.append(uid)
        for uid in expired:
            del self._store[group_id][uid]
            logger.debug("Cleaned up expired session: %s/%s", group_id, uid)
