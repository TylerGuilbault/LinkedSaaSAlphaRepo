# app/routers/thoughtpost.py
from __future__ import annotations
from typing import Optional, Dict, Any, List
from fastapi import APIRouter
from pydantic import BaseModel, Field
import os, re, html, httpx, hashlib
from openai import AsyncOpenAI

# ✅ create the client once at module load
oai_client = AsyncOpenAI()  # will read OPENAI_API_KEY from env

router = APIRouter(prefix="/generate", tags=["generate"])

# --- OpenAI config ---
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")  # default

# --- HF fallback (kept for safety) ---
HF_TOKEN = os.getenv("HF_API_TOKEN", "")
_raw_models = (os.getenv("REWRITER_MODEL", "") or os.getenv("HF_REWRITE_MODEL", "")).strip()
REWRITER_MODELS: List[str] = [m.strip() for m in _raw_models.split(",") if m.strip()] or [
    "HuggingFaceH4/zephyr-7b-beta",
    "google/flan-t5-base",
    "MBZUAI/LaMini-T5-738M",
]
HF_TIMEOUT = float(os.getenv("HF_TIMEOUT", "60"))
HF_API_BASE = "https://api-inference.huggingface.co/models/"

class ThoughtPostRequest(BaseModel):
    text: str = Field(..., min_length=1)
    tone: str = Field(default="professional")
    angle: Optional[str] = Field(default=None, description="e.g., career | leadership | market | hiring | ops")
    max_words: int = Field(default=230, ge=80, le=300)
    source_title: Optional[str] = None
    source_link: Optional[str] = None

class ThoughtPostResponse(BaseModel):
    draft: str

# --- add this helper near the top of the file (e.g., under imports) ---
def _fix_mojibake_roundtrip(s: str) -> str:
    """
    Fix UTF-8 text that was incorrectly decoded as CP1252/Latin-1.
    Example: 'â¢' -> '•', 'âœ…' -> '✅', 'ðŸ¤”' -> '🤔'.
    We try up to two passes in case it was mangled twice.
    """
    if not s:
        return s
    for _ in range(2):
        try:
            s2 = s.encode("latin1", errors="ignore").decode("utf-8", errors="ignore")
        except Exception:
            break
        if not s2 or s2 == s:
            break
        s = s2
    return s

def _hf_headers() -> Dict[str, str]:
    h = {"Content-Type": "application/json"}
    if HF_TOKEN:
        h["Authorization"] = f"Bearer {HF_TOKEN}"
    return h

# Tiny on-voice exemplars (few-shot)
FEW_SHOTS: List[str] = [
    (
        "INPUT:\nA large cloud vendor changes AI model partners.",
        "OUTPUT:\nWhy this matters: Vendor shifts force teams to prove their workflows aren’t overfit to one stack.\n"
        "Bottom line: Document one process end-to-end and make it portable (alt tools, data formats, rollback plan).\n"
        "Where could you add redundancy without slowing shipping?\n"
        "#Leadership #Execution"
    ),
    (
        "INPUT:\nA company pivots to hybrids before full EVs.",
        "OUTPUT:\nWhy this matters: Bridge products fund the roadmap while the hard tech matures.\n"
        "Bottom line: Sequence ambition—ship the 70% that keeps customers moving, invest the margin in the 100%.\n"
        "What ‘bridge feature’ would unblock your next milestone?\n"
        "#Strategy #Product"
    ),
]

_ANGLE_HINT = {
    "career":    "Translate to skills, portability, and compounding learning.",
    "leadership":"Prioritization, communication, and explicit tradeoffs.",
    "market":    "Competitive dynamics, capital access, and switching costs.",
    "hiring":    "Signals in interviews, ramp speed, real tools used.",
    "ops":       "Runbooks, SLAs, handoffs, and failure modes.",
}

