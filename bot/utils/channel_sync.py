"""
Telegram kanalidagi postlarni to'liq tahlil qilish, rasmlarni saralash (smartfon/noutbuk qoidasi),
narx va tavsiflarni ajratish hamda PostgreSQL (RDS) bazasiga sinxronlash moduli.
"""
import asyncio
import json
import logging
import re
import urllib.request
from html import unescape
from typing import Dict, List, Optional, Any

from bot.database.db import Database
from bot.parser.channel_parser import parse_channel_post_content
from bot.utils.photo_selector import select_best_index_async
from bot.utils.ssl_context import get_ssl_context

logger = logging.getLogger("ChannelSync")

async def fetch_channel_post_ids(channel_username: str) -> List[int]:
    """Kanalning ommaviy veb sahifasidan post identifikatorlarini (message_id) olish"""
    clean_username = channel_username.lstrip("@")
    url = f"https://t.me/s/{clean_username}"
    ctx = get_ssl_context()
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"})

    def _fetch():
        try:
            with urllib.request.urlopen(req, timeout=12, context=ctx) as r:
                html = r.read().decode("utf-8")
                matches = re.findall(rf"/{clean_username}/(\d+)", html)
                return sorted(list(set(int(m) for m in matches)))
        except Exception as e:
            logger.warning(f"Kanal veb sahifasini o'qishda xatolik: {e}")
            return []

    return await asyncio.to_thread(_fetch)

async def fetch_post_details(channel_username: str, message_id: int) -> Optional[Dict[str, Any]]:
    """Yagona post sahifasidan (embed) matn va barcha rasmlarni olish"""
    clean_username = channel_username.lstrip("@")
    url = f"https://t.me/{clean_username}/{message_id}?embed=1"
    ctx = get_ssl_context()
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"})

    def _fetch():
        try:
            with urllib.request.urlopen(req, timeout=10, context=ctx) as r:
                html = r.read().decode("utf-8")
                if "Post not found" in html or "tgme_widget_message_error" in html:
                    return {"deleted": True, "message_id": message_id}

                # CDN telesco.pe rasmlarini olish (emojilarni chiqarib tashlash)
                photos = re.findall(r"background-image:url\('([^']+)'\)", html)
                unique_photos = []
                for p in photos:
                    if "telesco.pe" not in p or "emoji" in p:
                        continue
                    if p not in unique_photos:
                        unique_photos.append(p)

                # Matnni ajratish
                text_m = re.search(r'class="tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>', html, re.DOTALL)
                raw_text = ""
                if text_m:
                    raw_text = unescape(re.sub(r'<br\s*/?>', '\n', text_m.group(1)))
                    raw_text = re.sub(r'<[^>]+>', '', raw_text).strip()

                return {
                    "deleted": False,
                    "message_id": message_id,
                    "text": raw_text,
                    "photos": unique_photos,
                    "post_url": f"https://t.me/{clean_username}/{message_id}"
                }
        except Exception as e:
            logger.debug(f"Post #{message_id} embed o'qishda xatolik: {e}")
            return None

    return await asyncio.to_thread(_fetch)

