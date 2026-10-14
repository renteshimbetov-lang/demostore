import json
from typing import Any, Dict, List, Optional
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from bot.config import config
from bot.utils.helpers import format_price
from bot.utils.currency import convert_usd_to_uzs, format_uzs_currency


def parse_gallery(prod: Dict[str, Any]) -> List[str]:
    try:
        g = json.loads(prod.get("gallery_images") or "[]")
        return [x for x in g if x]
    except Exception:
        return []


def selected_index(prod: Dict[str, Any], gallery: List[str]) -> int:
    img = prod.get("image_url")
    return gallery.index(img) if img in gallery else 0


def photo_input(ref: str) -> Optional[str]:
    """Galereya elementidan Telegramga yuboriladigan qiymat (file_id yoki URL)"""
    if not ref:
        return None
    if ref.startswith("/api/photo/"):
        return ref.split("/")[-1]
    if ref.startswith("http"):
        return ref
    return None


def build_moderation_caption(prod: Dict[str, Any], idx: int, total: int) -> str:
    price = prod.get("price") or 0
    uzs_amount = convert_usd_to_uzs(price)
    price_uzs = format_uzs_currency(uzs_amount)
    post_url = prod.get("post_url") or ""
    photo_line = (
        f"🖼 <b>Mini ilovadagi asosiy rasm:</b> {idx + 1}-rasm ({total} tadan)\n"
        if total > 1 else ""
    )
    return (
        f"🔔 <b>KANALDAN YANGI POST QABUL QILINDI!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📱 <b>Model:</b> {prod.get('name', '')}\n"
        f"💵 <b>Narxi:</b> ${price} (≈ {price_uzs})\n"
        f"🔗 <b>Kanal posti:</b> <a href=\"{post_url}\">Postni ko'rish</a>\n"
        f"{photo_line}"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"❓ <b>Shuni do'kon / mini ilovaga joylaylikmi?</b>"
    )


def build_moderation_keyboard(prod_id: int, idx: int, total: int) -> InlineKeyboardMarkup:
    rows = []
    if total > 1:
        prev_i = (idx - 1) % total
        next_i = (idx + 1) % total
        rows.append([
            InlineKeyboardButton(text="◀️", callback_data=f"chan_photo_{prod_id}_{prev_i}"),
            InlineKeyboardButton(text=f"🖼 {idx + 1} / {total}", callback_data=f"chan_photo_{prod_id}_{idx}"),
            InlineKeyboardButton(text="▶️", callback_data=f"chan_photo_{prod_id}_{next_i}"),
        ])
    rows.append([
        InlineKeyboardButton(text="🟢 Ha, joylansin", callback_data=f"chan_approve_{prod_id}"),
        InlineKeyboardButton(text="🔥 Hafta chegirmalariga joylash", callback_data=f"chan_discount_{prod_id}"),
    ])
    rows.append([
        InlineKeyboardButton(text="🔴 Rad etish", callback_data=f"chan_reject_{prod_id}"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)
