import os
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
from pydantic import BaseModel, Field

ENV_PATH = Path(__file__).resolve().parents[2] / ".env"

VERIFIED_FREE_CHAIN = [('gemini-3.6-flash', 'HIGH'), ('gemini-3.5-flash-lite', 'HIGH'), ('gemini-3.1-flash-lite', None)]


def get_clean_gemini_key() -> str:
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("GEMINI_ARGON_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return os.getenv("GEMINI_ARGON_API_KEY", "").strip().strip('"').strip("'")


def extract_non_thought_text(data: Dict[str, Any]) -> str:
    parts: List[Dict[str, Any]] = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
    answer_chunks = [p["text"].strip() for p in parts if "text" in p and not p.get("thought")]
    if answer_chunks:
        return "\n".join(answer_chunks).strip()
    if parts and "text" in parts[-1]:
        return parts[-1]["text"].strip()
    return ""


class TaskComplexity(str, Enum):
    FAST_ROUTING = "fast"
    DEEP_CODING = "smart"
    SUPREME_SYNTHESIS = "argon"


class SubscriptionTier(str, Enum):
    FREE = "free"
    STARTER = "starter"
    PRO_ULTRON = "pro_ultron"


class RouterRequest(BaseModel):
    user_id: str
    tier: SubscriptionTier = SubscriptionTier.FREE
    complexity: TaskComplexity = TaskComplexity.SUPREME_SYNTHESIS
    system_prompt: str
    user_prompt: str
    code_context: Optional[str] = None
    target_symbol: Optional[str] = None
    temperature: float = Field(default=0.5, ge=0.0, le=1.5)
    max_tokens: int = Field(default=8192, ge=64, le=65536)
    byok_api_key: Optional[str] = None
    byok_base_url: Optional[str] = None
    bypass_cache: bool = False


class NineBillionTokenRouter:
    async def _call_free_gemini(
        self, gemini_key: str, system_prompt: str, user_prompt: str
    ) -> Dict[str, Any]:
        if not gemini_key or "replace_with" in gemini_key:
            raise RuntimeError("GEMINI_ARGON_API_KEY missing in .env")

        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": gemini_key,
        }

        last_error = ""
        # Force IPv4 (0.0.0.0) so mobile hotspot IPv6 never causes httpx.ReadTimeout
        ipv4_async = httpx.AsyncHTTPTransport(verify=False, local_address="0.0.0.0")
        timeout_cfg = httpx.Timeout(30.0, connect=10.0, read=30.0, write=10.0)

        async with httpx.AsyncClient(transport=ipv4_async, timeout=timeout_cfg) as client:
            for model_name, thinking_level in VERIFIED_FREE_CHAIN:
                payload: Dict[str, Any] = {
                    "contents": [
                        {
                            "role": "user",
                            "parts": [{"text": f"{system_prompt}\n\nUser request: {user_prompt}"}],
                        }
                    ],
                }
                if thinking_level:
                    payload["generationConfig"] = {
                        "thinkingConfig": {"thinkingLevel": thinking_level}
                    }

                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent"
                try:
                    resp = await client.post(url, headers=headers, json=payload)
                    if resp.status_code == 200:
                        data = resp.json()
                        text = extract_non_thought_text(data)
                        return {
                            "content": text,
                            "provider_model": f"{model_name} ({thinking_level or 'DEFAULT'})",
                            "route_tier": f"free_tier_{model_name}",
                        }
                    last_error = f"{model_name} HTTP {resp.status_code}"
                except Exception as exc:
                    last_error = f"{model_name} {exc}"
                    continue
        raise RuntimeError(last_error)

    async def dispatch(self, req: RouterRequest) -> Dict[str, Any]:
        gemini_key = get_clean_gemini_key()
        user_text = req.user_prompt
        if req.code_context:
            user_text = f"{user_text}\n\n[CODE_CONTEXT]:\n{req.code_context}"
        return await self._call_free_gemini(gemini_key, req.system_prompt, user_text)
