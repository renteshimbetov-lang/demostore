import re
import time
from typing import Optional, Tuple, Dict

# USD kursi zaxirasi
DEFAULT_USD_RATE = 12850.0

def get_effective_usd_rate(provided_rate: Optional[float] = None) -> float:
    """Haqiqiy jonli Markaziy Bank kursini olish (fallback zaxirasi bilan)"""
    if provided_rate and provided_rate > 0:
        return float(provided_rate)
    try:
        from bot.utils.currency import get_current_usd_rate_sync
        rate = get_current_usd_rate_sync()
        if rate and rate > 0:
            return float(rate)
    except Exception:
        pass
    return DEFAULT_USD_RATE

# Media group (albom) larni qayta ishlash keshi (media_group_id -> timestamp)
_processed_media_groups: Dict[str, float] = {}

def normalize_keycaps_and_currency(text: str) -> str:
    """
    Kanal postlaridagi raqamli emojilar (keycap) va valyuta belgilarini ASCII ga o'tkazish:
    6️⃣3️⃣9️⃣💲 -> 639$
    """
    if not text:
        return ""
    
    keycaps = {
        '0️⃣': '0', '1️⃣': '1', '2️⃣': '2', '3️⃣': '3', '4️⃣': '4',
        '5️⃣': '5', '6️⃣': '6', '7️⃣': '7', '8️⃣': '8', '9️⃣': '9',
        '0\u20e3': '0', '1\u20e3': '1', '2\u20e3': '2', '3\u20e3': '3', '4\u20e3': '4',
        '5\u20e3': '5', '6\u20e3': '6', '7\u20e3': '7', '8\u20e3': '8', '9\u20e3': '9',
        '💲': '$', '💵': '$'
    }
    res = text
    for k, v in keycaps.items():
        res = res.replace(k, v)
        
    return res

def parse_price(text: str, usd_rate: Optional[float] = None) -> Optional[int]:
    """
    Kanal postidagi narxni har doim AQSH dollari ($) da aniqlaydi:
    - 6️⃣3️⃣9️⃣💲 -> 639
    - $879 -> 879
    - 579$ -> 579
    - 150 usd -> 150
    - 299 000 so'm -> joriy CBU kursi bo'yicha $25
    """
    if not text:
        return None

    rate = get_effective_usd_rate(usd_rate)
    normalized = normalize_keycaps_and_currency(text)
    normalized = re.sub(r"['’ʻʼ`]", "'", normalized.lower())

    # 1. Dollar formatlari: $639, 639$, 150 usd, $ 1,500
    usd_patterns = [
        r"\$\s*(\d[\d., ]*)",                        # $639, $ 1,500
        r"(\d[\d., ]*)\s*\$",                        # 639$, 150 $
        r"(\d[\d., ]*)\s*(?:usd|dollar)",            # 639 usd, 150 dollar
        r"(?:usd|dollar)\s*(\d[\d., ]*)"             # usd 639
    ]
    for pattern in usd_patterns:
        match = re.search(pattern, normalized)
        if match:
            raw_num = re.sub(r"[^\d]", "", match.group(1))
            if raw_num.isdigit():
                val = int(raw_num)
                if 1 <= val <= 100000:
                    return val

    # 2. So'm formatlari kiritilgan bo'lsa, dollarga ($) o'tkazish
    sum_patterns = [
        r"([\d\s.,]+)\s*(?:so[']?m|som|uzs)",
        r"(?:narxi|narx|baho|qiymati)[:\s]+([\d\s.,]+)\s*(?:so[']?m|som|uzs)"
    ]
    for pattern in sum_patterns:
        match = re.search(pattern, normalized)
        if match:
            raw_str = match.group(1).strip()
            cleaned = re.sub(r"[\s.,_]", "", raw_str)
            if cleaned.isdigit():
                val = int(cleaned)
                if val >= 1000:
                    return max(1, round(val / rate))

    # 3. 'k' formatlari (masalan: 1.2k$ yoki 650k)
    k_pattern = r"(\d+(?:[.,]\d+)?)\s*k(?:\$|\s*\$|\b)"
    k_match = re.search(k_pattern, normalized)
    if k_match:
        val_str = k_match.group(1).replace(",", ".")
        try:
            val_float = float(val_str)
            if val_float < 100: # Masalan 1.2k$ -> 1200$
                return int(val_float * 1000)
            elif val_float >= 100: # 650k so'm -> dollarga
                return max(1, round((val_float * 1000) / rate))
        except ValueError:
            pass

    # 4. 'Narxi: 639' kabi toza sonlar
    generic_match = re.search(r"(?:narxi|narx)[:\s]+([\d\s.,]+)", normalized)
    if generic_match:
        cleaned = re.sub(r"[\s.,_]", "", generic_match.group(1).strip())
        if cleaned.isdigit():
            val = int(cleaned)
            if val >= 10000:
                return max(1, round(val / rate))
            elif val > 0:
                return val

    return None

def clean_title_text(raw_line: str, full_text: str = "") -> str:
    """Sarlavhadan barcha emojilar, stikerlar, 'Nomi:' prefikslari va ortiqcha qavslarni tozalash (100% toza model nomi)"""
    # 1. Barcha Unicode emojilari va stiker belgilarini olib tashlash
    cleaned = re.sub(r"[\U00010000-\U0010ffff]", "", raw_line)
    cleaned = re.sub(r"[\u2600-\u27BF\u2300-\u23FF\u2B50\u2B55\uFE0F\uFE0E\u200D\u200C]", "", cleaned)
    
    # 2. Boshidagi belgilar va prefikslarni tozalash
    cleaned = re.sub(r"^[^\w\d]+", "", cleaned).strip()
    cleaned = re.sub(r"^(?:nomi|model|tovar|mahsulot|name)\s*[:\-]\s*", "", cleaned, flags=re.I).strip()
    
    # 3. Qavs ichidagi (256GB / Desert...) kabi ortiqcha matnlarni tozalash
    cleaned = re.sub(r"\s*\([^)]*\)", "", cleaned).strip()
    
    # 4. Oxiridagi narx yozuvlarini tozalash (masalan ' - 159$' yoki '- 175$')
    cleaned = re.sub(r"\s*-\s*\$?\d+\$?\s*$", "", cleaned).strip()
    
    # 5. Oxiridagi qolib ketgan noharfiy belgilarni tozalash
    cleaned = re.sub(r"[^\w\d]+$", "", cleaned).strip()
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned if cleaned else "Mahsulot"

def parse_channel_post_content(raw_text: str, usd_rate: Optional[float] = None) -> Tuple[str, str, int]:
    text = (raw_text or "").strip()
    price = parse_price(text, usd_rate=usd_rate) or 0

    lines = [line.strip() for line in text.split("\n") if line.strip()]
    if not lines:
        return "Yangi mahsulot", "", price

    first_line = lines[0]
    first_line_clean = re.sub(r"[#\W_]+", " ", first_line).strip().lower()
    if len(lines) > 1 and any(first_line_clean.startswith(prefix) for prefix in ["sotuvda", "aksiya", "yangilik", "assalom", "chegirma", "diqqat", "srochno"]):
        first_line = lines[1]
        description = "\n".join(lines[2:]) if len(lines) > 2 else lines[1]
    else:
        description = "\n".join(lines[1:]) if len(lines) > 1 else lines[0]

    first_line = re.sub(r"#\w+", "", first_line).strip()
    name = clean_title_text(first_line, text)
    if len(name) > 100:
        name = name[:97] + "..."

    return name, description, price
