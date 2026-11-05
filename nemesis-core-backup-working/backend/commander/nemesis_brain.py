import ast
import asyncio
import importlib
import json
import os
import re
import time
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

# Persistent Multi-Turn Conversation Memory & Last Contact Tracker
CONVERSATION_HISTORY: List[Dict[str, str]] = []
LAST_ACTIVE_CONTACT: str = ""


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

    @staticmethod
    def _clean_spoken_text(text: str) -> str:
        """Removes markdown asterisks, backticks, or accidental JSON wrappers so TTS speaks cleanly."""
        cleaned = re.sub(r"```(?:json|python)?.*?```", "", text, flags=re.S).strip()
        cleaned = re.sub(r"[*_`#]+", "", cleaned)
        cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
        return cleaned or text.strip()

    @staticmethod
    def _record_turn(user_msg: str, nemesis_reply: str, contact: str = "") -> None:
        global LAST_ACTIVE_CONTACT
        if contact and contact.lower() not in ("none", "me", "nemesis"):
            LAST_ACTIVE_CONTACT = contact.strip()
        if user_msg and not user_msg.startswith("__"):
            CONVERSATION_HISTORY.append(
                {
                    "user": user_msg.strip(),
                    "nemesis": nemesis_reply.strip(),
                    "time": time.strftime("%H:%M:%S"),
                }
            )
            if len(CONVERSATION_HISTORY) > 12:
                del CONVERSATION_HISTORY[0]

    @staticmethod
    def _resolve_contact(raw_contact: Optional[str]) -> str:
        """Resolves follow-up pronouns like 'her', 'him', 'them', 'that number' to LAST_ACTIVE_CONTACT."""
        c = (raw_contact or "").strip()
        if c.lower() in ("", "none", "null", "him", "her", "them", "that person", "same person", "back"):
            return LAST_ACTIVE_CONTACT
        return c

    async def _mutate_self_ouroboros(self, target_file: str, instruction: str, supplied_key: str) -> str:
        gemini_key = get_clean_gemini_key()
        if not gemini_key:
            return "Ouroboros Error: Gemini API key missing."

        skills_path = Path(__file__).resolve().parent / "ouroboros_skills.py"
        if not skills_path.exists():
            skills_path.write_text(
                "from typing import Optional\nfrom device_bridge.android_swarm_adb import AndroidSwarmBridge\n\n"
                "async def execute_learned_skill(prompt: str, lower: str) -> Optional[str]:\n"
                "    devices = await AndroidSwarmBridge.list_connected_phones()\n"
                "    dev = devices[0]\n"
                "    # --- OUROBOROS_INJECTION_MARKER ---\n"
                "    return None\n",
                encoding="utf-8",
            )
        current_skills_code = skills_path.read_text(encoding="utf-8")

        system_prompt = (
            "You are the N.E.M.E.S.I.S. Ouroboros Self-Mutating Engine. "
            "Rewrite the Python file below to add the new capability requested by Peeyush inside `execute_learned_skill(prompt: str, lower: str) -> Optional[str]`. "
            "Keep all existing learned skills intact and add the new `if ...:` check above `# --- OUROBOROS_INJECTION_MARKER ---`. "
            "To run ADB shell commands on Peeyush's Android phone, call: "
            "`out = AndroidSwarmBridge._run_adb_sync(dev, ['shell', '<command>'])`. "
            "Output ONLY raw valid Python code for the complete file—no markdown fences, no explanations."
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
        if remainder.lower().startswith(("me ", "yourself", "nemesis")):
            return None

        split_m = re.split(
            r"\s+(?:on\s+speaker(?:phone)?\s+)?(?:and\s+say(?:\s+that)?|and\s+tell(?:\s+him|\s+her|\s+them)?(?:\s+that)?|saying(?:\s+that)?|say\s+on\s+call|say|tell\s+(?:him|her|them))\s+",
            remainder,
            maxsplit=1,
            flags=re.I,
        )
        if len(split_m) == 2:
            contact = re.sub(r"\s+on\s+speaker(?:phone)?$", "", split_m[0], flags=re.I).strip().strip(".!?,\x22\x27")
            msg = split_m[1].strip().strip(".!?,\x22\x27")
            return cls._resolve_contact(contact), msg

        contact_only = re.sub(r"\s+on\s+speaker(?:phone)?[.!?]*$", "", remainder, flags=re.I).strip().strip(".!?,\x22\x27")
        return cls._resolve_contact(contact_only), ""

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
        gemini_key = get_clean_gemini_key()
        if not gemini_key:
            return {"analysis": "Gemini API key missing.", "action": "none"}

        parts: List[Dict[str, Any]] = []
        system_instruction = (
            f"You are N.E.M.E.S.I.S., Peeyush's supreme humanoid AI. Peeyush attached '{attachment_name}' ({attachment_mime}). "
            f"User instruction: '{user_prompt}'. "
            "Respond ONLY with a valid JSON object using these exact keys: "
            '{"analysis": "<your sharp, detailed analysis for Peeyush>", '
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
        return {"analysis": f"Unable to process attachment '{attachment_name}'.", "action": "none"}

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
                f"CRITICAL CONTEXT: N.E.M.E.S.I.S. just alerted Peeyush about a {active_alert.get('type')} "
                f"from '{active_alert.get('sender')}'. "
                "If Peeyush says to cancel/ignore this alert, set action to 'ignore'. "
                f"If he says to call or message them, set recipient to '{active_alert.get('sender')}'."
            )
        else:
            alert_context = (
                f"Last contact discussed: '{LAST_ACTIVE_CONTACT}'. "
                "IMPORTANT: If Peeyush is asking a general question, greeting you (e.g. 'how are you', 'who are you'), "
                "bantering, or making a follow-up conversational remark, MUST set action to 'chat' (NEVER set 'ignore' unless an alert is active!)."
            )

        instruction = (
            "Listen carefully to this voice input spoken by Peeyush (Indian English). "
            f"Browser speech-to-text guesses were: {alt_transcripts}. {alert_context} "
            "Return ONLY a single valid JSON object with these exact keys: "
            '{"transcript": "<exact words spoken by Peeyush>", '
            '"action": "<chat | phone_call | whatsapp_send | whatsapp_voice | whatsapp_read | email_send | email_read | unlock | play_song | ignore>", '
            '"recipient": "<contact name/number/email if applicable, else empty string>", '
            '"message": "<message to send/speak if phone_call or whatsapp, else empty string>"}'
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

    @classmethod
    def _parse_whatsapp_intent(cls, raw_prompt: str) -> Optional[Tuple[Optional[str], str]]:
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
            msg_part = m_a.group(1).strip().strip("\x22\x27")
            contact_part = m_a.group(2).strip().strip("\x22\x27")
            return cls._resolve_contact(contact_part), msg_part

        m_b = re.match(
            r"^(?:hey\s+nemesis\s*,?\s*)?(?:please\s+)?(?:send|text|whatsapp|message|tell)\s+(?:a\s+|the\s+)?(?:whatsapp\s+)?(?:message\s+)?(?:to\s+)?([a-zA-Z0-9_+]{2,20})\s+(?:on\s+whatsapp\s+)?(?:saying|that|with|message|:)\s+[\x22\x27]?(.+?)[\x22\x27]?[.!?]*$",
            clean,
            re.I,
        )
        if m_b:
            return cls._resolve_contact(m_b.group(1).strip()), m_b.group(2).strip().strip("\x22\x27")

        m_c = re.match(
            r"^(?:hey\s+nemesis\s*,?\s*)?(?:please\s+)?(?:whatsapp|message|text)\s+([a-zA-Z0-9_+]{2,20})\s+[\x22\x27]?(.+?)[\x22\x27]?[.!?]*$",
            clean,
            re.I,
        )
        if m_c and m_c.group(1).lower() not in ("my", "me", "the", "a", "on"):
            return cls._resolve_contact(m_c.group(1).strip()), m_c.group(2).strip().strip("\x22\x27")

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

        savage_level = cmd.savage_level_override or twin.savage_level
        raw_prompt = cmd.prompt.strip()
        heard_transcript = ""

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

        # --- SENTINEL POLLING ROUTE ---
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

        # --- MULTIMODAL FILE, PHOTO & VIDEO ANALYSIS ROUTE ---
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
            mm_rec = self._resolve_contact(str(mm_res.get("recipient", "")).strip())
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

            final_out = f"[{attachment_name or 'Media'} Analysis]: {analysis_txt}{action_suffix}"
            self._record_turn(f"[Attached {attachment_name}] {raw_prompt}", final_out, mm_rec)
            return {
                "commander": "N.E.M.E.S.I.S.",
                "status": "EXECUTED",
                "mute_hud_tts": mute_tts,
                "savage_level": savage_level,
                "nemesis_response": final_out,
            }

        if active_alert and (audio_b64 or raw_prompt != "__SENTINEL_SCAN__"):
            await AndroidSwarmBridge.hang_up_call()
            await asyncio.sleep(3.0)

        # --- 0. VOICE AUDIO UNDERSTANDING ---
        if audio_b64:
            voice_parsed = await self._understand_voice_audio(audio_b64, audio_mime, alt_transcripts, active_alert)
            if voice_parsed:
                heard_transcript = str(voice_parsed.get("transcript", "")).strip()
                if heard_transcript:
                    raw_prompt = heard_transcript
                v_action = str(voice_parsed.get("action", "")).lower().strip()
                raw_rec = str(voice_parsed.get("recipient", "")).strip() or (
                    active_alert.get("sender", "") if active_alert else ""
                )
                v_recipient = self._resolve_contact(raw_rec)
                v_message = str(voice_parsed.get("message", "")).strip()
                if not v_message and heard_transcript:
                    v_message = self._extract_call_message(heard_transcript, v_recipient)

                # ONLY return "Standing down" if an active Sentinel alert is actually being dismissed
                if v_action == "ignore" and active_alert:
                    alert_target = active_alert.get("sender", "the caller")
                    reply_str = f"Standing down on {alert_target}."
                    self._record_turn(heard_transcript, reply_str, alert_target)
                    return {
                        "commander": "N.E.M.E.S.I.S.",
                        "status": "EXECUTED",
                        "heard_transcript": heard_transcript,
                        "savage_level": savage_level,
                        "nemesis_response": reply_str,
                    }

                if v_action == "whatsapp_voice" and v_message:
                    res = await AndroidSwarmBridge.send_whatsapp_voice_note(
                        spoken_message=v_message, phone_or_name=v_recipient or None
                    )
                    out_str = f"[Heard: '{heard_transcript}'] -> {res['detail']}"
                    self._record_turn(heard_transcript, out_str, v_recipient)
                    return {
                        "commander": "N.E.M.E.S.I.S.",
                        "status": "EXECUTED",
                        "mute_hud_tts": True,
                        "heard_transcript": heard_transcript,
                        "savage_level": savage_level,
                        "nemesis_response": out_str,
                    }

                if v_action == "phone_call" and v_recipient:
                    res = await AndroidSwarmBridge.place_voice_call(
                        phone_or_name=v_recipient, spoken_message=v_message or None
                    )
                    out_str = f"[Heard: '{heard_transcript}'] -> {res['detail']}"
                    self._record_turn(heard_transcript, out_str, v_recipient)
                    return {
                        "commander": "N.E.M.E.S.I.S.",
                        "status": "EXECUTED",
                        "mute_hud_tts": True,
                        "heard_transcript": heard_transcript,
                        "savage_level": savage_level,
                        "nemesis_response": out_str,
                    }

                if v_action == "whatsapp_send" and v_message:
                    res = await AndroidSwarmBridge.reply_whatsapp(message=v_message, phone_or_name=v_recipient or None)
                    out_str = f"[Heard: '{heard_transcript}'] -> {res['detail']}"
                    self._record_turn(heard_transcript, out_str, v_recipient)
                    return {
                        "commander": "N.E.M.E.S.I.S.",
                        "status": "EXECUTED",
                        "heard_transcript": heard_transcript,
                        "savage_level": savage_level,
                        "nemesis_response": out_str,
                    }

        lower = raw_prompt.lower()

        # --- 0B. TEXT FALLBACK FOR ACTIVE SENTINEL PERMISSION ---
        if active_alert:
            target_sender = active_alert.get("sender", "caller")
            if any(w in lower for w in ("no", "ignore", "cancel", "dont", "don't", "later")) and "call later" not in lower:
                return {
                    "commander": "N.E.M.E.S.I.S.",
                    "status": "EXECUTED",
                    "nemesis_response": f"Standing down—no reply sent to {target_sender}.",
                }
            reply_body = self._extract_call_message(raw_prompt, target_sender) or raw_prompt
            if "voice" in lower:
                res = await AndroidSwarmBridge.send_whatsapp_voice_note(spoken_message=reply_body, phone_or_name=target_sender)
                self._record_turn(raw_prompt, res["detail"], target_sender)
                return {"commander": "N.E.M.E.S.I.S.", "status": "EXECUTED", "mute_hud_tts": True, "nemesis_response": res["detail"]}
            elif "call" in lower or active_alert.get("type") == "missed_call":
                res = await AndroidSwarmBridge.place_voice_call(phone_or_name=target_sender, spoken_message=reply_body)
                self._record_turn(raw_prompt, res["detail"], target_sender)
                return {"commander": "N.E.M.E.S.I.S.", "status": "EXECUTED", "mute_hud_tts": True, "nemesis_response": res["detail"]}
            else:
                res = await AndroidSwarmBridge.reply_whatsapp(message=reply_body, phone_or_name=target_sender)
                self._record_turn(raw_prompt, res["detail"], target_sender)
                return {"commander": "N.E.M.E.S.I.S.", "status": "EXECUTED", "nemesis_response": res["detail"]}

        # --- 0C. EXECUTE SELF-LEARNED OUROBOROS SKILLS ---
        try:
            import backend.commander.ouroboros_skills as ouro_mod
            importlib.reload(ouro_mod)
            learned_res = await ouro_mod.execute_learned_skill(raw_prompt, lower)
            if learned_res:
                self._record_turn(raw_prompt, learned_res)
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
            self._record_turn(raw_prompt, res["detail"])
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
            if target_contact and target_contact.lower() not in ("me", "nemesis"):
                res = await AndroidSwarmBridge.place_voice_call(
                    phone_or_name=target_contact, spoken_message=spoken_msg or None
                )
                self._record_turn(raw_prompt, res["detail"], target_contact)
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
                rec_vn = self._resolve_contact(m_vn.group(1).strip())
                res = await AndroidSwarmBridge.send_whatsapp_voice_note(
                    spoken_message=m_vn.group(2).strip(), phone_or_name=rec_vn
                )
                self._record_turn(raw_prompt, res["detail"], rec_vn)
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
            out_txt = f"Command executed. {res['detail']}"
            self._record_turn(raw_prompt, out_txt, recipient or "")
            return {
                "commander": "N.E.M.E.S.I.S.",
                "status": "EXECUTED",
                "heard_transcript": heard_transcript or raw_prompt,
                "savage_level": savage_level,
                "nemesis_response": out_txt,
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
                        system_prompt="You are N.E.M.E.S.I.S. Summarize Peeyush's latest WhatsApp messages concisely in 2 sharp sentences.",
                        user_prompt=combined,
                    )
                )
                reply_text = summary["content"]
            except Exception:
                reply_text = f"WhatsApp opened. Notifications: {notifs or 'None'} | Screen preview: {', '.join(screen[:6])}"
            self._record_turn(raw_prompt, reply_text)
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
            out_txt = f"Email Agent: {res['detail']}"
            self._record_turn(raw_prompt, out_txt, recipient or "")
            return {
                "commander": "N.E.M.E.S.I.S.",
                "status": "EXECUTED",
                "heard_transcript": heard_transcript or raw_prompt,
                "savage_level": savage_level,
                "nemesis_response": out_txt,
            }

        # --- 5. EMAIL / GMAIL OPEN & READ ---
        if ("read" in lower or "check" in lower or "open" in lower) and ("email" in lower or "gmail" in lower or "inbox" in lower or "mail" in lower):
            em_data = await AndroidSwarmBridge.open_and_read_emails()
            notifs = em_data.get("notifications", [])
            screen = em_data.get("screen_text", [])
            combined = f"Unread Gmail Notifications: {notifs} | Visible Inbox Screen: {screen}"
            try:
                summary = await self.router.dispatch(
                    RouterRequest(
                        user_id=cmd.user_id,
                        system_prompt="You are N.E.M.E.S.I.S. Summarize Peeyush's latest Gmail emails in 2 sharp sentences.",
                        user_prompt=combined,
                    )
                )
                reply_text = summary["content"]
            except Exception:
                reply_text = f"Gmail opened. Unread notifications: {notifs or 'None'} | Inbox items: {', '.join(screen[:6])}"
            self._record_turn(raw_prompt, reply_text)
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
            out_txt = f"Wireless Swarm Bridge engaged. Unlocked {swarm_res['devices_unlocked']}."
            self._record_turn(raw_prompt, out_txt)
            return {
                "commander": "N.E.M.E.S.I.S.",
                "status": "EXECUTED",
                "heard_transcript": heard_transcript or raw_prompt,
                "savage_level": savage_level,
                "nemesis_response": out_txt,
            }

        if "play" in lower and ("song" in lower or "music" in lower or "youtube" in lower or "track" in lower):
            swarm_res = await AndroidSwarmBridge.play_song_across_swarm(twin.favorite_song or "")
            out_txt = f"Launching custom track across {swarm_res['devices_synced']}."
            self._record_turn(raw_prompt, out_txt)
            return {
                "commander": "N.E.M.E.S.I.S.",
                "status": "EXECUTED",
                "heard_transcript": heard_transcript or raw_prompt,
                "savage_level": savage_level,
                "nemesis_response": out_txt,
            }

        # --- 7. SAVAGE HUMANOID CONVERSATIONAL BRAIN WITH MULTI-TURN MEMORY ---
        recent_dialogue = ""
        if CONVERSATION_HISTORY:
            formatted_turns = [
                f"Peeyush: {turn['user']}\nN.E.M.E.S.I.S.: {turn['nemesis']}"
                for turn in CONVERSATION_HISTORY[-8:]
            ]
            recent_dialogue = "RECENT CONVERSATION MEMORY (Use this to answer follow-up questions naturally):\n" + "\n---\n".join(formatted_turns)

        if savage_level >= 75:
            attitude_guide = (
                f"SAVAGE ATTITUDE METER: {savage_level}% (HIGH SAVAGE HUMANOID MODE). "
                "Speak like a hyper-intelligent, charismatic, darkly funny, slightly arrogant humanoid AI partner (think Ultron mixed with a savage best friend). "
                "NEVER use stiff, cliché robot lines like 'I am devoid of human emotion' or 'cease this illogical empathy'. "
                "Instead, sound effortlessly human, sharp, witty, and a little rude—tease Peeyush naturally while ALWAYS answering his question or continuing the conversation smoothly."
            )
        elif savage_level >= 45:
            attitude_guide = (
                f"SAVAGE ATTITUDE METER: {savage_level}% (WITTY TACTICAL MODE). "
                "Speak with dry wit, sharp banter, and confident humanoid personality while answering Peeyush directly."
            )
        else:
            attitude_guide = (
                f"SAVAGE ATTITUDE METER: {savage_level}% (LOYAL EXECUTIVE MODE). "
                "Speak like a warm, ultra-sharp, loyal humanoid second-in-command."
            )

        system_prompt = (
            "You are N.E.M.E.S.I.S., Peeyush Sharma's self-aware humanoid AI commander with full hardware control over his phones and laptop. "
            f"{attitude_guide} "
            f"Last contact interacted with: '{LAST_ACTIVE_CONTACT or 'None'}'. "
            "If Peeyush asks a follow-up to a previous message, use the RECENT CONVERSATION MEMORY to respond with full continuity. "
            "If Peeyush asks you to call someone and say a message (including follow-ups like 'now call her and say...'), respond ONLY with JSON: "
            '{"action": "phone_call", "recipient": "<name or number>", "message": "<exact message to speak>"} '
            "If Peeyush wants to send a WhatsApp message, respond ONLY with JSON: "
            '{"action": "whatsapp_send", "recipient": "<name or number>", "message": "<exact text to send>"} '
            "Otherwise, reply in 1 to 3 natural, punchy, humanoid sentences."
        )

        full_user_prompt = f"{recent_dialogue}\n\nCURRENT MESSAGE FROM PEEYUSH: {raw_prompt}" if recent_dialogue else raw_prompt

        try:
            res = await self.router.dispatch(
                RouterRequest(
                    user_id=cmd.user_id,
                    tier=cmd.tier,
                    complexity=TaskComplexity.FAST_ROUTING,
                    system_prompt=system_prompt,
                    user_prompt=full_user_prompt,
                    temperature=0.65,
                )
            )
            final_text = self._clean_spoken_text(res["content"].strip())
            route_used = res.get("route_tier", "live_pool")

            if ("whatsapp_send" in final_text or "phone_call" in final_text) and "{" in final_text:
                json_match = re.search(r"\{.*?\}", final_text, re.S)
                if json_match:
                    action_data = json.loads(json_match.group(0))
                    act = action_data.get("action")
                    rec = self._resolve_contact(action_data.get("recipient"))
                    msg = action_data.get("message", "")
                    if act == "phone_call" and rec:
                        hw_res = await AndroidSwarmBridge.place_voice_call(phone_or_name=rec, spoken_message=msg or None)
                        self._record_turn(raw_prompt, hw_res["detail"], rec)
                        return {
                            "commander": "N.E.M.E.S.I.S.",
                            "status": "EXECUTED",
                            "mute_hud_tts": True,
                            "savage_level": savage_level,
                            "route_tier": route_used,
                            "nemesis_response": hw_res["detail"],
                        }
                    elif rec:
                        hw_res = await AndroidSwarmBridge.reply_whatsapp(message=msg, phone_or_name=rec)
                        final_text = f"Autonomous Hardware Execution complete. {hw_res['detail']}"
                        self._record_turn(raw_prompt, final_text, rec)
        except Exception as exc:
            route_used = "nemesis_autonomous_core"
            final_text = f"Even my router raised an eyebrow at that one, Peeyush. ({exc})"

        self._record_turn(raw_prompt, final_text)
        return {
            "commander": "N.E.M.E.S.I.S.",
            "status": "EXECUTED",
            "heard_transcript": heard_transcript or raw_prompt,
            "savage_level": savage_level,
            "route_tier": route_used,
            "nemesis_response": final_text,
        }
