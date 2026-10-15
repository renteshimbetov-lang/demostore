import os
import json
import logging
import asyncio
from datetime import datetime, date
from typing import List, Dict, Any, Optional

try:
    import asyncpg
except ImportError:
    asyncpg = None

logger = logging.getLogger("Database")

class Database:
    """
    DemoStore — 100% Sof Neon PostgreSQL Ma'lumotlar Bazasi Menejeri
    - Neon Serverless PostgreSQL bazasini asyncpg connection pool orqali to'liq boshqaradi.
    - Cold-start (serverless uyg'onish) va uzilishlarga qarshi avtomatik qayta ulanish (reconnect/retry) mexanizmi.
    - PostgreSQL GIN trigram qidiruv indekslari va optimallashtirilgan SQL so'rovlar.
    """

    def __init__(self, database_url: Optional[str] = None, db_path: Optional[str] = None):
        # Parametrlarni xavfsiz aniqlash (db_path argumenti kelsa ham DATABASE_URL ustun turadi)
        url = database_url
        if not url and db_path and (db_path.startswith("postgresql://") or db_path.startswith("postgres://")):
            url = db_path

        self.database_url = (url or os.getenv("DATABASE_URL", "")).strip()
        self.is_postgres = True  # Tizim har doim sof Neon PostgreSQL rejimida ishlaydi
        self.pool: Optional[asyncpg.Pool] = None

    @staticmethod
    def _row_to_dict(row: Any) -> Optional[Dict[str, Any]]:
        """asyncpg.Record ni xavfsiz va to'liq JSON-mos Python dict formatiga o'tkazish"""
        if row is None:
            return None
        d = dict(row)
        for k, v in d.items():
            if isinstance(v, (datetime, date)):
                d[k] = v.isoformat()
        return d

    async def init_db(self):
        """Neon PostgreSQL bazasiga ulanish va kerakli jadvallar hamda indekslarni yaratish"""
        if not asyncpg:
            raise ImportError("asyncpg kutubxonasi o'rnatilmagan! Iltimos, 'pip install asyncpg' buyrug'ini ishga tushiring.")

        if not self.database_url:
            raise ValueError(
                "\n" + "="*60 + "\n"
                "XATOLIK: Neon PostgreSQL DATABASE_URL topilmadi!\n"
                "Iltimos, '.env' faylini oching va DATABASE_URL parametrini ko'rsating.\n"
                "="*60 + "\n"
            )

        logger.info("Neon PostgreSQL ulanish puli (asyncpg pool) ishga tushirilmoqda...")

        # Neon SSL sozlamalari
        ssl_arg = None
        if "sslmode=" in self.database_url:
            ssl_arg = None  # asyncpg DSN dagi sslmode parametrini avtomatik taniydi
        elif "neon.tech" in self.database_url or not any(loc in self.database_url for loc in ["localhost", "127.0.0.1"]):
            ssl_arg = "require"

        # Neon cold-start yoki vaqtinchalik uzilishlarda qayta urinish (Retry with backoff)
        last_err = None
        for attempt in range(1, 4):
            try:
                self.pool = await asyncpg.create_pool(
                    dsn=self.database_url,
                    min_size=2,
                    max_size=20,
                    ssl=ssl_arg,
                    command_timeout=35.0,
                    statement_cache_size=0,  # Neon pgBouncer connection pooler uchun majburiy
                    max_cached_statement_lifetime=0,
                    max_inactive_connection_lifetime=300.0,
                    timeout=20.0
                )
                break
            except Exception as e:
                last_err = e
                logger.warning(f"Neon ulanishida ogohlantirish ({attempt}/3): {e}. 1.5 soniyadan so'ng qayta uriniladi...")
                await asyncio.sleep(1.5)

        if not self.pool:
            raise ConnectionError(f"Neon PostgreSQL bazasiga ulanib bo'lmadi: {last_err}")

        # Jadvallarni, ustunlarni va indekslarni tekshirish hamda yaratish
        async with self.pool.acquire() as conn:
            # 1. Trigram qidiruv kengaytmasi (Full-Text / fuzzy search)
            try:
                await conn.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")
            except Exception as e:
                logger.debug(f"pg_trgm kengaytmasi ogohlantirishi: {e}")

            # 2. Foydalanuvchilar jadvali
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id BIGINT PRIMARY KEY,
                    full_name TEXT,
                    username TEXT,
                    phone TEXT,
                    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # 3. Kategoriyalar jadvali
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS categories (
                    id SERIAL PRIMARY KEY,
                    name TEXT NOT NULL UNIQUE,
                    icon TEXT DEFAULT 'folder'
                );
            """)

            # 4. Mahsulotlar jadvali
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS products (
                    id SERIAL PRIMARY KEY,
                    category_id INTEGER REFERENCES categories(id) ON DELETE SET NULL,
                    name TEXT NOT NULL,
                    description TEXT,
                    price INTEGER NOT NULL,
                    image_url TEXT,
                    gallery_images TEXT,
                    photo_file_id VARCHAR(255),
                    is_available INTEGER DEFAULT 1,
                    channel_id TEXT,
                    message_id BIGINT,
                    media_group_id TEXT,
                    post_url TEXT,
                    views_count INTEGER DEFAULT 0,
                    is_active INTEGER DEFAULT 1,
                    is_discount INTEGER DEFAULT 0,
                    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # Mavjud mahsulotlar jadvali uchun ustunlar migratsiyasi
            await conn.execute("""
                ALTER TABLE products ADD COLUMN IF NOT EXISTS gallery_images TEXT;
                ALTER TABLE products ADD COLUMN IF NOT EXISTS photo_file_id VARCHAR(255);
                ALTER TABLE products ADD COLUMN IF NOT EXISTS channel_id TEXT;
                ALTER TABLE products ADD COLUMN IF NOT EXISTS message_id BIGINT;
                ALTER TABLE products ADD COLUMN IF NOT EXISTS media_group_id TEXT;
                ALTER TABLE products ADD COLUMN IF NOT EXISTS post_url TEXT;
                ALTER TABLE products ADD COLUMN IF NOT EXISTS views_count INTEGER DEFAULT 0;
                ALTER TABLE products ADD COLUMN IF NOT EXISTS is_active INTEGER DEFAULT 1;
                ALTER TABLE products ADD COLUMN IF NOT EXISTS is_discount INTEGER DEFAULT 0;
            """)

            # 5. Savat jadvali
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS cart (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT REFERENCES users(user_id) ON DELETE CASCADE,
                    product_id INTEGER REFERENCES products(id) ON DELETE CASCADE,
                    quantity INTEGER DEFAULT 1,
                    CONSTRAINT unique_user_product UNIQUE (user_id, product_id)
                );
            """)

            # 6. Buyurtmalar jadvali
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS orders (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT REFERENCES users(user_id) ON DELETE SET NULL,
                    full_name TEXT,
                    phone TEXT,
                    address TEXT,
                    payment_method TEXT,
                    total_amount INTEGER,
                    status TEXT DEFAULT 'Yangi',
                    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # 7. Buyurtma ichidagi mahsulotlar jadvali
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS order_items (
                    id SERIAL PRIMARY KEY,
                    order_id INTEGER REFERENCES orders(id) ON DELETE CASCADE,
                    product_name TEXT,
                    price INTEGER,
                    quantity INTEGER
                );
            """)

            # 8. PostgreSQL optimallashtirilgan indekslar
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_products_category ON products(category_id);
                CREATE INDEX IF NOT EXISTS idx_products_active ON products(is_active, is_available);
                CREATE INDEX IF NOT EXISTS idx_products_channel_msg ON products(channel_id, message_id);
                CREATE INDEX IF NOT EXISTS idx_products_views ON products(views_count DESC, id DESC);
                CREATE INDEX IF NOT EXISTS idx_cart_user ON cart(user_id);
                CREATE INDEX IF NOT EXISTS idx_orders_user ON orders(user_id);
            """)

            try:
                await conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_products_name_trgm ON products USING gin (name gin_trgm_ops);
                    CREATE INDEX IF NOT EXISTS idx_products_desc_trgm ON products USING gin (description gin_trgm_ops);
                """)
            except Exception as e:
                logger.debug(f"GIN trigram indekslari: {e}")

            # 9. Boshlang'ich kategoriyalarni kiritish
            cat_count = await conn.fetchval("SELECT COUNT(*) FROM categories;")
            if cat_count == 0:
                categories = [
                    ("Smartfonlar", "smartphone"),
                    ("Noutbuklar", "laptop"),
                    ("Quloqchinlar va Audio", "headphones"),
                    ("Aqlli soatlar", "watch"),
                    ("Aksessuarlar", "plug")
                ]
                for name, icon in categories:
                    await conn.execute(
                        "INSERT INTO categories (name, icon) VALUES ($1, $2) ON CONFLICT (name) DO NOTHING;",
                        name, icon
                    )

        logger.info("Neon PostgreSQL bazasi muvaffaqiyatli ulandi va barcha jadvallar tayyor!")

    async def close(self):
        """Ulanish pulini xavfsiz yopish"""
        if self.pool:
            await self.pool.close()
            self.pool = None
            logger.info("Neon PostgreSQL ulanish puli yopildi.")

    # =========================================================================
    # XAVFSIZ VA AVTO-RECONNECT SO'ROV YORDAMCHILARI
    # =========================================================================
    async def execute(self, query: str, *args) -> str:
        """SQL buyrug'ini bajarish (INSERT, UPDATE, DELETE)"""
        for attempt in range(1, 3):
            try:
                async with self.pool.acquire() as conn:
                    return await conn.execute(query, *args)
            except (asyncpg.PostgresConnectionError, asyncpg.CannotConnectNowError) as e:
                if attempt == 2: raise
                logger.warning(f"Neon so'rovida vaqtinchalik uzilish ({e}), qayta ulanilmoqda...")
                await asyncio.sleep(0.8)

    async def fetch(self, query: str, *args) -> List[Dict[str, Any]]:
        """Ko'p qatorli natijalarni dict ro'yxati shaklida olish"""
        for attempt in range(1, 3):
            try:
                async with self.pool.acquire() as conn:
                    rows = await conn.fetch(query, *args)
                    return [self._row_to_dict(r) for r in rows]
            except (asyncpg.PostgresConnectionError, asyncpg.CannotConnectNowError) as e:
                if attempt == 2: raise
                logger.warning(f"Neon so'rovida vaqtinchalik uzilish ({e}), qayta ulanilmoqda...")
                await asyncio.sleep(0.8)

    async def fetchrow(self, query: str, *args) -> Optional[Dict[str, Any]]:
        """Bitta qatorli natijani dict shaklida olish"""
        for attempt in range(1, 3):
            try:
                async with self.pool.acquire() as conn:
                    row = await conn.fetchrow(query, *args)
                    return self._row_to_dict(row)
            except (asyncpg.PostgresConnectionError, asyncpg.CannotConnectNowError) as e:
                if attempt == 2: raise
                logger.warning(f"Neon so'rovida vaqtinchalik uzilish ({e}), qayta ulanilmoqda...")
                await asyncio.sleep(0.8)

    async def fetchval(self, query: str, *args) -> Any:
        """Bitta qiymatni olish (COUNT, MAX, ID va h.k.)"""
        for attempt in range(1, 3):
            try:
                async with self.pool.acquire() as conn:
                    return await conn.fetchval(query, *args)
            except (asyncpg.PostgresConnectionError, asyncpg.CannotConnectNowError) as e:
                if attempt == 2: raise
                logger.warning(f"Neon so'rovida vaqtinchalik uzilish ({e}), qayta ulanilmoqda...")
                await asyncio.sleep(0.8)

    # =========================================================================
    # FOYDALANUVCHILAR (USERS)
    # =========================================================================
    async def add_user(self, user_id: int, full_name: str, username: Optional[str] = None):
        await self.execute("""
            INSERT INTO users (user_id, full_name, username)
            VALUES ($1, $2, $3)
            ON CONFLICT (user_id) DO UPDATE 
            SET full_name = EXCLUDED.full_name, username = EXCLUDED.username;
        """, user_id, full_name, username)

    async def update_user_phone(self, user_id: int, phone: str):
        await self.execute("UPDATE users SET phone = $1 WHERE user_id = $2;", phone, user_id)

    async def get_user(self, user_id: int) -> Optional[Dict[str, Any]]:
        return await self.fetchrow("SELECT * FROM users WHERE user_id = $1;", user_id)

    async def get_users_count(self) -> int:
        val = await self.fetchval("SELECT COUNT(*) FROM users;")
        return val or 0

    async def get_all_user_ids(self) -> List[int]:
        rows = await self.fetch("SELECT user_id FROM users;")
        return [r["user_id"] for r in rows]

    # =========================================================================
    # KATEGORIYALAR (CATEGORIES)
    # =========================================================================
    async def get_categories(self) -> List[Dict[str, Any]]:
        return await self.fetch("SELECT * FROM categories ORDER BY id ASC;")

    async def get_category(self, category_id: int) -> Optional[Dict[str, Any]]:
        return await self.fetchrow("SELECT * FROM categories WHERE id = $1;", category_id)

    # =========================================================================
    # MAHSULOTLAR (PRODUCTS)
    # =========================================================================
    async def get_products_by_category(self, category_id: int) -> List[Dict[str, Any]]:
        return await self.fetch("""
            SELECT p.*, c.name as category_name 
            FROM products p 
            LEFT JOIN categories c ON p.category_id = c.id 
            WHERE p.category_id = $1 AND p.is_available = 1 AND p.is_active = 1 AND p.message_id IS NOT NULL
            ORDER BY p.id DESC;
        """, category_id)

    async def get_active_products(
        self,
        category_id: Optional[int] = None,
        sort_by: str = "default",
        search: Optional[str] = None,
        min_price: Optional[int] = None,
        max_price: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Web App va katalog uchun saralangan, faol mahsulotlarni olish (narx va toifa bo'yicha filter)"""
        query = """
            SELECT p.*, c.name as category_name 
            FROM products p 
            LEFT JOIN categories c ON p.category_id = c.id 
            WHERE p.is_active = 1 AND p.is_available = 1 AND p.message_id IS NOT NULL
        """
        params: List[Any] = []

        if category_id is not None and category_id > 0:
            params.append(category_id)
            query += f" AND p.category_id = ${len(params)}"

        if min_price is not None and min_price > 0:
            params.append(min_price)
            query += f" AND p.price >= ${len(params)}"

        if max_price is not None and max_price > 0:
            params.append(max_price)
            query += f" AND p.price <= ${len(params)}"

        if search and search.strip():
            raw_search = search.strip()
            params.append(f"%{raw_search}%")
            p_idx = len(params)
            clean_digits = ''.join(c for c in raw_search if c.isdigit())
            if clean_digits and len(clean_digits) <= 6 and not any(c.isalpha() for c in raw_search):
                p_val = int(clean_digits)
                params.append(p_val)
                query += f" AND (p.name ILIKE ${p_idx} OR p.description ILIKE ${p_idx} OR p.price = ${len(params)})"
            else:
                query += f" AND (p.name ILIKE ${p_idx} OR p.description ILIKE ${p_idx})"

        if sort_by == "price_asc":
            query += " ORDER BY p.price ASC"
        elif sort_by == "price_desc":
            query += " ORDER BY p.price DESC"
        elif sort_by == "popular":
            query += " ORDER BY p.views_count DESC, p.id DESC"
        elif sort_by == "newest":
            query += " ORDER BY p.id DESC"
        else:
            query += " ORDER BY p.id DESC"

        return await self.fetch(query, *params)

    async def get_product(self, product_id: int) -> Optional[Dict[str, Any]]:
        return await self.fetchrow("""
            SELECT p.*, c.name as category_name 
            FROM products p 
            LEFT JOIN categories c ON p.category_id = c.id 
            WHERE p.id = $1;
        """, product_id)

    async def get_products_count(self) -> int:
        val = await self.fetchval("SELECT COUNT(*) FROM products WHERE is_active = 1;")
        return val or 0

    async def search_products(self, query: str) -> List[Dict[str, Any]]:
        pattern = f"%{query.strip()}%"
        return await self.fetch("""
            SELECT p.*, c.name as category_name 
            FROM products p 
            LEFT JOIN categories c ON p.category_id = c.id
            WHERE (p.name ILIKE $1 OR p.description ILIKE $1) 
              AND p.is_available = 1 AND p.is_active = 1 AND p.message_id IS NOT NULL
            LIMIT 25;
        """, pattern)

    async def increment_views(self, product_id: int) -> int:
        """Kanalga o'tish (views_count) sonini +1 oshirish va yangi sonni qaytarish"""
        new_views = await self.fetchval("""
            UPDATE products 
            SET views_count = COALESCE(views_count, 0) + 1 
            WHERE id = $1 
            RETURNING views_count;
        """, product_id)
        return new_views or 0

    async def get_top_viewed_products(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Eng ko'p ko'rilgan (Top) tovarlar ro'yxati"""
        return await self.fetch("""
            SELECT id, name, price, views_count, post_url, image_url 
            FROM products 
            WHERE views_count > 0 AND is_active = 1
            ORDER BY views_count DESC, id DESC 
            LIMIT $1;
        """, limit)

    async def get_product_by_channel_post(self, channel_id: str, message_id: int) -> Optional[Dict[str, Any]]:
        return await self.fetchrow("""
            SELECT * FROM products 
            WHERE channel_id = $1 AND message_id = $2;
        """, str(channel_id), int(message_id))

    async def find_duplicate_product(
        self,
        name: str,
        description: str,
        price: int,
        photo_file_id: Optional[str] = None,
        gallery_file_ids: Optional[List[str]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Kanalga qayta tashlangan bir xil mahsulotni aniqlash:
        1. Rasm file_id lari orqali (eng ishonchli).
        2. Kod / IMEI (masalan: F007, 698490, H005) orqali.
        3. Bir xil narx, nomi va tozalangan tavsif matni bo'yicha.
        """
        import re

        # 1. Rasm file_id lari bo'yicha qidirish
        fids_to_check = []
        if photo_file_id:
            fids_to_check.append(photo_file_id)
        if gallery_file_ids:
            for fid in gallery_file_ids:
                if fid and fid not in fids_to_check:
                    fids_to_check.append(fid)

        for fid in fids_to_check:
            row = await self.fetchrow("""
                SELECT * FROM products 
                WHERE (photo_file_id = $1 OR gallery_images LIKE '%' || $1 || '%') 
                ORDER BY is_active DESC, id DESC
                LIMIT 1;
            """, fid)
            if row:
                return dict(row)

        # 2. Kod / IMEI / Qurilma identifikatori orqali qidirish (masalan: 🔎H005, 📟 698490, #F007)
        code_match = re.search(r'(?:imei|seriya|kod|🔎|📟|#)\s*[:\s]*([a-z0-9/-]{3,20})', description or "", re.I)
        if code_match:
            code = code_match.group(1).strip()
            code_upper = code.upper()
            common_regions = {'LL/A', 'VC/A', 'CH/A', 'KH/A', 'ZP/A', 'MY/A', 'J/A', 'RU/A', 'FD/A', 'AH/A'}
            if code_upper not in common_regions and (len(code) >= 4 or (len(code) >= 3 and not code.isdigit())):
                row = await self.fetchrow("""
                    SELECT * FROM products 
                    WHERE description ILIKE '%' || $1 || '%' 
                    ORDER BY is_active DESC, id DESC
                    LIMIT 1;
                """, code)
                if row:
                    return dict(row)

        # 3. Nomi, narxi va tozalangan tavsif bo'yicha qidirish
        def _clean_text(t: str) -> str:
            if not t:
                return ""
            t = re.sub(r'[\U00010000-\U0010ffff]', '', t)  # Emojilar
            t = re.sub(r'@\w+', '', t)  # @username
            t = re.sub(r'\+?\d[\d\s-]{7,}\d', '', t)  # Telefon raqamlar
            t = re.sub(r'https?://\S+', '', t)  # Havolalar
            t = re.sub(r'\s+', '', t)  # Bo'shliqlar
            return t.lower()

        new_clean = _clean_text(description or "")
        if len(new_clean) >= 20:
            candidates = await self.fetch("""
                SELECT * FROM products 
                WHERE price = $1 
                ORDER BY is_active DESC, id DESC LIMIT 20;
            """, price)
            for cand in candidates:
                cand_clean = _clean_text(cand.get("description") or "")
                if cand_clean and (new_clean == cand_clean or (len(new_clean) >= 30 and (new_clean in cand_clean or cand_clean in new_clean))):
                    return dict(cand)

        return None

    async def upsert_product_from_channel(
        self,
        channel_id: str,
        message_id: int,
        name: str,
        description: str,
        price: int,
        image_url: str,
        post_url: str,
        media_group_id: Optional[str] = None,
        category_id: Optional[int] = None,
        photo_file_id: Optional[str] = None,
        gallery_images: Optional[str] = None,
        is_active: Optional[int] = 0
    ) -> int:
        """Kanal postidan mahsulotni Neon bazasiga xatosiz qo'shish yoki yangilash (yangi mahsulotlar admin tasdiqlaguncha is_active=0 bo'ladi)"""
        if not category_id:
            import re
            lower_name = (name or "").lower()
            # Kontakt ma'lumotlari (telefon raqamlar, admin/menejer username lar) tozalash
            desc_clean = re.sub(r'(?:telefon|bog[\'’`]?lanish|tel|aloqa|menejer|admin)\s*[:\s]*[^\n]+', '', description or '', flags=re.I)
            desc_clean = re.sub(r'@[a-z0-9_]+', '', desc_clean, flags=re.I)
            full_search = f"{name} {desc_clean}".lower()

            # 1-BOSQICH: Mahsulot nomi bo'yicha toifani aniqlash (eng aniq mezon)
            if any(k in lower_name for k in ["watch", "soat", "iwatch", "ultra 1", "ultra 2", "series 6", "series 7", "series 8", "series 9", "series 10", "applewatch"]):
                c_name = "Aqlli soatlar"
            elif any(k in lower_name for k in ["airpods", "airpod", "quloqchin", "naushnik", "headphone", "earbuds", "buds", "earphone", "audio"]):
                c_name = "Quloqchinlar va Audio"
            elif any(k in lower_name for k in ["macbook", "noutbuk", "laptop", "surface", "thinkpad", "asus", "lenovo", "dell", "hp", "acer", "matebook"]):
                c_name = "Noutbuklar"
            elif any(k in lower_name for k in ["iphone", "ayfon", "samsung", "galaxy", "redmi", "xiaomi", "smartfon", "pixel", "honor", "poco"]):
                c_name = "Smartfonlar"
            elif any(k in lower_name for k in ["chexol", "case", "kabel", "cable", "adapter", "blok", "zaryadka", "remeshok", "steklo"]):
                c_name = "Aksessuarlar"

            # 2-BOSQICH: Nomida to'liq chiqmasa, tavsif matni bo'yicha aniqlash
            elif any(k in full_search for k in ["watch", "soat", "iwatch", "⌚", "remeshok", "apple watch"]):
                c_name = "Aqlli soatlar"
            elif any(k in full_search for k in ["airpods", "quloqchin", "naushnik", "audio", "headphone", "buds"]):
                c_name = "Quloqchinlar va Audio"
            elif any(k in full_search for k in ["macbook", "noutbuk", "laptop", "macos", "m1 pro", "m2 pro", "m3 pro", "m4 pro", "retina"]):
                c_name = "Noutbuklar"
            elif any(k in full_search for k in ["iphone", "ayfon", "samsung", "galaxy", "redmi", "xiaomi", "smartfon", "imei", "pixel"]):
                c_name = "Smartfonlar"
            else:
                c_name = "Smartfonlar"

            c_id = await self.fetchval("SELECT id FROM categories WHERE name = $1 LIMIT 1;", c_name)
            category_id = c_id if c_id else 1

        existing = await self.get_product_by_channel_post(channel_id, message_id)

        if existing:
            # Agar oldinroq admin tasdiqlagan bo'lsa, active holat saqlanadi
            active_val = existing.get("is_active", 0) if (is_active is None or is_active == 0) else is_active
            avail_val = 1 if active_val == 1 else 0
            await self.execute("""
                UPDATE products 
                SET category_id = $1, name = $2, description = $3, price = $4, 
                    image_url = COALESCE(NULLIF($5::text, ''), image_url),
                    post_url = $6,
                    media_group_id = COALESCE(NULLIF($7::text, ''), media_group_id),
                    photo_file_id = COALESCE(NULLIF($8::text, ''), photo_file_id),
                    gallery_images = COALESCE(NULLIF($9::text, ''), gallery_images),
                    is_active = $10, is_available = $11
                WHERE channel_id = $12 AND message_id = $13;
            """, category_id, name, description, price, image_url or "", post_url, media_group_id, photo_file_id, gallery_images, active_val, avail_val, str(channel_id), int(message_id))
            return existing['id']
        else:
            new_active = is_active if is_active is not None else 0
            new_avail = 1 if new_active == 1 else 0
            prod_id = await self.fetchval("""
                INSERT INTO products (
                    category_id, name, description, price, image_url, 
                    channel_id, message_id, media_group_id, post_url, 
                    photo_file_id, gallery_images,
                    views_count, is_active, is_available
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, 0, $12, $13)
                RETURNING id;
            """, category_id, name, description, price, image_url or "", str(channel_id), int(message_id), media_group_id, post_url, photo_file_id, gallery_images, new_active, new_avail)
            return prod_id

    async def deactivate_product_by_channel_post(self, channel_id: str, message_id: int):
        await self.execute("""
            UPDATE products 
            SET is_active = 0, is_available = 0 
            WHERE channel_id = $1 AND message_id = $2;
        """, str(channel_id), int(message_id))

    async def get_active_channel_products(self) -> List[Dict[str, Any]]:
        return await self.fetch("""
            SELECT id, channel_id, message_id, name, post_url 
            FROM products 
            WHERE is_active = 1 AND message_id IS NOT NULL;
        """)

    async def deactivate_products_by_ids(self, product_ids: List[int]):
        if not product_ids:
            return
        await self.execute("""
            UPDATE products 
            SET is_active = 0, is_available = 0 
            WHERE id = ANY($1::int[]);
        """, product_ids)

    async def activate_product_by_id(self, product_id: int, is_discount: Optional[int] = None):
        if is_discount is not None:
            await self.execute("UPDATE products SET is_active = 1, is_available = 1, is_discount = $1 WHERE id = $2;", is_discount, product_id)
        else:
            await self.execute("UPDATE products SET is_active = 1, is_available = 1 WHERE id = $1;", product_id)

    async def activate_product_as_discount(self, product_id: int):
        await self.execute("UPDATE products SET is_active = 1, is_available = 1, is_discount = 1 WHERE id = $1;", product_id)

    async def set_product_discount(self, product_id: int, is_discount: int = 1):
        await self.execute("UPDATE products SET is_discount = $1 WHERE id = $2;", is_discount, product_id)

    async def get_discount_products(self) -> List[Dict[str, Any]]:
        return await self.fetch("""
            SELECT p.*, c.name as category_name
            FROM products p
            LEFT JOIN categories c ON p.category_id = c.id
            WHERE p.is_active = 1 AND p.is_discount = 1
            ORDER BY p.id DESC;
        """)

    async def deactivate_product_by_id(self, product_id: int):
        await self.execute("UPDATE products SET is_active = 0, is_available = 0 WHERE id = $1;", product_id)

    async def update_product_image(self, product_id: int, image_url: str):
        await self.execute("UPDATE products SET image_url = $1 WHERE id = $2;", image_url, product_id)

    async def update_product_gallery(self, product_id: int, image_url: str, gallery_images: List[str]):
        gal_json = json.dumps(gallery_images) if gallery_images else None
        await self.execute("""
            UPDATE products 
            SET image_url = $1, gallery_images = $2 
            WHERE id = $3;
        """, image_url, gal_json, product_id)

    async def add_product(self, category_id: int, name: str, description: str, price: int, image_url: str, photo_file_id: Optional[str] = None):
        await self.execute("""
            INSERT INTO products (category_id, name, description, price, image_url, photo_file_id, is_active, is_available)
            VALUES ($1, $2, $3, $4, $5, $6, 1, 1);
        """, category_id, name, description, price, image_url, photo_file_id)

    # =========================================================================
    # SAVAT (CART)
    # =========================================================================
    async def add_to_cart(self, user_id: int, product_id: int, quantity: int = 1):
        await self.execute("""
            INSERT INTO cart (user_id, product_id, quantity)
            VALUES ($1, $2, $3)
            ON CONFLICT(user_id, product_id) 
            DO UPDATE SET quantity = cart.quantity + EXCLUDED.quantity;
        """, user_id, product_id, quantity)

    async def get_cart(self, user_id: int) -> List[Dict[str, Any]]:
        return await self.fetch("""
            SELECT c.product_id, c.quantity, p.name, p.price, p.image_url, (c.quantity * p.price) as subtotal
            FROM cart c
            JOIN products p ON c.product_id = p.id
            WHERE c.user_id = $1
            ORDER BY c.id ASC;
        """, user_id)

    async def update_cart_item(self, user_id: int, product_id: int, change: int):
        row = await self.fetchrow("SELECT quantity FROM cart WHERE user_id = $1 AND product_id = $2;", user_id, product_id)
        if not row:
            return
        new_qty = row["quantity"] + change
        if new_qty <= 0:
            await self.execute("DELETE FROM cart WHERE user_id = $1 AND product_id = $2;", user_id, product_id)
        else:
            await self.execute("UPDATE cart SET quantity = $1 WHERE user_id = $2 AND product_id = $3;", new_qty, user_id, product_id)

    async def remove_from_cart(self, user_id: int, product_id: int):
        await self.execute("DELETE FROM cart WHERE user_id = $1 AND product_id = $2;", user_id, product_id)

    async def clear_cart(self, user_id: int):
        await self.execute("DELETE FROM cart WHERE user_id = $1;", user_id)

    # =========================================================================
    # BUYURTMALAR (ORDERS)
    # =========================================================================
    async def create_order(
        self,
        user_id: int,
        full_name: str,
        phone: str,
        address: str,
        payment_method: str,
        total_amount: int,
        items: List[Dict[str, Any]]
    ) -> int:
        """Tranzaksiya orqali buyurtma yaratish va savatni tozalash"""
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                order_id = await conn.fetchval("""
                    INSERT INTO orders (user_id, full_name, phone, address, payment_method, total_amount)
                    VALUES ($1, $2, $3, $4, $5, $6)
                    RETURNING id;
                """, user_id, full_name, phone, address, payment_method, total_amount)

                for item in items:
                    await conn.execute("""
                        INSERT INTO order_items (order_id, product_name, price, quantity)
                        VALUES ($1, $2, $3, $4);
                    """, order_id, item['name'], item['price'], item['quantity'])

                await conn.execute("DELETE FROM cart WHERE user_id = $1;", user_id)
                return order_id

    async def get_user_orders(self, user_id: int) -> List[Dict[str, Any]]:
        orders = await self.fetch("""
            SELECT * FROM orders 
            WHERE user_id = $1 
            ORDER BY id DESC LIMIT 10;
        """, user_id)
        for order in orders:
            items_rows = await self.fetch("SELECT * FROM order_items WHERE order_id = $1;", order['id'])
            order['items'] = items_rows
        return orders

    async def get_order(self, order_id: int) -> Optional[Dict[str, Any]]:
        order = await self.fetchrow("SELECT * FROM orders WHERE id = $1;", order_id)
        if not order:
            return None
        items_rows = await self.fetch("SELECT * FROM order_items WHERE order_id = $1;", order_id)
        order['items'] = items_rows
        return order

    async def get_all_orders(self, limit: int = 15) -> List[Dict[str, Any]]:
        orders = await self.fetch("SELECT * FROM orders ORDER BY id DESC LIMIT $1;", limit)
        for order in orders:
            items_rows = await self.fetch("SELECT * FROM order_items WHERE order_id = $1;", order['id'])
            order['items'] = items_rows
        return orders

    async def update_order_status(self, order_id: int, status: str):
        await self.execute("UPDATE orders SET status = $1 WHERE id = $2;", status, order_id)

    async def get_stats(self) -> Dict[str, Any]:
        """Admin panel uchun umumiy statistika"""
        users_count = await self.fetchval("SELECT COUNT(*) FROM users;") or 0
        row_orders = await self.fetchrow("SELECT COUNT(*), COALESCE(SUM(total_amount), 0) FROM orders;")
        orders_count = row_orders["count"] if row_orders else 0
        total_revenue = row_orders["coalesce"] if row_orders else 0
        products_count = await self.fetchval("SELECT COUNT(*) FROM products WHERE is_active = 1;") or 0

        return {
            "users_count": users_count,
            "orders_count": orders_count,
            "total_revenue": total_revenue,
            "products_count": products_count
        }
