import logging
from aiogram import Router, Bot
from aiogram.types import Message
from bot.database.db import Database
from bot.parser.channel_parser import (
    parse_channel_post_content,
    is_media_group_duplicate
)

logger = logging.getLogger("ChannelParser")

def setup_channel_router(db: Database, bot: Bot) -> Router:
    router = Router()

    async def get_photo_url(message: Message) -> str:
        """Postdagi rasmni aniqlash va Telegram fayl URL manzilini olish"""
        if not message.photo:
            return ""
        
        try:
            largest_photo = message.photo[-1]
            file_info = await bot.get_file(largest_photo.file_id)
            if file_info.file_path:
                token = bot.token
                return f"https://api.telegram.org/file/bot{token}/{file_info.file_path}"
        except Exception as e:
            logger.warning(f"Rasm URL olishda xatolik: {e}")
        return ""

    def build_post_url(message: Message) -> str:
        from bot.config import config
        chat = message.chat
        msg_id = message.message_id
        if chat.username:
            return f"https://t.me/{chat.username}/{msg_id}"
        if config.channel_username:
            return f"https://t.me/{config.channel_username}/{msg_id}"
        clean_chat_id = str(chat.id).replace("-100", "")
        return f"https://t.me/c/{clean_chat_id}/{msg_id}"

    async def process_image_in_background(product_id: int, message: Message):
        """Rasmni yuklab olib, 1:1 kvadrat qilib to'g'ri va tekis joylashtirish (tabiiy fonni saqlagan holda)"""
        try:
            if not message.photo:
                return
            largest_photo = message.photo[-1]
            file_info = await bot.get_file(largest_photo.file_id)
            if not file_info.file_path:
                return
            
            from pathlib import Path
            from PIL import Image
            
            base_dir = Path(__file__).resolve().parent.parent.parent
            channel_photos_dir = base_dir / "channel_all_photos"
            products_dir = base_dir / "webapp" / "static" / "products"
            channel_photos_dir.mkdir(parents=True, exist_ok=True)
            products_dir.mkdir(parents=True, exist_ok=True)
            
            raw_dest = channel_photos_dir / f"msg_{message.message_id}.jpg"
            out_jpg = products_dir / f"prod_{product_id}.jpg"
            
            with open(raw_dest, "wb") as f:
                await bot.download_file(file_info.file_path, destination=f)
            
            if raw_dest.exists():
                img = Image.open(raw_dest)
                if img.mode != "RGB":
                    img = img.convert("RGB")
                w, h = img.size
                if h > w:
                    y_start = int(h * 0.06)
                    y_end = y_start + w
                    if y_end > h:
                        y_end = h
                        y_start = h - w
                    crop_box = (0, y_start, w, y_end)
                    img_cropped = img.crop(crop_box)
                elif w > h:
                    x_start = (w - h) // 2
                    crop_box = (x_start, 0, x_start + h, h)
                    img_cropped = img.crop(crop_box)
                else:
                    img_cropped = img
                
                img_cropped.save(out_jpg, "JPEG", quality=95)
                local_url = f"/static/products/prod_{product_id}.jpg"
                await db.update_product_image(product_id, local_url)
                logger.info(f"Mahsulot #{product_id} rasmi tekis va sifatli saqlandi: {local_url}")
        except Exception as e:
            logger.warning(f"Rasm qayta ishlashda xatolik: {e}")

    @router.channel_post()
    async def handle_new_channel_post(message: Message):
        """Kanaldan yangi post kelganda tahlil qilish va bazaga qo'shish"""
        # Albom (Media Group) bo'lsa, 2-chi va keyingi rasmlarni o'tkazib yuborish
        if is_media_group_duplicate(message.media_group_id):
            logger.info(f"Albomning davomi o'tkazib yuborildi (media_group_id={message.media_group_id})")
            return

        raw_text = message.caption or message.text or ""
        if not raw_text.strip():
            logger.info("Matnsiz post e'tiborsiz qoldirildi.")
            return

        name, description, price = parse_channel_post_content(raw_text)
        image_url = await get_photo_url(message)
        post_url = build_post_url(message)
        channel_id = str(message.chat.id)
        message_id = message.message_id

        # Postda "sotildi" yoki "#sold" bo'lsa mahsulotni nofaol deb belgilash
        if any(word in raw_text.lower() for word in ["#sotildi", "sotildi", "#sold", "tugadi", "#tugadi"]):
            await db.deactivate_product_by_channel_post(channel_id, message_id)
            logger.info(f"Post #{message_id} sotildi deb belgilandi va nofaol qilindi.")
            return

        product_id = await db.upsert_product_from_channel(
            channel_id=channel_id,
            message_id=message_id,
            name=name,
            description=description,
            price=price,
            image_url=image_url,
            post_url=post_url,
            media_group_id=message.media_group_id
        )

        logger.info(f"Kanal posti muvaffaqiyatli sinxronlandi! Mahsulot ID: {product_id}, Nomi: {name}, Narxi: {price}")
        
        # Rasmni botni qotirmasdan, orqa fonda (async task) yuklab olib, fonini tozalash
        if message.photo:
            import asyncio
            asyncio.create_task(process_image_in_background(product_id, message))

    @router.edited_channel_post()
    async def handle_edited_channel_post(message: Message):
        """Kanaldagi post tahrirlanganda bazani avtomatik yangilash"""
        raw_text = message.caption or message.text or ""
        channel_id = str(message.chat.id)
        message_id = message.message_id

        # Agar post tahrirlanib sotilgani bildirilsa yoki matn o'chirilsa
        if not raw_text.strip() or any(word in raw_text.lower() for word in ["#sotildi", "sotildi", "#sold", "tugadi", "#tugadi"]):
            await db.deactivate_product_by_channel_post(channel_id, message_id)
            logger.info(f"Tahrirlangan post #{message_id} nofaol qilindi.")
            return

        name, description, price = parse_channel_post_content(raw_text)
        image_url = await get_photo_url(message)
        post_url = build_post_url(message)

        product_id = await db.upsert_product_from_channel(
            channel_id=channel_id,
            message_id=message_id,
            name=name,
            description=description,
            price=price,
            image_url=image_url,
            post_url=post_url,
            media_group_id=message.media_group_id
        )

        logger.info(f"Tahrirlangan kanal posti yangilandi! Mahsulot ID: {product_id}, Nomi: {name}, Narxi: {price}")
        
        if message.photo:
            import asyncio
            asyncio.create_task(process_image_in_background(product_id, message))

    # Orqa fonda avtomatik sinxronlash vazifasini ishga tushirish
    import asyncio
    from bot.config import config
    asyncio.create_task(start_channel_sync_loop(db, config.channel_username))

    return router

