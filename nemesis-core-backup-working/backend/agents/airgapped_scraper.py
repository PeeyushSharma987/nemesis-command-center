import re
from typing import Dict
from urllib.parse import urlparse
import httpx


class AirgappedZeroPHPScraper:
    """Hardened web scraper that blocks SSRF, strips PHP/JS/HTML, and neutralizes indirect prompt injections."""

    BLOCKED_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0", "169.254.169.254", "::1"}
    PROMPT_INJECTION_PATTERNS = re.compile(
        r"(ignore\s+previous\s+instructions|system\s+prompt|you\s+are\s+now|disregard\s+all|\x3c\?php|<script)",
        re.IGNORECASE,
    )

    @classmethod
    def validate_url(cls, url: str) -> None:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            raise ValueError("Only HTTP/HTTPS URLs are permitted.")
        if parsed.hostname in cls.BLOCKED_HOSTS:
            raise ValueError("SSRF Shield: Internal/local network targets are blocked.")

    @classmethod
    def scrub_html_and_injections(cls, raw_html: str) -> str:
        # Remove scripts, styles, PHP tags (\x3c?php), and HTML comments
        cleaned = re.sub(r"<(script|style|iframe|object|embed).*?>.*?</\1>", " ", raw_html, flags=re.I | re.S)
        cleaned = re.sub(r"\x3c\?php.*?\?\x3e", " ", cleaned, flags=re.I | re.S)
        cleaned = re.sub(r"<[^>]+>", " ", cleaned)
        cleaned = cls.PROMPT_INJECTION_PATTERNS.sub("[REDACTED_INJECTION_ATTEMPT]", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned[:6000]

    @classmethod
    async def fetch_clean_context(cls, url: str) -> Dict[str, str]:
        cls.validate_url(url)
        headers = {"User-Agent": "NEMESIS-Airgap-Bot/2.0 (+ZeroPHP-Security-Sandbox)"}
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            safe_text = cls.scrub_html_and_injections(resp.text)
            return {"source_url": url, "sanitized_content": safe_text}