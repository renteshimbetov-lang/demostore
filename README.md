# 🛒 DemoStore — Telegram E-Commerce & Mini App Ekotizimi

Ushbu loyiha zamonaviy **Python 3**, **Aiogram 3.x**, **Neon Serverless PostgreSQL (asyncpg)**, **Aiohttp REST API** va **Telegram Mini App (Web App)** asosida yaratilgan toʻliq funksional internet-doʻkon va kanal sinxronizatsiyasi platformasidir.

---

## 🌟 Yangilangan va integratsiya qilingan imkoniyatlar

### 1. 📱 Zamonaviy Telegram Mini App (Frontend & UI)
- **Kategoriyalar (Chips)**: Yuqori panelda gorizontal skroll boʻladigan toifalar (Barchasi, Smartfonlar, Noutbuklar, Quloqchinlar va h.k.).
- **Narx boʻyicha saralash**:
  - Arzonidan qimmatiga (Narx: Oʻsish tartibida)
  - Qimmatidan arzoniga (Narx: Kamayish tartibida)
  - Ommabop (Eng koʻp kanalga oʻtilgan tovarlar)
- **Zamonaviy holatlar (UX)**:
  - Mahsulotlar yuklanayotganda nafis animatsiyali **Skeleton Loader (Shimmer effect)**;
  - Qidiruv natijasi boʻsh boʻlsa, nafis SVG vektor belgisi bilan **"Hech narsa topilmadi"** bloki va filtrlarni tozalash tugmasi.
- **Haptic Feedback**:
  - Har bir toifa, saralash, qidiruv va tugma bosilganda `Telegram.WebApp.HapticFeedback` orqali engil tebranish beriladi.
- **Dizayn qoidasi**:
  - Mini ilovada hech qanday emoji ishlatilmagan! Barcha elementlar sof **Lucide/Phosphor SVG vektor ikonkalari** asosida ishlab chiqilgan.

---

### 2. 📡 Kanal tahlilchisi (Channel Parser & Sync)
- **Universal narx formati**:
  - `150k`, `250 k`, `1.5m`
  - `$100`, `25 $`, `50 usd` (USD kursiga avtomatik koʻpaytiriladi)
  - `150 000 so'm`, `200 000 som`, `350.000 uzs`
  - `Narxi: 450 000`
- **Albom (Media Group) qoʻllab-quvvatlashi**:
  - Agar post bir nechta rasmdan iborat boʻlsa, tizim asosiy birinchi rasmni olib saqlaydi va qolgan dublikat xabarlarni oʻtkazib yuboradi.
- **Avtomatik sinxronizatsiya**:
  - Yangi post kelganda tovar bazaga qoʻshiladi (`channel_post`);
  - Kanaldagi post tahrirlanganda (`edited_channel_post`) bazadagi nomi, narxi, tavsifi va rasmi avtomatik yangilanadi;
  - Postda "sotildi" / "#sold" yozilsa yoki oʻchirilsa, mahsulot bazada nofaol (`is_active=False`) qilinadi.

---

### 3. 👑 Admin panel va Kliklar tahlili
- **Xavfsiz `/admin` buyrugʻi**:
  - Faqat `ADMIN_IDS` roʻyxatidagi adminlar uchun ishlaydi, begona foydalanuvchilar kira olmaydi.
- **Statistika hisoboti**:
  - Jami foydalanuvchilar soni;
  - Faol mahsulotlar soni;
  - Bajarilgan buyurtmalar va umumiy tushum;
  - **Foydalanuvchilar mini ilovadan kanalga eng koʻp oʻtgan (Top) tovarlar roʻyxati** (views_count boʻyicha saralangan).
- **Kliklarni hisoblash**:
  - Mini ilovada har safar **"Kanalda koʻrish"** tugmasi bosilganda `POST /api/products/{id}/click` orqali tovarning koʻrishlar soni (`views_count`) +1 ga oshirib boriladi.

---

## 📁 Loyiha tuzilmasi

```
demostore/
├── .env                  # Token, Neon DATABASE_URL va Port sozlamalari
├── main_store.py         # Bot va REST API serverini bir vaqtda yurgizuvchi fayl
├── test_system.py        # Tizim testlari (parser, neon db, views, sort)
├── run.sh                # Ishga tushirish skripti
├── requirements.txt      # Kutubxonalar
├── bot/
│   ├── config.py         # Konfiguratsiya
│   ├── database/
│   │   └── db.py         # DB migratsiyalari va querylar
│   ├── parser/
│   │   └── channel_parser.py # Narx ajratish va media group filtri
│   ├── api/
│   │   └── server.py     # Mini App REST API serveri (aiohttp)
│   ├── handlers/
│   │   ├── admin.py      # /admin va Top tovarlar statistikasi
│   │   ├── channel.py    # Kanal postlari va tahrirlarini ushlovchi
│   │   ├── catalog.py    # Katalog handlerlari
│   │   ├── cart.py       # Savat handlerlari
│   │   ├── checkout.py   # Buyurtma rasmiylashtirish
│   │   └── common.py     # /start, haqimizda, qidiruv
│   └── keyboards/        # Reply va Inline tugmalar
└── webapp/
    ├── index.html        # Mini App sahifasi
    ├── app.css           # Dizayn, shimmer loader va SVG stillari
    └── app.js            # Haptic, toifalar, saralash va kliklar mantig'i
```

---

## ⚡️ Ishga tushirish

```bash
cd demostore
./run.sh
```

Dastur bir vaqtning oʻzida:
1. **Telegram botni** faollashtiradi (`@demostore_test_bot`).
2. **Mini App va REST API serverini** `http://localhost:8090` da ishga tushiradi.
