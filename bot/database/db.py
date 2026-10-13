import aiosqlite
from typing import List, Dict, Any, Optional

class Database:
    def __init__(self, db_path: str):
        self.db_path = db_path

    async def init_db(self):
        """Ma'lumotlar bazasi jadvallarini yaratish va boshlang'ich ma'lumotlarni kiritish"""
        async with aiosqlite.connect(self.db_path, timeout=30.0) as db:
            await db.execute("PRAGMA journal_mode = WAL;")
            await db.execute("PRAGMA busy_timeout = 30000;")
            await db.execute("PRAGMA foreign_keys = ON;")
            
            # Foydalanuvchilar jadvali
            await db.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    full_name TEXT,
                    username TEXT,
                    phone TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # Kategoriyalar jadvali
            await db.execute("""
                CREATE TABLE IF NOT EXISTS categories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    icon TEXT DEFAULT 'folder'
                );
            """)

            # Mahsulotlar jadvali
            await db.execute("""
                CREATE TABLE IF NOT EXISTS products (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category_id INTEGER REFERENCES categories(id) ON DELETE CASCADE,
                    name TEXT NOT NULL,
                    description TEXT,
                    price INTEGER NOT NULL,
                    image_url TEXT,
                    is_available INTEGER DEFAULT 1,
                    channel_id TEXT,
                    message_id INTEGER,
                    media_group_id TEXT,
                    post_url TEXT,
                    views_count INTEGER DEFAULT 0,
                    is_active INTEGER DEFAULT 1
                );
            """)

            # Savat jadvali
            await db.execute("""
                CREATE TABLE IF NOT EXISTS cart (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER REFERENCES users(user_id) ON DELETE CASCADE,
                    product_id INTEGER REFERENCES products(id) ON DELETE CASCADE,
                    quantity INTEGER DEFAULT 1,
                    UNIQUE(user_id, product_id)
                );
            """)

            # Buyurtmalar jadvali
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

            # Buyurtma ichidagi mahsulotlar jadvali
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

            # Migratsiya: Mavjud products jadvaliga yangi ustunlarni tekshirish va qo'shish
            cursor = await db.execute("PRAGMA table_info(products);")
            columns = [row[1] for row in await cursor.fetchall()]

            new_columns = {
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

            # Boshlang'ich kategoriyalar va mahsulotlarni tekshirib to'ldirish
            cursor = await db.execute("SELECT COUNT(*) FROM categories;")
            count = (await cursor.fetchone())[0]
            if count == 0:
                await self._seed_initial_data(db)

    async def _seed_initial_data(self, db: aiosqlite.Connection):
        """Boshlang'ich kategoriyalarni kiritish (faqat toifalar, mahsulotlar faqat kanaldan olinadi)"""
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


    # --- User operations ---
    async def add_user(self, user_id: int, full_name: str, username: Optional[str] = None):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO users (user_id, full_name, username) 
                VALUES (?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET full_name = excluded.full_name, username = excluded.username;
            """, (user_id, full_name, username))
            await db.commit()

    async def update_user_phone(self, user_id: int, phone: str):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("UPDATE users SET phone = ? WHERE user_id = ?;", (phone, user_id))
            await db.commit()

    async def get_user(self, user_id: int) -> Optional[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM users WHERE user_id = ?;", (user_id,)) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    async def get_users_count(self) -> int:
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT COUNT(*) FROM users;") as cursor:
                return (await cursor.fetchone())[0]

    async def get_all_user_ids(self) -> List[int]:
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT user_id FROM users;") as cursor:
                rows = await cursor.fetchall()
                return [r[0] for r in rows]

    # --- Category operations ---
    async def get_categories(self) -> List[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM categories ORDER BY id ASC;") as cursor:
                rows = await cursor.fetchall()
                return [dict(r) for r in rows]

    async def get_category(self, category_id: int) -> Optional[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM categories WHERE id = ?;", (category_id,)) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    # --- Product operations ---
    async def get_products_by_category(self, category_id: int) -> List[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("""
                SELECT * FROM products 
                WHERE category_id = ? AND is_available = 1 AND is_active = 1 AND message_id IS NOT NULL
                ORDER BY id DESC;
            """, (category_id,)) as cursor:
                rows = await cursor.fetchall()
                return [dict(r) for r in rows]

    async def get_active_products(
        self,
        category_id: Optional[int] = None,
        sort_by: str = "default",
        search: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Web App va katalog uchun saralangan va faqat kanalda mavjud mahsulotlarni olish"""
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

            # Saralash tartibi (sort_by)
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
                return [dict(r) for r in rows]

    async def get_product(self, product_id: int) -> Optional[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM products WHERE id = ?;", (product_id,)) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    async def get_products_count(self) -> int:
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT COUNT(*) FROM products WHERE is_active = 1 AND message_id IS NOT NULL;") as cursor:
                return (await cursor.fetchone())[0]

    async def search_products(self, query: str) -> List[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            search_pattern = f"%{query.strip()}%"
            async with db.execute("""
                SELECT * FROM products 
                WHERE (name LIKE ? OR description LIKE ?) AND is_available = 1 AND is_active = 1 AND message_id IS NOT NULL
                LIMIT 20;
            """, (search_pattern, search_pattern)) as cursor:
                rows = await cursor.fetchall()
                return [dict(r) for r in rows]

    async def increment_views(self, product_id: int) -> int:
        """Kanalga o'tish (views_count) sonini +1 oshirish"""
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
                return [dict(r) for r in rows]

    # --- Channel Parser DB Operations ---
    async def get_product_by_channel_post(self, channel_id: str, message_id: int) -> Optional[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("""
                SELECT * FROM products 
                WHERE channel_id = ? AND message_id = ?;
            """, (str(channel_id), message_id)) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

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
        category_id: Optional[int] = None
    ) -> int:
        """Kanal postidan mahsulotni qo'shish yoki yangilash"""
        async with aiosqlite.connect(self.db_path) as db:
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
                
                c_cur = await db.execute("SELECT id FROM categories WHERE name = ? LIMIT 1;", (c_name,))
                c_row = await c_cur.fetchone()
                category_id = c_row[0] if c_row else 1

            existing = await self.get_product_by_channel_post(channel_id, message_id)
            if existing:
                await db.execute("""
                    UPDATE products 
                    SET category_id = ?, name = ?, description = ?, price = ?, 
                        image_url = CASE WHEN ? != '' THEN ? ELSE image_url END,
                        post_url = ?, media_group_id = ?, is_active = 1, is_available = 1
                    WHERE channel_id = ? AND message_id = ?;
                """, (category_id, name, description, price, image_url, image_url, post_url, media_group_id, str(channel_id), message_id))
                await db.commit()
                return existing['id']
            else:
                cur = await db.execute("""
                    INSERT INTO products (
                        category_id, name, description, price, image_url, 
                        channel_id, message_id, media_group_id, post_url, 
                        views_count, is_active, is_available
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 1, 1);
                """, (
                    category_id, name, description, price, image_url,
                    str(channel_id), message_id, media_group_id, post_url
                ))
                await db.commit()
                return cur.lastrowid

    async def deactivate_product_by_channel_post(self, channel_id: str, message_id: int):
        """Kanalda post o'chirilganda mahsulotni nofaol qilish (is_active=0)"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                UPDATE products SET is_active = 0, is_available = 0 
                WHERE channel_id = ? AND message_id = ?;
            """, (str(channel_id), message_id))
            await db.commit()

    async def get_active_channel_products(self) -> List[Dict[str, Any]]:
        """Kanalga ulangan va faol mahsulotlar ro'yxatini olish"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("""
                SELECT id, channel_id, message_id, post_url, name 
                FROM products 
                WHERE is_active = 1 AND message_id IS NOT NULL;
            """) as cursor:
                rows = await cursor.fetchall()
                return [dict(r) for r in rows]

    async def deactivate_products_by_ids(self, product_ids: List[int]):
        """O'chirilgan mahsulotlarni bir vaqtning o'zida nofaol qilish (is_active=0)"""
        if not product_ids:
            return
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
        import json
        async with aiosqlite.connect(self.db_path, timeout=30.0) as db:
            gallery = json.dumps([image_url])
            await db.execute("""
                UPDATE products 
                SET image_url = ?, 
                    gallery_images = CASE WHEN gallery_images IS NULL OR gallery_images = '' OR gallery_images = '[]' THEN ? ELSE gallery_images END 
                WHERE id = ?;
            """, (image_url, gallery, product_id))
            await db.commit()

    async def update_product_gallery(self, product_id: int, image_url: str, gallery_images: List[str]):
        """Mahsulot asosiy rasmi va barcha galereya rasmlarini yangilash"""
        import json
        async with aiosqlite.connect(self.db_path, timeout=30.0) as db:
            gallery_json = json.dumps(gallery_images)
            await db.execute("""
                UPDATE products 
                SET image_url = ?, gallery_images = ? 
                WHERE id = ?;
            """, (image_url, gallery_json, product_id))
            await db.commit()

    async def add_product(self, category_id: int, name: str, description: str, price: int, image_url: str):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO products (category_id, name, description, price, image_url, is_active, is_available)
                VALUES (?, ?, ?, ?, ?, 1, 1);
            """, (category_id, name, description, price, image_url))
            await db.commit()

    # --- Cart operations ---
    async def add_to_cart(self, user_id: int, product_id: int, quantity: int = 1):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO cart (user_id, product_id, quantity)
                VALUES (?, ?, ?)
                ON CONFLICT(user_id, product_id) 
                DO UPDATE SET quantity = cart.quantity + excluded.quantity;
            """, (user_id, product_id, quantity))
            await db.commit()

    async def get_cart(self, user_id: int) -> List[Dict[str, Any]]:
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
                return [dict(r) for r in rows]

    async def update_cart_item(self, user_id: int, product_id: int, change: int):
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
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM cart WHERE user_id = ? AND product_id = ?;", (user_id, product_id))
            await db.commit()

    async def clear_cart(self, user_id: int):
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

            # Savatni tozalash
            await db.execute("DELETE FROM cart WHERE user_id = ?;", (user_id,))
            await db.commit()
            return order_id

    async def get_user_orders(self, user_id: int) -> List[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("""
                SELECT * FROM orders 
                WHERE user_id = ? 
                ORDER BY id DESC LIMIT 10;
            """, (user_id,)) as cursor:
                rows = await cursor.fetchall()
                orders = [dict(r) for r in rows]

            for order in orders:
                async with db.execute("SELECT * FROM order_items WHERE order_id = ?;", (order['id'],)) as c_items:
                    order['items'] = [dict(it) for it in await c_items.fetchall()]

            return orders

    async def get_order(self, order_id: int) -> Optional[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM orders WHERE id = ?;", (order_id,)) as cursor:
                row = await cursor.fetchone()
                if not row:
                    return None
                order = dict(row)

            async with db.execute("SELECT * FROM order_items WHERE order_id = ?;", (order_id,)) as cursor:
                order['items'] = [dict(it) for it in await cursor.fetchall()]

            return order

    async def get_all_orders(self, limit: int = 15) -> List[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM orders ORDER BY id DESC LIMIT ?;", (limit,)) as cursor:
                rows = await cursor.fetchall()
                orders = [dict(r) for r in rows]

            for order in orders:
                async with db.execute("SELECT * FROM order_items WHERE order_id = ?;", (order['id'],)) as c_items:
                    order['items'] = [dict(it) for it in await c_items.fetchall()]

            return orders

    async def update_order_status(self, order_id: int, status: str):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("UPDATE orders SET status = ? WHERE id = ?;", (status, order_id))
            await db.commit()

    async def get_stats(self) -> Dict[str, Any]:
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
