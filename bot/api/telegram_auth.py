import hmac
import hashlib
import json
import logging
import os
import time
from typing import Any, Dict, Optional
from urllib.parse import parse_qsl, urlencode
from aiohttp import web
from bot.config import config

logger = logging.getLogger("TelegramAuth")


def validate_telegram_init_data(
    init_data: str,
    max_age_seconds: int = 86400,
    bot_token: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Telegram WebApp initData ni HMAC-SHA256 orqali tekshiradi.
    Muvaffaqiyatli bo'lsa user dict qaytaradi, aks holda None.
    
    Xavfsizlik:
    - Telegram imzosini tekshirish (HMAC-SHA256)
    - Replay attack dan himoya (auth_date tekshiruvi)
    - Vaqt manipulyatsiyasidan himoya
    """
    token = bot_token or config.bot_token
    if not init_data or not token:
        return None

    try:
        parsed = dict(parse_qsl(init_data, keep_blank_values=True))
        received_hash = parsed.pop("hash", None)
        if not received_hash:
            return None

        # Ma'lumotlarni alifbo tartibida saralab data_check_string hosil qilish
        data_check_arr = [f"{k}={v}" for k, v in sorted(parsed.items())]
        data_check_string = "\n".join(data_check_arr)

        # Telegram spetsifikatsiyasi bo'yicha maxfiy kalit
        secret_key = hmac.new(
            b"WebAppData",
            token.encode("utf-8"),
            hashlib.sha256
        ).digest()

        calculated_hash = hmac.new(
            secret_key,
            data_check_string.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(calculated_hash.lower(), received_hash.lower()):
            logger.warning("Telegram initData imzosi mos kelmadi.")
            return None

        # Replay attackdan himoya (sukut bo'yicha 24 soat)
        auth_date = int(parsed.get("auth_date", 0))
        now = time.time()
        if max_age_seconds > 0:
            if now - auth_date > max_age_seconds or auth_date > (now + 300):
                logger.warning(f"Telegram initData muddati o'tgan yoki vaqt noto'g'ri: auth_date={auth_date}, now={now}")
                return None

        user_raw = parsed.get("user")
        if user_raw:
            try:
                user = json.loads(user_raw)
                return user if isinstance(user, dict) else {}
            except Exception:
                return {}

        # Agar user parametri bo'lmasa lekin imzo to'g'ri bo'lsa (masalan, receiver bilan)
        return {
            "id": int(parsed.get("receiver_id", 0)) if parsed.get("receiver_id", "").isdigit() else 0,
            "query_id": parsed.get("query_id", "")
        }
    except Exception as e:
        logger.error(f"initData tekshirishda xatolik: {e}")
        return None


def extract_and_validate_telegram_user(
    request: web.Request,
    max_age_seconds: int = 86400,
    bot_token: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    aiohttp so'rovidan Telegram initData ni ajratib olib tekshiradi.
    Header ("X-Telegram-Init-Data") yoki Query param ("initData") qo'llab-quvvatlanadi.
    """
    # 1. Sinov yoki maxsus dev muhiti bayrogi
    bypass_env = os.getenv("BYPASS_TELEGRAM_AUTH", "").strip().lower()
    if bypass_env in ("1", "true", "yes"):
        return {"id": 999999999, "first_name": "DevUser", "is_dev": True}

    init_data = (
        request.headers.get("X-Telegram-Init-Data")
        or request.query.get("initData")
        or request.query.get("init_data")
    )

    if not init_data:
        # Authorization header: "tma <initData>" varianti
        auth_header = request.headers.get("Authorization", "")
        if auth_header.lower().startswith("tma "):
            init_data = auth_header[4:].strip()

    if not init_data:
        return None

    return validate_telegram_init_data(init_data, max_age_seconds=max_age_seconds, bot_token=bot_token)


def generate_telegram_init_data(
    user: Dict[str, Any],
    bot_token: str,
    auth_date: Optional[int] = None,
    query_id: Optional[str] = None
) -> str:
    """
    Testlar va simulyatsiya uchun to'g'ri Telegram initData generatsiya qilish yordamchisi.
    """
    data = {
        "auth_date": str(int(auth_date or time.time())),
        "user": json.dumps(user, separators=(",", ":"))
    }
    if query_id:
        data["query_id"] = query_id

    data_check_arr = [f"{k}={v}" for k, v in sorted(data.items())]
    data_check_string = "\n".join(data_check_arr)

    secret_key = hmac.new(
        b"WebAppData",
        bot_token.encode("utf-8"),
        hashlib.sha256
    ).digest()

    calculated_hash = hmac.new(
        secret_key,
        data_check_string.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()

    data["hash"] = calculated_hash
    return urlencode(data)
