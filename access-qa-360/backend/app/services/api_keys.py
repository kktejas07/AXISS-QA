"""Creating and checking API keys."""
import hashlib
import secrets

API_KEY_PREFIX = "wf_"


def hash_api_key(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def new_api_key() -> tuple[str, str, str]:
    """Returns (the key to show once, its recognisable prefix, the hash to store)."""
    token = API_KEY_PREFIX + secrets.token_urlsafe(32)
    return token, token[:10], hash_api_key(token)
