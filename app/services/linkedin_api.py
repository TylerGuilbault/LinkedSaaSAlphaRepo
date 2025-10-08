# app/services/linkedin_api.py
import httpx
import time
from typing import Tuple, Dict, Any
from urllib.parse import urlencode, quote
from app.config import settings
import os

# Verbose logging flag (dev only)
VERBOSE_LINKEDIN_LOG = os.getenv("LINKEDIN_VERBOSE_LOGGING", "false").lower() in ("1", "true", "yes")

AUTH_URL  = "https://www.linkedin.com/oauth/v2/authorization"
TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"
UGC_URL   = "https://api.linkedin.com/v2/ugcPosts"

USERINFO_URL = "https://www.linkedin.com/oauth/openid/connect/userinfo"
ME_URL = "https://api.linkedin.com/v2/me"
ASCII_ONLY = os.getenv("LINKEDIN_ASCII_ONLY", "false").lower() in ("1", "true", "yes")

def _preserve_paragraphs(t: str) -> str:
    """
    Ensure blank-line paragraph spacing survives LinkedIn's sanitizer by
    inserting a zero-width space between double newlines.
    """
    if not t:
        return ""
    # normalize newlines
    t = t.replace("\r\n", "\n").replace("\r", "\n")
    # de-dupe if already present
    t = t.replace("\n\n\u200B", "\n\n")
    # insert invisible spacer so LinkedIn keeps the blank line
    t = t.replace("\n\n", "\n\n\u200B")
    return t


