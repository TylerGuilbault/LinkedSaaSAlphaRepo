import httpx
from typing import Optional, Dict, Any
from app.config import settings

class HFClient:
    def __init__(self, api_token: Optional[str] = None, timeout: float = 60.0):
        self.api_token = api_token or settings.hf_api_token
        if not self.api_token:
            raise RuntimeError("HF_API_TOKEN is not set. Put it in .env or set it in the environment.")
        self.headers = {"Authorization": f"Bearer {self.api_token}"}
        self.client = httpx.Client(timeout=timeout)

    def text_generation(self, model: str, inputs: str, params: Optional[Dict[str, Any]] = None) -> str:
        url = f"https://api-inference.huggingface.co/models/{model}"
        payload = {"inputs": inputs}
        if params:
            payload.update({"parameters": params})
        r = self.client.post(url, headers=self.headers, json=payload)
        try:
            r.raise_for_status()
        except httpx.HTTPStatusError as e:
            detail = r.text[:500]
            raise RuntimeError(f"HuggingFace API error {r.status_code}: {detail}") from e
        data = r.json()
        # Handle common response shapes
        if isinstance(data, list) and data:
            if isinstance(data[0], dict):
                if "generated_text" in data[0]:
                    return data[0]["generated_text"]
                if "summary_text" in data[0]:
                    return data[0]["summary_text"]
        if isinstance(data, dict):
            if "generated_text" in data:
                return data["generated_text"]
            if "summary_text" in data:
                return data["summary_text"]
        return str(data)
