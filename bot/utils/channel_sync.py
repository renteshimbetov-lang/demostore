"""
Telegram kanalidagi postlarni to'liq tahlil qilish, rasmlarni saralash (smartfon/noutbuk/planshet qoidasi),
narx va tavsiflarni ajratish hamda PostgreSQL (RDS) bazasiga boshidan to'liq sinxronlash moduli.
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

async def fetch_channel_post_ids(channel_username: str, fetch_all: bool = True) -> List[int]:
    """Kanalning ommaviy veb sahifasidan post identifikatorlarini boshidan oxirigacha olish"""
    clean_username = channel_username.lstrip("@")
    ctx = get_ssl_context()
    all_ids = set()

    def _fetch_page(url: str) -> List[int]:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"})
            with urllib.request.urlopen(req, timeout=12, context=ctx) as r:
                html = r.read().decode("utf-8")
                matches = re.findall(rf"/{clean_username}/(\d+)", html)
                return [int(m) for m in matches]
        except Exception as e:
            logger.warning(f"Kanal sahifasini o'qishda xatolik ({url}): {e}")
            return []

    # 1. Eng oxirgi sahifani olish
    first_page_ids = await asyncio.to_thread(_fetch_page, f"https://t.me/s/{clean_username}")
    if not first_page_ids:
        return []
    all_ids.update(first_page_ids)

    # 2. Kanal boshigacha (barcha eski postlar) sahifalab orqaga qaytish (?before=min_id)
    if fetch_all:
        min_id = min(first_page_ids)
        while min_id > 1:
            older_ids = await asyncio.to_thread(_fetch_page, f"https://t.me/s/{clean_username}?before={min_id}")
            new_older = [x for x in older_ids if x < min_id]
            if not new_older:
                break
            all_ids.update(new_older)
            min_id = min(new_older)

    sorted_ids = sorted(list(all_ids))
    logger.info(f"Kanal (@{clean_username}) bo'yicha jami {len(sorted_ids)} ta post ID topildi (diapazon: {min(sorted_ids) if sorted_ids else 0} - {max(sorted_ids) if sorted_ids else 0})")
    return sorted_ids

async def fetch_post_details(channel_username: str, message_id: int) -> Optional[Dict[str, Any]]:
    """Yagona post sahifasidan (embed) matn va barcha haqiqiy rasmlarni olish"""
    clean_username = channel_username.lstrip("@")
    url = f"https://t.me/{clean_username}/{message_id}?embed=1"
    ctx = get_ssl_context()

    def _fetch():
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"})
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
    Kanalni boshidan oxirigacha to'liq tekshirish va bazani sinxronlash:
    1. Kanalning barcha postlarini (boshidan oxirigacha) skanlash.
    2. Sotilgan yoki o'chirilgan postlarni nofaol qilish.
    3. Yangi mahsulotlarni qabul qilish, kompyuter ko'rishi (CV) qoidasi bilan eng chiroyli rasmni asosiy qilib tanlash.
    4. Toifalarga (Smartfonlar, Planshetlar, Noutbuklar, Aqlli soatlar va h.k.) to'g'ri taqsimlash.
    5. Takroriy postlarni birlashtirish va bazani yangilash.
    """
    clean_username = channel_username.lstrip("@")
    channel_id = f"@{clean_username}"
    logger.info(f"Kanal (@{clean_username}) boshidan boshlab to'liq sinxronlash boshlandi...")

    post_ids = await fetch_channel_post_ids(clean_username, fetch_all=True)
    if not post_ids:
        logger.warning(f"Kanalda postlar topilmadi yoki ulanish cheklandi: @{clean_username}")
        return {"scanned": 0, "created": 0, "updated": 0, "deleted": 0, "products": []}

    scanned_count = len(post_ids)
    created_count = 0
    updated_count = 0
    deleted_count = 0
    synced_items = []

    # Jonli valyuta kursi
    from bot.utils.currency import get_cbu_usd_rate
    live_rate = await get_cbu_usd_rate()

    # Bir vaqtda tezkor so'rov yuborish uchun semafor (15 ta oqim)
    sem = asyncio.Semaphore(15)

    async def fetch_one(pid: int):
        async with sem:
            return await fetch_post_details(clean_username, pid)

    logger.info(f"Jami {len(post_ids)} ta post tafsilotlari tezkorlik bilan o'qilmoqda...")
    post_details_list = await asyncio.gather(*(fetch_one(pid) for pid in post_ids))

    logger.info("Postlar tahlil qilinmoqda va bazaga yozilmoqda...")
    for details in post_details_list:
        if not details:
            continue

        msg_id = details["message_id"]

        if details.get("deleted"):
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

        if not raw_text or len(raw_text) < 5:
            continue

        name, description, price, currency, price_uzs = parse_channel_post_content(raw_text, usd_rate=live_rate)

        if not price or price <= 0:
            continue

        # Rasmlarni saralash (smartfon/noutbuk/planshet qoidasi)
        if photos:
            best_idx = await select_best_index_async(name, description, photos)
            primary_photo = photos[best_idx]
            gallery_urls = [primary_photo] + [u for i, u in enumerate(photos) if i != best_idx]
        else:
            primary_photo = "/static/apple_3d_logo.png"
            gallery_urls = [primary_photo]

        post_url = details.get("post_url") or f"https://t.me/{clean_username}/{msg_id}"
        has_discount = any(w in raw_text.lower() for w in ["#chegirma", "chegirma", "#aksiya", "aksiya", "#skidka", "skidka", "#haftachegirmasi", "#sale", "discount"])

        # Mavjudligini tekshirish
        existing = await db.get_product_by_channel_post(channel_id, msg_id)
        if existing:
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
            # Takroriy tekshiruv (albom bir nechta postga bo'lingan bo'lsa)
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

    logger.info(f"To'liq sinxronlash yakunlandi: Jami {scanned_count} ta post, Yangi: {created_count}, Yangilangan: {updated_count}, O'chirilgan: {deleted_count}")
    return {
        "scanned": scanned_count,
        "created": created_count,
        "updated": updated_count,
        "deleted": deleted_count,
        "products": synced_items
    }
