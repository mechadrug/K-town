import aiohttp
from typing import Optional

class LLMClient:
    def __init__(self, base_url, api_key, model, provider="longcat"):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.provider = provider
        self._session = None
        self._call_count = 0

    async def _session_get(self):
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(headers={"Authorization":f"Bearer {self.api_key}","Content-Type":"application/json"})
        return self._session

    async def call(self, prompt, system=""):
        if not self.api_key:
            return f"[LLM mock] {prompt[:50]}..."
        s = await self._session_get()
        payload = {"model":self.model,"messages":[{"role":"system","content":system or "You are a character in K-town. Respond in Chinese."},{"role":"user","content":prompt}],"max_tokens":256,"temperature":0.7}
        try:
            async with s.post(f"{self.base_url}/v1/chat/completions",json=payload) as r:
                if r.status==200:
                    d=await r.json()
                    self._call_count+=1
                    return d["choices"][0]["message"]["content"]
                return f"[LLM error {r.status}]"
        except Exception as e:
            return f"[LLM error] {str(e)[:80]}"

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

