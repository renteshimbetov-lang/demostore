"""
Barcha mavjud mahsulotlarning rasmlarini Telegram rasmiy CDN (telesco.pe) orqali
to'liq yangilab, Neon PostgreSQL bazasiga yozish skripti.
"""
import asyncio
import json
import logging
import re
import ssl
import urllib.request
from dotenv import load_dotenv

load_dotenv()

from bot.config import config
from bot.database.db import Database

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("SyncPhotos")

_ssl_ctx = ssl._create_unverified_context()

def get_channel_post_photos(channel_username: str, message_id: int):
    url = f"https://t.me/{channel_username.lstrip('@')}/{message_id}?embed=1"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=10, context=_ssl_ctx) as resp:
            html = resp.read().decode("utf-8")
            # telesco.pe fayl manzillarini ajratib olish
            matches = re.findall(r"background-image:url\('(https://cdn\d*\.telesco\.pe/file/[^']+)'\)", html)
            # Dublikatlarni tartibni saqlagan holda tozalash
            seen = set()
            unique = []
            for m in matches:
                if m not in seen:
                    seen.add(m)
                    unique.append(m)
            return unique
    except Exception as e:
        logger.warning(f"Msg #{message_id} rasmlarini olishda xatolik: {e}")
        return []

async def sync():
    db = Database(database_url=config.database_url)
    await db.init_db()

    channel_username = config.channel_username or "shbdbdjdhdjjdhd"
    logger.info("Ma'lumotlar bazasi: Neon PostgreSQL")

    products = await db.fetch("SELECT id, name, description, message_id, image_url FROM products WHERE is_active = 1 ORDER BY id DESC;")
    logger.info(f"Jami {len(products)} ta faol mahsulot tekshirilmoqda...")

    updated_count = 0
    for p in products:
        msg_id = p.get("message_id")
        if not msg_id:
            continue

        photos = get_channel_post_photos(channel_username, msg_id)
        if photos:
            from bot.utils.photo_selector import select_best_index_async
            best_idx = await select_best_index_async(p.get("name", ""), p.get("description") or "", photos)
            primary_photo = photos[best_idx]
            gallery_urls = [primary_photo] + [u for i, u in enumerate(photos) if i != best_idx]
            gallery_json = json.dumps(gallery_urls)
            
            await db.execute("""
                UPDATE products 
                SET image_url = $1, gallery_images = $2 
                WHERE id = $3;
            """, primary_photo, gallery_json, p["id"])

            updated_count += 1
            logger.info(f"Mahsulot #{p['id']} ('{p['name']}'): {len(photos)} ta haqiqiy Telegram rasm yangilandi!")
        else:
            logger.warning(f"Mahsulot #{p['id']} (msg #{msg_id}): Telegramda rasm topilmadi.")

    logger.info(f"YAKUNLANDI! Jami {updated_count} ta mahsulotning rasmlari Telegram CDN orqali yangilandi!")

if __name__ == "__main__":
    asyncio.run(sync())
