import os
import json
import logging
from datetime import datetime, date
from typing import List, Dict, Any, Optional

try:
    import asyncpg
except ImportError:
    asyncpg = None

try:
    import aiosqlite
except ImportError:
    aiosqlite = None

logger = logging.getLogger("Database")

class Database:
    """
    Ma'lumotlar bazasi klassi:
    - Neon (PostgreSQL) bazasini asyncpg orqali to'liq qo'llab-quvvatlaydi.
    - DATABASE_URL ko'rsatilmaganda SQLite (aiosqlite) orqali zaxira rejimida ishlaydi.
    """
    def __init__(self, db_path: Optional[str] = None, database_url: Optional[str] = None):
        # Parametrlarni aniqlash
        if db_path and (db_path.startswith("postgresql://") or db_path.startswith("postgres://")):
            database_url = db_path
            db_path = "demostore.db"

        self.database_url = (database_url or os.getenv("DATABASE_URL", "")).strip()
        self.db_path = db_path or os.getenv("DATABASE_PATH", "demostore.db").strip()

        # Neon / PostgreSQL rejimi yoki SQLite
        self.is_postgres = bool(
            self.database_url and (
                self.database_url.startswith("postgresql://") or 
                self.database_url.startswith("postgres://")
            )
        )
        self.pool: Optional[Any] = None

    @staticmethod
    def _row_to_dict(row: Any) -> Optional[Dict[str, Any]]:
        """Row/Record ni xavfsiz JSON-mos dict ga o'girish"""
        if row is None:
            return None
        d = dict(row)
        for k, v in d.items():
            if isinstance(v, (datetime, date)):
                d[k] = v.isoformat()
        return d

    async def init_db(self):
        """Ma'lumotlar bazasini initsializatsiya qilish va kerakli jadvallarni avtomatik yaratish"""
        if self.is_postgres:
            await self._init_postgres()
        else:
            await self._init_sqlite()

    async def _init_postgres(self):
        """Neon PostgreSQL jadvallarini yaratish va indekslarni sozlash"""
        if not asyncpg:
            raise ImportError("asyncpg kutubxonasi o'rnatilmagan! Iltimos, 'pip install asyncpg' buyrug'ini ishga tushiring.")

        logger.info("Neon PostgreSQL ulanish puli (connection pool) yaratilmoqda...")

        # Neon SSL sozlamalari
        ssl_arg = None
        if "sslmode=" in self.database_url:
            ssl_arg = None  # asyncpg DSN dagi sslmode parametrini avtomatik taniydi
        elif "neon.tech" in self.database_url or not any(loc in self.database_url for loc in ["localhost", "127.0.0.1"]):
            ssl_arg = "require"

        self.pool = await asyncpg.create_pool(
            dsn=self.database_url,
            min_size=1,
            max_size=10,
            ssl=ssl_arg,
            command_timeout=30.0,
            statement_cache_size=0,
            max_cached_statement_lifetime=0
        )

        async with self.pool.acquire() as conn:
            # 1. Foydalanuvchilar jadvali
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id BIGINT PRIMARY KEY,
                    full_name TEXT,
                    username TEXT,
                    phone TEXT,
                    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # 2. Kategoriyalar jadvali
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS categories (
                    id SERIAL PRIMARY KEY,
                    name TEXT NOT NULL UNIQUE,
                    icon TEXT DEFAULT 'folder'
                );
            """)

            # 3. Mahsulotlar jadvali
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
            """)

            # 4. Savat jadvali
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS cart (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT REFERENCES users(user_id) ON DELETE CASCADE,
                    product_id INTEGER REFERENCES products(id) ON DELETE CASCADE,
                    quantity INTEGER DEFAULT 1,
                    CONSTRAINT unique_user_product UNIQUE (user_id, product_id)
                );
            """)

            # 5. Buyurtmalar jadvali
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

            # 6. Buyurtma ichidagi mahsulotlar jadvali
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS order_items (
                    id SERIAL PRIMARY KEY,
                    order_id INTEGER REFERENCES orders(id) ON DELETE CASCADE,
                    product_name TEXT,
                    price INTEGER,
                    quantity INTEGER
                );
            """)

            # Indekslar (tezkor qidiruv va filtrlash uchun)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_products_category ON products(category_id);
                CREATE INDEX IF NOT EXISTS idx_products_channel_msg ON products(channel_id, message_id);
                CREATE INDEX IF NOT EXISTS idx_products_active ON products(is_active, is_available);
                CREATE INDEX IF NOT EXISTS idx_cart_user ON cart(user_id);
                CREATE INDEX IF NOT EXISTS idx_orders_user ON orders(user_id);
            """)

            # Boshlang'ich kategoriyalarni tekshirib kiritish
            cat_count = await conn.fetchval("SELECT COUNT(*) FROM categories;")
            if cat_count == 0:
                categories = [
                    ("Noutbuklar", "laptop"),
                    ("Smartfonlar", "smartphone"),
                    ("Quloqchinlar va Audio", "headphones"),
                    ("Aqlli soatlar", "watch"),
                    ("Aksessuarlar", "plug")
                ]
                for name, icon in categories:
                    await conn.execute(
                        "INSERT INTO categories (name, icon) VALUES ($1, $2) ON CONFLICT (name) DO NOTHING;",
                        name, icon
                    )

        logger.info("Neon PostgreSQL jadvallari va migratsiyalari muvaffaqiyatli tayyorlandi!")

    async def _init_sqlite(self):
        """SQLite ma'lumotlar bazasi jadvallarini yaratish va boshlang'ich ma'lumotlarni kiritish"""
        if not aiosqlite:
            raise ImportError("aiosqlite kutubxonasi o'rnatilmagan!")

        async with aiosqlite.connect(self.db_path, timeout=30.0) as db:
            await db.execute("PRAGMA journal_mode = WAL;")
            await db.execute("PRAGMA busy_timeout = 30000;")
            await db.execute("PRAGMA foreign_keys = ON;")
            
            await db.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    full_name TEXT,
                    username TEXT,
                    phone TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            await db.execute("""
                CREATE TABLE IF NOT EXISTS categories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    icon TEXT DEFAULT 'folder'
                );
            """)

            await db.execute("""
                CREATE TABLE IF NOT EXISTS products (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category_id INTEGER REFERENCES categories(id) ON DELETE CASCADE,
                    name TEXT NOT NULL,
                    description TEXT,
                    price INTEGER NOT NULL,
                    image_url TEXT,
                    gallery_images TEXT,
                    photo_file_id TEXT,
                    is_available INTEGER DEFAULT 1,
                    channel_id TEXT,
                    message_id INTEGER,
                    media_group_id TEXT,
                    post_url TEXT,
                    views_count INTEGER DEFAULT 0,
                    is_active INTEGER DEFAULT 1
                );
            """)

            await db.execute("""
                CREATE TABLE IF NOT EXISTS cart (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER REFERENCES users(user_id) ON DELETE CASCADE,
                    product_id INTEGER REFERENCES products(id) ON DELETE CASCADE,
                    quantity INTEGER DEFAULT 1,
                    UNIQUE(user_id, product_id)
                );
            """)

            await db.execute("""
                CREATE TABLE IF NOT EXISTS orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER REFERENCES users(user_id),
                    full_name TEXT,
                    phone TEXT,
                    address TEXT,
                    payment_method TEXT,
                    total_amount INTEGER,
                    status TEXT DEFAULT 'Yangi',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            await db.execute("""
                CREATE TABLE IF NOT EXISTS order_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_id INTEGER REFERENCES orders(id) ON DELETE CASCADE,
                    product_name TEXT,
                    price INTEGER,
                    quantity INTEGER
                );
            """)

            await db.commit()

            cursor = await db.execute("PRAGMA table_info(products);")
            columns = [row[1] for row in await cursor.fetchall()]
            new_columns = {
                "gallery_images": "TEXT",
                "photo_file_id": "TEXT",
                "channel_id": "TEXT",
                "message_id": "INTEGER",
                "media_group_id": "TEXT",
                "post_url": "TEXT",
                "views_count": "INTEGER DEFAULT 0",
                "is_active": "INTEGER DEFAULT 1"
            }
            for col, col_type in new_columns.items():
                if col not in columns:
                    try:
                        await db.execute(f"ALTER TABLE products ADD COLUMN {col} {col_type};")
                    except Exception:
                        pass
            await db.commit()

            cursor = await db.execute("SELECT COUNT(*) FROM categories;")
            count = (await cursor.fetchone())[0]
            if count == 0:
                categories = [
                    ("Noutbuklar", "laptop"),
                    ("Smartfonlar", "smartphone"),
                    ("Quloqchinlar va Audio", "headphones"),
                    ("Aqlli soatlar", "watch"),
                    ("Aksessuarlar", "plug")
                ]
                for name, icon in categories:
                    await db.execute("INSERT INTO categories (name, icon) VALUES (?, ?);", (name, icon))
                await db.commit()

    async def close(self):
        """Baza ulanishini to'xtatish"""
        if self.is_postgres and self.pool:
            await self.pool.close()

    # --- User operations ---
    async def add_user(self, user_id: int, full_name: str, username: Optional[str] = None):
        if self.is_postgres:
            await self.pool.execute("""
                INSERT INTO users (user_id, full_name, username) 
                VALUES ($1, $2, $3)
                ON CONFLICT(user_id) DO UPDATE SET full_name = EXCLUDED.full_name, username = EXCLUDED.username;
            """, user_id, full_name, username)
        else:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    INSERT INTO users (user_id, full_name, username) 
                    VALUES (?, ?, ?)
                    ON CONFLICT(user_id) DO UPDATE SET full_name = excluded.full_name, username = excluded.username;
                """, (user_id, full_name, username))
                await db.commit()

    async def update_user_phone(self, user_id: int, phone: str):
        if self.is_postgres:
            await self.pool.execute("UPDATE users SET phone = $1 WHERE user_id = $2;", phone, user_id)
        else:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("UPDATE users SET phone = ? WHERE user_id = ?;", (phone, user_id))
                await db.commit()

    async def get_user(self, user_id: int) -> Optional[Dict[str, Any]]:
        if self.is_postgres:
            row = await self.pool.fetchrow("SELECT * FROM users WHERE user_id = $1;", user_id)
            return self._row_to_dict(row)
        else:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute("SELECT * FROM users WHERE user_id = ?;", (user_id,)) as cursor:
                    row = await cursor.fetchone()
                    return self._row_to_dict(row)

    async def get_users_count(self) -> int:
        if self.is_postgres:
            return (await self.pool.fetchval("SELECT COUNT(*) FROM users;")) or 0
        else:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute("SELECT COUNT(*) FROM users;") as cursor:
                    return (await cursor.fetchone())[0]

    async def get_all_user_ids(self) -> List[int]:
        if self.is_postgres:
            rows = await self.pool.fetch("SELECT user_id FROM users;")
            return [r["user_id"] for r in rows]
        else:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute("SELECT user_id FROM users;") as cursor:
                    rows = await cursor.fetchall()
                    return [r[0] for r in rows]

    # --- Category operations ---
    async def get_categories(self) -> List[Dict[str, Any]]:
        if self.is_postgres:
            rows = await self.pool.fetch("SELECT * FROM categories ORDER BY id ASC;")
            return [self._row_to_dict(r) for r in rows]
        else:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute("SELECT * FROM categories ORDER BY id ASC;") as cursor:
                    rows = await cursor.fetchall()
                    return [self._row_to_dict(r) for r in rows]

    async def get_category(self, category_id: int) -> Optional[Dict[str, Any]]:
        if self.is_postgres:
            row = await self.pool.fetchrow("SELECT * FROM categories WHERE id = $1;", category_id)
            return self._row_to_dict(row)
        else:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute("SELECT * FROM categories WHERE id = ?;", (category_id,)) as cursor:
                    row = await cursor.fetchone()
                    return self._row_to_dict(row)

    # --- Product operations ---
    async def get_products_by_category(self, category_id: int) -> List[Dict[str, Any]]:
        if self.is_postgres:
            rows = await self.pool.fetch("""
                SELECT * FROM products 
                WHERE category_id = $1 AND is_available = 1 AND is_active = 1 AND message_id IS NOT NULL
                ORDER BY id DESC;
            """, category_id)
            return [self._row_to_dict(r) for r in rows]
        else:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute("""
                    SELECT * FROM products 
                    WHERE category_id = ? AND is_available = 1 AND is_active = 1 AND message_id IS NOT NULL
                    ORDER BY id DESC;
                """, (category_id,)) as cursor:
                    rows = await cursor.fetchall()
                    return [self._row_to_dict(r) for r in rows]

    async def get_active_products(
        self,
        category_id: Optional[int] = None,
        sort_by: str = "default",
        search: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Web App va katalog uchun saralangan va faqat kanalda mavjud mahsulotlarni olish"""
        if self.is_postgres:
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

            if search and search.strip():
                pattern = f"%{search.strip()}%"
                params.append(pattern)
                p_idx = len(params)
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

            rows = await self.pool.fetch(query, *params)
            return [self._row_to_dict(r) for r in rows]
        else:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                query = "SELECT p.*, c.name as category_name FROM products p LEFT JOIN categories c ON p.category_id = c.id WHERE p.is_active = 1 AND p.is_available = 1 AND p.message_id IS NOT NULL"
                params: List[Any] = []

                if category_id is not None and category_id > 0:
                    query += " AND p.category_id = ?"
                    params.append(category_id)

                if search and search.strip():
                    pattern = f"%{search.strip()}%"
                    query += " AND (p.name LIKE ? OR p.description LIKE ?)"
                    params.extend([pattern, pattern])

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

                async with db.execute(query, params) as cursor:
                    rows = await cursor.fetchall()
                    return [self._row_to_dict(r) for r in rows]

    async def get_product(self, product_id: int) -> Optional[Dict[str, Any]]:
        if self.is_postgres:
            row = await self.pool.fetchrow("SELECT * FROM products WHERE id = $1;", product_id)
            return self._row_to_dict(row)
        else:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute("SELECT * FROM products WHERE id = ?;", (product_id,)) as cursor:
                    row = await cursor.fetchone()
                    return self._row_to_dict(row)

    async def get_products_count(self) -> int:
        if self.is_postgres:
            return (await self.pool.fetchval("SELECT COUNT(*) FROM products WHERE is_active = 1 AND message_id IS NOT NULL;")) or 0
        else:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute("SELECT COUNT(*) FROM products WHERE is_active = 1 AND message_id IS NOT NULL;") as cursor:
                    return (await cursor.fetchone())[0]

    async def search_products(self, query: str) -> List[Dict[str, Any]]:
        pattern = f"%{query.strip()}%"
        if self.is_postgres:
            rows = await self.pool.fetch("""
                SELECT * FROM products 
                WHERE (name ILIKE $1 OR description ILIKE $1) AND is_available = 1 AND is_active = 1 AND message_id IS NOT NULL
                LIMIT 20;
            """, pattern)
            return [self._row_to_dict(r) for r in rows]
        else:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute("""
                    SELECT * FROM products 
                    WHERE (name LIKE ? OR description LIKE ?) AND is_available = 1 AND is_active = 1 AND message_id IS NOT NULL
                    LIMIT 20;
                """, (pattern, pattern)) as cursor:
                    rows = await cursor.fetchall()
                    return [self._row_to_dict(r) for r in rows]

    async def increment_views(self, product_id: int) -> int:
        """Kanalga o'tish (views_count) sonini +1 oshirish"""
        if self.is_postgres:
            new_views = await self.pool.fetchval("""
                UPDATE products 
                SET views_count = COALESCE(views_count, 0) + 1 
                WHERE id = $1 
                RETURNING views_count;
            """, product_id)
            return new_views or 0
        else:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    "UPDATE products SET views_count = COALESCE(views_count, 0) + 1 WHERE id = ?;",
                    (product_id,)
                )
                await db.commit()
                async with db.execute("SELECT views_count FROM products WHERE id = ?;", (product_id,)) as cursor:
                    row = await cursor.fetchone()
                    return row[0] if row else 0

    async def get_top_viewed_products(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Eng ko'p kanalga o'tilgan (Top) tovarlar ro'yxati"""
        if self.is_postgres:
            rows = await self.pool.fetch("""
                SELECT id, name, price, views_count, post_url, image_url 
                FROM products 
                WHERE views_count > 0 
                ORDER BY views_count DESC, id DESC 
                LIMIT $1;
            """, limit)
            return [self._row_to_dict(r) for r in rows]
        else:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute("""
                    SELECT id, name, price, views_count, post_url, image_url 
                    FROM products 
                    WHERE views_count > 0 
                    ORDER BY views_count DESC, id DESC 
                    LIMIT ?;
                """, (limit,)) as cursor:
                    rows = await cursor.fetchall()
                    return [self._row_to_dict(r) for r in rows]

    # --- Channel Parser DB Operations ---
    async def get_product_by_channel_post(self, channel_id: str, message_id: int) -> Optional[Dict[str, Any]]:
        if self.is_postgres:
            row = await self.pool.fetchrow("""
                SELECT * FROM products 
                WHERE channel_id = $1 AND message_id = $2;
            """, str(channel_id), int(message_id))
            return self._row_to_dict(row)
        else:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute("""
                    SELECT * FROM products 
                    WHERE channel_id = ? AND message_id = ?;
                """, (str(channel_id), int(message_id))) as cursor:
                    row = await cursor.fetchone()
                    return self._row_to_dict(row)

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
        gallery_images: Optional[str] = None
    ) -> int:
        """Kanal postidan mahsulotni qo'shish yoki yangilash"""
        if not category_id:
            full_search = f"{name} {description}".lower()
            if any(k in full_search for k in ["macbook", "noutbuk", "laptop", "asus", "thinkpad", "lenovo", "dell", "hp"]):
                c_name = "Noutbuklar"
            elif any(k in full_search for k in ["iphone", "samsung", "redmi", "xiaomi", "smartfon", "telefon", "galaxy"]):
                c_name = "Smartfonlar"
            elif any(k in full_search for k in ["airpods", "quloqchin", "audio", "naushnik", "sony", "headphone"]):
                c_name = "Quloqchinlar va Audio"
            elif any(k in full_search for k in ["watch", "soat"]):
                c_name = "Aqlli soatlar"
            else:
                c_name = "Aksessuarlar"

            if self.is_postgres:
                c_id = await self.pool.fetchval("SELECT id FROM categories WHERE name = $1 LIMIT 1;", c_name)
                category_id = c_id if c_id else 1
            else:
                async with aiosqlite.connect(self.db_path) as db:
                    c_cur = await db.execute("SELECT id FROM categories WHERE name = ? LIMIT 1;", (c_name,))
                    c_row = await c_cur.fetchone()
                    category_id = c_row[0] if c_row else 1

        existing = await self.get_product_by_channel_post(channel_id, message_id)

        if self.is_postgres:
            if existing:
                await self.pool.execute("""
                    UPDATE products 
                    SET category_id = $1, name = $2, description = $3, price = $4, 
                        image_url = CASE WHEN $5 != '' THEN $5 ELSE image_url END,
                        post_url = $6, media_group_id = $7,
                        photo_file_id = CASE WHEN $8 IS NOT NULL AND $8 != '' THEN $8 ELSE photo_file_id END,
                        gallery_images = CASE WHEN $9 IS NOT NULL AND $9 != '' THEN $9 ELSE gallery_images END,
                        is_active = 1, is_available = 1
                    WHERE channel_id = $10 AND message_id = $11;
                """, category_id, name, description, price, image_url, post_url, media_group_id, photo_file_id, gallery_images, str(channel_id), int(message_id))
                return existing['id']
            else:
                prod_id = await self.pool.fetchval("""
                    INSERT INTO products (
                        category_id, name, description, price, image_url, 
                        channel_id, message_id, media_group_id, post_url, 
                        photo_file_id, gallery_images,
                        views_count, is_active, is_available
                    )
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, 0, 1, 1)
                    RETURNING id;
                """, category_id, name, description, price, image_url, str(channel_id), int(message_id), media_group_id, post_url, photo_file_id, gallery_images)
                return prod_id
        else:
            async with aiosqlite.connect(self.db_path) as db:
                if existing:
                    await db.execute("""
                        UPDATE products 
                        SET category_id = ?, name = ?, description = ?, price = ?, 
                            image_url = CASE WHEN ? != '' THEN ? ELSE image_url END,
                            post_url = ?, media_group_id = ?,
                            photo_file_id = CASE WHEN ? IS NOT NULL AND ? != '' THEN ? ELSE photo_file_id END,
                            gallery_images = CASE WHEN ? IS NOT NULL AND ? != '' THEN ? ELSE gallery_images END,
                            is_active = 1, is_available = 1
                        WHERE channel_id = ? AND message_id = ?;
                    """, (
                        category_id, name, description, price, 
                        image_url, image_url,
                        post_url, media_group_id,
                        photo_file_id, photo_file_id, photo_file_id, 
                        gallery_images, gallery_images, gallery_images,
                        str(channel_id), int(message_id)
                    ))
                    await db.commit()
                    return existing['id']
                else:
                    cur = await db.execute("""
                        INSERT INTO products (
                            category_id, name, description, price, image_url, 
                            channel_id, message_id, media_group_id, post_url, 
                            photo_file_id, gallery_images,
                            views_count, is_active, is_available
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 1, 1);
                    """, (
                        category_id, name, description, price, image_url,
                        str(channel_id), int(message_id), media_group_id, post_url,
                        photo_file_id, gallery_images
                    ))
                    await db.commit()
                    return cur.lastrowid

    async def deactivate_product_by_channel_post(self, channel_id: str, message_id: int):
        """Kanalda post o'chirilganda yoki sotilganda mahsulotni nofaol qilish (is_active=0)"""
        if self.is_postgres:
            await self.pool.execute("""
                UPDATE products SET is_active = 0, is_available = 0 
                WHERE channel_id = $1 AND message_id = $2;
            """, str(channel_id), int(message_id))
        else:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    UPDATE products SET is_active = 0, is_available = 0 
                    WHERE channel_id = ? AND message_id = ?;
                """, (str(channel_id), int(message_id)))
                await db.commit()

    async def get_active_channel_products(self) -> List[Dict[str, Any]]:
        """Kanalga ulangan va faol mahsulotlar ro'yxatini olish"""
        if self.is_postgres:
            rows = await self.pool.fetch("""
                SELECT id, channel_id, message_id, post_url, name 
                FROM products 
                WHERE is_active = 1 AND message_id IS NOT NULL;
            """)
            return [self._row_to_dict(r) for r in rows]
        else:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute("""
                    SELECT id, channel_id, message_id, post_url, name 
                    FROM products 
                    WHERE is_active = 1 AND message_id IS NOT NULL;
                """) as cursor:
                    rows = await cursor.fetchall()
                    return [self._row_to_dict(r) for r in rows]

    async def deactivate_products_by_ids(self, product_ids: List[int]):
        """O'chirilgan mahsulotlarni bir vaqtning o'zida nofaol qilish (is_active=0)"""
        if not product_ids:
            return
        if self.is_postgres:
            placeholders = ", ".join(f"${i+1}" for i in range(len(product_ids)))
            await self.pool.execute(
                f"UPDATE products SET is_active = 0, is_available = 0 WHERE id IN ({placeholders});",
                *product_ids
            )
        else:
            async with aiosqlite.connect(self.db_path) as db:
                placeholders = ",".join("?" for _ in product_ids)
                await db.execute(f"""
                    UPDATE products 
                    SET is_active = 0, is_available = 0 
                    WHERE id IN ({placeholders});
                """, product_ids)
                await db.commit()

    async def update_product_image(self, product_id: int, image_url: str):
        """Mahsulot rasmi manzilini yangilash (fon tozalangandan so'ng)"""
        gallery = json.dumps([image_url])
        if self.is_postgres:
            await self.pool.execute("""
                UPDATE products 
                SET image_url = $1, 
                    gallery_images = CASE WHEN gallery_images IS NULL OR gallery_images = '' OR gallery_images = '[]' THEN $2 ELSE gallery_images END 
                WHERE id = $3;
            """, image_url, gallery, product_id)
        else:
            async with aiosqlite.connect(self.db_path, timeout=30.0) as db:
                await db.execute("""
                    UPDATE products 
                    SET image_url = ?, 
                        gallery_images = CASE WHEN gallery_images IS NULL OR gallery_images = '' OR gallery_images = '[]' THEN ? ELSE gallery_images END 
                    WHERE id = ?;
                """, (image_url, gallery, product_id))
                await db.commit()

    async def update_product_gallery(self, product_id: int, image_url: str, gallery_images: List[str]):
        """Mahsulot asosiy rasmi va barcha galereya rasmlarini yangilash"""
        gallery_json = json.dumps(gallery_images)
        if self.is_postgres:
            await self.pool.execute("""
                UPDATE products 
                SET image_url = $1, gallery_images = $2 
                WHERE id = $3;
            """, image_url, gallery_json, product_id)
        else:
            async with aiosqlite.connect(self.db_path, timeout=30.0) as db:
                await db.execute("""
                    UPDATE products 
                    SET image_url = ?, gallery_images = ? 
                    WHERE id = ?;
                """, (image_url, gallery_json, product_id))
                await db.commit()

    async def add_product(self, category_id: int, name: str, description: str, price: int, image_url: str, photo_file_id: Optional[str] = None):
        if self.is_postgres:
            await self.pool.execute("""
                INSERT INTO products (category_id, name, description, price, image_url, photo_file_id, is_active, is_available)
                VALUES ($1, $2, $3, $4, $5, $6, 1, 1);
            """, category_id, name, description, price, image_url, photo_file_id)
        else:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    INSERT INTO products (category_id, name, description, price, image_url, photo_file_id, is_active, is_available)
                    VALUES (?, ?, ?, ?, ?, ?, 1, 1);
                """, (category_id, name, description, price, image_url, photo_file_id))
                await db.commit()

    # --- Cart operations ---
    async def add_to_cart(self, user_id: int, product_id: int, quantity: int = 1):
        if self.is_postgres:
            await self.pool.execute("""
                INSERT INTO cart (user_id, product_id, quantity)
                VALUES ($1, $2, $3)
                ON CONFLICT(user_id, product_id) 
                DO UPDATE SET quantity = cart.quantity + EXCLUDED.quantity;
            """, user_id, product_id, quantity)
        else:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    INSERT INTO cart (user_id, product_id, quantity)
                    VALUES (?, ?, ?)
                    ON CONFLICT(user_id, product_id) 
                    DO UPDATE SET quantity = cart.quantity + excluded.quantity;
                """, (user_id, product_id, quantity))
                await db.commit()

    async def get_cart(self, user_id: int) -> List[Dict[str, Any]]:
        if self.is_postgres:
            rows = await self.pool.fetch("""
                SELECT c.product_id, c.quantity, p.name, p.price, p.image_url, (c.quantity * p.price) as subtotal
                FROM cart c
                JOIN products p ON c.product_id = p.id
                WHERE c.user_id = $1
                ORDER BY c.id ASC;
            """, user_id)
            return [self._row_to_dict(r) for r in rows]
        else:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute("""
                    SELECT c.product_id, c.quantity, p.name, p.price, p.image_url, (c.quantity * p.price) as subtotal
                    FROM cart c
                    JOIN products p ON c.product_id = p.id
                    WHERE c.user_id = ?
                    ORDER BY c.id ASC;
                """, (user_id,)) as cursor:
                    rows = await cursor.fetchall()
                    return [self._row_to_dict(r) for r in rows]

    async def update_cart_item(self, user_id: int, product_id: int, change: int):
        if self.is_postgres:
            row = await self.pool.fetchrow("SELECT quantity FROM cart WHERE user_id = $1 AND product_id = $2;", user_id, product_id)
            if not row:
                return
            new_qty = row["quantity"] + change
            if new_qty <= 0:
                await self.pool.execute("DELETE FROM cart WHERE user_id = $1 AND product_id = $2;", user_id, product_id)
            else:
                await self.pool.execute("UPDATE cart SET quantity = $1 WHERE user_id = $2 AND product_id = $3;", new_qty, user_id, product_id)
        else:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute("SELECT quantity FROM cart WHERE user_id = ? AND product_id = ?;", (user_id, product_id))
                row = await cursor.fetchone()
                if not row:
                    return
                new_qty = row[0] + change
                if new_qty <= 0:
                    await db.execute("DELETE FROM cart WHERE user_id = ? AND product_id = ?;", (user_id, product_id))
                else:
                    await db.execute("UPDATE cart SET quantity = ? WHERE user_id = ? AND product_id = ?;", (new_qty, user_id, product_id))
                await db.commit()

    async def remove_from_cart(self, user_id: int, product_id: int):
        if self.is_postgres:
            await self.pool.execute("DELETE FROM cart WHERE user_id = $1 AND product_id = $2;", user_id, product_id)
        else:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("DELETE FROM cart WHERE user_id = ? AND product_id = ?;", (user_id, product_id))
                await db.commit()

    async def clear_cart(self, user_id: int):
        if self.is_postgres:
            await self.pool.execute("DELETE FROM cart WHERE user_id = $1;", user_id)
        else:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("DELETE FROM cart WHERE user_id = ?;", (user_id,))
                await db.commit()

    # --- Order operations ---
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
        if self.is_postgres:
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
        else:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute("""
                    INSERT INTO orders (user_id, full_name, phone, address, payment_method, total_amount)
                    VALUES (?, ?, ?, ?, ?, ?);
                """, (user_id, full_name, phone, address, payment_method, total_amount))
                order_id = cursor.lastrowid

                for item in items:
                    await db.execute("""
                        INSERT INTO order_items (order_id, product_name, price, quantity)
                        VALUES (?, ?, ?, ?);
                    """, (order_id, item['name'], item['price'], item['quantity']))

                await db.execute("DELETE FROM cart WHERE user_id = ?;", (user_id,))
                await db.commit()
                return order_id

    async def get_user_orders(self, user_id: int) -> List[Dict[str, Any]]:
        if self.is_postgres:
            rows = await self.pool.fetch("""
                SELECT * FROM orders 
                WHERE user_id = $1 
                ORDER BY id DESC LIMIT 10;
            """, user_id)
            orders = [self._row_to_dict(r) for r in rows]
            for order in orders:
                items_rows = await self.pool.fetch("SELECT * FROM order_items WHERE order_id = $1;", order['id'])
                order['items'] = [self._row_to_dict(it) for it in items_rows]
            return orders
        else:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute("""
                    SELECT * FROM orders 
                    WHERE user_id = ? 
                    ORDER BY id DESC LIMIT 10;
                """, (user_id,)) as cursor:
                    rows = await cursor.fetchall()
                    orders = [self._row_to_dict(r) for r in rows]

                for order in orders:
                    async with db.execute("SELECT * FROM order_items WHERE order_id = ?;", (order['id'],)) as c_items:
                        order['items'] = [self._row_to_dict(it) for it in await c_items.fetchall()]

                return orders

    async def get_order(self, order_id: int) -> Optional[Dict[str, Any]]:
        if self.is_postgres:
            row = await self.pool.fetchrow("SELECT * FROM orders WHERE id = $1;", order_id)
            if not row:
                return None
            order = self._row_to_dict(row)
            items_rows = await self.pool.fetch("SELECT * FROM order_items WHERE order_id = $1;", order_id)
            order['items'] = [self._row_to_dict(it) for it in items_rows]
            return order
        else:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute("SELECT * FROM orders WHERE id = ?;", (order_id,)) as cursor:
                    row = await cursor.fetchone()
                    if not row:
                        return None
                    order = self._row_to_dict(row)

                async with db.execute("SELECT * FROM order_items WHERE order_id = ?;", (order_id,)) as cursor:
                    order['items'] = [self._row_to_dict(it) for it in await cursor.fetchall()]

                return order

    async def get_all_orders(self, limit: int = 15) -> List[Dict[str, Any]]:
        if self.is_postgres:
            rows = await self.pool.fetch("SELECT * FROM orders ORDER BY id DESC LIMIT $1;", limit)
            orders = [self._row_to_dict(r) for r in rows]
            for order in orders:
                items_rows = await self.pool.fetch("SELECT * FROM order_items WHERE order_id = $1;", order['id'])
                order['items'] = [self._row_to_dict(it) for it in items_rows]
            return orders
        else:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute("SELECT * FROM orders ORDER BY id DESC LIMIT ?;", (limit,)) as cursor:
                    rows = await cursor.fetchall()
                    orders = [self._row_to_dict(r) for r in rows]

                for order in orders:
                    async with db.execute("SELECT * FROM order_items WHERE order_id = ?;", (order['id'],)) as c_items:
                        order['items'] = [self._row_to_dict(it) for it in await c_items.fetchall()]

                return orders

    async def update_order_status(self, order_id: int, status: str):
        if self.is_postgres:
            await self.pool.execute("UPDATE orders SET status = $1 WHERE id = $2;", status, order_id)
        else:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("UPDATE orders SET status = ? WHERE id = ?;", (status, order_id))
                await db.commit()

    async def get_stats(self) -> Dict[str, Any]:
        if self.is_postgres:
            users_count = await self.pool.fetchval("SELECT COUNT(*) FROM users;") or 0
            row_orders = await self.pool.fetchrow("SELECT COUNT(*), COALESCE(SUM(total_amount), 0) FROM orders;")
            orders_count = row_orders[0] if row_orders else 0
            total_revenue = row_orders[1] if row_orders else 0
            products_count = await self.pool.fetchval("SELECT COUNT(*) FROM products WHERE is_active = 1;") or 0

            return {
                "users_count": users_count,
                "orders_count": orders_count,
                "total_revenue": total_revenue,
                "products_count": products_count
            }
        else:
            async with aiosqlite.connect(self.db_path) as db:
                u_cur = await db.execute("SELECT COUNT(*) FROM users;")
                users_count = (await u_cur.fetchone())[0]

                o_cur = await db.execute("SELECT COUNT(*), COALESCE(SUM(total_amount), 0) FROM orders;")
                o_row = await o_cur.fetchone()
                orders_count = o_row[0]
                total_revenue = o_row[1]

                p_cur = await db.execute("SELECT COUNT(*) FROM products WHERE is_active = 1;")
                products_count = (await p_cur.fetchone())[0]

                return {
                    "users_count": users_count,
                    "orders_count": orders_count,
                    "total_revenue": total_revenue,
                    "products_count": products_count
                }
