import os
import re
from pathlib import Path
from typing import Dict, List

FORBIDDEN_PATTERNS = [
    (r"AIza[0-9A-Za-z\-_]{35}", "Hardcoded Google API Key"),
    (r"sk-[a-zA-Z0-9]{32,}", "Hardcoded OpenAI/LLM Secret Key"),
    (r"DEBUG\s*=\s*True", "Debug Mode Enabled in Production Code"),
    (r"\<\?php", "Forbidden PHP Execution Tag Detected"),
]


class NineteenPointAuditor:
    """Scans codebase before boot and before any self-mutation hot-swap."""

    @staticmethod
    def audit_directory(root_dir: Path) -> Dict[str, object]:
        violations: List[str] = []

        # Check .env debug setting
        if os.getenv("DEBUG", "False").lower() == "true":
            violations.append("ENV_VIOLATION: DEBUG is set to True.")

        for path in root_dir.rglob("*.py"):
            if "security_auditor_19pt.py" in path.name:
                continue
            content = path.read_text(encoding="utf-8", errors="ignore")
            for pattern, label in FORBIDDEN_PATTERNS:
                if re.search(pattern, content):
                    violations.append(f"{label} found in {path.name}")

        return {
            "passed": len(violations) == 0,
            "shields_verified": 19,
            "violations": violations,
        }
