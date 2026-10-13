import time
import logging
import asyncio
from typing import Optional, Dict, Any
import aiohttp

logger = logging.getLogger("CurrencyRate")

CBU_USD_URL = "https://cbu.uz/uz/arkhiv-kursov-valyut/json/all/USD/"
# Kesh amal qilish muddati (2 soat = 7200 soniya)
CACHE_TTL_SECONDS = 7200

# Xotiradagi kesh
_cached_rate: Optional[float] = None
_last_updated_time: float = 0.0
_cache_lock = asyncio.Lock()

def get_fallback_rate() -> float:
    """Zaxira (fallback) kursni .env yoki standart qiymatdan olish"""
    try:
        from bot.config import config
        return float(config.usd_rate)
    except Exception:
        return 12850.0

async def get_cbu_usd_rate(force_refresh: bool = False) -> float:
    """
    Markaziy bank (CBU) orqali joriy USD kursini olish (float formatda):
    - Har bir kirishda serverni ortiqcha yuklamaslik uchun 2 soat keshlanadi.
    - Tarmoq uzilsa yoki xatolik yuz bersa, oxirgi muvaffaqiyatli kesh yoki .env dagi USD_RATE ishlatiladi.
    """
    global _cached_rate, _last_updated_time

    now = time.time()
    if not force_refresh and _cached_rate is not None and (now - _last_updated_time) < CACHE_TTL_SECONDS:
        return _cached_rate

    async with _cache_lock:
        # Qulf ichida yana bir bor keshni tekshiramiz (Double-checked locking)
        now = time.time()
        if not force_refresh and _cached_rate is not None and (now - _last_updated_time) < CACHE_TTL_SECONDS:
            return _cached_rate

        connector = aiohttp.TCPConnector(ssl=False)
        timeout = aiohttp.ClientTimeout(total=8)
        headers = {"User-Agent": "Mozilla/5.0 (compatible; DemoStoreBot/1.0)"}

        try:
            async with aiohttp.ClientSession(connector=connector, timeout=timeout, headers=headers) as session:
                async with session.get(CBU_USD_URL) as response:
                    if response.status == 200:
                        data = await response.json()
                        extracted_rate: Optional[float] = None

                        if isinstance(data, list):
                            for item in data:
                                if item.get("Ccy") == "USD":
                                    extracted_rate = float(item["Rate"])
                                    break
                            if extracted_rate is None and len(data) > 0 and "Rate" in data[0]:
                                extracted_rate = float(data[0]["Rate"])
                        elif isinstance(data, dict) and "Rate" in data:
                            extracted_rate = float(data["Rate"])

                        if extracted_rate and extracted_rate > 0:
                            _cached_rate = extracted_rate
                            _last_updated_time = now
                            logger.info(f"Markaziy Bankdan (CBU) jonli USD kursi yangilandi: 1$ = {_cached_rate:,.2f} so'm")
                            return _cached_rate
                        else:
                            logger.warning("CBU javobidan USD Rate maydoni topilmadi.")
                    else:
                        logger.warning(f"CBU serveri javob bermadi: Status {response.status}")
        except Exception as e:
            logger.warning(f"CBU API ga ulanishda xatolik: {e}. Zaxira kursdan foydalaniladi.")

        # Xatolik holatida zaxira kurs
        if _cached_rate is not None:
            return _cached_rate

        fallback = get_fallback_rate()
        _cached_rate = fallback
        _last_updated_time = now
        logger.info(f"Zaxira USD kursi o'rnatildi: 1$ = {fallback} so'm")
        return fallback

def convert_usd_to_uzs(usd_price: float, rate: float) -> int:
    """Dollar narxini berilgan kurs bo'yicha so'mga hisoblash"""
    if not usd_price or usd_price <= 0:
        return 0
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
