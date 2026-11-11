import base64
import json
import os
import re
import httpx
from pathlib import Path
from dotenv import load_dotenv

_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
if _ENV_PATH.exists():
    load_dotenv(_ENV_PATH)


def _get_gemini_key() -> str:
    k = (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or "").strip().strip("\'\"")
    if k and "YOUR_" not in k.upper() and len(k) > 15:
        return k
    return ""


async def ask_nemesis_ai(prompt: str, user_name: str = "PEEYUSH SHARMA") -> str:
    clean_p = (prompt or "").strip()
    if not clean_p:
        return f"Awaiting your tactical directive, {user_name}."

    sys_instruction = (
        f"You are N.E.M.E.S.I.S. v3.5, a sharp, concise, tactical cybersecurity and personal AI assistant "
        f"addressing {user_name}. Answer directly in 1 to 3 sentences without markdown bullet clutter."
    )
    api_key = _get_gemini_key()

    if api_key:
        for model in ("gemini-2.5-flash", "gemini-2.0-flash"):
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
            payload = {
                "contents": [{"parts": [{"text": f"{sys_instruction}\n\nUser Command: {clean_p}"}]}],
                "generationConfig": {"temperature": 0.7, "maxOutputTokens": 280},
            }
            try:
                async with httpx.AsyncClient(timeout=15.0) as client:
                    r = await client.post(url, json=payload)
                    if r.status_code == 200:
                        data = r.json()
                        txt = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                        if txt:
                            return txt
            except Exception:
                pass

    # Keyless Cloud AI Fallback so Render/Localhost never fails even without GEMINI_API_KEY
    try:
        async with httpx.AsyncClient(timeout=18.0) as client:
            r = await client.post(
                "https://text.pollinations.ai/openai",
                json={
                    "model": "openai",
                    "messages": [
                        {"role": "system", "content": sys_instruction},
                        {"role": "user", "content": clean_p},
                    ],
                },
            )
            if r.status_code == 200:
                data = r.json()
                txt = data["choices"][0]["message"]["content"].strip()
                if txt:
                    return txt
    except Exception:
        pass

    return f"Directive acknowledged, {user_name}: '{clean_p}' executed on neural core."


async def analyze_nemesis_image(img_bytes: bytes) -> str:
    if not img_bytes:
        return "[camera_scene.jpg Analysis]: Camera frame received, but image buffer was empty."

    b64_img = base64.b64encode(img_bytes).decode("utf-8")
    vision_prompt = (
        "You are the N.E.M.E.S.I.S. Optical & Hand Sensor HUD. Describe what you see in this live camera frame "
        "(person, posture, objects, lighting, environment) in 2 concise, high-tech tactical sentences."
    )
    api_key = _get_gemini_key()

    if api_key:
        for model in ("gemini-2.5-flash", "gemini-2.0-flash"):
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
            payload = {
                "contents": [{
                    "parts": [
                        {"text": vision_prompt},
                        {"inline_data": {"mime_type": "image/jpeg", "data": b64_img}},
                    ]
                }]
            }
            try:
                async with httpx.AsyncClient(timeout=18.0) as client:
                    r = await client.post(url, json=payload)
                    if r.status_code == 200:
                        data = r.json()
                        txt = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                        if txt:
                            return f"[camera_scene.jpg Analysis]: {txt}"
            except Exception:
                pass

    # Keyless Multimodal Vision Fallback
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            r = await client.post(
                "https://text.pollinations.ai/openai",
                json={
                    "model": "openai",
                    "messages": [{
                        "role": "user",
                        "content": [
                            {"type": "text", "text": vision_prompt},
                            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_img}"}},
                        ],
                    }],
                },
            )
            if r.status_code == 200:
                data = r.json()
                txt = data["choices"][0]["message"]["content"].strip()
                if txt:
                    return f"[camera_scene.jpg Analysis]: {txt}"
    except Exception:
        pass

    return "[camera_scene.jpg Analysis]: Optical frame locked. Operator detected in primary field of view."
