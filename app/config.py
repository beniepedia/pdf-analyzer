import os
from ipaddress import ip_network
from dotenv import load_dotenv

load_dotenv()

API_KEY_NAME = "X-API-Key"
VALID_API_KEYS = {
    key for key in [
        os.getenv("API_KEY_1"),
        os.getenv("API_KEY_2"),
    ] if key
}

MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", "15"))
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024

LIBREOFFICE_TIMEOUT = int(os.getenv("LIBREOFFICE_TIMEOUT", "120"))

ALLOWED_ORIGINS = [
    origin.strip() for origin in os.getenv("ALLOWED_ORIGINS", "").split(",") if origin.strip()
]

BLOCKED_NETWORKS = [
    ip_network("127.0.0.0/8"),    # IPv4 localhost
    ip_network("10.0.0.0/8"),     # Private class A
    ip_network("172.16.0.0/12"),  # Private class B
    ip_network("192.168.0.0/16"), # Private class C
    ip_network("::1/128"),        # IPv6 localhost
    ip_network("fc00::/7"),       # IPv6 unique local
]