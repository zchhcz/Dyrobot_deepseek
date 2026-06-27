import time
import httpx
from ..utils.logger import setup_logger

logger = setup_logger(__name__)

DEEPSEEK_BASE_URL = "https://api.deepseek.com"
MAX_RETRIES = 3
RETRY_BACKOFF = 1.5  # exponential backoff multiplier


class DeepSeekClient:
    def __init__(
        self,
        api_key: str,
        model: str = "deepseek-chat",
        max_tokens: int = 2048,
        temperature: float = 0.7,
        timeout: float = 30.0,
    ):
        self.api_key = api_key
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.timeout = timeout
        self._client = httpx.Client(
            base_url=DEEPSEEK_BASE_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            timeout=timeout,
        )

    def chat(self, messages: list[dict], system_prompt: str | None = None) -> str:
        full_messages = []
        if system_prompt:
            full_messages.append({"role": "system", "content": system_prompt})
        full_messages.extend(messages)

        body = {
            "model": self.model,
            "messages": full_messages,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "stream": False,
        }

        last_error = None
        for attempt in range(MAX_RETRIES):
            try:
                resp = self._client.post("/v1/chat/completions", json=body)
                resp.raise_for_status()
                data = resp.json()
                return data["choices"][0]["message"]["content"]
            except httpx.HTTPStatusError as e:
                last_error = e
                logger.warning(
                    "DeepSeek API HTTP %d (attempt %d/%d): %s",
                    e.response.status_code,
                    attempt + 1,
                    MAX_RETRIES,
                    e.response.text[:300],
                )
                if e.response.status_code == 429:
                    time.sleep(RETRY_BACKOFF ** (attempt + 1))
                    continue
                if e.response.status_code >= 500:
                    time.sleep(RETRY_BACKOFF ** (attempt + 1))
                    continue
                raise
            except httpx.TimeoutException as e:
                last_error = e
                logger.warning("DeepSeek API timeout (attempt %d/%d)", attempt + 1, MAX_RETRIES)
                time.sleep(RETRY_BACKOFF ** (attempt + 1))
            except Exception as e:
                last_error = e
                logger.warning("DeepSeek API error (attempt %d/%d): %s", attempt + 1, MAX_RETRIES, str(e))
                time.sleep(RETRY_BACKOFF ** (attempt + 1))

        raise RuntimeError(f"DeepSeek API failed after {MAX_RETRIES} retries") from last_error

    def close(self):
        self._client.close()
