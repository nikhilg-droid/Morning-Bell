"""Settings for Morning Bell, read from environment variables (or a .env file)."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load_dotenv() -> None:
    env_file = ROOT / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv()

# --- Sarvam AI ---
SARVAM_API_KEY = os.environ.get("SARVAM_API_KEY", "")
SARVAM_BASE_URL = os.environ.get("SARVAM_BASE_URL", "https://api.sarvam.ai/v1")
SARVAM_MODEL = os.environ.get("SARVAM_MODEL", "sarvam-105b")

# --- Gmail / Calendar ---
# Optional extra Gmail search to narrow which emails go in the report, e.g. "-category:promotions".
# Empty = every email received in the last LOOKBACK_HOURS (spam, trash, sent and chats are excluded).
MAIL_QUERY = os.environ.get("MAIL_QUERY", "")
MAX_EMAILS = int(os.environ.get("MAX_EMAILS", "60"))
LOOKBACK_HOURS = int(os.environ.get("LOOKBACK_HOURS", "24"))
TIMEZONE = os.environ.get("TIMEZONE", "Asia/Kolkata")
CALENDAR_ID = os.environ.get("CALENDAR_ID", "primary")
PROCESSED_LABEL = os.environ.get("PROCESSED_LABEL", "MorningBell/Processed")
# Where the morning digest is sent. Empty = your own Gmail address.
DIGEST_TO = os.environ.get("DIGEST_TO", "")

CREDENTIALS_FILE = ROOT / "credentials.json"   # OAuth client downloaded from Google Cloud
TOKEN_FILE = ROOT / "token.json"               # created after first login

MAX_AGENT_STEPS = int(os.environ.get("MAX_AGENT_STEPS", "25"))
# Sarvam's default reply limit is only 2048 tokens - too small for a full report.
MAX_OUTPUT_TOKENS = int(os.environ.get("MAX_OUTPUT_TOKENS", "16000"))
