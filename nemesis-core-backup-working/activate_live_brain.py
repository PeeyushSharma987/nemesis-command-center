import ast
import re
from pathlib import Path

CURRENT = Path(__file__).resolve().parent
BASE_DIR = CURRENT if (CURRENT / "backend").exists() else CURRENT / "nemesis-core"
PROJECT_ROOT = BASE_DIR.parent
ADB_FILE = BASE_DIR / "device_bridge" / "android_swarm_adb.py"
BRAIN_FILE = BASE_DIR / "backend" / "commander" / "nemesis_brain.py"
HUD_PATH = BASE_DIR / "frontend_hud" / "index.html"
BAT_FILE = PROJECT_ROOT / "start_nemesis.bat"

print("=== N.E.M.E.S.I.S. FULL CODEBASE AUDIT & PRODUCTION STABILIZATION PATCH ===")

# ==============================================================================
# 1. PATCH android_swarm_adb.py: CONTACT CACHE, AUTO-RECONNECT & SAFE TTS QUOTES
# ==============================================================================
adb_code = ADB_FILE.read_text(encoding="utf-8")

# Add fast in-memory CONTACT_CACHE
if "CONTACT_CACHE:" not in adb_code:
    adb_code = adb_code.replace(
        "SEEN_ALERT_SIGNATURES: Set[str] = set()",
        "SEEN_ALERT_SIGNATURES: Set[str] = set()\nCONTACT_CACHE: Dict[str, str] = {}",
    )

# Upgrade _lookup_contact_number_sync to use CONTACT_CACHE and case-insensitive matching
fast_contact_lookup = r'''    @classmethod
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
'''

pattern_lookup = r"    @classmethod\s+def _lookup_contact_number_sync\(cls,.*?(?=\n    @classmethod)"
if re.search(pattern_lookup, adb_code, flags=re.S):
    adb_code = re.sub(pattern_lookup, lambda _: fast_contact_lookup.rstrip() + "\n", adb_code, flags=re.S)

# Ensure contractions like "I'll" or "don't" never break PowerShell SpeechSynthesizer
adb_code = adb_code.replace(
    'clean_speech = re.sub(r"[^a-zA-Z0-9,.?!\\s]", "", spoken_message).strip()',
    'clean_speech = re.sub(r"[^a-zA-Z0-9,.?!\\s]", " ", spoken_message.replace("\'", "")).strip()',
)

ast.parse(adb_code)
ADB_FILE.write_text(adb_code, encoding="utf-8")
print("[1/4] Stabilized android_swarm_adb.py: Added 0ms Contact Cache & safe PowerShell speech escaping.")

# ==============================================================================
# 2. PATCH nemesis_brain.py: STRIP MARKDOWN/JSON ARTIFACTS FROM SPOKEN OUTPUT
# ==============================================================================
brain_code = BRAIN_FILE.read_text(encoding="utf-8")

clean_text_helper = r'''    @staticmethod
    def _clean_spoken_text(text: str) -> str:
        """Removes markdown asterisks, backticks, or accidental JSON wrappers so TTS speaks cleanly."""
        cleaned = re.sub(r"```(?:json|python)?.*?```", "", text, flags=re.S).strip()
        cleaned = re.sub(r"[*_`#]+", "", cleaned)
        cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
        return cleaned or text.strip()
'''

if "def _clean_spoken_text" not in brain_code:
    brain_code = brain_code.replace(
        "    @staticmethod\n    def _record_turn",
        clean_text_helper + "\n    @staticmethod\n    def _record_turn",
    )
    brain_code = brain_code.replace(
        'final_text = res["content"].strip()',
        'final_text = self._clean_spoken_text(res["content"].strip())',
    )

ast.parse(brain_code)
BRAIN_FILE.write_text(brain_code, encoding="utf-8")
print("[2/4] Stabilized nemesis_brain.py: Added TTS markdown/JSON scrubber for natural humanoid speech.")

# ==============================================================================
# 3. PATCH frontend_hud/index.html: TTS WATCHDOG, REUSABLE MEDIAPIPE & 5.5s RELAY SYNC
# ==============================================================================
html = HUD_PATH.read_text(encoding="utf-8")

