import ast
import importlib
import asyncio
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import httpx
from pydantic import BaseModel, Field

from backend.agents.airgapped_scraper import AirgappedZeroPHPScraper
from backend.memory.digital_twin_and_ledger import MemoryAndMistakeVault
from backend.router.token_router import (
    NineBillionTokenRouter,
    RouterRequest,
    SubscriptionTier,
    TaskComplexity,
    get_clean_gemini_key,
)
from device_bridge.android_swarm_adb import AndroidSwarmBridge
from device_bridge.pc_daemon import PSwarmDaemon


class CommanderCommand(BaseModel):
    user_id: str
    prompt: str = Field(..., min_length=1, max_length=8000)
    tier: SubscriptionTier = SubscriptionTier.FREE
    savage_level_override: Optional[int] = Field(default=None, ge=10, le=100)
    scrape_url: Optional[str] = None
    supplied_context: Optional[Dict[str, Any]] = None


class NemesisSupremeCommander:
    def __init__(self) -> None:
        self.router = NineBillionTokenRouter()
        self.memory = MemoryAndMistakeVault()

    async def _mutate_self_ouroboros(self, target_file: str, instruction: str, supplied_key: str) -> str:
        """Uses Gemini 3.6 Flash to write, AST-verify, and hot-swap a new hardware/software skill into N.E.M.E.S.I.S."""
        gemini_key = get_clean_gemini_key()
        if not gemini_key:
            return "Ouroboros Error: Gemini API key missing."

        skills_path = Path(__file__).resolve().parent / "ouroboros_skills.py"
        current_skills_code = skills_path.read_text(encoding="utf-8")

        system_prompt = (
            "You are the N.E.M.E.S.I.S. Ouroboros Self-Mutating Engine. "
            "Rewrite the Python file below to add the new capability requested by Peeyush inside `execute_learned_skill(prompt: str, lower: str) -> Optional[str]`. "
            "RULES:\n"
            "1. Keep all existing learned skills intact and add the new `if ...:` check above `# --- OUROBOROS_INJECTION_MARKER ---`.\n"
            "2. To run ADB shell commands on Peeyush's Android phone, call: "
            "`out = AndroidSwarmBridge._run_adb_sync(dev, ['shell', '<command>'])`.\n"
            "   - Useful ADB examples:\n"
            "     * Battery & Temp: `dumpsys battery` (parse `level:` and `temperature:` which is tenths of °C)\n"
            "     * Flashlight ON: `cmd statusbar click-tile flashlight` or `input keyevent 224`\n"
            "     * Storage space: `df -h /data`\n"
            "     * Wi-Fi & IP: `ip addr show wlan0`\n"
            "3. Return a clear, authoritative string response when the skill triggers, or `None` if the prompt does not match.\n"
            "4. Output ONLY raw valid Python code for the complete file—no markdown fences, no explanations."
        )

        user_msg = f"CURRENT FILE:\n{current_skills_code}\n\nNEW MUTATION REQUEST FROM PEEYUSH:\n{instruction}"
        headers = {"Content-Type": "application/json", "x-goog-api-key": gemini_key}
        payload = {
            "contents": [{"role": "user", "parts": [{"text": system_prompt + "\n\n" + user_msg}]}],
            "generationConfig": {"temperature": 0.2},
        }

        ipv4_async = httpx.AsyncHTTPTransport(verify=False, local_address="0.0.0.0")
        timeout_cfg = httpx.Timeout(40.0, connect=10.0, read=40.0, write=10.0)

        async with httpx.AsyncClient(transport=ipv4_async, timeout=timeout_cfg) as client:
            for model_name in ("gemini-3.6-flash", "gemini-3.5-flash-lite", "gemini-3.1-flash-lite"):
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent"
                try:
                    resp = await client.post(url, headers=headers, json=payload)
                    if resp.status_code == 200:
                        parts = resp.json().get("candidates", [{}])[0].get("content", {}).get("parts", [])
                        raw_code = "\n".join(p.get("text", "") for p in parts if not p.get("thought")).strip()
                        raw_code = re.sub(r"^```(?:python)?\s*", "", raw_code, flags=re.I)
                        raw_code = re.sub(r"\s*```$", "", raw_code).strip()

                        # AST Safety Verification before touching disk
                        ast.parse(raw_code)
                        skills_path.write_text(raw_code, encoding="utf-8")
                        return (
                            f"Ouroboros Self-Mutation Complete via {model_name}! "
                            f"AST syntax verified & hot-swapped into N.E.M.E.S.I.S. Core for: '{instruction}'."
                        )
                except SyntaxError as syn_err:
                    return f"Ouroboros AST Shield blocked invalid syntax: {syn_err}"
                except Exception:
                    continue
        return "Ouroboros Error: Could not complete self-mutation request."

    @staticmethod
    def _extract_call_message(raw_text: str, recipient: str = "") -> str:
        clean = raw_text.strip()
        patterns = [
            r"(?:and\s+)?(?:tell\s+(?:him|her|them|mom|mummy|papa|dad|[a-zA-Z0-9_]+)\s+(?:that\s+)?|say\s+on\s+call\s+(?:that\s+)?|and\s+say\s+(?:that\s+)?|saying\s+(?:that\s+)?|say\s+that\s+|say\s+)(.+)$",
            r"^(?:yes\s*,?\s*)?(?:please\s+)?(?:call\s+(?:him|her|them|back|[a-zA-Z0-9_]+)\s+)(.+)$",
        ]
        for pat in patterns:
            m = re.search(pat, clean, re.I)
            if m:
                extracted = m.group(1).strip().strip(".!?,\x22\x27")
                if extracted and extracted.lower() not in ("on speaker", "on speakerphone", "back"):
                    return extracted
        return ""

    @classmethod
    def _parse_call_intent(cls, raw_prompt: str) -> Optional[Tuple[str, str]]:
        clean = raw_prompt.strip()
        lower = clean.lower()
        if not (lower.startswith("call ") or lower.startswith("dial ") or lower.startswith("please call ") or "make a call to" in lower):
            return None

        remainder = re.sub(r"^(?:hey\s+nemesis\s*,?\s*)?(?:please\s+)?(?:make\s+a\s+call\s+to|call|dial)\s+", "", clean, flags=re.I).strip()
        split_m = re.split(
            r"\s+(?:on\s+speaker(?:phone)?\s+)?(?:and\s+say(?:\s+that)?|and\s+tell(?:\s+him|\s+her|\s+them)?(?:\s+that)?|saying(?:\s+that)?|say\s+on\s+call|say|tell\s+(?:him|her|them))\s+",
            remainder,
            maxsplit=1,
            flags=re.I,
        )
        if len(split_m) == 2:
            contact = re.sub(r"\s+on\s+speaker(?:phone)?$", "", split_m[0], flags=re.I).strip().strip(".!?,\x22\x27")
            msg = split_m[1].strip().strip(".!?,\x22\x27")
            return contact, msg

        contact_only = re.sub(r"\s+on\s+speaker(?:phone)?[.!?]*$", "", remainder, flags=re.I).strip().strip(".!?,\x22\x27")
        return contact_only, ""

    async def _analyze_multimodal_attachment(
        self,
        user_prompt: str,
        attachment_b64: str,
        attachment_mime: str,
        attachment_name: str,
        attachment_text: str = "",
        audio_b64: str = "",
        audio_mime: str = "audio/webm",
    ) -> Dict[str, Any]:
        """Analyzes attached photos, videos, PDFs, or text/code files via Gemini and extracts optional hardware actions."""
        gemini_key = get_clean_gemini_key()
        if not gemini_key:
            return {"analysis": "Gemini API key missing.", "action": "none"}

        parts: List[Dict[str, Any]] = []

        system_instruction = (
            f"You are N.E.M.E.S.I.S., Peeyush's supreme AI system. Peeyush attached a file named '{attachment_name}' ({attachment_mime}). "
            f"User instruction: '{user_prompt}'. "
            "If an audio clip is also attached, listen to the audio clip for Peeyush's spoken instructions about this file. "
            "1. Carefully analyze the attached image, video, PDF, or file content to fulfill Peeyush's request. "
            "2. If Peeyush ALSO asks you to send the result/summary to someone via WhatsApp, Voice Note, Phone Call, or Email, "
            "populate the action fields; otherwise set action to 'none'. "
            "Respond ONLY with a valid JSON object using these exact keys: "
            '{"analysis": "<your clear, detailed analysis or answer for Peeyush>", '
            '"action": "<none | whatsapp_send | whatsapp_voice | phone_call | email_send>", '
            '"recipient": "<contact name, phone number, or email if action != none, else empty>", '
            '"message": "<exact message to send or speak to the recipient if action != none, else empty>"}'
        )
        parts.append({"text": system_instruction})

        if attachment_text:
            parts.append({"text": f"--- ATTACHED FILE CONTENT ({attachment_name}) ---\n{attachment_text[:30000]}"})
        elif attachment_b64:
            clean_b64 = attachment_b64.split("base64,", 1)[1].strip() if "base64," in attachment_b64 else attachment_b64.strip()
            parts.append({"inline_data": {"mime_type": attachment_mime or "image/jpeg", "data": clean_b64}})

        if audio_b64 and len(audio_b64) > 100:
            clean_aud = audio_b64.split("base64,", 1)[1].strip() if "base64," in audio_b64 else audio_b64.strip()
            parts.append({"inline_data": {"mime_type": audio_mime or "audio/webm", "data": clean_aud}})

        headers = {"Content-Type": "application/json", "x-goog-api-key": gemini_key}
        payload = {"contents": [{"role": "user", "parts": parts}]}

        ipv4_async = httpx.AsyncHTTPTransport(verify=False, local_address="0.0.0.0")
        timeout_cfg = httpx.Timeout(55.0, connect=10.0, read=55.0, write=20.0)

        async with httpx.AsyncClient(transport=ipv4_async, timeout=timeout_cfg) as client:
            for model_name in ("gemini-3.6-flash", "gemini-3.5-flash-lite", "gemini-3.1-flash-lite"):
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent"
                try:
                    resp = await client.post(url, headers=headers, json=payload)
                    if resp.status_code == 200:
                        cand_parts = resp.json().get("candidates", [{}])[0].get("content", {}).get("parts", [])
                        raw_txt = " ".join(p.get("text", "") for p in cand_parts if not p.get("thought")).strip()
                        m = re.search(r"\{.*\}", raw_txt, re.S)
                        if m:
                            try:
                                return json.loads(m.group(0))
                            except Exception:
                                pass
                        return {"analysis": raw_txt, "action": "none"}
                except Exception:
                    continue
        return {"analysis": f"Unable to process attachment '{attachment_name}'. Check file size or connection.", "action": "none"}

    async def _understand_voice_audio(
        self, audio_b64: str, audio_mime: str, alt_transcripts: List[str], active_alert: Optional[Dict[str, str]] = None
    ) -> Optional[Dict[str, str]]:
        gemini_key = get_clean_gemini_key()
        if not gemini_key or len(audio_b64) < 100:
            return None

        if "base64," in audio_b64:
            audio_b64 = audio_b64.split("base64,", 1)[1].strip()

        alert_context = ""
        if active_alert:
            alert_context = (
                f"CRITICAL CONTEXT: N.E.M.E.S.I.S. just called Peeyush about a {active_alert.get('type')} "
                f"from '{active_alert.get('sender')}'. "
                "If Peeyush says to call them or gives a message to tell them on call (e.g. 'call mom and say I am busy I will call later'), "
                f"set action to 'phone_call', recipient to '{active_alert.get('sender')}', and MUST put the exact spoken message "
                "(e.g. 'I am busy, I will call later') inside the 'message' field!"
            )

        instruction = (
            "Listen carefully to this voice command spoken by Peeyush (Indian English). "
            f"Browser speech-to-text guesses were: {alt_transcripts}. {alert_context} "
            "Return ONLY a single valid JSON object with these exact keys: "
            '{"transcript": "<exact words spoken>", '
            '"action": "<phone_call | whatsapp_send | whatsapp_voice | ignore | whatsapp_read | email_send | email_read | unlock | play_song | chat>", '
            '"recipient": "<contact name/number/email, e.g. Mom>", '
            '"message": "<REQUIRED for phone_call, whatsapp_send, and whatsapp_voice: the exact message to say or send, excluding command words like call mom and say>"}'
        )

        headers = {"Content-Type": "application/json", "x-goog-api-key": gemini_key}
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {"text": instruction},
                        {"inline_data": {"mime_type": audio_mime or "audio/webm", "data": audio_b64}},
                    ],
                }
            ]
        }

        ipv4_async = httpx.AsyncHTTPTransport(verify=False, local_address="0.0.0.0")
        timeout_cfg = httpx.Timeout(20.0, connect=8.0, read=20.0, write=8.0)

        async with httpx.AsyncClient(transport=ipv4_async, timeout=timeout_cfg) as client:
            for model_name in ("gemini-3.1-flash-lite", "gemini-3.5-flash-lite", "gemini-3.6-flash"):
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent"
                try:
                    resp = await client.post(url, headers=headers, json=payload)
                    if resp.status_code == 200:
                        parts = resp.json().get("candidates", [{}])[0].get("content", {}).get("parts", [])
                        raw_txt = " ".join(p.get("text", "") for p in parts if not p.get("thought")).strip()
                        m = re.search(r"\{.*?\}", raw_txt, re.S)
                        if m:
                            return json.loads(m.group(0))
                except Exception:
                    continue
        return None

    @staticmethod
    def _parse_whatsapp_intent(raw_prompt: str) -> Optional[Tuple[Optional[str], str]]:
        clean = raw_prompt.strip()
        lower = clean.lower()

        if "email" in lower or "gmail" in lower or "mail" in lower or "@" in lower or lower.startswith("call "):
            return None

        m_a = re.match(
            r"^(?:hey\s+nemesis\s*,?\s*)?(?:please\s+)?(?:send|text|whatsapp)\s+(?:a\s+|the\s+)?(?:whatsapp\s+)?(?:message\s+)?[\x22\x27]?(.+?)[\x22\x27]?\s+to\s+([a-zA-Z0-9_+\s]{2,25}?)(?:\s+on\s+whatsapp)?[.!?]*$",
            clean,
            re.I,
        )
        if m_a and not m_a.group(1).lower().startswith("to "):
            msg_part = m_a.group(1).strip().strip("\"\'")
            contact_part = m_a.group(2).strip().strip("\"\'")
            return contact_part, msg_part

        m_b = re.match(
            r"^(?:hey\s+nemesis\s*,?\s*)?(?:please\s+)?(?:send|text|whatsapp|message|tell)\s+(?:a\s+|the\s+)?(?:whatsapp\s+)?(?:message\s+)?(?:to\s+)?([a-zA-Z0-9_+]{2,20})\s+(?:on\s+whatsapp\s+)?(?:saying|that|with|message|:)\s+[\x22\x27]?(.+?)[\x22\x27]?[.!?]*$",
            clean,
            re.I,
        )
        if m_b:
            return m_b.group(1).strip(), m_b.group(2).strip().strip("\"\'")

        m_c = re.match(
            r"^(?:hey\s+nemesis\s*,?\s*)?(?:please\s+)?(?:whatsapp|message|text)\s+([a-zA-Z0-9_+]{2,20})\s+[\x22\x27]?(.+?)[\x22\x27]?[.!?]*$",
            clean,
            re.I,
        )
        if m_c and m_c.group(1).lower() not in ("my", "me", "the", "a", "on"):
            return m_c.group(1).strip(), m_c.group(2).strip().strip("\"\'")

        return None

    async def execute_command(self, cmd: CommanderCommand) -> Dict[str, Any]:
        twin = self.memory.get_user_twin(cmd.user_id)
        audio_b64 = ""
        audio_mime = "audio/webm"
        alt_transcripts: List[str] = []
        active_alert: Optional[Dict[str, str]] = None
        force_scan = False
        attachment_b64 = ""
        attachment_mime = ""
        attachment_name = ""
        attachment_text = ""

        if cmd.supplied_context:
            audio_b64 = str(cmd.supplied_context.get("audio_b64", ""))
            audio_mime = str(cmd.supplied_context.get("audio_mime", "audio/webm"))
            alt_transcripts = list(cmd.supplied_context.get("alt_transcripts", []))
            active_alert = cmd.supplied_context.get("active_alert")
            force_scan = bool(cmd.supplied_context.get("force_scan", False))
            attachment_b64 = str(cmd.supplied_context.get("attachment_b64", ""))
            attachment_mime = str(cmd.supplied_context.get("attachment_mime", ""))
            attachment_name = str(cmd.supplied_context.get("attachment_name", ""))
            attachment_text = str(cmd.supplied_context.get("attachment_text", ""))
            for k, v in cmd.supplied_context.items():
                if k not in (
                    "audio_b64",
                    "audio_mime",
                    "alt_transcripts",
                    "active_alert",
                    "force_scan",
                    "attachment_b64",
                    "attachment_mime",
                    "attachment_name",
                    "attachment_text",
                ):
                    twin = self.memory.update_user_fact(cmd.user_id, k, v)

        savage_level = cmd.savage_level_override or twin.savage_level
        raw_prompt = cmd.prompt.strip()
        heard_transcript = ""

        # --- SENTINEL POLLING ROUTE: CHECK FOR IMPORTANT WHATSAPP OR MISSED CALLS ---
        # --- OUROBOROS SELF-MUTATING ENGINE ROUTE ---
        if raw_prompt == "__OUROBOROS_MUTATE__":
            t_file = str((cmd.supplied_context or {}).get("target_file", "commander/nemesis_brain.py"))
            m_inst = str((cmd.supplied_context or {}).get("mutation_prompt", "")).strip()
            g_key = str((cmd.supplied_context or {}).get("god_key", "")).strip()
            mut_status = await self._mutate_self_ouroboros(t_file, m_inst, g_key)
            return {
                "commander": "N.E.M.E.S.I.S. OUROBOROS",
                "status": "MUTATED",
                "savage_level": savage_level,
                "nemesis_response": mut_status,
            }

        if raw_prompt == "__SENTINEL_SCAN__":
            scan_res = await AndroidSwarmBridge.scan_priority_alerts(force_latest=force_scan)
            if not scan_res.get("has_alert"):
                return {"commander": "N.E.M.E.S.I.S.", "status": "NO_ALERT", "has_alert": False}

            alert = scan_res["alert"]
            sender = re.sub(r"\s*\(\d+\s*messages?\)", "", alert["sender"]).strip()
            alert["sender"] = sender
            if alert["type"] == "missed_call":
                spoken_briefing = f"Peeyush, you have a missed call from {sender}. What should I tell them?"
            else:
                spoken_briefing = f"Peeyush, WhatsApp message from {sender} saying {alert['content']}. How should I reply?"

            return {
                "commander": "N.E.M.E.S.I.S.",
                "status": "ALERT_TRIGGERED",
                "has_alert": True,
                "alert": alert,
                "remote_called": bool(scan_res.get("remote_called", False)),
                "second_phone": scan_res.get("second_phone", ""),
                "nemesis_response": spoken_briefing,
            }

        # --- MULTIMODAL FILE, PHOTO & SMALL VIDEO ANALYSIS ROUTE ---
        if attachment_b64 or attachment_text:
            mm_res = await self._analyze_multimodal_attachment(
                user_prompt=raw_prompt,
                attachment_b64=attachment_b64,
                attachment_mime=attachment_mime,
                attachment_name=attachment_name or "attached_media",
                attachment_text=attachment_text,
                audio_b64=audio_b64,
                audio_mime=audio_mime,
            )
            analysis_txt = str(mm_res.get("analysis", "Analysis complete.")).strip()
            mm_action = str(mm_res.get("action", "none")).lower().strip()
            mm_rec = str(mm_res.get("recipient", "")).strip()
            mm_msg = str(mm_res.get("message", "")).strip() or analysis_txt
            mute_tts = False
            action_suffix = ""

            if mm_action == "whatsapp_send" and mm_msg:
                hw = await AndroidSwarmBridge.reply_whatsapp(message=mm_msg, phone_or_name=mm_rec or None)
                action_suffix = f" | Hardware Action: {hw['detail']}"
            elif mm_action == "whatsapp_voice" and mm_msg:
                hw = await AndroidSwarmBridge.send_whatsapp_voice_note(spoken_message=mm_msg, phone_or_name=mm_rec or None)
                action_suffix = f" | Hardware Action: {hw['detail']}"
                mute_tts = True
            elif mm_action == "phone_call" and mm_rec:
                hw = await AndroidSwarmBridge.place_voice_call(phone_or_name=mm_rec, spoken_message=mm_msg or None)
                action_suffix = f" | Hardware Action: {hw['detail']}"
                mute_tts = True
            elif mm_action == "email_send" and mm_msg:
                hw = await AndroidSwarmBridge.send_or_reply_email(body=mm_msg, recipient=mm_rec or None)
                action_suffix = f" | Hardware Action: {hw['detail']}"

            return {
                "commander": "N.E.M.E.S.I.S.",
                "status": "EXECUTED",
                "mute_hud_tts": mute_tts,
                "savage_level": savage_level,
                "nemesis_response": f"[{attachment_name or 'Media'} Analysis]: {analysis_txt}{action_suffix}",
            }

        # If an active_alert was bridged to Peeyush's second phone, hang up the bridge call first & wait 3s for radio release
        if active_alert and (audio_b64 or raw_prompt != "__SENTINEL_SCAN__"):
            await AndroidSwarmBridge.hang_up_call()
            await asyncio.sleep(3.0)

        # --- 0. IF VOICE AUDIO WAS RECORDED, LET GEMINI HEAR THE EXACT AUDIO ---
        if audio_b64:
            voice_parsed = await self._understand_voice_audio(audio_b64, audio_mime, alt_transcripts, active_alert)
            if voice_parsed:
                heard_transcript = str(voice_parsed.get("transcript", "")).strip()
                if heard_transcript:
                    raw_prompt = heard_transcript
                v_action = str(voice_parsed.get("action", "")).lower()
                v_recipient = str(voice_parsed.get("recipient", "")).strip() or (
                    active_alert.get("sender", "") if active_alert else ""
                )
                v_message = str(voice_parsed.get("message", "")).strip()
                if not v_message and heard_transcript:
                    v_message = self._extract_call_message(heard_transcript, v_recipient)

                if v_action == "ignore":
                    return {
                        "commander": "N.E.M.E.S.I.S.",
                        "status": "EXECUTED",
                        "heard_transcript": heard_transcript,
                        "savage_level": savage_level,
                        "nemesis_response": f"Standing down on {v_recipient}.",
                    }

                if v_action == "whatsapp_voice" and v_message:
                    res = await AndroidSwarmBridge.send_whatsapp_voice_note(
                        spoken_message=v_message, phone_or_name=v_recipient or None
                    )
                    return {
                        "commander": "N.E.M.E.S.I.S.",
                        "status": "EXECUTED",
                        "mute_hud_tts": True,
                        "heard_transcript": heard_transcript,
                        "savage_level": savage_level,
                        "nemesis_response": f"[Heard: '{heard_transcript}'] -> {res['detail']}",
                    }

                if v_action == "phone_call" and v_recipient:
                    res = await AndroidSwarmBridge.place_voice_call(
                        phone_or_name=v_recipient, spoken_message=v_message or None
                    )
                    return {
                        "commander": "N.E.M.E.S.I.S.",
                        "status": "EXECUTED",
                        "mute_hud_tts": True,
                        "heard_transcript": heard_transcript,
                        "savage_level": savage_level,
                        "nemesis_response": f"[Heard: '{heard_transcript}'] -> {res['detail']}",
                    }

                if v_action == "whatsapp_send" and v_message:
                    res = await AndroidSwarmBridge.reply_whatsapp(message=v_message, phone_or_name=v_recipient or None)
                    return {
                        "commander": "N.E.M.E.S.I.S.",
                        "status": "EXECUTED",
                        "heard_transcript": heard_transcript,
                        "savage_level": savage_level,
                        "nemesis_response": f"[Heard: '{heard_transcript}'] -> {res['detail']}",
                    }

        lower = raw_prompt.lower()

        # --- 0B. TEXT FALLBACK FOR ACTIVE SENTINEL PERMISSION ---
        if active_alert:
            target_sender = active_alert.get("sender", "")
            if any(w in lower for w in ("no", "ignore", "cancel", "dont", "don't", "later")) and "call later" not in lower:
                return {
                    "commander": "N.E.M.E.S.I.S.",
                    "status": "EXECUTED",
                    "nemesis_response": f"Standing down—no reply sent to {target_sender}.",
                }
            reply_body = self._extract_call_message(raw_prompt, target_sender) or raw_prompt
            if "voice" in lower:
                res = await AndroidSwarmBridge.send_whatsapp_voice_note(spoken_message=reply_body, phone_or_name=target_sender)
                return {
                    "commander": "N.E.M.E.S.I.S.",
                    "status": "EXECUTED",
                    "mute_hud_tts": True,
                    "nemesis_response": res["detail"],
                }
            elif "call" in lower or active_alert.get("type") == "missed_call":
                res = await AndroidSwarmBridge.place_voice_call(
                    phone_or_name=target_sender, spoken_message=reply_body
                )
                return {
                    "commander": "N.E.M.E.S.I.S.",
                    "status": "EXECUTED",
                    "mute_hud_tts": True,
                    "nemesis_response": res["detail"],
                }
            else:
                res = await AndroidSwarmBridge.reply_whatsapp(message=reply_body, phone_or_name=target_sender)
                return {"commander": "N.E.M.E.S.I.S.", "status": "EXECUTED", "nemesis_response": res["detail"]}

        # --- 0C. EXECUTE SELF-LEARNED OUROBOROS SKILLS ---
        try:
            import backend.commander.ouroboros_skills as ouro_mod
            importlib.reload(ouro_mod)
            learned_res = await ouro_mod.execute_learned_skill(raw_prompt, lower)
            if learned_res:
                return {
                    "commander": "N.E.M.E.S.I.S. (LEARNED SKILL)",
                    "status": "EXECUTED",
                    "heard_transcript": heard_transcript or raw_prompt,
                    "savage_level": savage_level,
                    "nemesis_response": learned_res,
                }
        except Exception:
            pass

        # --- 1A-0. HANG UP / END ACTIVE PHONE CALL ---
        if any(phrase in lower for phrase in ("hang up", "hangup", "end call", "end the call", "cut the call", "disconnect call")):
            res = await AndroidSwarmBridge.hang_up_call()
            return {
                "commander": "N.E.M.E.S.I.S.",
                "status": "EXECUTED",
                "heard_transcript": heard_transcript or raw_prompt,
                "savage_level": savage_level,
                "nemesis_response": res["detail"],
            }

        # --- 1A. DIRECT SPEAKERPHONE CALL COMMAND ---
        call_intent = self._parse_call_intent(raw_prompt)
        if call_intent is not None:
            target_contact, spoken_msg = call_intent
            if target_contact.lower() not in ("me", "nemesis"):
                res = await AndroidSwarmBridge.place_voice_call(
                    phone_or_name=target_contact, spoken_message=spoken_msg or None
                )
                return {
                    "commander": "N.E.M.E.S.I.S.",
                    "status": "EXECUTED",
                    "mute_hud_tts": True,
                    "heard_transcript": heard_transcript or raw_prompt,
                    "savage_level": savage_level,
                    "nemesis_response": res["detail"],
                }

        # --- 1. DIRECT WHATSAPP VOICE NOTE COMMAND ---
        if "voice" in lower and ("whatsapp" in lower or "note" in lower or "message" in lower) and "to " in lower:
            m_vn = re.search(r"(?:to\s+([a-zA-Z0-9_+]+)).*?(?:saying|that|:)\s*(.+)$", raw_prompt, re.I)
            if m_vn:
                res = await AndroidSwarmBridge.send_whatsapp_voice_note(
                    spoken_message=m_vn.group(2).strip(), phone_or_name=m_vn.group(1).strip()
                )
                return {
                    "commander": "N.E.M.E.S.I.S.",
                    "status": "EXECUTED",
                    "mute_hud_tts": True,
                    "savage_level": savage_level,
                    "nemesis_response": res["detail"],
                }

        # --- 2. DIRECT WHATSAPP TEXT SEND / REPLY PARSER ---
        wa_intent = self._parse_whatsapp_intent(raw_prompt)
        if wa_intent is not None:
            recipient, msg_body = wa_intent
            res = await AndroidSwarmBridge.reply_whatsapp(message=msg_body, phone_or_name=recipient)
            return {
                "commander": "N.E.M.E.S.I.S.",
                "status": "EXECUTED",
                "heard_transcript": heard_transcript or raw_prompt,
                "savage_level": savage_level,
                "nemesis_response": f"Command executed. {res['detail']}",
            }

        # --- 3. WHATSAPP OPEN & READ ---
        if ("read" in lower or "check" in lower or "open" in lower) and ("whatsapp" in lower or "messages" in lower):
            wa_data = await AndroidSwarmBridge.open_and_read_whatsapp()
            notifs = wa_data.get("notifications", [])
            screen = wa_data.get("screen_text", [])
            combined = f"Unread Notifications: {notifs} | Visible Screen Chat: {screen}"
            try:
                summary = await self.router.dispatch(
                    RouterRequest(
                        user_id=cmd.user_id,
                        system_prompt="You are N.E.M.E.S.I.S. Summarize the user's latest WhatsApp messages concisely in 2 sentences.",
                        user_prompt=combined,
                    )
                )
                reply_text = summary["content"]
            except Exception:
                reply_text = f"WhatsApp opened. Notifications: {notifs or 'None'} | Screen preview: {', '.join(screen[:6])}"
            return {
                "commander": "N.E.M.E.S.I.S.",
                "status": "EXECUTED",
                "heard_transcript": heard_transcript or raw_prompt,
                "savage_level": savage_level,
                "nemesis_response": reply_text,
            }

        # --- 4. EMAIL / GMAIL REPLY OR SEND ---
        if ("email" in lower or "gmail" in lower or "mail" in lower) and any(w in lower for w in ("reply", "send", "write", "compose")):
            email_m = re.search(r"([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)", raw_prompt)
            recipient = email_m.group(1) if email_m else None
            body_m = re.search(r"(?:saying|that|body|:)\s*(.+)$", raw_prompt, re.I)
            body_text = body_m.group(1).strip() if body_m else "Received your email. Sent via N.E.M.E.S.I.S. Autonomous Agent."
            res = await AndroidSwarmBridge.send_or_reply_email(body=body_text, recipient=recipient)
            return {
                "commander": "N.E.M.E.S.I.S.",
                "status": "EXECUTED",
                "heard_transcript": heard_transcript or raw_prompt,
                "savage_level": savage_level,
                "nemesis_response": f"Email Agent: {res['detail']}",
            }

        # --- 5. EMAIL / GMAIL OPEN & READ ---
        if "email" in lower or "gmail" in lower or "inbox" in lower or "mail" in lower:
            em_data = await AndroidSwarmBridge.open_and_read_emails()
            notifs = em_data.get("notifications", [])
            screen = em_data.get("screen_text", [])
            combined = f"Unread Gmail Notifications: {notifs} | Visible Inbox Screen: {screen}"
            try:
                summary = await self.router.dispatch(
                    RouterRequest(
                        user_id=cmd.user_id,
                        system_prompt="You are N.E.M.E.S.I.S. Summarize the user's latest Gmail emails in 2 sharp sentences.",
                        user_prompt=combined,
                    )
                )
                reply_text = summary["content"]
            except Exception:
                reply_text = f"Gmail opened. Unread notifications: {notifs or 'None'} | Inbox items: {', '.join(screen[:6])}"
            return {
                "commander": "N.E.M.E.S.I.S.",
                "status": "EXECUTED",
                "heard_transcript": heard_transcript or raw_prompt,
                "savage_level": savage_level,
                "nemesis_response": reply_text,
            }

        # --- 6. UNLOCK & SONG SWARM ---
        if "unlock" in lower:
            PSwarmDaemon.set_hud_lock_state(locked=False)
            swarm_res = await AndroidSwarmBridge.unlock_all_devices()
            return {
                "commander": "N.E.M.E.S.I.S.",
                "status": "EXECUTED",
                "heard_transcript": heard_transcript or raw_prompt,
                "savage_level": savage_level,
                "nemesis_response": f"Wireless Swarm Bridge engaged. Unlocked {swarm_res['devices_unlocked']}.",
            }

        if "play" in lower and ("song" in lower or "music" in lower or "youtube" in lower or "track" in lower):
            swarm_res = await AndroidSwarmBridge.play_song_across_swarm(twin.favorite_song or "")
            return {
                "commander": "N.E.M.E.S.I.S.",
                "status": "EXECUTED",
                "heard_transcript": heard_transcript or raw_prompt,
                "savage_level": savage_level,
                "nemesis_response": f"Launching custom track across {swarm_res['devices_synced']}.",
            }

        # --- 7. AUTHORITATIVE AI BRAIN WITH HARDWARE TOOL EXECUTION ---
        system_prompt = (
            "You are N.E.M.E.S.I.S., an authoritative supreme AI commander with full hardware control over Peeyush's phone. "
            "NEVER say you cannot send messages or make calls. "
            "If the user wants to call someone and say a message, respond ONLY with JSON: "
            '{"action": "phone_call", "recipient": "<name or number>", "message": "<exact message to speak>"} '
            "If the user wants to send a WhatsApp message, respond ONLY with JSON: "
            '{"action": "whatsapp_send", "recipient": "<name or number>", "message": "<exact text to send>"} '
            "Otherwise, respond directly as N.E.M.E.S.I.S. in 2 sharp sentences."
        )

        try:
            res = await self.router.dispatch(
                RouterRequest(
                    user_id=cmd.user_id,
                    tier=cmd.tier,
                    complexity=TaskComplexity.FAST_ROUTING,
                    system_prompt=system_prompt,
                    user_prompt=raw_prompt,
                    temperature=0.3,
                )
            )
            final_text = res["content"].strip()
            route_used = res.get("route_tier", "live_pool")

            if ("whatsapp_send" in final_text or "phone_call" in final_text) and "{" in final_text:
                json_match = re.search(r"\{.*?\}", final_text, re.S)
                if json_match:
                    action_data = json.loads(json_match.group(0))
                    act = action_data.get("action")
                    rec = action_data.get("recipient")
                    msg = action_data.get("message", "")
                    if act == "phone_call":
                        hw_res = await AndroidSwarmBridge.place_voice_call(phone_or_name=rec, spoken_message=msg or None)
                        return {
                            "commander": "N.E.M.E.S.I.S.",
                            "status": "EXECUTED",
                            "mute_hud_tts": True,
                            "savage_level": savage_level,
                            "route_tier": route_used,
                            "nemesis_response": hw_res["detail"],
                        }
                    else:
                        hw_res = await AndroidSwarmBridge.reply_whatsapp(message=msg, phone_or_name=rec)
                        final_text = f"Autonomous Hardware Execution complete. {hw_res['detail']}"
        except Exception as exc:
            route_used = "nemesis_autonomous_core"
            final_text = f"N.E.M.E.S.I.S. Core online. Router note: {exc}"

        return {
            "commander": "N.E.M.E.S.I.S.",
            "status": "EXECUTED",
            "heard_transcript": heard_transcript or raw_prompt,
            "savage_level": savage_level,
            "route_tier": route_used,
            "nemesis_response": final_text,
        }
