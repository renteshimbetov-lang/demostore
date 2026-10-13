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
    """Sarlavhadan emojilar, 'Nomi:' prefikslari va ortiqcha belgilarni tozalash, xususiyatlarni qo'shish"""
    cleaned = re.sub(r"^[^\w\d]+", "", raw_line).strip()
    cleaned = re.sub(r"^(?:nomi|model|tovar|mahsulot|name)\s*[:\-]\s*", "", cleaned, flags=re.I).strip()
    
    if cleaned and full_text:
        lower_cleaned = cleaned.lower()
        lower_full = full_text.lower()

        # 1. MACBOOKLAR
        if "macbook" in lower_cleaned or "macbook" in lower_full or "laptop" in lower_cleaned:
            spec_parts = []
            cpu_match = re.search(r"(?:protsessor|chip)[:\s]+[^\w]*(M\d(?:\s*(?:pro|max|ultra))?)", full_text, re.I)
            if cpu_match:
                spec_parts.append(cpu_match.group(1).strip())
                
            ram_match = re.search(r"(?:operativ|ram)[:\s]+[^\w]*(\d+\s*gb)", full_text, re.I)
            if ram_match:
                spec_parts.append(ram_match.group(1).replace(" ", "").upper())
                
            ssd_match = re.search(r"(?:asosiy\s*xotira|xotira|ssd|rom)[:\s]+[^\w]*(\d+\s*(?:gb|tb))", full_text, re.I)
            if ssd_match:
                spec_parts.append(ssd_match.group(1).replace(" ", "").upper())
                
            if spec_parts:
                specs_str = " / ".join(spec_parts)
                if specs_str.lower() not in cleaned.lower():
                    cleaned = f"{cleaned} ({specs_str})"

        # 2. IPHONE VA SMARTFONLAR
        elif "iphone" in lower_cleaned or "iphone" in lower_full or "pro max" in lower_cleaned or "samsung" in lower_cleaned:
            spec_parts = []
            
            # Xotira (Storage)
            storage_m = re.search(r"(?:🧠\s*|xotira[:\s]+|\b)(\d+\s*(?:gb|tb))\b", full_text, re.I)
            if storage_m:
                spec_parts.append(storage_m.group(1).replace(" ", "").upper())
                
            # Rang (Color)
            color_cand = re.search(r"(?:🎨\s*|rangi?[:\s]+)(natural|desert|black|silver|blue|gold|white|pink|space\s*black|titanium)", full_text, re.I)
            if color_cand:
                spec_parts.append(color_cand.group(1).strip().capitalize())
            else:
                for c in ["natural", "desert", "black", "silver", "blue", "gold", "white", "pink"]:
                    if re.search(r"\b" + c + r"\b", lower_full):
                        spec_parts.append(c.capitalize())
                        break
                        
            # Yomkost / Batareya %
            bat_m = re.search(r"(?:🔋\s*|yomkost[:\s]+|ёмкость[:\s]+|batareya[:\s]+|\b)(\d{2,3}\s*%)", full_text, re.I)
            if bat_m:
                spec_parts.append(bat_m.group(1).strip())

            if spec_parts:
                specs_str = " / ".join(spec_parts)
                if not any(part.lower() in cleaned.lower() for part in spec_parts):
                    cleaned = f"{cleaned} ({specs_str})"

    return cleaned if cleaned else "Mahsulot"

def parse_channel_post_content(raw_text: str) -> Tuple[str, str, int]:
    text = (raw_text or "").strip()
    price = parse_price(text) or 0

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
