from typing import List, Dict, Any

def format_price(amount: int) -> str:
    """Raqamni dollar ($) formatiga o'tkazish, masalan 639 -> '$639'"""
    formatted = f"{amount:,}".replace(",", " ")
    return f"${formatted}"

def format_order_summary(order_id: int, full_name: str, phone: str, address: str, payment_method: str, items: List[Dict[str, Any]], total: int, status: str = "Yangi") -> str:
    lines = [
        f"🛍 <b>Buyurtma #{order_id}</b>",
        f"━━━━━━━━━━━━━━━━━━",
        f"👤 <b>Mijoz:</b> {full_name}",
        f"📞 <b>Telefon:</b> {phone}",
        f"📍 <b>Manzil:</b> {address}",
        f"💳 <b>Toʻlov turi:</b> {payment_method}",
        f"📌 <b>Holat:</b> <i>{status}</i>",
        f"━━━━━━━━━━━━━━━━━━",
        f"<b>Mahsulotlar:</b>"
    ]
    for i, it in enumerate(items, 1):
        lines.append(f"{i}. {it['name']} — {it['quantity']} x {format_price(it['price'])} = <b>{format_price(it['price'] * it['quantity'])}</b>")
    lines.append(f"━━━━━━━━━━━━━━━━━━")
    lines.append(f"💰 <b>Jami toʻlov:</b> <b>{format_price(total)}</b>")
    return "\n".join(lines)

def is_phone_product(name: str = "", description: str = "") -> bool:
    """Mahsulot telefon / smartfon ekanligini aniqlash"""
    text = f"{name or ''} {description or ''}".lower()
    if any(k in text for k in ["macbook", "noutbuk", "laptop", "surface", "asus", "thinkpad", "dell", "hp"]):
        return False
    if any(k in text for k in ["iphone", "samsung", "redmi", "xiaomi", "telefon", "smartfon", "galaxy", "pro max", "plus", "mini"]):
        return True
    return False

def is_laptop_product(name: str = "", description: str = "") -> bool:
    """Mahsulot noutbuk / MacBook ekanligini aniqlash"""
    text = f"{name or ''} {description or ''}".lower()
    return any(k in text for k in ["macbook", "noutbuk", "laptop", "surface", "thinkpad", "asus", "dell", "hp", "mac"])

