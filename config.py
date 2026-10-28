"""Uygulama ayarlari. .env dosyasindan okunur."""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env")


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


# --- Telegram ---
BOT_TOKEN: str = os.getenv("BOT_TOKEN", "").strip()
ALLOWED_USER_IDS = {
    int(x.strip())
    for x in os.getenv("ALLOWED_USER_IDS", "").split(",")
    if x.strip().isdigit()
}

# --- Veritabani ---
DB_PATH: str = os.getenv("DB_PATH") or str(BASE_DIR / "finance.db")

# --- Piyasa / veri ---
BASE_CURRENCY: str = os.getenv("BASE_CURRENCY", "TRY").upper()
HISTORY_PERIOD: str = os.getenv("HISTORY_PERIOD", "6mo")
QUOTE_PERIOD: str = os.getenv("QUOTE_PERIOD", "5d")
CACHE_TTL: int = _env_int("CACHE_TTL", 180)  # saniye

# Bulut (Render) icin: Neon/Supabase gibi PostgreSQL baglanti adresi.
# Bos birakilirsa yerel SQLite kullanilir (finance.db).
DATABASE_URL: str = os.getenv("DATABASE_URL", "").strip()

# --- Zamanlanmis gorevler ---
SCAN_MINUTES: int = _env_int("SCAN_MINUTES", 60)
ALERT_CHECK_SECONDS: int = _env_int("ALERT_CHECK_SECONDS", 180)

# --- Ani hareket alarmi (yuzde) ---
BIG_MOVE_PCT: float = float(os.getenv("BIG_MOVE_PCT", "5.0"))
