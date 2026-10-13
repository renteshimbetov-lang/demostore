import asyncio
import os
from dotenv import load_dotenv
load_dotenv('.env')
import asyncpg

async def update_db():
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("DATABASE_URL topilmadi!")
        return

    print("Neon PostgreSQL ga ulanmoqda...")
    conn = await asyncpg.connect(db_url, ssl="require")

    # 1. Categories nomlarini to'g'irlash: 1 = Smartfonlar, 2 = Noutbuklar
    await conn.execute("UPDATE categories SET name = 'tmp_smart' WHERE id = 2;")
    await conn.execute("UPDATE categories SET name = 'Smartfonlar', icon = 'smartphone' WHERE id = 1;")
    await conn.execute("UPDATE categories SET name = 'Noutbuklar', icon = 'laptop' WHERE id = 2;")
    await conn.execute("UPDATE categories SET name = 'Quloqchinlar va Audio', icon = 'headphones' WHERE id = 3;")
    await conn.execute("UPDATE categories SET name = 'Aqlli soatlar', icon = 'watch' WHERE id = 4;")
    await conn.execute("UPDATE categories SET name = 'Aksessuarlar', icon = 'plug' WHERE id = 5;")
    print("Categories jadvali yangilandi: 1 = Smartfonlar, 2 = Noutbuklar.")

    # 2. Barcha noutbuklarni category_id = 2 ga o'tkazish
    r_laptops = await conn.execute("""
        UPDATE products 
        SET category_id = 2 
        WHERE LOWER(name) LIKE '%macbook%' 
           OR LOWER(name) LIKE '%surface%' 
           OR LOWER(name) LIKE '%asus%' 
           OR LOWER(name) LIKE '%laptop%' 
           OR LOWER(name) LIKE '%noutbuk%';
    """)
    print(f"Noutbuklar category_id = 2 ga o'tkazildi: {r_laptops}")

    # 3. Product 24 nomini va rasmini to'g'irlash
    await conn.execute("""
        UPDATE products 
        SET name = 'iPhone 17 Pro (256GB / Blue)', 
            image_url = 'https://cdn4.telesco.pe/file/uOTNEh_9x_OwAHwcY5nuZ', 
            category_id = 1 
        WHERE id = 24;
    """)
    print("Product 24 nomi va rasmi to'g'irlandi.")

    # 4. Telefonlarni category_id = 1 ga o'tkazish
    r_phones = await conn.execute("""
        UPDATE products 
        SET category_id = 1 
        WHERE LOWER(name) LIKE '%iphone%' 
           OR LOWER(name) LIKE '%samsung%' 
           OR LOWER(name) LIKE '%redmi%' 
           OR LOWER(name) LIKE '%xiaomi%' 
           OR LOWER(name) LIKE '%galaxy%' 
           OR LOWER(name) LIKE '%smartfon%'
           OR id IN (18, 24, 27, 28, 29, 30, 33, 34, 35);
    """)
    print(f"Telefonlar category_id = 1 ga o'tkazildi: {r_phones}")

    # 5. Telefonlar nomlariga xotira, rang va yomkostni kiritish (aniq ko'rinishi uchun)
    updates = [
        (18, 'iPhone Air (256GB / Black / 100%)'),
        (27, 'IPHONE 16 PRO MAX (256GB / Natural / 89%)'),
        (28, 'IPHONE 17 PRO MAX (256GB / Silver / 92%)'),
        (29, 'IPHONE 16 PRO MAX (256GB / Natural / 89%)'),
        (30, 'IPHONE 15 PRO MAX (256GB / Black / 80%)'),
        (33, 'IPHONE 16 PRO (128GB / Black / 88%)'),
        (34, 'IPHONE AIR (256GB / Black / 94%)'),
        (35, 'IPHONE 16 PRO MAX (256GB / Desert / 100%)'),
    ]
    for pid, new_name in updates:
        await conn.execute("UPDATE products SET name = $1 WHERE id = $2;", new_name, pid)
    print("Telefonlar sarlavhalari to'liq spetsifikatsiyalar bilan boyitildi.")

    # Tekshirish
    prods = await conn.fetch("""
        SELECT p.id, p.category_id, c.name as cat_name, p.name, p.price, p.image_url 
        FROM products p 
        LEFT JOIN categories c ON p.category_id = c.id 
        WHERE p.message_id IS NOT NULL
        ORDER BY p.category_id, p.id;
    """)
    print(f"\n--- BAZADAGI HOLAT (Jami: {len(prods)} ta mahsulot) ---")
    for p in prods:
        print(f"Cat {p['category_id']} [{p['cat_name']}]: ID {p['id']} - {p['name']} (${p['price']}) Img: {bool(p['image_url'])}")

    await conn.close()

if __name__ == "__main__":
    asyncio.run(update_db())