async def full_channel_sync(db: Database, channel_username: str, auto_activate: bool = True) -> Dict[str, Any]:
    """
    Kanalni to'liq tekshirish va bazani sinxronlash:
    1. Kanal postlarini skanlash.
    2. Sotilgan yoki o'chirilgan postlarni nofaol qilish.
    3. Yangi mahsulotlarni qabul qilish, kompyuter ko'rishi (CV) qoidasi bilan eng chiroyli rasmni asosiy qilib tanlash.
    4. Baza bilan integratsiya qilish.
    """
    clean_username = channel_username.lstrip("@")
    logger.info(f"Kanal (@{clean_username}) to'liq sinxronlash boshlandi...")

    post_ids = await fetch_channel_post_ids(clean_username)
    if not post_ids:
        logger.warning(f"Kanalda postlar topilmadi yoki ulanish cheklandi: @{clean_username}")
        return {"scanned": 0, "created": 0, "updated": 0, "deleted": 0, "products": []}

    scanned_count = len(post_ids)
    created_count = 0
    updated_count = 0
    deleted_count = 0
    synced_items = []

    # 1. Albom va postlarni guruhlash uchun tahlil
    channel_id = f"@{clean_username}"

    for msg_id in post_ids:
        details = await fetch_post_details(clean_username, msg_id)
        if not details:
            continue

        if details.get("deleted"):
            # Kanalda o'chirilgan post bo'lsa bazadan nofaol qilish
            existing = await db.get_product_by_channel_post(channel_id, msg_id)
            if existing and existing.get("is_active") == 1:
                await db.deactivate_product_by_channel_post(channel_id, msg_id)
                deleted_count += 1
            continue

        raw_text = details.get("text", "")
        photos = details.get("photos", [])

        # Postda sotildi belgisi bormi
        if any(word in raw_text.lower() for word in ["#sotildi", "sotildi", "#sold", "tugadi", "#tugadi"]):
            await db.deactivate_product_by_channel_post(channel_id, msg_id)
            deleted_count += 1
            continue

        # Matn bo'lmasa yoki narx topilmasa o'tkazib yuborish
        if not raw_text or len(raw_text) < 5:
            continue

        from bot.utils.currency import get_cbu_usd_rate
        live_rate = await get_cbu_usd_rate()
        name, description, price, currency, price_uzs = parse_channel_post_content(raw_text, usd_rate=live_rate)

        # Agar narx aniqlanmagan bo'lsa (e'lon yoki oddiy xabar)
        if not price or price <= 0:
            continue

        # Rasmlarni saralash (smartfon/noutbuk qoidasi)
        if photos:
            best_idx = await select_best_index_async(name, description, photos)
            primary_photo = photos[best_idx]
            # Galereyada tanlangan asosiy rasm birinchi o'ringa joylanadi
            gallery_urls = [primary_photo] + [u for i, u in enumerate(photos) if i != best_idx]
        else:
            primary_photo = "/static/apple_3d_logo.png"
            gallery_urls = [primary_photo]

        post_url = details.get("post_url") or f"https://t.me/{clean_username}/{msg_id}"
        has_discount = any(w in raw_text.lower() for w in ["#chegirma", "chegirma", "#aksiya", "aksiya", "#skidka", "skidka", "#haftachegirmasi", "#sale", "discount"])

        # Mavjudligini tekshirish
        existing = await db.get_product_by_channel_post(channel_id, msg_id)
        if existing:
            # Yangilash (agar avval yoki matnda chegirma bo'lsa is_discount=1 saqlanadi)
            disc_flag = 1 if (has_discount or existing.get("is_discount") == 1) else 0
            await db.execute("""
                UPDATE products 
                SET name = $1, description = $2, price = $3, image_url = $4,
                    gallery_images = $5, post_url = $6, currency = $7, price_uzs = $8,
                    is_active = $9, is_available = 1, is_discount = $10
                WHERE id = $11;
            """, name, description, price, primary_photo, json.dumps(gallery_urls),
                 post_url, currency, price_uzs, 1 if auto_activate else existing.get("is_active", 0), disc_flag, existing["id"])
            updated_count += 1
            synced_items.append({"id": existing["id"], "name": name, "price": price, "action": "updated"})
        else:
            # Takroriy tekshiruv (bitta mahsulot albom orqali bir necha xabarga bo'lingan bo'lishi mumkin)
            dup = await db.find_duplicate_product(name=name, description=description, price=price)
            if dup:
                dup_id = dup["id"]
                disc_flag = 1 if (has_discount or dup.get("is_discount") == 1) else 0
                await db.execute("""
                    UPDATE products 
                    SET post_url = $1, channel_id = $2, message_id = $3,
                        gallery_images = $4, image_url = $5, is_discount = $6
                    WHERE id = $7;
                """, post_url, channel_id, msg_id, json.dumps(gallery_urls), primary_photo, disc_flag, dup_id)
                updated_count += 1
                continue

            # Yangi mahsulot qo'shish
            pid = await db.upsert_product_from_channel(
                channel_id=channel_id,
                message_id=msg_id,
                name=name,
                description=description,
                price=price,
                image_url=primary_photo,
                post_url=post_url,
                gallery_images=json.dumps(gallery_urls),
                is_active=1 if auto_activate else 0,
                currency=currency,
                price_uzs=price_uzs
            )
            if has_discount and pid:
                await db.execute("UPDATE products SET is_discount = 1 WHERE id = $1;", pid)
            created_count += 1
            synced_items.append({"id": pid, "name": name, "price": price, "action": "created"})

    logger.info(f"Sinxronlash yakunlandi: Jami {scanned_count} ta post, Yangi: {created_count}, Yangilangan: {updated_count}, O'chirilgan: {deleted_count}")
    return {
        "scanned": scanned_count,
        "created": created_count,
        "updated": updated_count,
        "deleted": deleted_count,
        "products": synced_items
    }
