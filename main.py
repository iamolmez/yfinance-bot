"""YFinance Bot - Giris Noktasi.

Calistirmak icin:
1. .env dosyasi olusturun (bkz. .env.example) ve BOT_TOKEN'i doldurun
2. python main.py

Bulut (Render/Railway) icin:
- Platform PORT ortam degiskeni atarsa kucuk bir HTTP saglik sunucusu acilir
- Kalici disk icin DB_PATH'yi /data/finance.db yapin ve volume baglayin
"""
import logging
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from telegram import Update
from telegram.ext import Application, Defaults

import config
from bot.handlers import register_handlers
from bot.jobs import setup_jobs
from database import init_db

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def start_health_server() -> None:
    """Bulut platformlarinin saglik kontrolu icin mini HTTP sunucusu.

    Render ve Railway PORT ortam degiskenini set eder; app o portu dinlemek
    zorundadir. Lokal kullanimda PORT yoksa baslatilmaz.
    """
    raw_port = os.getenv("PORT")
    if not raw_port:
        return
    try:
        port = int(raw_port)
    except ValueError:
        return

    class HealthHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"OK")

        def log_message(self, *args):
            pass  # istek loglari gurultu yapar, bastirilir

    srv = HTTPServer(("0.0.0.0", port), HealthHandler)
    threading.Thread(target=srv.serve_forever, daemon=True, name="health").start()
    logger.info("Saglik sunucusu PORT %s uzerinde basladi", port)


def main() -> None:
    if not config.BOT_TOKEN:
        print("=" * 60)
        print("BOT_TOKEN bos! Kurulum:")
        print("1. Telegram'da @BotFather ile bot olustur, token al")
        print("2. .env.example dosyasini .env olarak kopyala")
        print("3. .env icindeki BOT_TOKEN ve ALLOWED_USER_IDS doldur")
        print("4. Tekrar python main.py calistir")
        print("=" * 60)
        return

    init_db()
    logger.info("Veritabani hazir: %s", config.DB_PATH)

    start_health_server()

    defaults = Defaults(parse_mode="HTML")
    app = (
        Application.builder()
        .token(config.BOT_TOKEN)
        .defaults(defaults)
        .build()
    )

    register_handlers(app)
    setup_jobs(app)

    logger.info("Bot baslatiliyor...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
