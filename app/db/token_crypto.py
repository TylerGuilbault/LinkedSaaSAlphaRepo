from cryptography.fernet import Fernet
from app.config import settings

def _fernet() -> Fernet:
    if not settings.fernet_key:
        raise RuntimeError("FERNET_KEY is missing in .env")
    return Fernet(settings.fernet_key.encode())

def encrypt_token(plain: str) -> str:
    return _fernet().encrypt(plain.encode()).decode()

def decrypt_token(cipher: str) -> str:
    from cryptography.fernet import InvalidToken
    try:
        return _fernet().decrypt(cipher.encode()).decode()
    except (TypeError, InvalidToken) as e:
        # Log and propagate for caller to handle (return 400)
        print(f"[token_crypto] Decrypt error: {e}", flush=True)
        raise
