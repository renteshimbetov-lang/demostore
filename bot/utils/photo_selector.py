import io
import ssl
import asyncio
import logging
import urllib.request
from typing import List, Optional
from PIL import Image, ImageOps, ImageStat
from bot.utils.helpers import is_phone_product, is_laptop_product

logger = logging.getLogger("PhotoSelector")


def _image_features(img_bytes: bytes) -> Optional[dict]:
    """
    Rasmning 2 ta asosiy belgisini hisoblash:
    - sym:  gorizontal simmetriya farqi (kichik = to'g'ridan olingan)
    - dark: yuqori-markaz (ekran) zonasidagi to'q piksellar ulushi.
            Ochiq noutbukning ekrani to'q/rangli bo'ladi (0.5+),
            yopiq qopqoq (orqa tarafi) esa och kulrang alyuminiy (~0.0).
    """
    try:
        im = Image.open(io.BytesIO(img_bytes)).convert("RGB").resize((120, 160))
        g = im.convert("L")
        gm = ImageOps.mirror(g)
        a = g.tobytes()
        b = gm.tobytes()
        sym = sum(abs(x - y) for x, y in zip(a, b)) / len(a)

        screen = g.crop((20, 15, 100, 80)).tobytes()
        dark = sum(1 for p in screen if p < 90) / len(screen)
        return {"sym": sym, "dark": dark}
    except Exception as e:
        logger.debug(f"Rasm xususiyatlarini hisoblashda xatolik: {e}")
        return None


def pick_best_index(name: str, description: str, images: List[Optional[bytes]]) -> int:
    """
    Asosiy rasm indeksini tanlash.

    - Smartfonlar: har doim 1-rasm (orqa tarafi — kamera va rang ko'rinadi).
    - Noutbuklar: TO'G'RIDAN olingan OCHIQ holat (ekran + klaviatura) tanlanadi.
        1) Ekran zonasi to'q bo'lgan (dark >= 0.4) rasmlar — ya'ni ochiq noutbuk;
           yopiq qopqoq (orqa taraf) bu shartdan o'tmaydi.
        2) Ular orasidan eng simmetrik (to'g'ridan olingan) rasm.
        Agar hech biri mos kelmasa — 1-rasm.
    """
    if len(images) <= 1:
        return 0
    if is_phone_product(name, description) or not is_laptop_product(name, description):
        return 0

    candidates = []
    for idx, b in enumerate(images[:5]):
        if not b:
            continue
        f = _image_features(b)
        if f and f["dark"] >= 0.4:
            candidates.append((f["sym"], idx))

    if not candidates:
        return 0
    candidates.sort()
    return candidates[0][1]


def fetch_url_bytes(url: str, timeout: float = 5.0) -> Optional[bytes]:
    try:
        from bot.utils.ssl_context import get_ssl_context
        ctx = get_ssl_context()
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            return resp.read()
    except Exception as e:
        logger.debug(f"Rasm yuklab olishda xatolik ({url[:40]}): {e}")
        return None


async def load_image_bytes(ref: str, bot=None) -> Optional[bytes]:
    """ref — http(s) URL, '/api/photo/<file_id>' yoki to'g'ridan file_id"""
    try:
        if ref.startswith("http"):
            return await asyncio.to_thread(fetch_url_bytes, ref)
        file_id = ref.split("/")[-1] if ref.startswith("/api/photo/") else ref
        if bot is not None and file_id:
            buf = await bot.download(file_id)
            return buf.read() if buf else None
    except Exception as e:
        logger.debug(f"Rasm baytlarini olishda xatolik: {e}")
    return None


async def select_best_index_async(name: str, description: str, refs: List[str], bot=None) -> int:
    if len(refs) <= 1 or is_phone_product(name, description) or not is_laptop_product(name, description):
        return 0
    images = await asyncio.gather(*(load_image_bytes(r, bot) for r in refs[:5]))
    return await asyncio.to_thread(pick_best_index, name, description, list(images))
