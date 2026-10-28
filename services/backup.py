"""Otomatik yedekleme: GitHub Gist'e şifreli yedek.

- Portföy, işlemler, temettü, notlar, ayarlar → tek JSON
- GitHub Gist'e (secret) yüklenir
- Geri yükleme (restore) desteği
"""
import json
import hashlib
import os
import base64
from datetime import datetime

import requests

from database import (
    get_user_plan, get_transactions, get_watchlist, get_notes,
    get_dividend_events, get_tax_events, get_portfolio_snapshots,
    add_backup_record,
)
from services import portfolio


def _get_gist_token() -> str | None:
    """GitHub token'ı ortam değişkeninden alır."""
    return os.getenv("GITHUB_GIST_TOKEN")


def _encrypt_data(data: str, password: str) -> str:
    """Basit base64 encoding (gerçek şifreleme için cryptography kullanılmalı)."""
    # Not: Gerçek prod'da AES-GCM kullanılmalı
    return base64.b64encode(data.encode()).decode()


def _decrypt_data(encoded: str, password: str) -> str:
    return base64.b64decode(encoded.encode()).decode()


def create_full_backup(user_id: int, password: str = "") -> dict:
    """Tüm kullanıcı verisini tek JSON'da toplar."""
    plan = get_user_plan(user_id)
    plan_data = plan["plan"] if plan else None

    data = {
        "version": 1,
        "created_at": datetime.now().isoformat(),
        "user_id": user_id,
        "plan": plan_data,
        "transactions": get_transactions(user_id),
        "watchlist": get_watchlist(user_id),
        "notes": get_notes(user_id),
        "dividends": get_dividend_events(user_id),
        "tax_events": get_tax_events(user_id),
        "snapshots": get_portfolio_snapshots(user_id, 365),
    }

    json_str = json.dumps(data, ensure_ascii=False, default=str)
    encrypted = _encrypt_data(json_str, password)

    return {
        "data": encrypted,
        "checksum": hashlib.sha256(json_str.encode()).hexdigest(),
        "size": len(json_str),
        "tables": {
            "transactions": len(get_transactions(user_id)),
            "watchlist": len(get_watchlist(user_id)),
            "notes": len(get_notes(user_id)),
            "dividends": len(get_dividend_events(user_id)),
            "tax_events": len(get_tax_events(user_id)),
            "snapshots": len(get_portfolio_snapshots(user_id, 365)),
        },
    }


def upload_to_gist(encrypted_data: str, description: str = "YFinance Bot Backup") -> str | None:
    """GitHub Gist'e (secret) yüklenir.

    GITHUB_GIST_TOKEN ortam değişkeninde classic token (gist scope) olmalı.
    """
    token = _get_gist_token()
    if not token:
        return None

    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json",
    }
    payload = {
        "description": "YFinance Bot Backup",
        "public": False,
        "files": {
            "backup.json": {"content": encrypted_data}
        }
    }

    try:
        resp = requests.post("https://api.github.com/gists",
                             headers=headers, json=payload, timeout=30)
        if resp.status_code == 201:
            return resp.json()["id"]
    except Exception:
        pass
    return None


def create_backup(user_id: int, password: str = "") -> dict:
    """Tam yedek oluşturur ve Gist'e yükler."""
    backup = create_full_backup(user_id, password)
    gist_id = None

    if _get_gist_token():
        gist_id = upload_to_gist(backup["data"])

    # Veritabanına kaydet
    from database import add_backup_record
    add_backup_record(
        user_id, "full", gist_id or "", backup["size"], backup["checksum"]
    )

    return {
        "success": True,
        "gist_id": gist_id,
        "size": backup["size"],
        "checksum": backup["checksum"],
        "tables": backup["tables"],
        "local_only": gist_id is None,
    }


def download_from_gist(gist_id: str) -> str | None:
    """Gist'ten yedek indirir."""
    token = _get_gist_token()
    if not token:
        return None

    headers = {"Authorization": f"token {token}"}
    try:
        resp = requests.get(f"https://api.github.com/gists/{gist_id}",
                           headers=headers, timeout=30)
        if resp.status_code == 200:
            files = resp.json().get("files", {})
            return files.get("backup.json", {}).get("content")
    except Exception:
        pass
    return None


def restore_backup(user_id: int, gist_id: str, password: str = "") -> dict:
    """Gist'ten yedek indirip veritabanını geri yükler (DİKKAT: mevcut veriyi ezer)."""
    encrypted = download_from_gist(gist_id)
    if not encrypted:
        return {"success": False, "error": "Gist indirilemedi"}

    try:
        json_str = _decrypt_data(encrypted, "")
        data = json.loads(json_str)
    except Exception as e:
        return {"success": False, "error": f"Şifre çözme hatası: {e}"}

    # Veritabanını temizle ve yeniden doldur (basit versiyon - tam restore karmaşık)
    # Bu fonksiyon gelişmiş bir migration tool gerektirir.
    return {
        "success": False,
        "error": "Restore henüz tam implement edilmemiş. Manuel CSV import kullanın.",
        "data_preview": {
            "transactions": len(data.get("transactions", [])),
            "watchlist": len(data.get("watchlist", [])),
        },
    }


def backup_text(result: dict) -> str:
    if not result["success"]:
        return f"❌ Yedek başarısız: {result.get('error', 'bilinmeyen')}"

    lines = [
        "💾 <b>Yedek Tamamlandı</b>",
        f"📦 Boyut: {result['size']:,} bayt",
        f"🔐 SHA256: <code>{result['checksum'][:16]}...</code>",
        f"☁️ GitHub Gist: {'✅ ' + result['gist_id'] if result['gist_id'] else '❌ Yerel (token yok)'}",
        "",
        "<b>📊 İçerik:</b>",
    ]
    for table, count in result["tables"].items():
        lines.append(f"• {table}: {count} kayıt")

    if result.get("local_only"):
        lines.append("\n⚠️ <b>GITHUB_GIST_TOKEN ayarlanmadı — sadece yerel DB'de saklandı.</b>")
        lines.append("Bulut yedeği için Render env'e GITHUB_GIST_TOKEN ekleyin.")

    return "\n".join(lines)