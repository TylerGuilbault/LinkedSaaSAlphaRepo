# app/auth/oidc.py
import time
import httpx
from jose import jwt, exceptions as jose_errors

# Known LinkedIn issuer variants seen in the wild
LINKEDIN_ISS_ALLOWLIST = {
    "https://www.linkedin.com",
    "https://www.linkedin.com/",
    "https://www.linkedin.com/oauth",
    "https://www.linkedin.com/oauth/",
}

LINKEDIN_JWKS = "https://www.linkedin.com/oauth/openid/jwks"
ALGS = ["RS256"]

_jwks_cache = None
_jwks_cached_at = 0

async def _get_jwks():
    global _jwks_cache, _jwks_cached_at
    if (not _jwks_cache) or (time.time() - _jwks_cached_at > 3600):
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(LINKEDIN_JWKS)
            r.raise_for_status()
            _jwks_cache = r.json()
            _jwks_cached_at = time.time()
    return _jwks_cache

def _select_jwk_for_token(id_token: str, jwks: dict) -> dict:
    header = jwt.get_unverified_header(id_token)
    kid = header.get("kid")
    if not kid:
        raise ValueError("ID token header missing 'kid'")
    for k in jwks.get("keys", []):
        if k.get("kid") == kid:
            return k
    raise ValueError(f"No matching JWK for kid={kid}")

def _iss_unverified(id_token: str) -> str | None:
    try:
        return jwt.get_unverified_claims(id_token).get("iss")
    except Exception:
        return None

async def decode_linkedin_id_token(
    id_token: str,
    audience: str | None = None,
    allow_expired: bool = False,
    allow_issuer_any: bool = False,
) -> dict:
    """
    Verifies signature with LinkedIn JWKS. If allow_expired=True, ignores 'exp'.
    If allow_issuer_any=True, skips issuer check (still signature-verified).
    Otherwise, requires iss to be one of LINKEDIN_ISS_ALLOWLIST.
    """
    jwks = await _get_jwks()
    jwk = _select_jwk_for_token(id_token, jwks)

    opts = {
        "verify_aud": audience is not None,
        "verify_exp": not allow_expired,
        "verify_iss": False,  # we'll enforce issuer ourselves (or skip)
    }

    try:
        claims = jwt.decode(
            id_token,
            jwk,
            algorithms=ALGS,
            audience=audience if audience else None,
            options=opts,
        )
    except jose_errors.ExpiredSignatureError:
        if allow_expired:
            # retry ignoring exp (signature still verified)
            claims = jwt.decode(
                id_token,
                jwk,
                algorithms=ALGS,
                audience=audience if audience else None,
                options={"verify_aud": audience is not None, "verify_exp": False, "verify_iss": False},
            )
        else:
            raise

    # Enforce issuer unless explicitly disabled
    if not allow_issuer_any:
        iss = claims.get("iss")
        if iss not in LINKEDIN_ISS_ALLOWLIST:
            # Provide a helpful message for debugging
            raise jose_errors.JWTClaimsError(f"Invalid issuer: {iss}")

    return claims
