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
        ("mini_app_buttons.css", "mini_app_buttons.min.css"),
        ("admin.js", "admin.min.js"),
        ("admin.css", "admin.min.css")
    ]
    for orig, mini in min_files:
        orig_p = os.path.join(webapp_dir, orig)
        mini_p = os.path.join(webapp_dir, mini)
        assert os.path.exists(mini_p), f"Minifikatsiya qilingan fayl topilmadi: {mini}"
        orig_sz = os.path.getsize(orig_p)
        mini_sz = os.path.getsize(mini_p)
        assert mini_sz < orig_sz, f"{mini} hajmi {orig} dan kichik bo'lishi kerak!"
        print(f"  [OK] {mini} mavjud va siqilgan ({orig_sz // 1024}KB -> {mini_sz // 1024}KB).")

    print("\n--- 6. Admin Mini App va API xavfsizlik/boshqaruv testlari ---")
    from bot.api.server import create_web_app
    from aiohttp.test_utils import TestClient, TestServer

    db = Database(database_url=config.database_url)
    await db.init_db()

    # 6.1 Yangi mahsulot qo'shish (create_product_admin)
    admin_prod_id = await db.create_product_admin(
        name="Admin Test iPad Pro M4",
        price=1350,
        description="OLED ekranli eng so'nggi iPad",
        category_id=None,
        currency="USD",
        price_uzs=None,
        is_discount=1,
        is_active=1,
        image_url="https://example.com/ipad_test.jpg"
    )
    assert admin_prod_id > 0
    prod = await db.get_product(admin_prod_id)
    assert prod["name"] == "Admin Test iPad Pro M4"
    assert prod["is_discount"] == 1
    assert prod["is_active"] == 1
    print(f"  [OK] Admin Mini App orqali mahsulot qo'shildi: ID #{admin_prod_id}")

    # 6.2 Mahsulotni tahrirlash (update_product_admin)
    await db.update_product_admin(
        product_id=admin_prod_id,
        name="Admin Test iPad Pro M4 256GB",
        price=1400,
        description="Yangilangan tavsif",
        category_id=None,
        currency="USD",
        price_uzs=None,
        is_discount=0,
        is_active=1,
        image_url="https://example.com/ipad_updated.jpg"
    )
    prod = await db.get_product(admin_prod_id)
    assert prod["name"] == "Admin Test iPad Pro M4 256GB"
    assert prod["price"] == 1400
    assert prod["is_discount"] == 0
    print("  [OK] Admin mahsulot ma'lumotlarini muvaffaqiyatli tahrirladi.")

    # 6.3 Faollik va chegirma holatlarini almashtirish (toggle_product_active & toggle_product_discount)
    new_active = await db.toggle_product_active(admin_prod_id)
    assert new_active == 0
    new_active2 = await db.toggle_product_active(admin_prod_id)
    assert new_active2 == 1

    new_disc = await db.toggle_product_discount(admin_prod_id)
    assert new_disc == 1
    new_disc2 = await db.toggle_product_discount(admin_prod_id)
    assert new_disc2 == 0
    print("  [OK] Admin real-vaqtda mahsulot faolligi va chegirmasini yoqib-o'chirdi (toggles).")

    # 6.4 Admin mahsulotlar qidiruvi va filtratsiyasi (get_all_products_admin)
    all_admin_prods = await db.get_all_products_admin(search="Admin Test iPad", limit=10)
    assert len(all_admin_prods) >= 1
    assert all_admin_prods[0]["id"] == admin_prod_id
    print("  [OK] Admin mahsulotlar qidiruvi va filtratsiyasi to'g'ri ishladi.")

    # 6.5 Admin Dashboard statistikasi (get_stats)
    stats = await db.get_stats()
    assert "total_products_count" in stats
    assert "discount_count" in stats
    assert "today_orders" in stats
    assert "today_revenue" in stats
    print(f"  [OK] Admin Dashboard kengaytirilgan statistikasi: jami {stats['total_products_count']} ta mahsulot, {stats['discount_count']} ta chegirma.")

    # 6.6 Admin API xavfsizlik va ruxsatlar tekshiruvi (401, 403, 200)
    token = config.bot_token or "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
    config.bot_token = token
    app = create_web_app(db=db, webapp_dir=webapp_dir, bot=None)
    client = TestClient(TestServer(app))
    await client.start_server()

    # A) Hech qanday Telegram sessiyasiz so'rov -> 401 Unauthorized
    r_unauth = await client.get("/api/admin/check")
    assert r_unauth.status == 401
    print("  [OK] Telegram sessiyasiz Admin API ga so'rov 401 Unauthorized bilan to'xtatildi.")

    # B) Admin bo'lmagan foydalanuvchi so'rovi -> 403 Forbidden
    non_admin_user = {"id": 1122334455, "first_name": "OddiyMijoz", "username": "oddiy_mijoz"}
    non_admin_init = generate_telegram_init_data(non_admin_user, token)
    r_forbidden = await client.get("/api/admin/check", headers={"X-Telegram-Init-Data": non_admin_init})
    assert r_forbidden.status == 403
    print("  [OK] Admin bo'lmagan foydalanuvchi Admin API ga kiritilmadi (403 Forbidden).")

    # C) Tizim administratori so'rovi -> 200 OK
    admin_id = config.admin_ids[0] if config.admin_ids else 999999999
    if not config.admin_ids:
        config.admin_ids = [admin_id]
    admin_user = {"id": admin_id, "first_name": "StoreAdmin", "username": "store_admin"}
    admin_init = generate_telegram_init_data(admin_user, token)
    r_admin_check = await client.get("/api/admin/check", headers={"X-Telegram-Init-Data": admin_init})
    assert r_admin_check.status == 200
    check_json = await r_admin_check.json()
    assert check_json.get("is_admin") is True
    print(f"  [OK] Tizim admini (ID: {admin_id}) muvaffaqiyatli autentifikatsiyadan o'tdi (200 OK).")

    # D) Admin Dashboard API tekshiruvi
    r_dash = await client.get("/api/admin/dashboard", headers={"X-Telegram-Init-Data": admin_init})
    assert r_dash.status == 200
    dash_json = await r_dash.json()
    assert "stats" in dash_json and "top_products" in dash_json
    print("  [OK] Admin Dashboard API to'liq ma'lumotlar bilan javob berdi.")

    # E) Tashqi brauzer (Safari/Chrome) uchun Admin Session Token & Login tekshiruvi
    from bot.api.telegram_auth import generate_admin_session_token, verify_admin_token
    admin_session_token = generate_admin_session_token(admin_id, token)
    verified = verify_admin_token(admin_session_token, token, config.admin_ids)
    assert verified is not None and verified["id"] == admin_id
    # API ga Telegram sessiyasiz faqat token bilan so'rov yuborish (Brauzer orqali)
    r_token_auth = await client.get("/api/admin/check", headers={"X-Admin-Token": admin_session_token})
    assert r_token_auth.status == 200
    token_json = await r_token_auth.json()
    assert token_json.get("is_admin") is True

    # /api/admin/login testi (Brauzerda ID yoki parol bilan kirish)
    r_login = await client.post("/api/admin/login", json={"credential": str(admin_id)})
    assert r_login.status == 200
    login_data = await r_login.json()
    assert login_data.get("ok") is True and "admin_token" in login_data
    print("  [OK] Tashqi brauzer (Safari/Chrome) uchun Admin Login va Session Token muvaffaqiyatli ishlayapti.")

    # F) Barcha nofaollarni bittada faollashtirish (activate-all) testi
    # Avval tovarimizni nofaol qilamiz
    await db.execute("UPDATE products SET is_active = 0 WHERE id = $1;", admin_prod_id)
    r_act = await client.post("/api/admin/products/activate-all", headers={"X-Admin-Token": admin_session_token})
    assert r_act.status == 200
    act_data = await r_act.json()
    assert act_data.get("success") is True
    prod_now = await db.get_product(admin_prod_id)
    assert prod_now["is_active"] == 1
    print("  [OK] Barcha nofaol tovarlarni bittada faollashtirish (activate-all) muvaffaqiyatli ishladi.")

    # Tozalash
    await client.close()
    await db.delete_product(admin_prod_id)
    deleted_prod = await db.get_product(admin_prod_id)
    assert deleted_prod is None
    print("  [OK] Admin mahsulotni muvaffaqiyatli o'chirdi (delete_product).")
    await db.close()

    print("\n✅ Barcha sinovlar, xavfsizlik va kesh/minifikatsiya tekshiruvlari muvaffaqiyatli yakunlandi!")

if __name__ == "__main__":
    asyncio.run(run_full_tests())
