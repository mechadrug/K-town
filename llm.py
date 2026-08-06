"""LLM client with per-provider adapters.

K-town supports multiple LLM vendors; each speaks a different wire format.
`call()` dispatches to the adapter registered for `provider`.

- deepseek / openai: OpenAI Chat Completions API
- longcat: Anthropic Messages API
- unknown providers fall back to OpenAI Chat Completions.
"""
import aiohttp


class _OpenAICompat:
    """OpenAI Chat Completions 协议（DeepSeek、OpenAI、硅基流动等）。"""
    path = "/v1/chat/completions"

    @staticmethod
    def build_payload(model, prompt, system):
        return {
            "model": model,
            "max_tokens": 256,
            "temperature": 0.7,
            "messages": [
                {"role": "system", "content": system or "You are a character in K-town. Respond in Chinese."},
                {"role": "user", "content": prompt},
            ],
        }

    @staticmethod
    def parse(data):
        return data["choices"][0]["message"]["content"]


class _AnthropicCompat:
    """Anthropic Messages API 协议（LongCat 等兼容端点）。"""
    path = "/v1/messages"

    @staticmethod
    def build_payload(model, prompt, system):
        return {
            "model": model,
            "max_tokens": 256,
            "temperature": 0.7,
            "system": system or "You are a character in K-town. Respond in Chinese.",
            "messages": [{"role": "user", "content": prompt}],
        }

    @staticmethod
    def parse(data):
        return data["content"][0]["text"]


_ADAPTERS = {
    "deepseek": _OpenAICompat,
    "openai": _OpenAICompat,
    "longcat": _AnthropicCompat,
}


class LLMClient:
    def __init__(self, base_url, api_key, model, provider="longcat"):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.provider = provider
        self._adapter = _ADAPTERS.get(provider, _OpenAICompat)
        self._session = None
        self._call_count = 0

    async def _session_get(self):
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"})
        return self._session

    async def call(self, prompt, system=""):
        if not self.api_key:
            return f"[LLM mock] {prompt[:50]}..."
        s = await self._session_get()
        payload = self._adapter.build_payload(self.model, prompt, system)
        url = f"{self.base_url}{self._adapter.path}"
        try:
            async with s.post(url, json=payload) as r:
                if r.status == 200:
                    d = await r.json()
                    self._call_count += 1
                    return self._adapter.parse(d)
                return f"[LLM error {r.status}]"
        except Exception as e:
            return f"[LLM error] {str(e)[:80]}"

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()
