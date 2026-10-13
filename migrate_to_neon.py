"""
SQLite'dan Neon PostgreSQL bazasiga mavjud ma'lumotlarni ko'chirish (migratsiya) skripti.
Ishlatish:
    python migrate_to_neon.py
yoki
    python migrate_to_neon.py "postgresql://user:pass@ep-xyz.neon.tech/neondb?sslmode=require"
"""
import sys
import os
import asyncio
import logging
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("MigrateToNeon")

async def migrate():
    from bot.database.db import Database
    import aiosqlite

    db_url = sys.argv[1] if len(sys.argv) > 1 else os.getenv("DATABASE_URL", "").strip()
    sqlite_path = os.getenv("DATABASE_PATH", "demostore.db").strip()

    if not db_url:
        logger.error(
            "DATABASE_URL topilmadi! Iltimos, .env faylida DATABASE_URL sozlang yoki "
            "buyruq orqali uzating:\n"
            "python migrate_to_neon.py 'postgresql://user:pass@ep-xyz.neon.tech/neondb?sslmode=require'"
        )
        return

    if not os.path.exists(sqlite_path):
        logger.warning(f"SQLite fayli '{sqlite_path}' topilmadi. Ko'chirish uchun ma'lumot yo'q.")
        return

    logger.info(f"1. SQLite bazasi ochilmoqda: {sqlite_path}")
    logger.info(f"2. Neon PostgreSQL bazasi ulanmoqda...")

    pg_db = Database(database_url=db_url)
    await pg_db.init_db()

    async with aiosqlite.connect(sqlite_path) as s_db:
        s_db.row_factory = aiosqlite.Row

        # 1. Kategoriyalarni ko'chirish
        async with s_db.execute("SELECT * FROM categories;") as cur:
            categories = [dict(r) for r in await cur.fetchall()]
        
        logger.info(f"Ko'chirilmoqda: {len(categories)} ta kategoriya...")
        for c in categories:
            await pg_db.pool.execute("""
                INSERT INTO categories (id, name, icon) 
                VALUES ($1, $2, $3)
                ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, icon = EXCLUDED.icon;
            """, c['id'], c['name'], c.get('icon', 'folder'))

        # 2. Foydalanuvchilarni ko'chirish
        async with s_db.execute("SELECT * FROM users;") as cur:
            users = [dict(r) for r in await cur.fetchall()]
        
        logger.info(f"Ko'chirilmoqda: {len(users)} ta foydalanuvchi...")
        for u in users:
            await pg_db.pool.execute("""
                INSERT INTO users (user_id, full_name, username, phone)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (user_id) DO UPDATE SET full_name = EXCLUDED.full_name, username = EXCLUDED.username, phone = EXCLUDED.phone;
            """, u['user_id'], u.get('full_name', ''), u.get('username'), u.get('phone'))

        # 3. Mahsulotlarni ko'chirish
        async with s_db.execute("SELECT * FROM products;") as cur:
            products = [dict(r) for r in await cur.fetchall()]

        logger.info(f"Ko'chirilmoqda: {len(products)} ta mahsulot...")
        for p in products:
            await pg_db.pool.execute("""
                INSERT INTO products (
                    id, category_id, name, description, price, image_url, gallery_images,
                    is_available, channel_id, message_id, media_group_id, post_url,
                    views_count, is_active
                ) VALUES (
                    $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14
                )
                ON CONFLICT (id) DO UPDATE SET
                    name = EXCLUDED.name,
                    description = EXCLUDED.description,
                    price = EXCLUDED.price,
                    image_url = EXCLUDED.image_url,
                    gallery_images = EXCLUDED.gallery_images,
                    is_available = EXCLUDED.is_available,
                    channel_id = EXCLUDED.channel_id,
                    message_id = EXCLUDED.message_id,
                    media_group_id = EXCLUDED.media_group_id,
                    post_url = EXCLUDED.post_url,
                    views_count = EXCLUDED.views_count,
                    is_active = EXCLUDED.is_active;
            """, 
                p['id'], p.get('category_id'), p['name'], p.get('description'), p.get('price', 0),
                p.get('image_url'), p.get('gallery_images'), p.get('is_available', 1),
                p.get('channel_id'), p.get('message_id'), p.get('media_group_id'),
                p.get('post_url'), p.get('views_count', 0), p.get('is_active', 1)
            )

        # 4. Buyurtmalarni ko'chirish
        async with s_db.execute("SELECT * FROM orders;") as cur:
            orders = [dict(r) for r in await cur.fetchall()]

        logger.info(f"Ko'chirilmoqda: {len(orders)} ta buyurtma...")
        for o in orders:
            await pg_db.pool.execute("""
                INSERT INTO orders (id, user_id, full_name, phone, address, payment_method, total_amount, status)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                ON CONFLICT (id) DO NOTHING;
            """, o['id'], o.get('user_id'), o.get('full_name'), o.get('phone'), o.get('address'), o.get('payment_method'), o.get('total_amount'), o.get('status', 'Yangi'))

        # 5. Buyurtma mahsulotlarini ko'chirish
        async with s_db.execute("SELECT * FROM order_items;") as cur:
            items = [dict(r) for r in await cur.fetchall()]

        logger.info(f"Ko'chirilmoqda: {len(items)} ta buyurtma mahsulotlari...")
        for it in items:
            await pg_db.pool.execute("""
                INSERT INTO order_items (id, order_id, product_name, price, quantity)
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (id) DO NOTHING;
            """, it['id'], it.get('order_id'), it.get('product_name'), it.get('price'), it.get('quantity'))

        # Serial sekvensiyalarni yangilash (ID larning keyingi qiymatlari to'g'ri ishlashi uchun)
        for tbl in ["categories", "products", "orders", "order_items", "cart"]:
            try:
                await pg_db.pool.execute(f"""
                    SELECT setval(pg_get_serial_sequence('{tbl}', 'id'), COALESCE(MAX(id), 1)) FROM {tbl};
                """)
            except Exception as e:
                logger.debug(f"Sequence update note ({tbl}): {e}")

    await pg_db.close()
    logger.info("TABRIKLAYMIZ! Barcha ma'lumotlar Neon PostgreSQL bazasiga muvaffaqiyatli ko'chirildi!")

if __name__ == "__main__":
    asyncio.run(migrate())
