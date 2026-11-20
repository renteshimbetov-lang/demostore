#!/usr/bin/env python3
"""
Telegram kanalidagi postlarni to'g'ridan-to'g'ri skan qilib,
PostgreSQL bazasiga rasmlar qoidasi bilan to'liq sinxronlash skripti.
"""
import asyncio
import os
import sys
from dotenv import load_dotenv

# Loyiha ildiz katalogini yuklash
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, root_dir)
load_dotenv(os.path.join(root_dir, ".env"))

from bot.config import config
from bot.database.db import Database
from bot.utils.channel_sync import full_channel_sync

async def main():
    print("=" * 60)
    print("🚀 TECHNO PRICE / DEMOSTORE — KANAL BILAN SINXRONLASH")
    print("=" * 60)
    print(f"📡 Kanal: @{config.channel_username.lstrip('@')}")
    print(f"🗄 Baza: AWS RDS PostgreSQL ({config.database_url.split('@')[-1] if '@' in config.database_url else 'configured'})")
    print("-" * 60)

    db = Database(database_url=config.database_url)
    await db.init_db()

    try:
        result = await full_channel_sync(db, config.channel_username, auto_activate=True)
        print("-" * 60)
        print("✅ SINXRONLASH MUVAFFAQIYATLI YAKUNLANDI:")
        print(f"   • Skan qilingan postlar: {result['scanned']} ta")
        print(f"   • Yangi qo'shilgan mahsulotlar: {result['created']} ta")
        print(f"   • Yangilangan mahsulotlar: {result['updated']} ta")
        print(f"   • O'chirilgan/sotilgan postlar: {result['deleted']} ta")
        print("-" * 60)
        for item in result.get("products", []):
            print(f"   📦 #{item['id']} {item['name']} — ${item['price']} ({item['action']})")
        print("=" * 60)
    finally:
        await db.close()

if __name__ == "__main__":
    asyncio.run(main())
