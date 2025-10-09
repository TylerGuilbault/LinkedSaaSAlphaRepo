# app/services/rewrite.py
import os
from typing import Optional
import re, html

# OpenAI (sync client)
try:
    from openai import OpenAI
except Exception:
    OpenAI = None  # keep import from crashing if lib missing

_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
_API_KEY = os.getenv("OPENAI_API_KEY")

_client: Optional["OpenAI"] = None
if OpenAI and _API_KEY:
    try:
        _client = OpenAI(api_key=_API_KEY)
    except Exception:
        _client = None


def _light_cleanup(s: str) -> str:
    if not s:
        return ""
    t = html.unescape(s)
    # normalize newlines and limit multiple blank lines
    t = re.sub(r"(?:\r\n|\r|\n)", "\n", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    # remove raw URLs (your link card handles preview)
    t = re.sub(r"https?://\S+", "", t)
    return t.strip()


def rewrite_linkedin(text: str, tone: str = "professional") -> str:
    """
    OpenAI-first, no Hugging Face, never raises.
    Synchronous to match the /generate/post endpoint.
    On any error or missing key, returns the original text (cleaned) so the API never 500s.
    """
    base = (text or "").strip()
    if not base:
        return ""

    # If no OpenAI available, just return lightly cleaned input
    if not _client:
        return _light_cleanup(base)

    prompt = (
        f"Rewrite the content below as a clean LinkedIn post in a {tone} tone.\n"
        f"- Use natural paragraphs (one blank line between paragraphs).\n"
        f"- Use 1–3 tasteful emojis if they fit (e.g., ✅, 🤔).\n"
        f"- Bullets are OK if they help clarity; keep the post readable.\n"
        f"- No raw URLs in the body (they will be attached separately).\n"
        f"- No markdown formatting. Keep under 240 words.\n\n"
        f"CONTENT:\n{base}"
    )

    try:
        resp = _client.chat.completions.create(
            model=_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5,
            max_tokens=400,
        )
        out = (resp.choices[0].message.content or "").strip()
        return _light_cleanup(out) or _light_cleanup(base)
    except Exception:
        # Fail-safe: never crash the request
        return _light_cleanup(base)

