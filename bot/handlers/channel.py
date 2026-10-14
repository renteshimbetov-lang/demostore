import asyncio
import logging
from typing import Dict, List, Optional
from aiogram import Router, Bot
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

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

    def extract_photo_file_id(message: Message) -> Optional[str]:
        """Xabardan rasm file_id sini xavfsiz ajratib olish (photo yoki rasm hujjat)"""
        try:
            if message.photo:
                return message.photo[-1].file_id
            if message.document and message.document.mime_type and message.document.mime_type.startswith("image/"):
                return message.document.file_id
        except Exception as e:
            logger.warning(f"File ID ajratishda xatolik: {e}")
        return None

    def extract_all_photo_file_ids(messages: List[Message]) -> List[str]:
        """Bir nechta xabarlardan barcha rasm file_id larini tartib bilan olish"""
        file_ids: List[str] = []
        for msg in messages:
            fid = extract_photo_file_id(msg)
            if fid and fid not in file_ids:
                file_ids.append(fid)
        return file_ids

    def fetch_channel_embed_photos(channel_username: str, message_id: int) -> List[str]:
        """Ommaviy Telegram kanal postidan rasmiy CDN rasmlari (telesco.pe) ni olish"""
        if not channel_username:
            return []
        import urllib.request, re, ssl
        url = f"https://t.me/{channel_username.lstrip('@')}/{message_id}?embed=1"
        ctx = ssl._create_unverified_context()
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        try:
            with urllib.request.urlopen(req, timeout=6, context=ctx) as resp:
                html = resp.read().decode("utf-8")
                matches = re.findall(r"background-image:url\('(https://cdn\d*\.telesco\.pe/file/[^']+)'\)", html)
                seen = set()
                unique = []
                for m in matches:
                    if m not in seen:
                        seen.add(m)
                        unique.append(m)
                return unique
        except Exception as e:
            logger.debug(f"Embed rasm olishda xatolik: {e}")
            return []

    async def save_product_from_messages(main_msg: Message, all_messages: List[Message], is_edit: bool = False):
        """Bir yoki bir nechta xabardan (albomdan) mahsulotni yaratish yoki yangilash"""
        import json
        from bot.config import config
        from bot.utils.moderation import build_moderation_caption, build_moderation_keyboard, photo_input

        raw_text = (main_msg.caption or main_msg.text or "").strip()
        channel_id = str(main_msg.chat.id)
        message_id = main_msg.message_id

        # Postda "sotildi" yoki "#sold" bo'lsa mahsulotni nofaol deb belgilash
        if any(word in raw_text.lower() for word in ["#sotildi", "sotildi", "#sold", "tugadi", "#tugadi"]):
            await db.deactivate_product_by_channel_post(channel_id, message_id)
            logger.info(f"Post #{message_id} sotildi deb belgilandi va nofaol qilindi.")
            return

        name, description, price = parse_channel_post_content(raw_text)
        existing = await db.get_product_by_channel_post(channel_id, message_id)

        # Tahrirlangan postda Telegram faqat bitta xabarni yuboradi —
        # mavjud galereya va admin tanlagan rasm o'zgarmasdan saqlanadi.
        keep_media = bool(is_edit and existing)

        image_url = ""
        gallery_urls: List[str] = []
        primary_file_id = None
        if not keep_media:
            # 1-manba: Telegram file_id lar (doimiy, tezkor, xatosiz tartibda)
            file_ids = extract_all_photo_file_ids(all_messages)
            if file_ids:
                gallery_urls = [f"/api/photo/{fid}" for fid in file_ids]
                image_url = gallery_urls[0]
                primary_file_id = file_ids[0]
            else:
                # 2-manba: ommaviy kanal CDN rasmlari
                chan_user = main_msg.chat.username or config.channel_username
                gallery_urls = await asyncio.to_thread(fetch_channel_embed_photos, chan_user, message_id) if chan_user else []
                if gallery_urls:
                    image_url = gallery_urls[0]
                    primary_file_id = None
                else:
                    image_url = "/static/apple_3d_logo.png"
                    gallery_urls = [image_url]

        async with _db_write_lock:
            product_id = await db.upsert_product_from_channel(
                channel_id=channel_id,
                message_id=message_id,
                name=name,
                description=description,
                price=price,
                image_url=image_url,
                post_url=build_post_url(main_msg),
                media_group_id=main_msg.media_group_id,
                photo_file_id=primary_file_id,
                gallery_images=json.dumps(gallery_urls) if gallery_urls else None,
                is_active=0  # Yangi postlar admin 'Ha' deguncha mini ilovada ko'rinmaydi!
            )

        logger.info(f"Kanal posti qabul qilindi! ID: {product_id}, {name}, ${price}, asosiy rasm: {image_url[:60]}")

        # Allaqachon tasdiqlangan post tahrirlansa, adminga qayta so'rov yuborilmaydi
        if existing and existing.get("is_active") == 1:
            return

        prod = await db.get_product(product_id)
        if not prod:
            return
        gallery = json.loads(prod.get("gallery_images") or "[]") or [prod.get("image_url")]
        idx = gallery.index(prod["image_url"]) if prod.get("image_url") in gallery else 0
        caption = build_moderation_caption(prod, idx, len(gallery))
        kb = build_moderation_keyboard(product_id, idx, len(gallery))
        photo = photo_input(prod.get("image_url") or "")

        for admin_id in config.admin_ids:
            try:
                if photo:
                    await bot.send_photo(chat_id=admin_id, photo=photo, caption=caption, reply_markup=kb, parse_mode="HTML")
                else:
                    await bot.send_message(chat_id=admin_id, text=caption, reply_markup=kb, parse_mode="HTML")
            except Exception as e:
                logger.warning(f"Adminga bildirishnoma yuborishda xatolik ({admin_id}): {e}")
                try:
                    await bot.send_message(chat_id=admin_id, text=caption, reply_markup=kb, parse_mode="HTML")
                except Exception:
                    pass

    async def _process_debounced_media_group(mg_id: str):
        """Albomning barcha 2-4 ta rasmi Telegramdan kelib bo'lgach (0.4s debounce) tezkor qayta ishlash"""
        try:
            await asyncio.sleep(0.4)
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

        await save_product_from_messages(message, [message], is_edit=True)

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
