import os
from textwrap import dedent
from typing import List
from app.services.hf_client import HFClient
from app.config import settings

BASE_STYLE = '''You are a professional LinkedIn ghostwriter.
Rewrite the input into a concise, insightful LinkedIn post.
Keep it under 120-180 words, avoid hype, add 1-3 tasteful hashtags at the end.'''

def _truncate(text: str, max_chars: int = 3500) -> str:
    return text[:max_chars]

def _candidates_from_env() -> List[str]:
    raw = (settings.rewriter_model or "").strip()
    if not raw:
        return ["MBZUAI/LaMini-T5-738M", "google/flan-t5-base", "google/flan-t5-small", "sshleifer/distilbart-cnn-12-6"]
    return [m.strip() for m in raw.split(",") if m.strip()]

def _build_prompt(text: str, tone: str) -> str:
    # Works for T5/FLAN and general seq2seq
    system = BASE_STYLE + f" Tone: {tone}."
    return dedent(f'''
    Instruction: {system}
    Input:
    {_truncate(text)}
    Output:
    ''').strip()

def rewrite_linkedin(post_draft: str, tone: str = "professional") -> str:
    prompt = _build_prompt(post_draft, tone)
    params = {"max_new_tokens": 140, "temperature": 0.7, "top_p": 0.95}
    hf = HFClient()

    errors = []
    for model in _candidates_from_env():
        try:
            return hf.text_generation(model, prompt, params=params)
        except Exception as e:
            errors.append(f"{model}: {e}")
            continue
    raise RuntimeError("All rewrite models failed. Tried -> " + " | ".join(errors))
