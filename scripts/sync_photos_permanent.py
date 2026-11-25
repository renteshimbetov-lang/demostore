#!/usr/bin/env python3
"""
Doimiy mahsulot rasmlarini Telegram kanaldan yuklab olib,
serverning o'zida (/webapp/static/products/) saqlash va
baza (RDS PostgreSQL)dagi eskirgan telesco.pe havolalarini
doimiy /static/products/<id>.jpg ga almashtirish skripti.
"""
import asyncio
import os
import re
import ssl
import sys
import urllib.request
import aiohttp
import asyncpg
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(BASE_DIR, ".env"))

DATABASE_URL = os.getenv("DATABASE_URL")
CHANNEL_USERNAME = os.getenv("CHANNEL_USERNAME", "shbdbdjdhdjjdhd").lstrip("@")
STATIC_PRODUCTS_DIR = os.path.join(BASE_DIR, "webapp", "static", "products")
os.makedirs(STATIC_PRODUCTS_DIR, exist_ok=True)

ssl_ctx = ssl._create_unverified_context()

async def download_image_async(session: aiohttp.ClientSession, url: str, target_path: str) -> bool:
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            if resp.status == 200:
                data = await resp.read()
                if len(data) > 1000:
                    with open(target_path, "wb") as f:
                        f.write(data)
                    return True
    except Exception as e:
        pass
    return False

async def fetch_fresh_post_photos(session: aiohttp.ClientSession, message_id: int) -> list:
    url = f"https://t.me/{CHANNEL_USERNAME}/{message_id}?embed=1"
    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}
    try:
        async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=10), ssl=False) as resp:
            if resp.status == 200:
                html = await resp.text()
                matches = re.findall(r"background-image:url\('([^\']+)'\)", html)
                # Faqat haqiqiy mahsulot rasmlari (emojilarni chiqarib tashlash)
                clean_photos = []
                for m in matches:
                    if "telesco.pe" in m and "emoji" not in m:
                        if m not in clean_photos:
                            clean_photos.append(m)
                return clean_photos
    except Exception as e:
        pass
    return []

async def process_product(sem, pool, session, prod):
    async with sem:
        p_id = prod["id"]
        m_id = prod.get("message_id")
        target_path = os.path.join(STATIC_PRODUCTS_DIR, f"{p_id}.jpg")
        rel_url = f"/static/products/{p_id}.jpg"

        # Agar rasm allaqachon mavjud va hajmi yaxshi bo'lsa
        if os.path.exists(target_path) and os.path.getsize(target_path) > 3000:
            if prod.get("image_url") != rel_url:
                async with pool.acquire() as conn:
                    await conn.execute("UPDATE products SET image_url = $1 WHERE id = $2", rel_url, p_id)
            print(f"✅ #{p_id} {prod['name']} -> Allaqachon mavjud ({os.path.getsize(target_path)} bayt)")
            return True

        if not m_id:
            print(f"⚠️ #{p_id} {prod['name']} -> message_id yo'q!")
            return False

        photos = await fetch_fresh_post_photos(session, m_id)
        if not photos:
            print(f"❌ #{p_id} {prod['name']} (msg #{m_id}) -> Kanaldan rasm topilmadi")
            return False

        main_photo_url = photos[0]
        ok = await download_image_async(session, main_photo_url, target_path)
        if ok:
            async with pool.acquire() as conn:
                await conn.execute("UPDATE products SET image_url = $1 WHERE id = $2", rel_url, p_id)
            print(f"🎉 #{p_id} {prod['name']} -> Muvaffaqiyatli yuklandi va bazaga yozildi ({os.path.getsize(target_path)} bayt)")
            return True
        else:
            print(f"❌ #{p_id} {prod['name']} -> Rasm baytlarini yuklab bo'lmadi")
            return False

async def main():
    print(f"🚀 Mahsulot rasmlarini serverga doimiy yuklash boshlandi...")
    print(f"📂 Saqlash joyi: {STATIC_PRODUCTS_DIR}")
    print(f"📡 Kanal: @{CHANNEL_USERNAME}")

    pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=10)
    async with pool.acquire() as conn:
        products = await conn.fetch("SELECT id, name, message_id, image_url, channel_id FROM products WHERE is_active = 1 ORDER BY id DESC;")
    
    print(f"📊 Jami faol mahsulotlar: {len(products)} ta")

    sem = asyncio.Semaphore(6)
    conn_tcp = aiohttp.TCPConnector(ssl=False, limit=30)
    async with aiohttp.ClientSession(connector=conn_tcp) as session:
        tasks = [process_product(sem, pool, session, p) for p in products]
        results = await asyncio.gather(*tasks)

    success_count = sum(1 for r in results if r)
    print(f"\n=======================================================")
    print(f"🏁 Yakunlandi: {success_count} / {len(products)} ta mahsulot rasmi tayyor!")
    print(f"=======================================================\n")
    await pool.close()

if __name__ == "__main__":
    asyncio.run(main())