# Fix 3A: Add Speech Watchdog + Deep Humanoid Voice Selection so the 3D jaw never gets stuck open
old_tts_hook = """    // Synchronize speechSynthesis with 3D Low-Poly Lip/Jaw Articulation
    if ('speechSynthesis' in window) {
      const origSpeak = window.speechSynthesis.speak.bind(window.speechSynthesis);
      window.speechSynthesis.speak = function(utterance) {
        if (utterance) {
          utterance.addEventListener('start', () => { window.nemesisFaceState.isSpeaking = true; });
          utterance.addEventListener('end', () => { window.nemesisFaceState.isSpeaking = false; });
          utterance.addEventListener('error', () => { window.nemesisFaceState.isSpeaking = false; });
        }
        window.nemesisFaceState.isSpeaking = true;
        return origSpeak(utterance);
      };
    }"""

new_tts_hook = """    // Synchronize speechSynthesis with 3D Low-Poly Lip/Jaw Articulation + Watchdog Timer
    if ('speechSynthesis' in window) {
      let speechWatchdog = null;
      const origSpeak = window.speechSynthesis.speak.bind(window.speechSynthesis);
      window.speechSynthesis.speak = function(utterance) {
        if (utterance) {
          utterance.text = String(utterance.text || '').replace(/[*_`#]/g, '');
          const voices = window.speechSynthesis.getVoices();
          const preferred = voices.find(v => /Google UK English Male|Microsoft Mark|Microsoft David|en-IN/i.test(v.name));
          if (preferred) utterance.voice = preferred;
          if (!utterance.rate) utterance.rate = 1.03;

          const stopMouth = () => {
            window.nemesisFaceState.isSpeaking = false;
            if (speechWatchdog) { clearTimeout(speechWatchdog); speechWatchdog = null; }
          };
          utterance.addEventListener('start', () => { window.nemesisFaceState.isSpeaking = true; });
          utterance.addEventListener('end', stopMouth);
          utterance.addEventListener('error', stopMouth);

          if (speechWatchdog) clearTimeout(speechWatchdog);
          const estMs = Math.min(24000, Math.max(3000, utterance.text.length * 85));
          speechWatchdog = setTimeout(stopMouth, estMs);
        }
        window.nemesisFaceState.isSpeaking = true;
        return origSpeak(utterance);
      };
    }"""

if old_tts_hook in html:
    html = html.replace(old_tts_hook, new_tts_hook)

# Fix 3B: Reuse MediaPipe Hands instance across camera toggles so WebGL never leaks
html = html.replace(
    "const hands = new window.Hands({",
    "const hands = window.__nemesisHandsInstance || (window.__nemesisHandsInstance = new window.Hands({",
)
html = html.replace(
    "locateFile: (f) => `https://cdn.jsdelivr.net/npm/@mediapipe/hands/${f}`\n          });",
    "locateFile: (f) => `https://cdn.jsdelivr.net/npm/@mediapipe/hands/${f}`\n          }));",
)

# Fix 3C: Tune remote second-phone pickup timer to 5500ms (since ADB already waited 3.8s while dialing)
html = html.replace(
    "const waitMs = remoteCalled ? 9000 : 1600;",
    "const waitMs = remoteCalled ? 5500 : 1600;",
)

HUD_PATH.write_text(html, encoding="utf-8")
print("[3/4] Stabilized frontend_hud/index.html: Added TTS jaw watchdog, reusable MediaPipe instance & 5.5s relay sync.")

# ==============================================================================
# 4. UPDATE start_nemesis.bat FOR 1-CLICK DEPLOYMENT LAUNCH
# ==============================================================================
bat_content = r"""@echo off
title N.E.M.E.S.I.S. // Supreme Command Center
cd /d "%~dp0\nemesis-core"
echo ===================================================
echo   LAUNCHING N.E.M.E.S.I.S. v2.0 COMMAND CENTER
echo ===================================================
start "" http://localhost:8000
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
pause
"""
BAT_FILE.write_text(bat_content, encoding="utf-8")
print("[4/4] Updated start_nemesis.bat for one-click server + Chrome HUD launch!")
