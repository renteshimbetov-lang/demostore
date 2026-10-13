import io
import ssl
import logging
import urllib.request
from typing import List, Tuple, Optional
from PIL import Image, ImageOps
from bot.utils.helpers import is_phone_product, is_laptop_product

logger = logging.getLogger("PhotoSelector")

def calculate_symmetry_diff(img_bytes: bytes) -> float:
    """
    Rasmning gorizontal simmetriya farqini hisoblash.
    To'g'ridan olingan (Front view) ochiq noutbuklar yuqori simmetriyaga ega bo'ladi (past ball, odatda < 35).
    Burchakdan/yonboshdan olingan (Side view) noutbuklar asimmetrik bo'ladi (yuqori ball, odatda > 45).
    """
    try:
        im = Image.open(io.BytesIO(img_bytes)).convert("L").resize((100, 100))
        mirrored = ImageOps.mirror(im)
        # Pillow 10+ moslik
        try:
            d1 = list(im.get_flattened_data())
            d2 = list(mirrored.get_flattened_data())
        except AttributeError:
            d1 = list(im.getdata())
            d2 = list(mirrored.getdata())
        return sum(abs(p1 - p2) for p1, p2 in zip(d1, d2)) / 10000.0
    except Exception as e:
        logger.debug(f"Simmetriya hisoblashda xatolik: {e}")
        return 999.0

def fetch_image_bytes(url: str, timeout: float = 3.0) -> Optional[bytes]:
    """Rasm URL manzilidan kichik hajmini o'qish"""
    try:
        ctx = ssl._create_unverified_context()
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            return resp.read()
    except Exception as e:
        logger.debug(f"Rasm yuklab olishda xatolik ({url[:40]}): {e}")
        return None

def select_best_product_photos(
    name: str,
    description: str,
    photo_urls: List[str]
) -> Tuple[Optional[str], List[str]]:
    """
    Mahsulot turi (noutbuk yoki telefon) va rasmlarning holatiga qarab
    eng to'g'ri asosiy rasmni va saralangan galereyani tanlash.
    
    Qoidalar:
    1. Smartfonlar (Telefonlar):
       Oldi ko'rinishi (qora ekran) emas, faqat ORQA TARAFI (kameralar, rang ko'rinishi) 
       birinchi (asosiy) rasm sifatida tanlanadi (photo_urls[0]).
       
    2. Noutbuklar (MacBook, Laptop):
       TO'G'RIDAN OLINGAN (Front view - ekran va klaviatura to'g'rida ochiq) rasm asosiy qilinadi.
       Agar bir nechta rasm bo'lsa, simmetriya tahlili orqali eng to'g'ri (Front) rasm tanlanadi.
       Agar to'g'ridan olingan rasmda dog'lar bo'lsa yoki admin boshqa rasmni xohlasa,
       admin panelda 'Boshqa rasmni tanlash' orqali almashtirilishi mumkin.
    """
    if not photo_urls:
        return None, []

    if len(photo_urls) == 1:
        return photo_urls[0], photo_urls

    is_phone = is_phone_product(name, description)
    is_laptop = is_laptop_product(name, description)

    if is_phone:
        # Telefonlar uchun har doim orqa tarafi (1-rasm)
        return photo_urls[0], photo_urls

    if is_laptop:
        # Noutbuklar uchun: birinchi 2-3 ta rasmni simmetriya bo'yicha tahlil qilish
        scores = []
        for idx in range(min(3, len(photo_urls))):
            u = photo_urls[idx]
            if u.startswith("http"):
                b = fetch_image_bytes(u)
                if b:
                    score = calculate_symmetry_diff(b)
                    scores.append((score, idx))

        if scores:
            scores.sort(key=lambda x: x[0])
            best_idx = scores[0][1]
            best_url = photo_urls[best_idx]
            # Galereyada tanlangan rasmni birinchi o'ringa qo'yish
            ordered = [best_url] + [u for i, u in enumerate(photo_urls) if i != best_idx]
            return best_url, ordered

    # Standart holat
    return photo_urls[0], photo_urls
