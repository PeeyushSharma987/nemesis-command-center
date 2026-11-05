import json
import os
from pathlib import Path
from typing import Any, Dict, List, Tuple

import httpx
from fastapi import WebSocket, WebSocketDisconnect

ROOT_DIR = Path(__file__).resolve().parents[2]
ENV_PATH = ROOT_DIR / ".env"

VERIFIED_VISION_CHAIN = [('gemini-3.6-flash', 'HIGH'), ('gemini-3.5-flash-lite', 'HIGH'), ('gemini-3.1-flash-lite', None)]


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


class LiveCameraEyeController:
    @staticmethod
    def _extract_frame(raw_message: str) -> Tuple[str, int]:
        savage_level = 85
        frame_str = ""
        try:
            data = json.loads(raw_message)
            if isinstance(data, dict):
                savage_level = int(data.get("savage_level", 85))
                for key in ("frame_b64", "frame", "image", "image_b64", "data"):
                    val = data.get(key)
                    if isinstance(val, str) and len(val) > 50:
                        frame_str = val
                        break
        except Exception:
            frame_str = raw_message.strip()

        if "base64," in frame_str:
            frame_str = frame_str.split("base64,", 1)[1]
        return frame_str.strip(), savage_level

    async def _call_free_vision(self, gemini_key: str, clean_b64: str, savage_level: int) -> Tuple[str, str]:
        if not gemini_key or "replace_with" in gemini_key:
            raise RuntimeError("No AQ. key configured")

        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": gemini_key,
        }
        last_err = ""
        ipv4_async = httpx.AsyncHTTPTransport(verify=False, local_address="0.0.0.0")
        timeout_cfg = httpx.Timeout(30.0, connect=10.0, read=30.0, write=10.0)

        async with httpx.AsyncClient(transport=ipv4_async, timeout=timeout_cfg) as client:
            for model_name, thinking_level in VERIFIED_VISION_CHAIN:
                payload: Dict[str, Any] = {
                    "contents": [
                        {
                            "role": "user",
                            "parts": [
                                {
                                    "text": (
                                        f"You are N.E.M.E.S.I.S. Live Camera Eye (Savage Level {savage_level}%). "
                                        "Look closely at this webcam image. Explicitly name the exact object the person "
                                        "is holding in their hand (or describe their glasses, expression, and clothes if "
                                        "not holding anything) and deliver a witty, savage 2-sentence roast about it."
                                    )
                                },
                                {"inline_data": {"mime_type": "image/jpeg", "data": clean_b64}},
                            ],
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
                        body = resp.json()
                        text = extract_non_thought_text(body)
                        return text, f"{model_name} ({thinking_level or 'DEFAULT'})"
                    last_err = f"{model_name} HTTP {resp.status_code}"
                except Exception as exc:
                    last_err = f"{model_name} {exc}"
                    continue
        raise RuntimeError(last_err)

    async def inspect_frame(self, raw_message: str) -> Dict[str, Any]:
        gemini_key = get_clean_gemini_key()
        clean_b64, savage_level = self._extract_frame(raw_message)

        if len(clean_b64) < 100:
            roast_text = "Click Enable Camera & Hands first so your live webcam feed is active before scanning."
            provider = "live_eye_guard"
        else:
            try:
                roast_text, provider = await self._call_free_vision(gemini_key, clean_b64, savage_level)
            except Exception as exc:
                roast_text = f"Vision scan error: {exc}"
                provider = "vision_error"

        return {
            "status": "VISION_LOCKED",
            "provider": provider,
            "nemesis_vision": roast_text,
            "vision_roast": roast_text,
            "roast": roast_text,
            "message": roast_text,
            "nemesis_speech": roast_text,
            "nemesis_response": roast_text,
        }

    async def handle_live_session(self, websocket: WebSocket, session_id: str) -> None:
        await websocket.accept()
        try:
            while True:
                raw_msg = await websocket.receive_text()
                result = await self.inspect_frame(raw_msg)
                result["session_id"] = session_id
                await websocket.send_json(result)
        except WebSocketDisconnect:
            return