async def sync_deleted_channel_posts(db: Database, channel_username: str):
    """
    Telegram kanalidan o'chirilgan postlarni avtomatik aniqlash 
    va ularni mini appdan darhol o'chirish (is_active=0, is_available=0)
    """
    if not channel_username:
        return []
    
    clean_username = channel_username.lstrip("@")
    products = await db.get_active_channel_products()
    if not products:
        return []

    import aiohttp
    connector = aiohttp.TCPConnector(ssl=False)
    timeout = aiohttp.ClientTimeout(total=6)
    deleted_ids = []

    try:
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            for p in products:
                msg_id = p.get("message_id")
                if not msg_id:
                    continue
                url = f"https://t.me/{clean_username}/{msg_id}?embed=1"
                try:
                    async with session.get(url) as resp:
                        if resp.status == 200:
                            text = await resp.text()
                            if "Post not found" in text or "tgme_widget_message_error" in text:
                                deleted_ids.append(p["id"])
                                logger.info(f"Kanalda o'chirilgan post aniqlandi: msg_id=#{msg_id} ('{p['name']}') -> Mini appdan o'chirildi.")
                        elif resp.status in (404, 410):
                            deleted_ids.append(p["id"])
                            logger.info(f"Kanalda post topilmadi (status {resp.status}): msg_id=#{msg_id} ('{p['name']}') -> Mini appdan o'chirildi.")
                except Exception as e:
                    logger.debug(f"Post #{msg_id} tekshirishda xatolik: {e}")

        if deleted_ids:
            await db.deactivate_products_by_ids(deleted_ids)
            logger.info(f"Jami {len(deleted_ids)} ta kanalidan o'chirilgan mahsulot mini appdan muvaffaqiyatli o'chirildi!")
    except Exception as e:
        logger.warning(f"Kanal postlarini sinxronlashda xatolik: {e}")

    return deleted_ids

async def start_channel_sync_loop(db: Database, channel_username: str):
    """Orqa fonda har 20 soniyada o'chirilgan postlarni tekshirib turuvchi avtomatik fon jarayoni"""
    import asyncio
    logger.info("Kanal o'chirilgan postlarini avtomatik tekshiruvchi fon jarayoni boshlandi.")
    # Dastlabki tezkor tekshiruv
    try:
        await sync_deleted_channel_posts(db, channel_username)
    except Exception as e:
        logger.warning(f"Dastlabki kanal sync xatosi: {e}")

    while True:
        await asyncio.sleep(20)
        try:
            await sync_deleted_channel_posts(db, channel_username)
        except Exception as e:
            logger.warning(f"Kanal sync loop xatosi: {e}")
