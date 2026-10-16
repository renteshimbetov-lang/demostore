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
    name, desc, price, currency, price_uzs = parse_channel_post_content("MacBook Air M3\nJuda yaxshi holatda\nNarxi: 1200$")
    assert "MacBook" in name
    assert price == 1200
    assert currency == "USD"
    print(f"  [OK] Post tahlili muvaffaqiyatli: {name}, ${price}")

    name2, desc2, price2, curr2, uzs2 = parse_channel_post_content("Apple TYPE-C Adapter\n299 000 so'm")
    assert curr2 == "UZS"
    assert uzs2 == 299000
    print(f"  [OK] So'mda post tahlili muvaffaqiyatli: {name2}, {uzs2} so'm, valyuta={curr2}")

    print("\n--- 3. Ma'lumotlar bazasi va Sinxronizatsiya testlari (Neon PostgreSQL) ---")
    from bot.config import config
    db = Database(database_url=config.database_url)
    await db.init_db()

    test_channel_id = "-100999999999"
    # Oldingi testlardan qolgan test mahsulotlarini tozalash
    await db.execute("DELETE FROM products WHERE channel_id = $1;", test_channel_id)

    # Kanal postidan mahsulot qo'shish (Dastlab admin tasdiqlaguncha is_active=0 bo'ladi)
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
    prod_pending = await db.get_product(prod_id)
    assert prod_pending['is_active'] == 0, "Yangi kanal posti admin 'Ha' deguncha nofaol (0) bo'lishi kerak"
    print(f"  [OK] Kanal postidan mahsulot qo'shildi (tasdiq kutmoqda, is_active=0): ID #{prod_id}")

    # Admin 'Ha' deb tasdiqlaganda faollashadi
    await db.activate_product_by_id(prod_id)
    prod_approved = await db.get_product(prod_id)
    assert prod_approved['is_active'] == 1, "Admin tasdiqlagach is_active=1 bo'lishi kerak"
    print("  [OK] Admin 'Ha' deb tasdiqladi: mahsulot faollashtirildi (is_active=1)")

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
    await db.activate_product_by_id(prod_id)

    v1 = await db.increment_views(prod_id)
    v2 = await db.increment_views(prod_id)
    assert v2 >= 2
    print(f"  [OK] Kanalda ko'rish (views_count) muvaffaqiyatli oshirildi: {v2} ta")

    # Ikkinchi test mahsulotini qo'shish va tasdiqlash
    prod2_id = await db.upsert_product_from_channel(
        channel_id=test_channel_id,
        message_id=99902,
        name="MacBook Pro 14 M3 Pro",
        description="Kuchli noutbuk",
        price=2200,
        image_url="https://example.com/mac2.jpg",
        post_url="https://t.me/test_channel/99902"
    )
    await db.activate_product_by_id(prod2_id)
    await db.increment_views(prod2_id)

    await db.execute("UPDATE products SET views_count = 99999 WHERE id = $1;", prod_id)
    top = await db.get_top_viewed_products(limit=50)
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

    print("\n--- 4. Xavfsizlik va Spam himoyasi testlari (HMAC & Click Limiting) ---")
    from bot.api.telegram_auth import generate_telegram_init_data, validate_telegram_init_data
    import time

    test_token = "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
    test_user = {"id": 888777666, "first_name": "SecureUser", "username": "secureuser"}

    # 4.1 HMAC-SHA256 haqiqiy imzo tekshiruvi
    valid_init_data = generate_telegram_init_data(test_user, test_token)
    user_parsed = validate_telegram_init_data(valid_init_data, bot_token=test_token)
    assert user_parsed is not None and user_parsed["id"] == 888777666
    print("  [OK] Telegram initData HMAC-SHA256 imzosi muvaffaqiyatli tekshirildi.")

    # 4.2 Soxta imzo (Tampered data)
    tampered_data = valid_init_data.replace("SecureUser", "HackerUser")
    assert validate_telegram_init_data(tampered_data, bot_token=test_token) is None
    print("  [OK] Soxtalashtirilgan initData imzosi muvaffaqiyatli aniqlandi va rad etildi.")

    # 4.3 Replay attack (vaqti o'tgan auth_date)
    expired_data = generate_telegram_init_data(test_user, test_token, auth_date=int(time.time() - 90000))
    assert validate_telegram_init_data(expired_data, max_age_seconds=86400, bot_token=test_token) is None
    print("  [OK] Muddati o'tgan (replay attack) initData rad etildi.")

    # 4.4 Bir user 1 soatda 1 marta bosishi (Spam/Bot click himoyasi)
    # Yangi test mahsulot qo'shamiz
    click_prod_id = await db.upsert_product_from_channel(
        channel_id=test_channel_id,
        message_id=99999,
        name="Click Limit Test Product",
        description="Test",
        price=100,
        image_url="https://example.com/click_test.jpg",
        post_url="https://t.me/test_channel/99999"
    )
    # Oldingi test kliklarini tozalash
    await db.execute("DELETE FROM product_clicks WHERE product_id = $1;", click_prod_id)
    await db.execute("UPDATE products SET views_count = 0 WHERE id = $1;", click_prod_id)

    # 1-klik (user1) -> muvaffaqiyatli oshishi kerak
    inc1, count1 = await db.increment_views_safe(click_prod_id, 111222)
    assert inc1 is True, "Birinchi klik hisoblanishi kerak"
    assert count1 == 1, f"Kutilgan: 1, haqiqiy: {count1}"

    # 2-klik (user1 ayni o'sha soatda yana bosdi) -> oshmasligi kerak!
    inc2, count2 = await db.increment_views_safe(click_prod_id, 111222)
    assert inc2 is False, "1 soat ichida qayta klik rad etilishi (False) kerak"
    assert count2 == 1, f"Views oshmasligi kerak: kutilgan 1, haqiqiy {count2}"

    # 3-klik (boshqa user2 bosdi) -> muvaffaqiyatli oshishi kerak
    inc3, count3 = await db.increment_views_safe(click_prod_id, 333444)
    assert inc3 is True, "Boshqa user bosganda hisoblanishi kerak"
    assert count3 == 2, f"Kutilgan: 2, haqiqiy: {count3}"
    print("  [OK] 1 soatlik foydalanuvchi klik limiti (product_clicks) to'liq ishonchli ishladi.")

    # Test mahsulotlarini Neon bazadan tozalash
    await db.execute("DELETE FROM product_clicks WHERE product_id = $1;", click_prod_id)
    await db.execute("DELETE FROM products WHERE channel_id = $1;", test_channel_id)
    await db.close()

    print("\n--- 5. Redis Kesh va Frontend Asset Minifikatsiyasi testlari ---")
    import fakeredis.aioredis
    from bot.utils.cache import CacheManager

    # 5.1 Redis Kesh menejeri testi (L1 RAM + L2 Redis)
    fake_redis = fakeredis.aioredis.FakeRedis()
    test_cm = CacheManager(redis_client=fake_redis)
    assert test_cm.is_redis_active() is True

    # Rasm keshga yozish
    dummy_img = b"\x89PNG\r\n\x1a\n\x00TEST_IMAGE_DATA"
    await test_cm.set_photo("test_file_id_999", dummy_img, "image/png", ttl_seconds=3600)

    # 1-o'qish: L1 xotiradan olish
    p1 = await test_cm.get_photo("test_file_id_999")
    assert p1 is not None and p1[0] == dummy_img and p1[1] == "image/png"
    print("  [OK] L1 RAM xotirasidan rasm muvaffaqiyatli o'qildi.")

    # Server qayta yuklanganda (L1 RAM bo'shab qolganda) L2 Redis-dan tiklanish
    test_cm._memory_cache.clear()
    p2 = await test_cm.get_photo("test_file_id_999")
    assert p2 is not None and p2[0] == dummy_img and p2[1] == "image/png"
    print("  [OK] Server qayta yonganda L2 Redis keshidan rasm muvaffaqiyatli tiklandi (Persistent Cache).")

    # JSON ma'lumotlar (valyuta/kurs) keshini tekshirish
    await test_cm.set_json("test_rate", {"rate": 12850}, ttl_seconds=60)
    test_cm._json_cache.clear()
    r = await test_cm.get_json("test_rate")
    assert r is not None and r["rate"] == 12850
    print("  [OK] JSON / Valyuta kursi Redis keshida muvaffaqiyatli saqlandi va tiklandi.")
    await test_cm.close()

    # 5.2 Frontend Asset Minifikatsiyasi tekshiruvi
    base_dir = os.path.dirname(os.path.abspath(__file__))
    webapp_dir = os.path.join(base_dir, "webapp")
    min_files = [
        ("app.js", "app.min.js"),
        ("app.css", "app.min.css"),
        ("mini_app_core.js", "mini_app_core.min.js"),
        ("mini_app_buttons.css", "mini_app_buttons.min.css")
    ]
    for orig, mini in min_files:
        orig_p = os.path.join(webapp_dir, orig)
        mini_p = os.path.join(webapp_dir, mini)
        assert os.path.exists(mini_p), f"Minifikatsiya qilingan fayl topilmadi: {mini}"
        orig_sz = os.path.getsize(orig_p)
        mini_sz = os.path.getsize(mini_p)
        assert mini_sz < orig_sz, f"{mini} hajmi {orig} dan kichik bo'lishi kerak!"
        print(f"  [OK] {mini} mavjud va siqilgan ({orig_sz // 1024}KB -> {mini_sz // 1024}KB).")

    print("\n✅ Barcha sinovlar, xavfsizlik va kesh/minifikatsiya tekshiruvlari muvaffaqiyatli yakunlandi!")

if __name__ == "__main__":
    asyncio.run(run_full_tests())