def _sanitize_for_linkedin(text: str) -> str:
    """Optional ASCII-only sanitizer to avoid mojibake on publish."""
    if not text:
        return ""

    if not ASCII_ONLY:
        # Keep natural Unicode and preserve blank-line paragraphs
        t = _preserve_paragraphs(text)
        return t

    # ASCII-only fallback (unchanged)
    t = text
    t = t.replace("•", "- ")
    t = t.replace("–", "-").replace("—", "-")
    t = (t
         .replace("✅", "[✓]")
         .replace("🤔", "?")
         .replace("👉", "->")
         .replace("📌", "-")
         .replace("🤝", "")
         .replace("🚀", "")
         .replace("💡", "")
    )
    t = t.encode("ascii", "ignore").decode("ascii")
    import re
    t = re.sub(r"\s{2,}", " ", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()


def get_person_id(access_token: str) -> str:
    """Return the person id from /v2/me, or '' on failure."""
    try:
        with httpx.Client(timeout=httpx.Timeout(30, connect=5)) as c:
            r = c.get(
                ME_URL,
                headers={"Authorization": f"Bearer {access_token}"},
                params={"projection": "(id)"}
            )
            if r.status_code != 200:
                log_request_id(r)
                try:
                    print("[get_person_id] fail:", r.status_code, r.text, flush=True)
                except Exception:
                    pass
                return ""
            data = r.json()
            return str(data.get("id", "")) or ""
    except Exception as e:
        print(f"[get_person_id] error: {e}", flush=True)
        return ""


def get_person_id_with_response(access_token: str) -> tuple:
    """Return (person_id, status_code, text). person_id is '' on failure."""
    try:
        with httpx.Client(timeout=httpx.Timeout(30, connect=5)) as c:
            r = c.get(
                ME_URL,
                headers={"Authorization": f"Bearer {access_token}"},
                params={"projection": "(id)"}
            )
            status = r.status_code
            text = r.text
            if status != 200:
                log_request_id(r)
                try:
                    print("[get_person_id_with_response] fail:", status, text, flush=True)
                except Exception:
                    pass
                return "", status, text
            data = r.json()
            return str(data.get("id", "")) or "", status, text
    except Exception as e:
        print(f"[get_person_id_with_response] error: {e}", flush=True)
        return "", 0, str(e)


def get_me_raw(access_token: str) -> dict:
    """Return LinkedIn /v2/me raw response: {status, headers, text, json (if parseable)}"""
    try:
        with httpx.Client(timeout=httpx.Timeout(30, connect=5)) as c:
            r = c.get(ME_URL, headers={"Authorization": f"Bearer {access_token}"})
            log_request_id(r)
            out = {
                "status": r.status_code,
                "headers": {k: v for k, v in r.headers.items()},
                "text": r.text,
                "json": None,
            }
            try:
                out["json"] = r.json()
            except Exception:
                out["json"] = None
            return out
    except Exception as e:
        print(f"[get_me_raw] error: {e}", flush=True)
        return {"status": 0, "headers": {}, "text": str(e), "json": None}

def me_id(access_token: str) -> str:
    """Return the person id from /v2/me, or '' on failure."""
    try:
        with httpx.Client(timeout=httpx.Timeout(30, connect=5)) as c:
            r = c.get(
                ME_URL,
                headers={"Authorization": f"Bearer {access_token}"},
                params={"projection": "(id)"}
            )
            if r.status_code != 200:
                log_request_id(r)
                try:
                    print("[me_id] fail:", r.status_code, r.text, flush=True)
                except Exception:
                    pass
                return ""
            data = r.json()
            # LinkedIn returns {"id": "123456789"} (string of digits)
            return str(data.get("id", "")) or ""
    except Exception as e:
        print(f"[me_id] error: {e}", flush=True)
        return ""

def userinfo_sub(access_token: str) -> str:
    try:
        with httpx.Client(timeout=60) as c:
            r = c.get(USERINFO_URL, headers={"Authorization": f"Bearer {access_token}"})
            if r.status_code != 200:
                print(f"[userinfo_sub] non-200: {r.status_code} {r.text}", flush=True)
                return ""
            data = r.json()
            sub = data.get("sub", "")
            if not sub:
                print(f"[userinfo_sub] no 'sub' in payload: {data}", flush=True)
            return sub
    except Exception as e:
        print(f"[userinfo_sub] error: {e}", flush=True)
        return ""

# Create an article share (OG link)
def post_article_share(access_token: str, author_urn: str, url: str, text: str = "") -> tuple:
    text = _sanitize_for_linkedin(text)
    payload = {
        "author": author_urn,
        "lifecycleState": "PUBLISHED",
        "specificContent": {
            "com.linkedin.ugc.ShareContent": {
                "shareCommentary": {"text": text},
                "shareMediaCategory": "ARTICLE",
                "media": [{"status": "READY", "originalUrl": url}]
            }
        },
        "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
    }

    # REMOVE the manual dumps/bytes
    # body = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    with httpx.Client(timeout=60) as c:
        r = c.post(
            UGC_URL,
            headers={
                "Authorization": f"Bearer {access_token}",
                # Let httpx set Content-Type appropriately for JSON
                "X-Restli-Protocol-Version": "2.0.0",
            },
            json=payload,  # <— let httpx serialize and set UTF-8 correctly
        )
        return r.status_code in (201, 202), r

# Register image upload
def register_image_upload(access_token: str, author_urn: str) -> dict:
    register_url = "https://api.linkedin.com/v2/assets?action=registerUpload"
    payload = {
        "registerUploadRequest": {
            "owner": author_urn,
            "recipes": ["urn:li:digitalmediaRecipe:feedshare-image"],
            "serviceRelationships": [{
                "relationshipType": "OWNER",
                "identifier": "urn:li:userGeneratedContent"
            }]
        }
    }
    with httpx.Client(timeout=60) as c:
        r = c.post(
            register_url,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        r.raise_for_status()
        return r.json()

# Upload image asset
def upload_image_asset(upload_url: str, image_bytes: bytes) -> bool:
    headers = {"Content-Type": "application/octet-stream"}
    with httpx.Client(timeout=60) as c:
        r = c.put(upload_url, headers=headers, content=image_bytes)
        return r.status_code in (201, 202)

# Create image share post
def post_image_share(access_token: str, author_urn: str, asset_urn: str, text: str = "") -> tuple:
    text = _sanitize_for_linkedin(text)
    payload = {
        "author": author_urn,
        "lifecycleState": "PUBLISHED",
        "specificContent": {
            "com.linkedin.ugc.ShareContent": {
                "shareCommentary": {"text": text},
                "shareMediaCategory": "IMAGE",
                "media": [{"status": "READY", "media": asset_urn}]
            }
        },
        "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
    }

    # body = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    with httpx.Client(timeout=60) as c:
        r = c.post(
            UGC_URL,
            headers={
                "Authorization": f"Bearer {access_token}",
                "X-Restli-Protocol-Version": "2.0.0",
            },
            json=payload,  # <—
        )
        return r.status_code in (201, 202), r

# Exchange refresh_token for new access token
def exchange_refresh_for_token(refresh_token: str) -> dict:
    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": settings.linkedin_client_id,
        "client_secret": settings.linkedin_client_secret,
    }
    with httpx.Client(timeout=httpx.Timeout(30, connect=5)) as c:
        r = c.post(
            TOKEN_URL,
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        r.raise_for_status()
        return r.json()


# Helper: log request id if present in LinkedIn response
def log_request_id(resp):
    req_id = resp.headers.get("x-restli-request-id")
    if req_id:
        print(f"[LinkedIn] request id: {req_id}", flush=True)

# Helper: retry logic for LinkedIn API
def linkedin_request_with_retry(method, url, **kwargs):
    max_attempts = 4
    backoff = 2
    for attempt in range(1, max_attempts + 1):
        try:
            with httpx.Client(timeout=httpx.Timeout(30, connect=5)) as c:
                resp = c.request(method, url, **kwargs)
            log_request_id(resp)
            if resp.status_code in (429, 500, 502, 503, 504):
                print(f"[LinkedIn] {url} attempt {attempt} got {resp.status_code}, retrying...", flush=True)
                if attempt < max_attempts:
                    time.sleep(backoff * attempt)
                    continue
            return resp
        except httpx.RequestError as e:
            print(f"[LinkedIn] Request error: {e}", flush=True)
            if attempt < max_attempts:
                time.sleep(backoff * attempt)
                continue
            raise
    raise Exception(f"LinkedIn API failed after {max_attempts} attempts")

from typing import Optional


def auth_url(state: str, scopes: Optional[str] = None) -> str:
    """Return the authorization url. If scopes is provided use that, otherwise use settings.linkedin_scopes."""
    params = {
        "response_type": "code",
        "client_id": settings.linkedin_client_id,
        "redirect_uri": settings.linkedin_redirect_uri,
        "scope": scopes or settings.linkedin_scopes,
        "state": state,
    }
    qs = urlencode(params, quote_via=quote, safe=":/")
    return f"{AUTH_URL}?{qs}"

def exchange_code_for_token(code: str) -> Dict[str, Any]:
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": settings.linkedin_redirect_uri,
        "client_id": settings.linkedin_client_id,
        "client_secret": settings.linkedin_client_secret,
    }
    # Harden: use retry logic and timeouts
    resp = linkedin_request_with_retry(
        "POST", TOKEN_URL,
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    resp.raise_for_status()
    data = resp.json()
    # Capture refresh_token if present
    refresh_token = data.get("refresh_token")
    if refresh_token:
        data["refresh_token"] = refresh_token
    return data

# New: exchange refresh_token for new access token
def exchange_refresh_for_token(refresh_token: str) -> Dict[str, Any]:
    payload = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": settings.linkedin_client_id,
        "client_secret": settings.linkedin_client_secret,
    }
    resp = linkedin_request_with_retry(
        "POST", TOKEN_URL,
        data=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    resp.raise_for_status()
    return resp.json()

def post_text(access_token: str, author_urn: str, text: str) -> Tuple[bool, Any]:
    text = _sanitize_for_linkedin(text)
    payload = {
        "author": author_urn,
        "lifecycleState": "PUBLISHED",
        "specificContent": {
            "com.linkedin.ugc.ShareContent": {
                "shareCommentary": {"text": text},
                "shareMediaCategory": "NONE",
            }
        },
        "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
    }

    # body = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    try:
        with httpx.Client(timeout=60) as c:
            r = c.post(
                UGC_URL,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "X-Restli-Protocol-Version": "2.0.0",
                },
                json=payload,  # <—
            )
            # Basic logs (kept)
            print("[post_text] status:", r.status_code, flush=True)
            print("[post_text] request json:", payload, flush=True)
            print("[post_text] response text:", r.text, flush=True)
            log_request_id(r)

            # Verbose: print request headers, response headers when enabled
            if VERBOSE_LINKEDIN_LOG:
                try:
                    verbose_out = {
                        "request_headers": {
                            "Authorization": f"Bearer {access_token}",
                            "Content-Type": "application/json",
                            "X-Restli-Protocol-Version": "2.0.0",
                        },
                        "request_json": payload,
                        "response_status": r.status_code,
                        "response_headers": dict(r.headers),
                        "response_text": r.text,
                    }
                    try:
                        with open('/tmp/linkedin_verbose.log', 'a') as f:
                            f.write("--- POST_TEXT VERBOSE ---\n")
                            f.write(str(verbose_out) + "\n")
                    except Exception:
                        pass
                except Exception:
                    pass
            # Additionally, when verbose enabled, print request headers/body and response headers to stdout
            if VERBOSE_LINKEDIN_LOG:
                try:
                    req = getattr(r, 'request', None)
                    if req is not None:
                        try:
                            req_body = req.content.decode('utf-8') if isinstance(req.content, (bytes, bytearray)) else str(req.content)
                        except Exception:
                            req_body = str(req.content)
                        print('[post_text][VERBOSE] Outgoing request headers:', dict(req.headers), flush=True)
                        print('[post_text][VERBOSE] Outgoing request body:', req_body, flush=True)
                    print('[post_text][VERBOSE] Response headers:', dict(r.headers), flush=True)
                except Exception as e:
                    print('[post_text][VERBOSE] error printing verbose info:', e, flush=True)
            if r.status_code in (201, 202):
                return True, r
            # Bubble up error details for 4xx/5xx
            error_info = {
                "status": r.status_code,
                "body": r.text
            }
            try:
                err_json = r.json()
                error_info["serviceErrorCode"] = err_json.get("serviceErrorCode")
                error_info["message"] = err_json.get("message")
            except Exception:
                pass
            return False, error_info
    except Exception as e:
        print("[post_text] error:", e, flush=True)
        return False, {"exception": str(e)}
# --- helpers for OpenID id_token parsing ---
import base64, json

def _b64url_decode(part: str) -> bytes:
    pad = "=" * (-len(part) % 4)
    return base64.urlsafe_b64decode(part + pad)

def extract_sub_from_id_token(id_token: str) -> str:
    try:
        parts = id_token.split(".")
        if len(parts) < 2:
            return ""
        payload = parts[1]
        claims = json.loads(_b64url_decode(payload).decode("utf-8"))
        return claims.get("sub", "")
    except Exception:
        return ""

