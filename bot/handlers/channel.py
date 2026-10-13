import asyncio
import logging
from pathlib import Path
from typing import Dict, List, Optional
from PIL import Image
from aiogram import Router, Bot
from aiogram.types import Message

from bot.database.db import Database
from bot.parser.channel_parser import parse_channel_post_content

logger = logging.getLogger("ChannelParser")

def setup_channel_router(db: Database, bot: Bot) -> Router:
    router = Router()

    # Bir vaqtda bir nechta post kelganda DB yozilishlarini xavfsiz tartibga soluvchi qulf
    _db_write_lock = asyncio.Lock()

    # Albom (MediaGroup) larni barcha 2-4 ta rasmlari kelib bo'lishini kutuvchi bufer
    _media_group_buffers: Dict[str, List[Message]] = {}
    _media_group_tasks: Dict[str, asyncio.Task] = {}

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

    async def download_and_crop_image(file_id: str, raw_dest: Path, out_dest: Path) -> bool:
        """Rasmni yuklab olib 1:1 kvadrat formatda sifatli saqlash"""
        try:
            file_info = await bot.get_file(file_id)
            if not file_info.file_path:
                return False
            
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
                
                img_cropped.save(out_dest, "JPEG", quality=95)
                return True
        except Exception as e:
            logger.warning(f"Rasm qayta ishlashda xatolik ({raw_dest.name}): {e}")
        return False

    async def process_media_images_in_background(product_id: int, messages: List[Message]):
        """Barcha 2-4 ta rasmni orqa fonda galereyaga va asosiy 1:1 kvadrat formatga saqlash"""
        try:
            base_dir = Path(__file__).resolve().parent.parent.parent
            channel_photos_dir = base_dir / "channel_all_photos"
            products_dir = base_dir / "webapp" / "static" / "products"
            gallery_dir = base_dir / "webapp" / "static" / "gallery"
            
            channel_photos_dir.mkdir(parents=True, exist_ok=True)
            products_dir.mkdir(parents=True, exist_ok=True)
            gallery_dir.mkdir(parents=True, exist_ok=True)

            primary_url = ""
            gallery_urls = []

            # Rasmli xabarlarni tartib bilan olish
            photo_messages = [m for m in messages if m.photo]
            for idx, msg in enumerate(photo_messages):
                largest_photo = msg.photo[-1]
                raw_dest = channel_photos_dir / f"msg_{msg.message_id}.jpg"

                if idx == 0:
                    # 1-rasm: Mahsulotning asosiy 1:1 rasmi
                    out_jpg = products_dir / f"prod_{product_id}.jpg"
                    success = await download_and_crop_image(largest_photo.file_id, raw_dest, out_jpg)
                    if success:
                        primary_url = f"/static/products/prod_{product_id}.jpg"
                        gallery_urls.append(primary_url)
                else:
                    # 2, 3, 4-rasmlar: Galereya rasmlari
                    gallery_dest = gallery_dir / f"prod_{product_id}_photo_{idx + 1}.jpg"
                    success = await download_and_crop_image(largest_photo.file_id, raw_dest, gallery_dest)
                    if success:
                        gallery_urls.append(f"/static/gallery/prod_{product_id}_photo_{idx + 1}.jpg")

            if primary_url and gallery_urls:
                await db.update_product_gallery(product_id, primary_url, gallery_urls)
                logger.info(f"Mahsulot #{product_id} uchun {len(gallery_urls)} ta rasm galereyaga muvaffaqiyatli saqlandi!")
            elif primary_url:
                await db.update_product_image(product_id, primary_url)
        except Exception as e:
            logger.warning(f"Galereya rasmlarini qayta ishlashda xatolik (#{product_id}): {e}")

    async def save_product_from_messages(main_msg: Message, all_messages: List[Message]):
        """Bir yoki bir nechta xabardan (albomdan) mahsulotni yaratish yoki yangilash"""
        raw_text = (main_msg.caption or main_msg.text or "").strip()
        channel_id = str(main_msg.chat.id)
        message_id = main_msg.message_id

        # Postda "sotildi" yoki "#sold" bo'lsa mahsulotni nofaol deb belgilash
        if any(word in raw_text.lower() for word in ["#sotildi", "sotildi", "#sold", "tugadi", "#tugadi"]):
            await db.deactivate_product_by_channel_post(channel_id, message_id)
            logger.info(f"Post #{message_id} sotildi deb belgilandi va nofaol qilindi.")
            return

        name, description, price = parse_channel_post_content(raw_text)
        image_url = await get_photo_url(main_msg)
        post_url = build_post_url(main_msg)

        async with _db_write_lock:
            product_id = await db.upsert_product_from_channel(
                channel_id=channel_id,
                message_id=message_id,
                name=name,
                description=description,
                price=price,
                image_url=image_url,
                post_url=post_url,
                media_group_id=main_msg.media_group_id
            )

        logger.info(f"Kanal posti qabul qilindi! Mahsulot ID: {product_id}, Nomi: {name}, Narxi: ${price}, Rasmlar soni: {len(all_messages)}")

        # Rasmlarni yuklab olib galereya bilan birga saqlash
        if any(m.photo for m in all_messages):
            asyncio.create_task(process_media_images_in_background(product_id, all_messages))

    async def _process_debounced_media_group(mg_id: str):
        """Albomning barcha 2-4 ta rasmi Telegramdan kelib bo'lgach (1.2s debounce) qayta ishlash"""
        try:
            await asyncio.sleep(1.2)
            messages = _media_group_buffers.pop(mg_id, [])
            _media_group_tasks.pop(mg_id, None)

            if not messages:
                return

            # Xabarlarni message_id bo'yicha tartiblaymiz
            messages.sort(key=lambda m: m.message_id)

            # Matni (caption) bor xabarni aniqlaymiz
            main_msg = next((m for m in messages if (m.caption or m.text or "").strip()), None)
            if not main_msg:
                main_msg = messages[0]

            raw_text = (main_msg.caption or main_msg.text or "").strip()
            if not raw_text:
                logger.info(f"Albom #{mg_id} ({len(messages)} ta rasm) da matn topilmadi, e'tiborsiz qoldirildi.")
                return

            await save_product_from_messages(main_msg, messages)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Albom #{mg_id} qayta ishlashda xatolik: {e}", exc_info=True)

    @router.channel_post()
    async def handle_new_channel_post(message: Message):
        """Kanaldan yangi post kelganda (yakka yoki albom/ketma-ket) qabul qilish"""
        # 1. Agar xabar Media Group (Albom) bo'lsa
        if message.media_group_id:
            mg_id = str(message.media_group_id)
            if mg_id not in _media_group_buffers:
                _media_group_buffers[mg_id] = []
            _media_group_buffers[mg_id].append(message)

            # Oldingi taymerni bekor qilib, 1.2 soniya yangi xabarlarni kutamiz
            if mg_id in _media_group_tasks and not _media_group_tasks[mg_id].done():
                _media_group_tasks[mg_id].cancel()

            _media_group_tasks[mg_id] = asyncio.create_task(_process_debounced_media_group(mg_id))
            return

        # 2. Agar oddiy yakka post bo'lsa
        raw_text = (message.caption or message.text or "").strip()
        if not raw_text:
            logger.info(f"Matnsiz yakka post #{message.message_id} e'tiborsiz qoldirildi.")
            return

        await save_product_from_messages(message, [message])

    @router.edited_channel_post()
    async def handle_edited_channel_post(message: Message):
        """Kanaldagi post tahrirlanganda bazani avtomatik yangilash"""
        raw_text = (message.caption or message.text or "").strip()
        channel_id = str(message.chat.id)
        message_id = message.message_id

        if not raw_text or any(word in raw_text.lower() for word in ["#sotildi", "sotildi", "#sold", "tugadi", "#tugadi"]):
            await db.deactivate_product_by_channel_post(channel_id, message_id)
            logger.info(f"Tahrirlangan post #{message_id} nofaol qilindi.")
            return

        await save_product_from_messages(message, [message])

    # Orqa fonda avtomatik sinxronlash vazifasini ishga tushirish
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
    logger.info("Kanal o'chirilgan postlarini avtomatik tekshiruvchi fon jarayoni boshlandi.")
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
