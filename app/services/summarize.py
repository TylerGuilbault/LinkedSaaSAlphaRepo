from app.services.hf_client import HFClient
from app.config import settings

def summarize_text(text: str, max_length: int = 180, min_length: int = 60) -> str:
    prompt = text.strip()
    params = {
        "max_length": max_length,
        "min_length": min_length,
        "do_sample": False
    }
    hf = HFClient()
    out = hf.text_generation(settings.summarizer_model, prompt, params=params)
    return out
