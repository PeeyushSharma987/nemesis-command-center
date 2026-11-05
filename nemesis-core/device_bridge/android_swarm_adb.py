import asyncio
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from urllib.parse import quote

PHONE_PIN = "6969"
CUSTOM_SONG_URL = 'https://youtu.be/MJyKN-8UncM?si=EpXJxKEED99A7ftR'

# Optional: Secondary phone number to dial if you are away from your PC (e.g. "919876543210")
AWAY_FORWARD_NUMBER = "+916267187671"

WHATSAPP_CONTACTS: Dict[str, str] = {}
SEEN_ALERT_SIGNATURES: Set[str] = set()
CONTACT_CACHE: Dict[str, str] = {}
SELF_DIALED_NUMBERS: Set[str] = set()
IS_NEMESIS_CALLING: bool = False
NEMESIS_COOLDOWN_UNTIL: float = 0.0
CALL_LOG_PRIMED: bool = False


class AndroidSwarmBridge:
    """Self-healing Android hardware bridge with Sentinel Call Alerts, Voice Notes, and Speakerphone Callbacks."""

    @staticmethod
    def get_adb_path() -> str:
        candidates = [
            Path(__file__).resolve().parents[1] / "platform-tools" / "adb.exe",
            Path(__file__).resolve().parents[2] / "platform-tools" / "adb.exe",
        ]
        for candidate in candidates:
            if candidate.exists():
                return str(candidate)
        return shutil.which("adb") or ""

    @classmethod
    def _discover_gateway_ips(cls) -> List[str]:
        ips = ["10.252.25.170"]
        try:
            res = subprocess.run(["ipconfig"], capture_output=True, text=True, timeout=5)
            found = re.findall(r"Default Gateway[\s\.:]+(?:[a-f0-9:%]+\s+)?(\d+\.\d+\.\d+\.\d+)", res.stdout, re.I)
            for ip in found:
                if ip not in ips:
                    ips.insert(0, ip)
        except Exception:
            pass
        return ips

    @classmethod
    def _parse_active_devices(cls, adb_bin: str) -> List[str]:
        res = subprocess.run([adb_bin, "devices"], capture_output=True, text=True, timeout=6)
        lines = res.stdout.strip().splitlines()[1:]
        return [
            line.split()[0]
            for line in lines
            if ("\tdevice" in line or " device" in line) and not line.startswith("*")
        ]

    @classmethod
    def _ensure_connected_sync(cls) -> List[str]:
        adb_bin = cls.get_adb_path()
        if not adb_bin:
            return ["SIMULATED_PHONE_1"]
        try:
            devices = cls._parse_active_devices(adb_bin)
            if devices:
                return devices
            subprocess.run([adb_bin, "disconnect"], capture_output=True, text=True, timeout=4)
            for gw_ip in cls._discover_gateway_ips():
                subprocess.run([adb_bin, "connect", f"{gw_ip}:5555"], capture_output=True, text=True, timeout=5)
            devices = cls._parse_active_devices(adb_bin)
            if devices:
                return devices
        except Exception:
            pass
        return ["SIMULATED_PHONE_1"]

    @classmethod
    async def list_connected_phones(cls) -> List[str]:
        return await asyncio.to_thread(cls._ensure_connected_sync)

    @classmethod
    def _run_adb_sync(cls, serial: str, args: List[str], timeout: int = 12) -> str:
        adb_bin = cls.get_adb_path()
        if serial.startswith("SIMULATED_") or not adb_bin:
            return ""
        try:
            res = subprocess.run(
                [adb_bin, "-s", serial] + args,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="ignore",
                timeout=timeout,
            )
            return (res.stdout or res.stderr).strip()
        except Exception:
            return ""

    @classmethod
    def _wake_and_unlock_sync(cls, serial: str) -> None:
        cls._run_adb_sync(serial, ["shell", "input keyevent 224"])
        time.sleep(0.9)
        cls._run_adb_sync(
            serial,
            ["shell", "wm dismiss-keyguard; input keyevent 82; input swipe 540 1850 540 300 350"],
        )
        if PHONE_PIN:
            time.sleep(0.5)
            cls._run_adb_sync(serial, ["shell", f"input text {PHONE_PIN} && input keyevent 66"])

    @classmethod
    def _dump_ui_xml_sync(cls, serial: str) -> str:
        cls._run_adb_sync(serial, ["shell", "uiautomator dump /sdcard/nemesis_ui.xml"])
        return cls._run_adb_sync(serial, ["shell", "cat /sdcard/nemesis_ui.xml"])

    @classmethod
    def _lookup_contact_number_sync(cls, serial: str, name_or_number: str) -> Optional[str]:
        """Resolves a contact name to a +91 phone number using instant cache + case-insensitive ADB dump."""
        raw_target = (name_or_number or "").strip()
        if not raw_target:
            return None

        # If already a phone number, normalize directly
        digits_only = re.sub(r"\D", "", raw_target)
        if len(digits_only) >= 10:
            return f"91{digits_only[-10:]}"

        cache_key = raw_target.lower()
        if cache_key in CONTACT_CACHE:
            return CONTACT_CACHE[cache_key]

        out = cls._run_adb_sync(
            serial,
            ["shell", "content query --uri content://com.android.contacts/data/phones --projection display_name:data1"],
            timeout=10,
        )
        if not out or "Error" in out:
            return None

        best_partial: Optional[str] = None
        for line in out.splitlines():
            m_name = re.search(r"display_name=([^,]+)", line)
            m_num = re.search(r"data1=([^\s,]+)", line)
            if not (m_name and m_num):
                continue
            disp = m_name.group(1).strip().lower()
            num_digits = re.sub(r"\D", "", m_num.group(1))
            if len(num_digits) < 10:
                continue
            normalized = f"91{num_digits[-10:]}"
            CONTACT_CACHE[disp] = normalized

            if disp == cache_key:
                return normalized
            if cache_key in disp or disp in cache_key:
                best_partial = normalized

        if best_partial:
            CONTACT_CACHE[cache_key] = best_partial
        return best_partial

    @classmethod
    def _tap_ui_node_sync(cls, serial: str, resource_keywords: List[str], desc_keywords: List[str]) -> bool:
        xml = cls._dump_ui_xml_sync(serial)
        if not xml:
            return False
        for node in re.findall(r"<node[^>]+>", xml):
            res_id = (re.search(r'resource-id="([^"]*)"', node) or [None, ""])[1].lower()
            desc = (re.search(r'content-desc="([^"]*)"', node) or [None, ""])[1].lower()
            text = (re.search(r'text="([^"]*)"', node) or [None, ""])[1].lower()
            if "meta ai" in text or "meta ai" in desc:
                continue
            bounds = re.search(r'bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"', node)
            if not bounds:
                continue
            matched = any(k in res_id for k in resource_keywords) or any(
                k in desc or k in text for k in desc_keywords
            )
            if matched:
                x1, y1, x2, y2 = map(int, bounds.groups())
                cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
                cls._run_adb_sync(serial, ["shell", f"input tap {cx} {cy}"])
                return True
        return False

    @classmethod
    def _find_and_tap_whatsapp_contact_sync(cls, serial: str, contact_name: str) -> bool:
        target = contact_name.strip().lower()
        xml = cls._dump_ui_xml_sync(serial)
        if not xml:
            return False
        candidates = []
        for node in re.findall(r"<node[^>]+>", xml):
            res_id = (re.search(r'resource-id="([^"]*)"', node) or [None, ""])[1].lower()
            text = (re.search(r'text="([^"]*)"', node) or [None, ""])[1].strip()
            desc = (re.search(r'content-desc="([^"]*)"', node) or [None, ""])[1].strip()
            tl = text.lower()
            if not tl or "meta ai" in tl or "meta ai" in desc.lower() or "search" in res_id:
                continue
            bounds = re.search(r'bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"', node)
            if not bounds:
                continue
            x1, y1, x2, y2 = map(int, bounds.groups())
            if y1 < 220:
                continue
            if tl == target or target in tl:
                priority = 0 if tl == target else 1
                candidates.append((priority, (x1 + x2) // 2, (y1 + y2) // 2))
        if candidates:
            candidates.sort(key=lambda x: x[0])
            _, cx, cy = candidates[0]
            cls._run_adb_sync(serial, ["shell", f"input tap {cx} {cy}"])
            return True
        return False

    @classmethod
    def _extract_notifications_sync(cls, serial: str, package_filter: str) -> List[str]:
        raw = cls._run_adb_sync(serial, ["shell", "dumpsys notification --noredact"], timeout=15)
        if not raw:
            return []
        messages: List[str] = []
        blocks = re.split(r"NotificationRecord\(", raw)
        for blk in blocks[1:]:
            if package_filter.lower() not in blk[:300].lower():
                continue
            title_m = re.search(r"android\.title=(?:String\s*)?\(?([^\n\r\)]+)", blk)
            text_m = re.search(r"android\.(?:bigText|text)=(?:String\s*)?\(?([^\n\r\)]+)", blk)
            title = title_m.group(1).strip() if title_m else "Unknown"
            text = text_m.group(1).strip() if text_m else ""
            if text and text.lower() != "null" and "checking for new messages" not in text.lower():
                entry = f"{title}: {text}"
                if entry not in messages:
                    messages.append(entry)
        return messages[:6]

    @classmethod
    def _get_call_state_sync(cls, serial: str) -> int:
        """
        Returns Android hardware telephony state:
        0 = IDLE (no call), 1 = RINGING (incoming call active), 2 = OFFHOOK (dialing/in-call)
        """
        raw = cls._run_adb_sync(serial, ["shell", "dumpsys telephony.registry"], timeout=6)
        states = [int(m.group(1)) for m in re.finditer(r"mCallState=(\d+)", raw)]
        if 1 in states:
            return 1
        if 2 in states:
            return 2
        return 0

    @classmethod
    def _extract_missed_calls_sync(cls, serial: str) -> List[Dict[str, str]]:
        """
        Queries ONLY completed Missed Calls (type=3) from Android CallLog.
        Never reads active outgoing/incallui notifications so N.E.M.E.S.I.S. never detects its own calls.
        """
        global CALL_LOG_PRIMED
        raw_log = cls._run_adb_sync(
            serial,
            ["shell", 'content query --uri content://call_log/calls --projection _id:number:name:type:date --where "type=3"'],
            timeout=8,
        )
        if not raw_log or "Error" in raw_log or "No result" in raw_log:
            CALL_LOG_PRIMED = True
            return []

        own_digits = re.sub(r"\D", "", AWAY_FORWARD_NUMBER)[-10:] if AWAY_FORWARD_NUMBER else ""
        parsed_calls: List[Dict[str, str]] = []

        for line in raw_log.strip().splitlines():
            id_m = re.search(r"_id=(\d+)", line)
            num_m = re.search(r"number=([^,\s]+)", line)
            name_m = re.search(r"name=([^,]+)", line)
            type_m = re.search(r"type=(\d+)", line)
            date_m = re.search(r"date=(\d+)", line)

            # Strictly enforce type=3 (Missed Call only, never outgoing type=2)
            if type_m and type_m.group(1) != "3":
                continue

            call_id = id_m.group(1) if id_m else ""
            num = num_m.group(1).strip() if num_m else ""
            name = name_m.group(1).strip() if name_m else ""
            date_ts = date_m.group(1) if date_m else call_id
            clean_num = re.sub(r"\D", "", num)[-10:]

            # Ignore calls from the second phone or numbers N.E.M.E.S.I.S. dialed itself
            if clean_num and (clean_num == own_digits or clean_num in SELF_DIALED_NUMBERS):
                continue

            caller = name if (name and name.lower() != "null") else num
            if caller:
                sig = f"call_id:{call_id}:{date_ts}"
                parsed_calls.append({"sender": caller, "number": num, "sig": sig})

        # Sort by call _id / timestamp ascending and keep the latest 3
        parsed_calls = parsed_calls[-3:]

        # On very first boot, mark old missed calls from earlier in the day as already seen
        if not CALL_LOG_PRIMED:
            for item in parsed_calls:
                SEEN_ALERT_SIGNATURES.add(item["sig"])
            CALL_LOG_PRIMED = True

        return list(reversed(parsed_calls))

    @classmethod
    async def dial_owner_second_phone(cls) -> Dict[str, Any]:
        """Dials Peeyush's second phone on speakerphone so he can hear the alert and speak instructions remotely."""
        global IS_NEMESIS_CALLING, NEMESIS_COOLDOWN_UNTIL
        devices = await cls.list_connected_phones()
        dev = devices[0]
        if dev.startswith("SIMULATED_") or not AWAY_FORWARD_NUMBER:
            return {"status": "SKIPPED", "detail": "No AWAY_FORWARD_NUMBER configured."}

        def _sync_dial_owner() -> str:
            global IS_NEMESIS_CALLING, NEMESIS_COOLDOWN_UNTIL
            IS_NEMESIS_CALLING = True
            NEMESIS_COOLDOWN_UNTIL = time.time() + 45.0
            SELF_DIALED_NUMBERS.add(re.sub(r"\D", "", AWAY_FORWARD_NUMBER)[-10:])
            cls._wake_and_unlock_sync(dev)
            cls._run_adb_sync(
                dev,
                ["shell", "am", "start", "-a", "android.intent.action.CALL", "-d", f"tel:{AWAY_FORWARD_NUMBER}"],
            )
            time.sleep(2.8)
            cls._tap_ui_node_sync(dev, ["sim_1", "account_list", "text1"], ["sim 1", "jio"])
            time.sleep(1.0)
            cls._tap_ui_node_sync(
                dev,
                ["speaker", "audio_route", "incall_second_button", "audio"],
                ["speaker", "speakerphone"],
            )
            cls._run_adb_sync(dev, ["shell", "media volume --stream 0 --set 15"])
            return f"Dialed owner second phone ({AWAY_FORWARD_NUMBER}) on speakerphone."

        detail = await asyncio.to_thread(_sync_dial_owner)
        return {"device": dev, "status": "OWNER_CALLED", "detail": detail}

    @classmethod
    async def scan_priority_alerts(cls, force_latest: bool = False) -> Dict[str, Any]:
        """
        Waits until any ringing incoming call finishes (mCallState == 0),
        ignores N.E.M.E.S.I.S.'s own outbound calls, and bridges new alerts to the second phone.
        """
        global IS_NEMESIS_CALLING, NEMESIS_COOLDOWN_UNTIL
        devices = await cls.list_connected_phones()
        dev = devices[0]
        if dev.startswith("SIMULATED_"):
            return {"has_alert": False, "reason": "Phone offline"}

        def _sync_scan() -> Dict[str, Any]:
            global IS_NEMESIS_CALLING, NEMESIS_COOLDOWN_UNTIL

            # 1. If N.E.M.E.S.I.S. is currently in an outbound call or cooldown window, do not scan!
            if not force_latest and (IS_NEMESIS_CALLING or time.time() < NEMESIS_COOLDOWN_UNTIL):
                if cls._get_call_state_sync(dev) == 0 and time.time() >= NEMESIS_COOLDOWN_UNTIL:
                    IS_NEMESIS_CALLING = False
                else:
                    return {"has_alert": False, "reason": "Nemesis call active or in cooldown"}

            # 2. Check hardware call state: if phone is RINGING (1) or OFFHOOK (2), wait until it finishes!
            call_state = cls._get_call_state_sync(dev)
            if call_state == 1:
                # Incoming call is currently ringing! Wait until ringing stops before calling Peeyush's 2nd phone
                return {"has_alert": False, "reason": "Incoming call still ringing — waiting for call to end"}
            if call_state == 2:
                return {"has_alert": False, "reason": "Phone line currently in use"}

            # Give Android 2.5 seconds after a call ends to write the missed call entry cleanly
            missed_calls = cls._extract_missed_calls_sync(dev)
            wa_notifs = cls._extract_notifications_sync(dev, "com.whatsapp")

            candidates: List[Dict[str, str]] = []
            for mc in missed_calls:
                candidates.append(
                    {
                        "type": "missed_call",
                        "sender": mc["sender"],
                        "content": "Missed Phone Call",
                        "sig": mc["sig"],
                    }
                )

            for wm in wa_notifs:
                if "messages from" in wm.lower() or "backup in progress" in wm.lower():
                    continue
                sender, detail = (wm.split(":", 1) + ["New message"])[:2]
                candidates.append(
                    {
                        "type": "whatsapp",
                        "sender": sender.strip(),
                        "content": detail.strip(),
                        "sig": f"wa:{wm}",
                    }
                )

            for item in candidates:
                if force_latest or item["sig"] not in SEEN_ALERT_SIGNATURES:
                    SEEN_ALERT_SIGNATURES.add(item["sig"])
                    remote_called = False
                    if AWAY_FORWARD_NUMBER:
                        IS_NEMESIS_CALLING = True
                        NEMESIS_COOLDOWN_UNTIL = time.time() + 45.0
                        SELF_DIALED_NUMBERS.add(re.sub(r"\D", "", AWAY_FORWARD_NUMBER)[-10:])
                        # Wait 2.5s after missed call ends so cellular radio is 100% ready to dial out
                        time.sleep(2.5)
                        cls._wake_and_unlock_sync(dev)
                        cls._run_adb_sync(
                            dev,
                            ["shell", "am", "start", "-a", "android.intent.action.CALL", "-d", f"tel:{AWAY_FORWARD_NUMBER}"],
                        )
                        time.sleep(2.8)
                        cls._tap_ui_node_sync(dev, ["sim_1", "account_list", "text1"], ["sim 1", "jio"])
                        time.sleep(1.0)
                        cls._tap_ui_node_sync(
                            dev,
                            ["speaker", "audio_route", "incall_second_button", "audio"],
                            ["speaker", "speakerphone"],
                        )
                        cls._run_adb_sync(dev, ["shell", "media volume --stream 0 --set 15"])
                        remote_called = True
                    return {
                        "has_alert": True,
                        "alert": item,
                        "remote_called": remote_called,
                        "second_phone": AWAY_FORWARD_NUMBER,
                    }

            return {"has_alert": False}

        return await asyncio.to_thread(_sync_scan)

    @classmethod
    def _extract_screen_texts_sync(cls, serial: str) -> List[str]:
        xml = cls._dump_ui_xml_sync(serial)
        if not xml:
            return []
        texts: List[str] = []
        ignore = {"whatsapp", "search", "chats", "updates", "communities", "calls", "type a message", "send", "ask meta ai or search", "meta ai"}
        for m in re.finditer(r'text="([^"]+)"', xml):
            val = m.group(1).strip()
            if len(val) >= 2 and val.lower() not in ignore and val not in texts:
                texts.append(val)
        return texts[-12:]

    @classmethod
    async def unlock_all_devices(cls, pin_code: str = PHONE_PIN) -> Dict[str, Any]:
        devices = await cls.list_connected_phones()
        for dev in devices:
            await asyncio.to_thread(cls._wake_and_unlock_sync, dev)
        return {"action": "UNLOCK_ALL_MOBILE_DEVICES", "devices_unlocked": devices, "count": len(devices), "status": "ALL_DEVICES_UNLOCKED"}

    @classmethod
    async def play_song_across_swarm(cls, youtube_url: str) -> Dict[str, Any]:
        youtube_url = CUSTOM_SONG_URL
        devices = await cls.list_connected_phones()
        for dev in devices:
            await asyncio.to_thread(cls._wake_and_unlock_sync, dev)
            await asyncio.to_thread(
                cls._run_adb_sync,
                dev,
                ["shell", "am", "start", "-a", "android.intent.action.VIEW", "-d", youtube_url],
            )
        return {"action": "SYNC_MEDIA_SWARM", "devices_synced": devices, "media_url": youtube_url, "status": "PLAYING_ON_ALL_DEVICES"}

    @classmethod
    async def open_and_read_whatsapp(cls) -> Dict[str, Any]:
        devices = await cls.list_connected_phones()
        dev = devices[0]
        if dev.startswith("SIMULATED_"):
            return {"status": "OFFLINE", "messages": ["Phone not connected via ADB."]}

        def _sync_read() -> Dict[str, Any]:
            cls._wake_and_unlock_sync(dev)
            notifs = cls._extract_notifications_sync(dev, "com.whatsapp")
            cls._run_adb_sync(dev, ["shell", "am start -n com.whatsapp/.HomeActivity"])
            time.sleep(2.0)
            screen_items = cls._extract_screen_texts_sync(dev)
            return {"notifications": notifs, "screen_text": screen_items}

        data = await asyncio.to_thread(_sync_read)
        return {"device": dev, "notifications": data["notifications"], "screen_text": data["screen_text"]}

    @classmethod
    async def reply_whatsapp(cls, message: str, phone_or_name: Optional[str] = None) -> Dict[str, Any]:
        devices = await cls.list_connected_phones()
        dev = devices[0]
        if dev.startswith("SIMULATED_"):
            return {"status": "SIMULATED_CLOUD_EXECUTION", "detail": "[Cloud Demo Mode]: Simulated hardware action executed cleanly (Download the Device Bridge Kit in the top bar to link your physical Android phone via ADB)."}

        def _sync_reply() -> str:
            cls._wake_and_unlock_sync(dev)
            contact_label = (phone_or_name or "").strip()
            resolved_number = cls._lookup_contact_number_sync(dev, contact_label) if contact_label else ""

            if resolved_number:
                url = f"https://api.whatsapp.com/send?phone={resolved_number}&text={quote(message)}"
                cls._run_adb_sync(
                    dev,
                    ["shell", "am", "start", "-a", "android.intent.action.VIEW", "-p", "com.whatsapp", "-d", f'"{url}"'],
                )
                time.sleep(2.8)
                if not cls._tap_ui_node_sync(dev, ["com.whatsapp:id/send"], ["send"]):
                    cls._run_adb_sync(dev, ["shell", "input keyevent 66"])
                return f"Dispatched WhatsApp text to {contact_label} ({resolved_number}): '{message}'"

            if contact_label:
                cls._run_adb_sync(dev, ["shell", "am start -n com.whatsapp/.HomeActivity"])
                time.sleep(1.8)
                found_chat = cls._find_and_tap_whatsapp_contact_sync(dev, contact_label)
                if not found_chat:
                    tapped_search = cls._tap_ui_node_sync(
                        dev,
                        ["com.whatsapp:id/menuitem_search", "com.whatsapp:id/search_bar_inner_layout"],
                        ["search"],
                    )
                    if tapped_search:
                        time.sleep(0.8)
                        safe_q = contact_label.replace(" ", "%s")
                        cls._run_adb_sync(dev, ["shell", f'input text "{safe_q}"'])
                        time.sleep(1.5)
                        found_chat = cls._find_and_tap_whatsapp_contact_sync(dev, contact_label)

                if not found_chat:
                    return f"Could not find contact '{contact_label}' in Contacts or WhatsApp."
                time.sleep(1.2)

            cls._tap_ui_node_sync(dev, ["com.whatsapp:id/entry"], ["type a message", "message"])
            time.sleep(0.4)
            safe_text = message.replace("'", "").replace('"', "").replace(" ", "%s")
            cls._run_adb_sync(dev, ["shell", f'input text "{safe_text}"'])
            time.sleep(0.7)
            if not cls._tap_ui_node_sync(dev, ["com.whatsapp:id/send"], ["send"]):
                cls._run_adb_sync(dev, ["shell", "input keyevent 66"])
            target_desc = contact_label if contact_label else "active WhatsApp chat"
            return f"Sent WhatsApp text to {target_desc}: '{message}'"

        status_msg = await asyncio.to_thread(_sync_reply)
        return {"device": dev, "status": "SENT", "detail": status_msg}

    @classmethod
    async def send_whatsapp_voice_note(cls, spoken_message: str, phone_or_name: Optional[str] = None) -> Dict[str, Any]:
        """Holds the WhatsApp Voice Note mic button in the background while speaking the message at 100% volume."""
        devices = await cls.list_connected_phones()
        dev = devices[0]
        if dev.startswith("SIMULATED_"):
            return {"status": "SIMULATED_CLOUD_EXECUTION", "detail": "[Cloud Demo Mode]: Simulated hardware action executed cleanly (Download the Device Bridge Kit in the top bar to link your physical Android phone via ADB)."}

        def _sync_voice_note() -> str:
            cls._wake_and_unlock_sync(dev)
            contact_label = (phone_or_name or "").strip()
            resolved_number = cls._lookup_contact_number_sync(dev, contact_label) if contact_label else ""

            if resolved_number:
                url = f"https://api.whatsapp.com/send?phone={resolved_number}"
                cls._run_adb_sync(
                    dev,
                    ["shell", "am", "start", "-a", "android.intent.action.VIEW", "-p", "com.whatsapp", "-d", f'"{url}"'],
                )
                time.sleep(2.6)
            elif contact_label:
                cls._run_adb_sync(dev, ["shell", "am start -n com.whatsapp/.HomeActivity"])
                time.sleep(1.8)
                cls._find_and_tap_whatsapp_contact_sync(dev, contact_label)
                time.sleep(1.2)

            # Locate the WhatsApp Voice Note microphone button (com.whatsapp:id/voice_note_btn)
            xml = cls._dump_ui_xml_sync(dev)
            mic_coords = (990, 2130)
            if xml:
                for node in re.findall(r"<node[^>]+>", xml):
                    res_id = (re.search(r'resource-id="([^"]*)"', node) or [None, ""])[1].lower()
                    desc = (re.search(r'content-desc="([^"]*)"', node) or [None, ""])[1].lower()
                    if "voice_note_btn" in res_id or "voice message" in desc:
                        bounds = re.search(r'bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"', node)
                        if bounds:
                            x1, y1, x2, y2 = map(int, bounds.groups())
                            mic_coords = ((x1 + x2) // 2, (y1 + y2) // 2)
                            break

            mx, my = mic_coords
            adb_bin = cls.get_adb_path()
            clean_speech = re.sub(r"[^a-zA-Z0-9,.?!\s]", " ", spoken_message.replace("'", "")).strip() or "Hello, I am busy right now."

            # Calculate hold duration so the mic stays pressed for the entire spoken sentence + 2.2s buffer
            word_count = len(clean_speech.split())
            hold_ms = max(5500, min(14000, word_count * 520 + 2600))

            # 1. Start holding the WhatsApp mic button asynchronously (non-blocking)
            swipe_proc = subprocess.Popen(
                [adb_bin, "-s", dev, "shell", f"input swipe {mx} {my} {mx} {my} {hold_ms}"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            # 2. Wait 0.8s for WhatsApp voice recording to start, then speak out loud at 100% volume
            time.sleep(0.8)
            ps_script = (
                "$w = New-Object -ComObject WScript.Shell; "
                "1..12 | ForEach-Object { $w.SendKeys([char]175) }; "
                "Add-Type -AssemblyName System.Speech; "
                "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
                "$s.Volume = 100; $s.Rate = -1; "
                f"$s.Speak('{clean_speech}');"
            )
            subprocess.run(["powershell", "-NoProfile", "-Command", ps_script], capture_output=True, timeout=14)

            # 3. Wait for the mic hold swipe to finish and release, sending the recorded voice note
            try:
                swipe_proc.wait(timeout=15)
            except Exception:
                swipe_proc.kill()

            return f"Recorded and sent WhatsApp Voice Note to {contact_label or 'chat'}: '{clean_speech}'"

        detail = await asyncio.to_thread(_sync_voice_note)
        return {"device": dev, "status": "VOICE_NOTE_SENT", "detail": detail}

    @classmethod
    def _terminate_active_call_sync(cls, serial: str) -> None:
        """Ends any active cellular call using Android Telecom manager, keyevent 6, and UI fallback."""
        global IS_NEMESIS_CALLING, NEMESIS_COOLDOWN_UNTIL
        IS_NEMESIS_CALLING = False
        NEMESIS_COOLDOWN_UNTIL = time.time() + 10.0
        cls._run_adb_sync(serial, ["shell", "cmd telecom end-call; input keyevent 6"])
        time.sleep(0.4)
        cls._tap_ui_node_sync(
            serial,
            ["end_call", "hangup", "disconnect", "incall_end_call"],
            ["end call", "hang up", "disconnect"],
        )

    @classmethod
    async def hang_up_call(cls) -> Dict[str, Any]:
        """Manually hangs up any ongoing phone call across connected devices."""
        devices = await cls.list_connected_phones()
        dev = devices[0]
        if dev.startswith("SIMULATED_"):
            return {"status": "SIMULATED_CLOUD_EXECUTION", "detail": "[Cloud Demo Mode]: Simulated hardware action executed cleanly (Download the Device Bridge Kit in the top bar to link your physical Android phone via ADB)."}

        await asyncio.to_thread(cls._terminate_active_call_sync, dev)
        return {"device": dev, "status": "CALL_ENDED", "detail": "Active phone call terminated."}

    @classmethod
    async def place_voice_call(cls, phone_or_name: str, spoken_message: Optional[str] = None) -> Dict[str, Any]:
        """Dials with +91 on speakerphone, waits 9s, speaks as Peeyush's assistant, and hangs up."""
        devices = await cls.list_connected_phones()
        dev = devices[0]
        if dev.startswith("SIMULATED_"):
            return {"status": "SIMULATED_CLOUD_EXECUTION", "detail": "[Cloud Demo Mode]: Simulated hardware action executed cleanly (Download the Device Bridge Kit in the top bar to link your physical Android phone via ADB)."}

        def _sync_call() -> str:
            cls._wake_and_unlock_sync(dev)
            clean_target = (phone_or_name or "").strip()
            num = cls._lookup_contact_number_sync(dev, clean_target)
            if not num:
                return f"Could not find phone number for '{clean_target}' in your Android Contacts."

            clean_digits = num.lstrip("+")
            if len(clean_digits) == 10:
                dial_num = f"+91{clean_digits}"
            elif clean_digits.startswith("91") and len(clean_digits) == 12:
                dial_num = f"+{clean_digits}"
            else:
                dial_num = f"+{clean_digits}"

            # Lock Sentinel so it never loops on its own outbound call
            global IS_NEMESIS_CALLING, NEMESIS_COOLDOWN_UNTIL
            IS_NEMESIS_CALLING = True
            NEMESIS_COOLDOWN_UNTIL = time.time() + 45.0
            SELF_DIALED_NUMBERS.add(re.sub(r"\D", "", dial_num)[-10:])

            # Dial the +91 number directly via Android Telecom CALL intent
            cls._run_adb_sync(
                dev,
                ["shell", "am", "start", "-a", "android.intent.action.CALL", "-d", f"tel:{dial_num}"],
            )
            time.sleep(2.8)

            # If a dual-SIM selector popped up, tap SIM 1 automatically
            cls._tap_ui_node_sync(dev, ["sim_1", "account_list", "text1"], ["sim 1", "jio"])
            time.sleep(1.0)

            # Tap the Speakerphone button on the InCallUI screen and raise call volume
            tapped_speaker = cls._tap_ui_node_sync(
                dev,
                ["speaker", "audio_route", "incall_second_button", "audio"],
                ["speaker", "speakerphone"],
            )
            cls._run_adb_sync(dev, ["shell", "media volume --stream 0 --set 15"])

            # Wait 9 seconds for pickup, speak natural assistant message, then hang up
            if spoken_message and spoken_message.strip():
                clean_speech = re.sub(r"[^a-zA-Z0-9,.?!\s]", " ", spoken_message.replace("'", "")).strip()
                if clean_speech:
                    time.sleep(9.0)
                    ps_script = (
                        "$w = New-Object -ComObject WScript.Shell; "
                        "1..12 | ForEach-Object { $w.SendKeys([char]175) }; "
                        "Add-Type -AssemblyName System.Speech; "
                        "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
                        "$s.Volume = 100; $s.Rate = -1; "
                        f"$s.Speak(\"Hello, I am Nemesis, Peeyush's assistant. {clean_speech}\");"
                    )
                    subprocess.run(["powershell", "-NoProfile", "-Command", ps_script], capture_output=True, timeout=25)
                    time.sleep(1.2)
                    cls._terminate_active_call_sync(dev)
                    return f"Called {clean_target}, delivered message ('{clean_speech}'), and hung up."

            spk_state = "Speakerphone ON" if tapped_speaker else "Dialing screen active"
            return f"Calling {clean_target} ({dial_num}) — {spk_state}."

        detail = await asyncio.to_thread(_sync_call)
        return {"device": dev, "status": "CALLING", "detail": detail}

    @classmethod
    async def open_and_read_emails(cls) -> Dict[str, Any]:
        devices = await cls.list_connected_phones()
        dev = devices[0]
        if dev.startswith("SIMULATED_"):
            return {"status": "OFFLINE", "emails": ["Phone not connected via ADB."]}

        def _sync_email_read() -> Dict[str, Any]:
            cls._wake_and_unlock_sync(dev)
            notifs = cls._extract_notifications_sync(dev, "com.google.android.gm")
            cls._run_adb_sync(dev, ["shell", "monkey -p com.google.android.gm -c android.intent.category.LAUNCHER 1"])
            time.sleep(2.2)
            screen_items = cls._extract_screen_texts_sync(dev)
            return {"notifications": notifs, "screen_text": screen_items}

        data = await asyncio.to_thread(_sync_email_read)
        return {"device": dev, "notifications": data["notifications"], "screen_text": data["screen_text"]}

    @classmethod
    async def send_or_reply_email(cls, body: str, recipient: Optional[str] = None, subject: str = "N.E.M.E.S.I.S. Automated Response") -> Dict[str, Any]:
        devices = await cls.list_connected_phones()
        dev = devices[0]
        if dev.startswith("SIMULATED_"):
            return {"status": "SIMULATED_CLOUD_EXECUTION", "detail": "[Cloud Demo Mode]: Simulated hardware action executed cleanly (Download the Device Bridge Kit in the top bar to link your physical Android phone via ADB)."}

        def _sync_email_send() -> str:
            cls._wake_and_unlock_sync(dev)
            if recipient and "@" in recipient:
                mailto_uri = f"mailto:{recipient.strip()}?subject={quote(subject)}&body={quote(body)}"
                cls._run_adb_sync(
                    dev,
                    ["shell", "am", "start", "-a", "android.intent.action.SENDTO", "-d", f'"{mailto_uri}"'],
                )
                time.sleep(2.5)
                cls._tap_ui_node_sync(dev, ["com.google.android.gm:id/send", "id/send"], ["send"])
                return f"Sent email to {recipient} with body: '{body}'"
            else:
                cls._run_adb_sync(dev, ["shell", "monkey -p com.google.android.gm -c android.intent.category.LAUNCHER 1"])
                time.sleep(1.5)
                cls._tap_ui_node_sync(dev, ["reply"], ["reply"])
                time.sleep(1.2)
                safe_text = body.replace("'", "").replace('"', "").replace(" ", "%s")
                cls._run_adb_sync(dev, ["shell", f'input text "{safe_text}"'])
                time.sleep(0.8)
                cls._tap_ui_node_sync(dev, ["com.google.android.gm:id/send", "id/send"], ["send"])
                return f"Replied to active email thread: '{body}'"

        detail = await asyncio.to_thread(_sync_email_send)
        return {"device": dev, "status": "SENT", "detail": detail}
