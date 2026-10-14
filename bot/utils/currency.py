import os
import time
import json
import logging
import asyncio
from typing import Optional, Dict, Any
from pathlib import Path
import aiohttp

logger = logging.getLogger("CurrencyRate")

# Markaziy Bank API standart manzili va kesh sozlamalari
DEFAULT_CBU_API_URL = "https://cbu.uz/oz/arkhiv-kursov-valyut/json/USD/"
# Serverga har soniyada ortiqcha so'rov yubormaslik uchun 10 daqiqalik yengil kesh (600 soniya)
CACHE_TTL_SECONDS = 600

# Diskdagi oxirgi muvaffaqiyatli saqlangan kurs fayli (Fail-safe zaxira)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_CACHE_FILE = _PROJECT_ROOT / ".cbu_rate_cache.json"

# Xotiradagi tezkor kesh
_cached_rate: Optional[float] = None
_last_updated_time: float = 0.0
_last_successful_rate: Optional[float] = None
_cache_lock = asyncio.Lock()


def get_cbu_api_url() -> str:
    """Markaziy Bank API URL manzilini CBU_API_URL muhit o'zgaruvchisidan yoki standartdan olish"""
    url = os.getenv("CBU_API_URL", "").strip()
    if url:
        return url
    try:
        from bot.config import config
        cfg_url = getattr(config, "cbu_api_url", None)
        if cfg_url:
            return cfg_url
    except Exception:
        pass
    return DEFAULT_CBU_API_URL


def _load_disk_cache() -> Optional[float]:
    """Diskdagi oxirgi muvaffaqiyatli saqlangan kursni o'qish"""
    try:
        if _CACHE_FILE.exists():
            with open(_CACHE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                rate = float(data.get("rate", 0))
                if rate > 0:
                    return rate
    except Exception as e:
        logger.debug(f"Diskdagi keshni o'qishda xatolik: {e}")
    return None


def _save_disk_cache(rate: float):
    """Muvaffaqiyatli olingan kursni diskka zaxira sifatida saqlash"""
    try:
        data = {
            "rate": rate,
            "updated_at": time.time()
        }
        with open(_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.debug(f"Diskka kesh yozishda ogohlantirish: {e}")


def get_fallback_rate() -> float:
    """
    Zaxira (fallback) kursni olish:
    1. Oxirgi muvaffaqiyatli olingan kurs
    2. Diskdagi kesh
    3. .env dagi USD_RATE yoki 12850.0
    """
    global _last_successful_rate
    if _last_successful_rate and _last_successful_rate > 0:
        return _last_successful_rate

    disk_rate = _load_disk_cache()
    if disk_rate and disk_rate > 0:
        _last_successful_rate = disk_rate
        return disk_rate

    try:
        from bot.config import config
        return float(config.usd_rate)
    except Exception:
        return 12850.0


def get_current_usd_rate_sync() -> float:
    """Sinxron kontekstlar (moderatsiya, matn tayyorlash) uchun joriy keshdagi kurs"""
    global _cached_rate
    if _cached_rate and _cached_rate > 0:
        return _cached_rate
    return get_fallback_rate()


async def get_cbu_usd_rate(force_refresh: bool = False) -> float:
    """
    Markaziy bank (CBU) orqali joriy USD kursini olish (float formatda):
    - Kesh muddati 10 daqiqa (CACHE_TTL_SECONDS = 600).
    - Agar kesh 10 daqiqadan oshmagan bo'lsa, o'shandan foydalaniladi.
    - 10 daqiqa o'tgach, keyingi hisob-kitob paytida avtomatik API'ga yangi so'rov yuboriladi.
    - Agar API ishlamay qolsa, oxirgi muvaffaqiyatli saqlangan kursdan foydalaniladi (fallback).
    """
    global _cached_rate, _last_updated_time, _last_successful_rate

    now = time.time()
    # 1. 10 daqiqalik yengil kesh tekshiruvi
    if not force_refresh and _cached_rate is not None and (now - _last_updated_time) < CACHE_TTL_SECONDS:
        return _cached_rate

    async with _cache_lock:
        # Qulf ichida yana bir bor keshni tekshiramiz (Double-checked locking)
        now = time.time()
        if not force_refresh and _cached_rate is not None and (now - _last_updated_time) < CACHE_TTL_SECONDS:
            return _cached_rate

        api_url = get_cbu_api_url()
        connector = aiohttp.TCPConnector(ssl=False)
        timeout = aiohttp.ClientTimeout(total=8)
        headers = {"User-Agent": "Mozilla/5.0 (compatible; DemoStoreBot/1.0)"}

        try:
            async with aiohttp.ClientSession(connector=connector, timeout=timeout, headers=headers) as session:
                async with session.get(api_url) as response:
                    if response.status == 200:
                        try:
                            data = await response.json(content_type=None)
                        except Exception:
                            text = await response.text()
                            data = json.loads(text)

                        extracted_rate: Optional[float] = None

                        if isinstance(data, list):
                            for item in data:
                                if item.get("Ccy") == "USD" and "Rate" in item:
                                    extracted_rate = float(item["Rate"])
                                    break
                            if extracted_rate is None and len(data) > 0 and "Rate" in data[0]:
                                extracted_rate = float(data[0]["Rate"])
                        elif isinstance(data, dict):
                            if "Rate" in data:
                                extracted_rate = float(data["Rate"])
                            elif "rate" in data:
                                extracted_rate = float(data["rate"])

                        if extracted_rate and extracted_rate > 0:
                            _cached_rate = extracted_rate
                            _last_successful_rate = extracted_rate
                            _last_updated_time = now
                            _save_disk_cache(extracted_rate)
                            logger.info(f"Markaziy Bankdan (CBU) jonli USD kursi yangilandi: 1$ = {_cached_rate:,.2f} so'm")
                            return _cached_rate
                        else:
                            logger.warning(f"CBU ({api_url}) javobidan USD Rate maydoni topilmadi.")
                    else:
                        logger.warning(f"CBU serveri javob bermadi: Status {response.status}")
        except Exception as e:
            logger.warning(f"CBU API ({api_url}) ga ulanishda xatolik: {e}. Zaxira kursdan foydalaniladi.")

        # Xatolik holatida oxirgi muvaffaqiyatli saqlangan kursdan foydalaniladi (fallback)
        fallback = get_fallback_rate()
        if _cached_rate is None:
            _cached_rate = fallback
            _last_updated_time = now
        logger.info(f"Zaxira / oxirgi muvaffaqiyatli USD kursi ishlatilmoqda: 1$ = {fallback} so'm")
        return fallback


def convert_usd_to_uzs(usd_price: float, rate: Optional[float] = None) -> int:
    """Dollar narxini berilgan yoki joriy kurs bo'yicha so'mga hisoblash"""
    if not usd_price or usd_price <= 0:
        return 0
    if not rate or rate <= 0:
        rate = get_current_usd_rate_sync()
    return int(round(usd_price * rate))


def format_uzs_currency(amount: int) -> str:
    """So'm narxini chiroyli formatda chiqarish: 12850000 -> '12 850 000 soʻm'"""
    if not amount:
        return "0 soʻm"
    formatted = f"{amount:,}".replace(",", " ")
    return f"{formatted} soʻm"


def format_rate_compact(rate: float) -> str:
    """Jonli kursni sarlavha uchun ixcham ko'rinishda chiqarish: '💵 1$ = 12 850 soʻm'"""
    rate_int = int(round(rate))
    formatted = f"{rate_int:,}".replace(",", " ")
    return f"💵 1$ = {formatted} soʻm"
