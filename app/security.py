from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader
from ipaddress import ip_address
from urllib.parse import urlparse

from app.config import API_KEY_NAME, VALID_API_KEYS, BLOCKED_NETWORKS

api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)


async def verify_api_key(api_key: str = Security(api_key_header)):
    """Dependency function to check API Key in HTTP Headers."""
    if not api_key or api_key not in VALID_API_KEYS:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API Key tidak valid atau tidak ditemukan dalam header 'X-API-Key'.",
        )
    return api_key


def is_ssrf_safe(url: str) -> bool:
    """Return True if URL is allowed (http/https only, no localhost/private IP)."""
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False
        hostname = parsed.hostname
        if not hostname:
            return False
        try:
            ip = ip_address(hostname)
        except ValueError:
            # Hostname (not raw IP) — allow
            return True
        for network in BLOCKED_NETWORKS:
            if ip in network:
                return False
        return True
    except Exception:
        return False