def _extract_terms(title: Optional[str], text: str) -> List[str]:
    raw = " ".join([title or "", text or ""])
    caps = re.findall(r"\b[A-Z][A-Za-z0-9\-]{2,}\b", raw)
    common = re.findall(
        r"\b(ai|copilot|policy|loan|equity|funding|pricing|roadmap|security|privacy|compliance|supply chain|hybrid|erev|valuation)\b",
        raw, flags=re.I,
    )
    pool = list(dict.fromkeys([*caps, *[c.title() for c in common]]))
    return pool[:8]

def _detect_topics(text: str) -> List[str]:
    t = text.lower()
    tags: List[str] = []
    if any(k in t for k in ["ai", "model", "llm", "copilot", "anthropic", "openai"]): tags.append("#AI")
    if any(k in t for k in ["supply chain", "logistics", "manufacturing"]):           tags.append("#SupplyChain")
    if any(k in t for k in ["finance", "loan", "equity", "valuation", "funding"]):    tags.append("#Finance")
    if any(k in t for k in ["policy", "regulation", "administration", "trade"]):      tags.append("#Policy")
    if any(k in t for k in ["product", "roadmap", "launch", "feature"]):              tags.append("#Product")
    if any(k in t for k in ["hiring", "recruit", "talent"]):                          tags.append("#Hiring")
    if any(k in t for k in ["ops", "oncall", "runbook", "incident", "sla"]):          tags.append("#Operations")
    return tags


from typing import Optional  # keep this at the top of the file

from typing import Optional

def _build_prompt(
    text: str,
    tone: str,
    angle: Optional[str],
    max_words: int,
    source_title: Optional[str],
    source_link: Optional[str],
) -> str:
    angle_key = (angle or "").strip().lower()
    angle_hint = {
        "career":     "Translate to skills and compounding learning.",
        "leadership": "Prioritization, communication, and explicit tradeoffs.",
        "market":     "Competitive dynamics and switching costs.",
        "hiring":     "Signals in interviews and ramp speed.",
        "ops":        "Runbooks, SLAs, handoffs, and failure modes.",
    }.get(angle_key, "Relate it to professional practice and peer learning.")

    src_title = (source_title or "").strip()

    prompt = f"""
You are a seasoned LinkedIn thought leader. Write a natural, engaging post for professionals based on the ARTICLE below.

ARTICLE:
{src_title}
{text}

Write it like a human:
- Use short paragraphs with blank lines between them (no walls of text).
- Emojis are optional (0–3), use only if they feel natural.
- Bullets (•) are optional—use only if they help clarity.
- End with one reflective question on its own line.
- Add 1–4 tasteful hashtags at the end (#Leadership etc.), not “hashtag#”.
- Do NOT include any URLs (the system attaches the link preview).
- Stay under {max_words} words.
- Tone: {tone}. Angle: {angle_key or "general"} — {angle_hint}

Return only the post body exactly as it should appear.
""".strip()
    return prompt


# ---------- OpenAI primary ----------
async def _call_openai(prompt: str) -> str:
    resp = await oai_client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": "You are a professional LinkedIn content strategist."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.4,
        max_tokens=700,  # was 300 — allow longer outputs
    )
    return (resp.choices[0].message.content or "").strip()


# ---------- HF fallback ----------
async def _hf_generate_one(model: str, prompt: str) -> str:
    url = HF_API_BASE + model
    payload: Dict[str, Any] = {
        "inputs": prompt,
        "parameters": {
            "max_new_tokens": 260,
            "temperature": 0.4,
            "repetition_penalty": 1.15,
            "return_full_text": False,
        }
    }
    async with httpx.AsyncClient(timeout=HF_TIMEOUT) as client:
        r = await client.post(url, headers=_hf_headers(), json=payload)
        if r.status_code in (502,503,504,503):
            r = await client.post(url, headers=_hf_headers(), json=payload)
        r.raise_for_status()
        data = r.json()
    if isinstance(data, list) and data:
        item = data[0]
        if isinstance(item, dict):
            return (item.get("generated_text")
                    or item.get("summary_text")
                    or item.get("output_text")
                    or "").strip()
        return str(item).strip()
    if isinstance(data, dict):
        return (data.get("generated_text")
                or data.get("summary_text")
                or data.get("output_text")
                or "").strip()
    return str(data).strip()

