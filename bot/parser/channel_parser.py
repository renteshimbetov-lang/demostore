import re
import time
from typing import Optional, Tuple, Dict

# USD kursi (agar so'mda kiritilsa, dollarga aylantirish uchun)
DEFAULT_USD_RATE = 12800

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

def parse_price(text: str, usd_rate: int = DEFAULT_USD_RATE) -> Optional[int]:
    """
    Kanal postidagi narxni har doim AQSH dollari ($) da aniqlaydi:
    - 6️⃣3️⃣9️⃣💲 -> 639
    - $879 -> 879
    - 579$ -> 579
    - 150 usd -> 150
    """
    if not text:
        return None

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
                    return round(val / usd_rate)

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
                return round((val_float * 1000) / usd_rate)
        except ValueError:
            pass

    # 4. 'Narxi: 639' kabi toza sonlar
    generic_match = re.search(r"(?:narxi|narx)[:\s]+([\d\s.,]+)", normalized)
    if generic_match:
        cleaned = re.sub(r"[\s.,_]", "", generic_match.group(1).strip())
        if cleaned.isdigit():
            val = int(cleaned)
            if val >= 10000:
                return round(val / usd_rate)
            elif val > 0:
                return val

    return None

def clean_title_text(raw_line: str, full_text: str = "") -> str:
    """Sarlavhadan emojilar, 'Nomi:' prefikslari va ortiqcha belgilarni tozalash"""
    cleaned = re.sub(r"^[^\w\d]+", "", raw_line).strip()
    cleaned = re.sub(r"^(?:nomi|model|tovar|mahsulot|name)\s*[:\-]\s*", "", cleaned, flags=re.I).strip()
    
    if cleaned and full_text and ("macbook" in cleaned.lower() or "iphone" in cleaned.lower() or "samsung" in cleaned.lower()):
        spec_parts = []
        
        # Protsessor
        cpu_match = re.search(r"(?:protsessor|chip)[:\s]+[^\w]*(M\d(?:\s*(?:pro|max|ultra))?)", full_text, re.I)
        if cpu_match:
            spec_parts.append(cpu_match.group(1).strip())
            
        # RAM
        ram_match = re.search(r"(?:operativ|ram)[:\s]+[^\w]*(\d+\s*gb)", full_text, re.I)
        if ram_match:
            spec_parts.append(ram_match.group(1).replace(" ", "").upper())
            
        # SSD / Asosiy xotira
        ssd_match = re.search(r"(?:asosiy\s*xotira|xotira|ssd|rom)[:\s]+[^\w]*(\d+\s*(?:gb|tb))", full_text, re.I)
        if ssd_match:
            spec_parts.append(ssd_match.group(1).replace(" ", "").upper())
            
        if spec_parts:
            specs_str = " / ".join(spec_parts)
            if specs_str.lower() not in cleaned.lower():
                cleaned = f"{cleaned} ({specs_str})"

    return cleaned if cleaned else "Mahsulot"

def parse_channel_post_content(raw_text: str) -> Tuple[str, str, int]:
    text = (raw_text or "").strip()
    price = parse_price(text) or 0

    lines = [line.strip() for line in text.split("\n") if line.strip()]
    if not lines:
        return "Yangi mahsulot", "", price

    first_line = lines[0]
    first_line = re.sub(r"#\w+", "", first_line).strip()
    name = clean_title_text(first_line, text)
    if len(name) > 100:
        name = name[:97] + "..."

    description = "\n".join(lines[1:]) if len(lines) > 1 else lines[0]

    return name, description, price

def is_media_group_duplicate(media_group_id: Optional[str]) -> bool:
    if not media_group_id:
        return False

    current_time = time.time()
    expired = [k for k, t in _processed_media_groups.items() if current_time - t > 300]
    for k in expired:
        _processed_media_groups.pop(k, None)

    if media_group_id in _processed_media_groups:
        return True

    _processed_media_groups[media_group_id] = current_time
    return False
