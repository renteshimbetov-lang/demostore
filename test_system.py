import asyncio
import os
import sys

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bot.database.db import Database
from bot.parser.channel_parser import parse_price, parse_channel_post_content

async def run_full_tests():
    print("--- 1. Narx tahlilchisi (Price Parser) testlari (USD format) ---")
    test_cases = [
        ("$100", 100),
        ("25 $", 25),
        ("50 usd", 50),
        ("6️⃣3️⃣9️⃣💲", 639),
        ("7️⃣4️⃣9️⃣💲", 749),
        ("9️⃣2️⃣9️⃣💲", 929),
        ("5️⃣7️⃣9️⃣💲", 579),
        ("8️⃣7️⃣9️⃣💲", 879),
        ("Apple iPhone 15 Pro Max\nNarxi: 1200$\nHolati: Yangi", 1200),
        ("1.2k$", 1200),
        ("Narxi: 650", 650)
    ]

    for raw, expected in test_cases:
        parsed = parse_price(raw)
        assert parsed == expected, f"Xatolik: '{raw}' -> {parsed}, kutilgan: {expected}"
        print(f"  [OK] '{raw}' => ${parsed}")

    print("\n--- 2. Kanal post matnini tahlil qilish (Parser) ---")
    name, desc, price = parse_channel_post_content("MacBook Air M3\nJuda yaxshi holatda\nNarxi: 1200$")
    assert "MacBook" in name
    assert price == 1200
    print(f"  [OK] Post tahlili muvaffaqiyatli: {name}, ${price}")

    print("\n--- 3. Ma'lumotlar bazasi va Sinxronizatsiya testlari (Neon PostgreSQL) ---")
    from bot.config import config
    db = Database(database_url=config.database_url)
    await db.init_db()

    test_channel_id = "-100999999999"
    # Oldingi testlardan qolgan test mahsulotlarini tozalash
    await db.execute("DELETE FROM products WHERE channel_id = $1;", test_channel_id)

    # Kanal postidan mahsulot qo'shish
    prod_id = await db.upsert_product_from_channel(
        channel_id=test_channel_id,
        message_id=99901,
        name="MacBook Air M3",
        description="Juda yupqa va kuchli noutbuk",
        price=1500,
        image_url="https://example.com/mac.jpg",
        post_url="https://t.me/test_channel/99901",
        media_group_id="mg_test_123"
    )
    print(f"  [OK] Kanal postidan mahsulot qo'shildi: ID #{prod_id}")

    # Kanal posti tahrirlanganda yangilanish
    updated_id = await db.upsert_product_from_channel(
        channel_id=test_channel_id,
        message_id=99901,
        name="MacBook Air M3 16GB",
        description="Yangilangan tavsif",
        price=1650,
        image_url="https://example.com/mac_updated.jpg",
        post_url="https://t.me/test_channel/99901",
        media_group_id="mg_test_123"
    )
    assert prod_id == updated_id, "Tahrirlanganda ayni o'sha mahsulot yangilanishi kerak"
    prod = await db.get_product(prod_id)
    assert prod['name'] == "MacBook Air M3 16GB"
    assert prod['price'] == 1650
    print("  [OK] Kanal posti tahrirlanganda bazada avtomatik yangilandi.")

    # Kanalda post o'chirilganda/sotilganda nofaol qilish
    await db.deactivate_product_by_channel_post(test_channel_id, 99901)
    prod_deactivated = await db.get_product(prod_id)
    assert prod_deactivated['is_active'] == 0
    print("  [OK] Post nofaol (is_active=0) qilindi.")

    # Mahsulotni qayta faollashtirib ko'rishlarni sinash
    await db.upsert_product_from_channel(
        channel_id=test_channel_id,
        message_id=99901,
        name="MacBook Air M3 16GB",
        description="Yana sotuvda",
        price=1650,
        image_url="https://example.com/mac.jpg",
        post_url="https://t.me/test_channel/99901"
    )

    v1 = await db.increment_views(prod_id)
    v2 = await db.increment_views(prod_id)
    assert v2 >= 2
    print(f"  [OK] Kanalda ko'rish (views_count) muvaffaqiyatli oshirildi: {v2} ta")

    # Ikkinchi test mahsulotini qo'shish
    prod2_id = await db.upsert_product_from_channel(
        channel_id=test_channel_id,
        message_id=99902,
        name="MacBook Pro 14 M3 Pro",
        description="Kuchli noutbuk",
        price=2200,
        image_url="https://example.com/mac2.jpg",
        post_url="https://t.me/test_channel/99902"
    )
    await db.increment_views(prod2_id)

    top = await db.get_top_viewed_products(limit=15)
    assert len(top) >= 2
    assert any(p['id'] == prod_id for p in top)
    assert top[0]['views_count'] >= top[1]['views_count']
    print(f"  [OK] Top tovarlar ro'yxati saralangan: Eng ko'p ko'rilgan '{top[0]['name']}' ({top[0]['views_count']} ta ko'rish)")

    # Saralash testlari (sort_by)
    prods_asc = await db.get_active_products(sort_by="price_asc")
    prods_desc = await db.get_active_products(sort_by="price_desc")
    assert prods_asc[0]['price'] <= prods_asc[-1]['price']
    assert prods_desc[0]['price'] >= prods_desc[-1]['price']
    print("  [OK] Mahsulotlarni narx bo'yicha o'sish va kamayish tartibida saralash to'g'ri ishladi.")

    # Test mahsulotlarini Neon bazadan tozalash
    await db.execute("DELETE FROM products WHERE channel_id = $1;", test_channel_id)
    await db.close()

    print("\n✅ Barcha sinovlar Neon PostgreSQL bazasida muvaffaqiyatli yakunlandi!")

if __name__ == "__main__":
    asyncio.run(run_full_tests())