async def _hf_generate(models: List[str], prompt: str) -> str:
    last_err = None
    for m in models:
        try:
            out = await _hf_generate_one(m, prompt)
            if out:
                return out
        except Exception as e:
            last_err = e
            continue
    if last_err:
        raise last_err
    return ""

# ---------- Cleanup / shaping ----------
# --- replace your _strip_mojibake with this version ---
def _strip_mojibake(text: str) -> str:
    if not text:
        return ""

    t = text

    # Detect mojibake patterns (bad CP1252/Latin-1 sequences)
    if re.search(r"[\u0080-\u009F]|[Ââ][\u0080-\u00BF]|ð[\u0080-\u00BF]", t):
        try:
            t = _fix_mojibake_roundtrip(t)
        except Exception:
            pass

    # Fallback repairs that sometimes sneak through
    t = (t
         .replace("\u00C2\u00A0", " ")  # NBSP -> space
         .replace("Â ", " ")
    )

    # Decode any HTML entities
    t = html.unescape(t)

    # Strip CP1252 control chars and normalize ellipses
    t = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", "", t)
    t = re.sub(r"\s*\.\s*\.\s*\.?\s*", ". ", t)

    # Normalize newlines; allow only single blank lines
    t = re.sub(r"(?:\r\n|\r|\n)", "\n", t)
    lines = [ln.strip() for ln in t.split("\n")]
    cleaned, blank = [], 0
    for ln in lines:
        if ln == "":
            blank += 1
            if blank <= 1:
                cleaned.append("")
        else:
            blank = 0
            cleaned.append(ln)

    return "\n".join(cleaned).strip()

def _choose_tags(body: str, topics: List[str], angle_key: str, base_tags: List[str], add_privacy: bool=False) -> List[str]:
    base: List[str] = []
    seen = set()
    for h in base_tags:
        h1 = h.strip()
        if not h1 or h1.lower() in seen:
            continue
        seen.add(h1.lower())
        base.append(h1)
    if base:
        return base[:3]

    want: List[str] = []
    raw = body.lower()
    if re.search(r"\b(ai|model|genai|llm|copilot)\b", raw): want.append("#AI")
    if re.search(r"\b(supply chain|logistics|manufacturing)\b", raw): want.append("#SupplyChain")
    if re.search(r"\b(finance|loan|equity|valuation|funding)\b", raw): want.append("#Finance")
    if re.search(r"\b(policy|regulation|administration|trade)\b", raw): want.append("#Policy")
    if add_privacy: want.append("#Privacy")

    angle_defaults = {
        "career":     ["#CareerGrowth", "#Upskilling"],
        "leadership": ["#Leadership", "#Execution"],
        "market":     ["#MarketTrends", "#Strategy"],
        "hiring":     ["#Hiring", "#TeamBuilding"],
        "ops":        ["#Operations", "#Reliability"],
    }
    picks = topics[:3] or want or angle_defaults.get(angle_key, ["#Leadership"])
    # Keep at most 3, unique
    out, seen2 = [], set()
    for h in picks:
        hl = h.lower()
        if hl in seen2: continue
        seen2.add(hl); out.append(h)
        if len(out) == 3: break
    return out

def _enforce_shape(t: str, max_words: int, angle: Optional[str], topics: List[str],
                   source_title: Optional[str], terms: List[str]) -> str:
    if not t:
        t = ""

    low = t.lower()
    if low.startswith("you are") or low.startswith("write") or "keep it under" in low:
        t = re.sub(r"(?is)^.*?(?=\w)", "", t).strip()

    subj = (terms[0] if terms else (source_title or "this change")).strip()

    raw_ctx = f"{source_title or ''} {t}"
    is_voice = re.search(r"\b(call|voice|record(ing|ed)?|transcript|telephony|phone)\b", raw_ctx, re.I)
    is_priv  = re.search(r"\b(consent|privacy|data|DPA|GDPR|CCPA|retention|revocation)\b", raw_ctx, re.I)
    voice_priv = bool(is_voice or is_priv)

    # Don’t force a specific header—just ensure the first line mentions the subject once
    first_line = re.split(r"(?<=\n)|(?<=[.!?])\s+", body, maxsplit=1)[0]
    if subj and subj.lower() not in first_line.lower():
        body = f"{subj}: {body}".strip()


    angle_key = (angle or "").lower()
    angle_line_map = {
        "career":     "Bottom line: turn this into a skill you practice this week—show one concrete example in your next 1:1.",
        "leadership": "Bottom line: make the tradeoffs explicit—risk, timeline, reversibility—and write the decision down.",
        "market":     "Bottom line: watch second-order effects on pricing power, switching costs, and partner leverage.",
        "hiring":     "Bottom line: tune interview signals and onboarding to the tools you’ll use in 90 days.",
        "ops":        "Bottom line: adjust runbooks where this changes handoffs, incident paths, or SLAs.",
    }
    if voice_priv and angle_key == "leadership":
        angle_line_map["leadership"] = (
            "Bottom line: treat recorded conversations as sensitive data—confirm consent flows, DPAs, retention, and revocation before any pilot."
        )

    # Ensure we have a Bottom line
    if "Bottom line:" not in body:
        body = f"{body.rstrip()} {angle_line_map.get(angle_key, 'Bottom line: ship one small, reversible change this week and measure impact.')}"

    # Ensure a contextual question
    if "?" not in body:
        q_map = {
            "career":     f"What would you upskill first if {subj} landed on your roadmap?",
            "leadership": f"What policy or process would you update first given {subj}?",
            "market":     f"Does {subj} change your roadmap or pricing in the next two quarters?",
            "hiring":     f"What interview signal would help you hire better for teams affected by {subj}?",
            "ops":        f"What runbook or SLA would you adjust first if {subj} were in production?",
        }
        body = body.rstrip(". ") + " " + q_map.get(angle_key, f"How would you respond to {subj} in your context?")

    # Word budget
    words = body.split()
    if len(words) > max_words:
        body = " ".join(words[:max_words]).rstrip(",;:") + "."

    final_tags = _choose_tags(body=body, topics=topics, angle_key=angle_key, base_tags=tags, add_privacy=voice_priv)

    # Tidy
    body = re.sub(r"\s*\.\s*\.\s*\.?\s*", ". ", body)
    body = re.sub(r"\s{2,}", " ", body).strip()

    return (body + "\n\n" + " ".join(final_tags)).strip()

def _cleanup(out_text: str, req: ThoughtPostRequest) -> str:
    t = _strip_mojibake(out_text or "")
    # remove any raw URLs; the link card handles preview
    t = re.sub(r'https?://\S+', '', t).strip()
    return t


    # (If you still want automatic hashtags, append them here — otherwise let the model’s tags stand.)
    return t.strip()

def _pick_deterministic(seq, seed_text, salt=""):
    if not seq:
        return None
    h = hashlib.md5((seed_text + "|" + salt).encode("utf-8")).digest()
    idx = int.from_bytes(h[:2], "big") % len(seq)
    return seq[idx]

def _structure_linkedin(core_text: str, max_words: int) -> str:
    """
    Preserve the model's formatting:
      - keep emojis and bullets as-is
      - keep blank lines (at most 2 in a row)
      - normalize CRLF to LF
      - hard-cap word count if needed
    """
    if not core_text:
        return ""

    t = core_text

    # Normalize newlines but DO NOT collapse single blank lines
    t = re.sub(r"\r\n?", "\n", t)

    # Trim whitespace per line but keep line structure
    lines = [ln.rstrip() for ln in t.split("\n")]
    t = "\n".join(lines)

    # Cap excessive blank lines (3+ → 2)
    t = re.sub(r"\n{3,}", "\n\n", t)

    # Hard word budget
    words = t.split()
    if len(words) > max_words:
        t = " ".join(words[:max_words]).rstrip(",;:") + "…"

    return t.strip()

def _normalize_linkedin_markup(text: str) -> str:
    if not text:
        return ""

    t = text

    # 1) Kill markdown bold/italics markers only (keep words)
    t = re.sub(r"\*\*(.*?)\*\*", r"\1", t)   # **bold**
    t = re.sub(r"\*(.*?)\*", r"\1", t)       # *italic*
    t = re.sub(r"_(.*?)_", r"\1", t)         # _italic_

    # 2) Convert numeric lists at line start to dash bullets
    #    "1. Foo" -> "– Foo"
    lines = re.split(r"(?:\r\n|\r|\n)", t)
    conv = []
    for ln in lines:
        conv.append(re.sub(r"^\s*\d+\.\s+", "– ", ln))
    t = "\n".join(conv)

    # 3) Normalize 'hashtag#Tag' -> '#Tag' (and collapse dup spaces)
    t = re.sub(r"(?i)\bhashtag\s*#?(\w+)", r"#\1", t)

    # 4) Ensure no raw URLs (the link card handles preview)
    t = re.sub(r"https?://\S+", "", t).strip()

    # 5) Keep short paragraphs with single blank lines
    t = re.sub(r"[ \t]{2,}", " ", t)          # extra spaces
    t = re.sub(r"(?:\r\n|\r|\n)", "\n", t)    # normalize EOL
    t = re.sub(r"\n{3,}", "\n\n", t)          # cap blank lines

    return t.strip()

# app/routers/thoughtpost.py

@router.post("/thoughtpost", response_model=ThoughtPostResponse)
async def generate_thoughtpost(req: ThoughtPostRequest) -> Dict[str, str]:
    import re as _re, html as _html

    def _first_sentence(s: str, limit: int = 240) -> str:
        if not s:
            return ""
        # strip URLs, HTML entities -> unicode, collapse spaces
        s = _re.sub(r'https?://\S+', '', s)
        s = _html.unescape(s)
        s = _re.sub(r'\s+', ' ', s).strip()
        # take first sentence-ish
        parts = _re.split(r'(?<=[.!?])\s+', s)
        head = (parts[0] if parts else s).strip()
        if len(head) > limit:
            head = head[: limit - 1].rstrip(",;: ") + "…"
        return head

    def _fallback_from_req(r: ThoughtPostRequest) -> str:
        title   = (r.source_title or "").strip()
        summary = (r.text or "").strip()
        head = _first_sentence(summary) or (title if title else "Quick update")
        if title and head and not head.lower().startswith(title.lower()):
            headline = f"{title}: {head}"
        else:
            headline = head or (title or "Quick update")

        body_lines = [
            headline,
            "",
            "• ✅ What changed: Summarize the impact and scope so priorities don’t drift.",
            "• Impact: Clarify who’s affected and which KPIs or deadlines move.",
            "• Next step: Write the tradeoffs (timeline, resources, risk) and share the decision in one place.",
            "",
            "What’s the first tradeoff you’ll make to keep focus? 🤔"
        ]
        return "\n".join(body_lines).strip()

    try:
        prompt = _build_prompt(
            text=req.text,
            tone=req.tone.strip(),
            angle=req.angle,
            max_words=req.max_words,
            source_title=req.source_title,
            source_link=req.source_link,
        )

        raw = ""
        try:
            raw = await _call_openai(prompt)
        except Exception as e:
            print(f"[openai.error] {e}", flush=True)
            try:
                raw = await _hf_generate(REWRITER_MODELS, prompt)
            except Exception as e2:
                print(f"[hf.error] {e2}", flush=True)
                raw = ""

        cleaned = _cleanup(raw, req)
        cleaned = _re.sub(r'https?://\S+', '', cleaned or "").strip()

        if not cleaned:
            cleaned = _fallback_from_req(req)

        return {"draft": cleaned}

    except Exception as e:
        print(f"[thoughtpost.fatal] {e}", flush=True)
        return {"draft": _fallback_from_req(req)}

@router.get("/thoughtpost/ping")
async def thoughtpost_ping():
    return {"ok": True}
