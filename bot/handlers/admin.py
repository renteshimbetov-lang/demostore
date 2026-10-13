import asyncio
import json
import logging
from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto
from aiogram.fsm.context import FSMContext

from bot.config import config
from bot.database.db import Database
from bot.states.states import AdminStates
from bot.utils.helpers import format_price
from bot.parser.channel_parser import parse_channel_post_content

def setup_admin_router(db: Database, bot: Bot) -> Router:
    router = Router()

    def is_admin(user_id: int) -> bool:
        return user_id in config.admin_ids

    def get_admin_menu_inline() -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="📢 Kanalga yangi post tayyorlash & joylash", callback_data="admin_create_post")],
                [
                    InlineKeyboardButton(text="📊 Statistika", callback_data="admin_stats"),
                    InlineKeyboardButton(text="📦 Buyurtmalar", callback_data="admin_orders")
                ],
                [
                    InlineKeyboardButton(text="✉️ Xabar tarqatish (Broadcast)", callback_data="admin_broadcast"),
                    InlineKeyboardButton(text="➕ Yangi mahsulot", callback_data="admin_add_product")
                ],
                [InlineKeyboardButton(text="🔄 Kanal postlarini sinxronlash", callback_data="admin_sync_channel")]
            ]
        )

    def get_order_status_keyboard(order_id: int) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="Qabul qilindi", callback_data=f"status_{order_id}_Qabul qilindi"),
                    InlineKeyboardButton(text="Yetkazilmoqda", callback_data=f"status_{order_id}_Yetkazilmoqda")
                ],
                [
                    InlineKeyboardButton(text="Yetkazildi", callback_data=f"status_{order_id}_Yetkazildi"),
                    InlineKeyboardButton(text="Bekor qilindi", callback_data=f"status_{order_id}_Bekor qilindi")
                ],
                [InlineKeyboardButton(text="Buyurtmalar ro'yxatiga", callback_data="admin_orders")]
            ]
        )

    @router.message(Command("admin"))
    @router.message(F.text == "Admin Panel")
    @router.message(F.text == "⚙️ Admin Panel")
    async def admin_panel_handler(message: Message, state: FSMContext):
        # Faqat adminlar ko'ra oladigan tekshiruv
        if not message.from_user or not is_admin(message.from_user.id):
            return

        await state.clear()
        stats = await db.get_stats()
        text = (
            f"👑 <b>ADMIN BOSHQARUV PANELI</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👥 Foydalanuvchilar: <b>{stats['users_count']}</b> nafar\n"
            f"📦 Faol mahsulotlar: <b>{stats['products_count']}</b> ta\n"
            f"🛍 Buyurtmalar: <b>{stats['orders_count']}</b> ta\n"
            f"💰 Jami aylanma: <b>{format_price(stats['total_revenue'])}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"⚡️ <i>Kerakli bo'limni tanlang:</i>"
        )
        await message.answer(text, reply_markup=get_admin_menu_inline(), parse_mode="HTML")

    @router.callback_query(F.data == "admin_stats")
    async def show_stats_callback(callback: CallbackQuery):
        if not is_admin(callback.from_user.id):
            return

        stats = await db.get_stats()
        top_viewed = await db.get_top_viewed_products(limit=10)

        lines = [
            "<b>Do'kon Statistikasi va Hisoboti</b>\n",
            f"Foydalanuvchilar soni: <b>{stats['users_count']}</b> nafar",
            f"Jami mahsulotlar soni: <b>{stats['products_count']}</b> ta",
            f"Bajarilgan buyurtmalar: <b>{stats['orders_count']}</b> ta",
            f"Umumiy aylanma: <b>{format_price(stats['total_revenue'])}</b>\n",
            "<b>Mini ilovadan kanalga eng ko'p o'tilgan tovarlar (Top):</b>"
        ]

        if top_viewed:
            for idx, p in enumerate(top_viewed, 1):
                lines.append(f"{idx}. {p['name']} — <b>{p['views_count']} marta</b> ko'rilgan ({format_price(p['price'])})")
        else:
            lines.append("<i>Hozircha kanalga o'tishlar statistikasi mavjud emas.</i>")

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Ortga", callback_data="admin_main")]
        ])

        if callback.message:
            await callback.message.edit_text("\n".join(lines), reply_markup=keyboard, parse_mode="HTML")
        await callback.answer()

    @router.callback_query(F.data == "admin_main")
    async def admin_main_callback(callback: CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            return

        await state.clear()
        stats = await db.get_stats()
        text = (
            f"👑 <b>ADMIN BOSHQARUV PANELI</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👥 Foydalanuvchilar: <b>{stats['users_count']}</b> nafar\n"
            f"📦 Faol mahsulotlar: <b>{stats['products_count']}</b> ta\n"
            f"🛍 Buyurtmalar: <b>{stats['orders_count']}</b> ta\n"
            f"💰 Jami aylanma: <b>{format_price(stats['total_revenue'])}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"⚡️ <i>Kerakli bo'limni tanlang:</i>"
        )
        if callback.message:
            if callback.message.photo:
                await callback.message.delete()
                await callback.message.answer(text, reply_markup=get_admin_menu_inline(), parse_mode="HTML")
            else:
                await callback.message.edit_text(text, reply_markup=get_admin_menu_inline(), parse_mode="HTML")
        await callback.answer()

    @router.callback_query(F.data == "admin_orders")
    async def show_orders_callback(callback: CallbackQuery):
        if not is_admin(callback.from_user.id):
            return

        orders = await db.get_all_orders(limit=10)
        if not orders:
            text = "Hozircha yangi buyurtmalar yo'q."
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Ortga", callback_data="admin_main")]
            ])
            if callback.message:
                await callback.message.edit_text(text, reply_markup=keyboard)
            await callback.answer()
            return

        text = "<b>Oxirgi 10 ta buyurtma:</b>\n"
        buttons = []
        for o in orders:
            buttons.append([
                InlineKeyboardButton(
                    text=f"#{o['id']} | {o['full_name']} | {format_price(o['total_amount'])} ({o['status']})",
                    callback_data=f"adm_order_{o['id']}"
                )
            ])
        buttons.append([InlineKeyboardButton(text="Asosiy menyu", callback_data="admin_main")])

        if callback.message:
            await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML")
        await callback.answer()

    @router.callback_query(F.data.startswith("adm_order_"))
    async def view_order_detail(callback: CallbackQuery):
        if not is_admin(callback.from_user.id):
            return

        order_id = int(callback.data.split("_")[2])
        order = await db.get_order(order_id)
        if not order:
            await callback.answer("Buyurtma topilmadi!", show_alert=True)
            return

        lines = [
            f"<b>Buyurtma #{order['id']} ma'lumotlari:</b>\n",
            f"Mijoz: {order['full_name']}",
            f"Telefon: {order['phone']}",
            f"Manzil: {order['address']}",
            f"To'lov: {order['payment_method']}",
            f"Holat: <b>{order['status']}</b>",
            f"Sana: {order['created_at']}\n",
            "Mahsulotlar:"
        ]
        for it in order.get('items', []):
            lines.append(f"  • {it['product_name']} — {it['quantity']} x {format_price(it['price'])}")
        lines.append(f"\nJami: <b>{format_price(order['total_amount'])}</b>")

        if callback.message:
            await callback.message.edit_text(
                "\n".join(lines),
                reply_markup=get_order_status_keyboard(order['id']),
                parse_mode="HTML"
            )
        await callback.answer()

    @router.callback_query(F.data.startswith("status_"))
    async def change_order_status(callback: CallbackQuery):
        if not is_admin(callback.from_user.id):
            return

        parts = callback.data.split("_")
        order_id = int(parts[1])
        new_status = parts[2]

        await db.update_order_status(order_id, new_status)
        order = await db.get_order(order_id)

        # Foydalanuvchiga bildirishnoma yuborish
        if order and order.get('user_id'):
            try:
                await bot.send_message(
                    chat_id=order['user_id'],
                    text=(
                        f"<b>Buyurtmangiz holati yangilandi!</b>\n\n"
                        f"Buyurtma #{order_id}\n"
                        f"Yangi holat: <b>{new_status}</b>"
                    ),
                    parse_mode="HTML"
                )
            except Exception:
                pass

        await callback.answer(f"Holat '{new_status}' ga o'zgartirildi!")
        
        lines = [
            f"<b>Buyurtma #{order['id']} ma'lumotlari:</b>\n",
            f"Mijoz: {order['full_name']}",
            f"Telefon: {order['phone']}",
            f"Manzil: {order['address']}",
            f"To'lov: {order['payment_method']}",
            f"Holat: <b>{new_status}</b>",
            f"Sana: {order['created_at']}\n",
            "Mahsulotlar:"
        ]
        for it in order.get('items', []):
            lines.append(f"  • {it['product_name']} — {it['quantity']} x {format_price(it['price'])}")
        lines.append(f"\nJami: <b>{format_price(order['total_amount'])}</b>")

        if callback.message:
            await callback.message.edit_text(
                "\n".join(lines),
                reply_markup=get_order_status_keyboard(order['id']),
                parse_mode="HTML"
            )

    # --- Broadcast (Xabar tarqatish) ---
    @router.callback_query(F.data == "admin_broadcast")
    async def start_broadcast(callback: CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            return

        await state.set_state(AdminStates.waiting_for_broadcast)
        text = "<b>Barcha foydalanuvchilarga xabar yuborish:</b>\n\nYuboriladigan xabar matnini kiriting yoki /cancel deb yozing:"
        if callback.message:
            await callback.message.answer(text, parse_mode="HTML")
        await callback.answer()

    @router.message(AdminStates.waiting_for_broadcast)
    async def process_broadcast(message: Message, state: FSMContext):
        if not message.from_user or not is_admin(message.from_user.id):
            return

        if message.text == "/cancel":
            await state.clear()
            await message.answer("Xabar tarqatish bekor qilindi.")
            return

        await state.clear()
        broadcast_text = message.text or ""
        user_ids = await db.get_all_user_ids()

        status_msg = await message.answer(f"Xabar {len(user_ids)} ta foydalanuvchiga yuborilmoqda...")

        success_count = 0
        fail_count = 0

        for uid in user_ids:
            try:
                await bot.send_message(chat_id=uid, text=broadcast_text, parse_mode="HTML")
                success_count += 1
            except Exception:
                fail_count += 1

        await status_msg.edit_text(
            f"<b>Xabar tarqatish yakunlandi!</b>\n\n"
            f"Yetkazildi: {success_count} ta\n"
            f"Xatolik (bloklagan): {fail_count} ta",
            parse_mode="HTML"
        )

    # --- Yangi mahsulot qo'shish ---
    @router.callback_query(F.data == "admin_add_product")
    async def start_add_product(callback: CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            return

        categories = await db.get_categories()
        buttons = []
        for cat in categories:
            buttons.append([InlineKeyboardButton(text=cat['name'], callback_data=f"addprod_cat_{cat['id']}")])
        buttons.append([InlineKeyboardButton(text="Bekor qilish", callback_data="admin_main")])

        if callback.message:
            await callback.message.edit_text(
                "<b>Qaysi kategoriyaga mahsulot qo'shmoqchisiz?</b>",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
                parse_mode="HTML"
            )
        await callback.answer()

    @router.callback_query(F.data.startswith("addprod_cat_"))
    async def select_category_for_new_prod(callback: CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            return

        cat_id = int(callback.data.split("_")[2])
        await state.update_data(category_id=cat_id)
        await state.set_state(AdminStates.waiting_for_name)

        if callback.message:
            await callback.message.answer("Mahsulot <b>nomini</b> kiriting:\n(Masalan: <i>iPhone 16 Pro Max</i>)", parse_mode="HTML")
        await callback.answer()

    @router.message(AdminStates.waiting_for_name)
    async def process_new_prod_name(message: Message, state: FSMContext):
        await state.update_data(name=message.text.strip())
        await state.set_state(AdminStates.waiting_for_desc)
        await message.answer("Mahsulot <b>tavsifini</b> (xususiyatlarini) kiriting:")

    @router.message(AdminStates.waiting_for_desc)
    async def process_new_prod_desc(message: Message, state: FSMContext):
        await state.update_data(description=message.text.strip())
        await state.set_state(AdminStates.waiting_for_price)
        await message.answer("Mahsulot <b>narxini</b> faqat raqamda kiriting (so'mda, masalan: <i>15000000</i>):")

    @router.message(AdminStates.waiting_for_price)
    async def process_new_prod_price(message: Message, state: FSMContext):
        price_text = message.text.replace(" ", "").strip()
        if not price_text.isdigit():
            await message.answer("Iltimos, narxni faqat butun musbat raqam ko'rinishida kiriting:")
            return

        await state.update_data(price=int(price_text))
        await state.set_state(AdminStates.waiting_for_image)
        await message.answer(
            "Mahsulot <b>rasmining internet havolasini (URL)</b> yuboring yoki o'tkazib yuborish uchun <code>-</code> belgisini yozing:\n"
            "(Masalan: <i>https://example.com/phone.jpg</i>)",
            parse_mode="HTML"
        )

    @router.message(AdminStates.waiting_for_image)
    async def process_new_prod_image(message: Message, state: FSMContext):
        img_url = message.text.strip()
        if img_url == "-":
            img_url = ""

        data = await state.get_data()
        await db.add_product(
            category_id=data['category_id'],
            name=data['name'],
            description=data['description'],
            price=data['price'],
            image_url=img_url
        )
        await state.clear()

        await message.answer(
            f"<b>'{data['name']}'</b> muvaffaqiyatli qo'shildi va katalogda ko'rinadi!",
            parse_mode="HTML"
        )

    # =========================================================================
    # 1. Kanalga yangi post tayyorlash va chop etish (Admin Chat)
    # =========================================================================
    _admin_mg_buffers: dict = {}
    _admin_mg_tasks: dict = {}

    def extract_admin_photos(msgs: list) -> list:
        fids = []
        for m in msgs:
            if m.photo:
                fid = m.photo[-1].file_id
                if fid not in fids:
                    fids.append(fid)
        return fids

    async def _send_admin_draft_preview(user_id: int, state: FSMContext, msgs: list):
        main_msg = next((m for m in msgs if (m.caption or m.text or "").strip()), msgs[0])
        raw_text = (main_msg.caption or main_msg.text or "").strip()
        if not raw_text:
            await bot.send_message(
                chat_id=user_id,
                text="⚠️ Iltimos, mahsulot rasmi bilan birga uning nomi va narxini ham yozib yuboring.\nBekor qilish uchun <code>/cancel</code> deb yozing.",
                parse_mode="HTML"
            )
            return

        name, description, price = parse_channel_post_content(raw_text)
        file_ids = extract_admin_photos(msgs)

        # Rasm tanlash mantig'i:
        # 1-rasm odatda yon tarafdan olingan bo'ladi.
        # Keyingi (2-rasm) esa to'g'ridan olingan bo'ladi!
        # Agar keyingi rasm bo'lmasa, 1-rasm (yon tarafdan olingani) olinadi.
        if len(file_ids) >= 2:
            primary_fid = file_ids[1]  # Keyingi to'g'ridan olingan rasm
            ordered_fids = [file_ids[1], file_ids[0], *file_ids[2:]]
        elif file_ids:
            primary_fid = file_ids[0]
            ordered_fids = file_ids
        else:
            primary_fid = None
            ordered_fids = []

        price_uzs = format_price(price * config.usd_rate)
        await state.update_data(
            name=name,
            description=description,
            price=price,
            raw_text=raw_text,
            photo_file_id=primary_fid,
            all_photo_file_ids=ordered_fids
        )

        preview_text = (
            f"✨ <b>YANGI POST PREVIEW (KO'RISH)</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📱 <b>Model:</b> {name}\n"
            f"💵 <b>Narxi:</b> ${price} (≈ {price_uzs})\n\n"
            f"📋 <b>Kanal posti tavsifi:</b>\n"
            f"{description}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"❓ <b>Shuni kanalga va do'konga joylaylikmi?</b>"
        )
        confirm_kb = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="🟢 Ha, kanalga joylash", callback_data="admin_publish_channel_post"),
                InlineKeyboardButton(text="🔴 Yo'q, bekor qilish", callback_data="admin_cancel_channel_post")
            ]
        ])

        if primary_fid:
            await bot.send_photo(chat_id=user_id, photo=primary_fid, caption=preview_text, reply_markup=confirm_kb, parse_mode="HTML")
        else:
            await bot.send_message(chat_id=user_id, text=preview_text, reply_markup=confirm_kb, parse_mode="HTML")

    @router.callback_query(F.data == "admin_create_post")
    async def start_create_post(callback: CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            return

        await state.set_state(AdminStates.waiting_for_channel_post)
        text = (
            "📢 <b>KANALGA YANGI POST TAYYORLASH</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "Mahsulot <b>rasmini</b> (yoki albom rasmlarini) va <b>tavsifini</b> (nomi, narxi, parametrlari) yuboring.\n\n"
            "<i>Misol matn:</i>\n"
            "<code>Apple iPhone 16 Pro Max\n"
            "256GB / Desert Titanium / 100% batareya\n"
            "Narxi: 1250$\n"
            "Holati: Yangi, karobka-dokument</code>\n\n"
            "⚡️ Bekor qilish uchun <code>/cancel</code> deb yozing."
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="admin_main")]
        ])
        if callback.message:
            if callback.message.photo:
                await callback.message.delete()
                await callback.message.answer(text, reply_markup=kb, parse_mode="HTML")
            else:
                await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
        await callback.answer()

    @router.message(AdminStates.waiting_for_channel_post)
    async def process_channel_post_draft(message: Message, state: FSMContext):
        if not message.from_user or not is_admin(message.from_user.id):
            return

        if message.text == "/cancel":
            await state.clear()
            await message.answer("❌ Post tayyorlash bekor qilindi.", reply_markup=get_admin_menu_inline())
            return

        # Agar bir nechta rasm (media group) bo'lsa, barchasini 0.8 soniya kutib yig'ib olamiz
        if message.media_group_id:
            mg_id = str(message.media_group_id)
            if mg_id not in _admin_mg_buffers:
                _admin_mg_buffers[mg_id] = []
            _admin_mg_buffers[mg_id].append(message)

            if mg_id in _admin_mg_tasks and not _admin_mg_tasks[mg_id].done():
                _admin_mg_tasks[mg_id].cancel()

            async def _process_debounced_admin_mg(mg: str, uid: int):
                try:
                    await asyncio.sleep(0.8)
                    msgs = _admin_mg_buffers.pop(mg, [])
                    _admin_mg_tasks.pop(mg, None)
                    if msgs:
                        msgs.sort(key=lambda m: m.message_id)
                        await _send_admin_draft_preview(uid, state, msgs)
                except asyncio.CancelledError:
                    pass

            _admin_mg_tasks[mg_id] = asyncio.create_task(_process_debounced_admin_mg(mg_id, message.from_user.id))
            return

        await _send_admin_draft_preview(message.from_user.id, state, [message])

    @router.callback_query(F.data == "admin_publish_channel_post")
    async def publish_channel_post_callback(callback: CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            return

        data = await state.get_data()
        if not data or not data.get("name"):
            await callback.answer("Ma'lumot topilmadi yoki muddat o'tgan.", show_alert=True)
            return

        await state.clear()
        channel_target = config.channel_id or f"@{config.channel_username}"
        channel_caption = (
            f"<b>{data['name']}</b>\n\n"
            f"{data['description']}\n\n"
            f"💵 <b>Narxi:</b> ${data['price']}\n"
            f"🛒 <b>Mini ilovada xarid qilish:</b> {config.channel_url}"
        )

        all_photos = data.get("all_photo_file_ids") or ([data["photo_file_id"]] if data.get("photo_file_id") else [])

        try:
            if len(all_photos) > 1:
                media = [
                    InputMediaPhoto(media=fid, caption=channel_caption if i == 0 else "", parse_mode="HTML")
                    for i, fid in enumerate(all_photos[:10])
                ]
                sent_msgs = await bot.send_media_group(chat_id=channel_target, media=media)
                chan_msg_id = sent_msgs[0].message_id
            elif data.get("photo_file_id"):
                sent = await bot.send_photo(
                    chat_id=channel_target,
                    photo=data["photo_file_id"],
                    caption=channel_caption,
                    parse_mode="HTML"
                )
                chan_msg_id = sent.message_id
            else:
                sent = await bot.send_message(
                    chat_id=channel_target,
                    text=channel_caption,
                    parse_mode="HTML"
                )
                chan_msg_id = sent.message_id

            post_url = (
                f"https://t.me/{config.channel_username}/{chan_msg_id}"
                if config.channel_username
                else f"https://t.me/c/{str(channel_target).replace('-100', '')}/{chan_msg_id}"
            )

            # Bazaga va mini ilovaga saqlash
            primary_fid = data.get("photo_file_id")
            img_url = f"/api/photo/{primary_fid}" if primary_fid else "/static/apple_3d_logo.png"
            gallery_urls = [f"/api/photo/{fid}" for fid in all_photos] if all_photos else [img_url]
            await db.upsert_product_from_channel(
                channel_id=str(channel_target),
                message_id=chan_msg_id,
                name=data["name"],
                description=data["description"],
                price=data["price"],
                image_url=img_url,
                post_url=post_url,
                photo_file_id=primary_fid,
                gallery_images=json.dumps(gallery_urls)
            )

            # Chat toza (clean) turishi uchun tasdiqlash xabarini darhol o'chirib tashlaymiz!
            if callback.message:
                try:
                    await callback.message.delete()
                except Exception:
                    pass

            await callback.answer("✅ Kanalga va do'konga muvaffaqiyatli joylandi!", show_alert=True)
        except Exception as e:
            await callback.answer(f"Kanalga yuborishda xatolik: {e}", show_alert=True)

    @router.callback_query(F.data == "admin_cancel_channel_post")
    async def cancel_channel_post_callback(callback: CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            return

        await state.clear()
        if callback.message:
            try:
                await callback.message.delete()
            except Exception:
                pass
        await callback.answer("❌ Post bekor qilindi.", show_alert=False)

    # =========================================================================
    # 2. Kanaldan kelgan postlarni moderatsiya qilish (Approve / Reject)
    # =========================================================================
    @router.callback_query(F.data.startswith("chan_approve_"))
    async def approve_channel_post_callback(callback: CallbackQuery):
        if not is_admin(callback.from_user.id):
            return

        prod_id = int(callback.data.split("_")[2])
        await db.activate_product_by_id(prod_id)
        prod = await db.get_product(prod_id)
        name = prod["name"] if prod else "Mahsulot"

        # Chat toza (clean) turishi uchun tasdiqlash xabari darhol o'chiriladi!
        if callback.message:
            try:
                await callback.message.delete()
            except Exception:
                pass

        await callback.answer(f"✅ '{name}' tasdiqlandi va do'konga joylandi!", show_alert=False)

    @router.callback_query(F.data.startswith("chan_reject_"))
    async def reject_channel_post_callback(callback: CallbackQuery):
        if not is_admin(callback.from_user.id):
            return

        prod_id = int(callback.data.split("_")[2])
        await db.deactivate_product_by_id(prod_id)
        prod = await db.get_product(prod_id)
        name = prod["name"] if prod else "Mahsulot"

        del_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🗑 Kanaldan ham o'chirish", callback_data=f"chan_delmsg_{prod_id}")],
            [InlineKeyboardButton(text="❌ Xabarni tozalash (O'chirish)", callback_data="admin_dismiss_msg")]
        ])
        res_text = (
            f"❌ <b>MAHSULOT RAD ETILDI!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📱 <b>Model:</b> {name}\n\n"
            f"⚠️ <i>Mahsulot mini ilovadan (do'kondan) olib tashlandi va xaridorlarga ko'rinmaydi.</i>"
        )
        if callback.message:
            if callback.message.photo:
                await callback.message.edit_caption(caption=res_text, reply_markup=del_kb, parse_mode="HTML")
            else:
                await callback.message.edit_text(text=res_text, reply_markup=del_kb, parse_mode="HTML")
        await callback.answer("❌ Mahsulot rad etildi.")

    @router.callback_query(F.data.startswith("chan_delmsg_"))
    async def delete_channel_msg_callback(callback: CallbackQuery):
        if not is_admin(callback.from_user.id):
            return

        prod_id = int(callback.data.split("_")[2])
        prod = await db.get_product(prod_id)
        if prod and prod.get("channel_id") and prod.get("message_id"):
            try:
                await bot.delete_message(chat_id=prod["channel_id"], message_id=prod["message_id"])
                await db.deactivate_product_by_id(prod_id)
                if callback.message:
                    try:
                        await callback.message.delete()
                    except Exception:
                        pass
                await callback.answer("🗑 Post Telegram kanalidan ham o'chirildi!", show_alert=True)
            except Exception as e:
                await callback.answer(f"O'chirishda xatolik: {e}", show_alert=True)
        else:
            await callback.answer("Post ma'lumotlari topilmadi.", show_alert=True)

    @router.callback_query(F.data == "admin_dismiss_msg")
    async def dismiss_msg_callback(callback: CallbackQuery):
        if callback.message:
            try:
                await callback.message.delete()
            except Exception:
                pass
        await callback.answer()

    # =========================================================================
    # 3. Kanal postlarini qo'lda sinxronlash
    # =========================================================================
    @router.callback_query(F.data == "admin_sync_channel")
    async def sync_channel_callback(callback: CallbackQuery):
        if not is_admin(callback.from_user.id):
            return

        await callback.answer("Sinxronlash boshlandi...")
        from bot.handlers.channel import sync_deleted_channel_posts
        deleted = await sync_deleted_channel_posts(db, config.channel_username)
        res_text = (
            f"🔄 <b>Kanal muvaffaqiyatli sinxronlandi!</b>\n"
            f"O'chirilgan postlar: <b>{len(deleted)} ta</b> aniqlandi va mini appdan olib tashlandi."
        )
        if callback.message:
            await callback.message.answer(res_text, parse_mode="HTML")

    # =========================================================================
    # 4. Admin chatda to'g'ridan-to'g'ri rasm va narx yuborganda avtomatik post taklif qilish
    # =========================================================================
    @router.message(F.photo)
    async def auto_detect_admin_post(message: Message, state: FSMContext):
        if not message.from_user or not is_admin(message.from_user.id):
            return

        cur_state = await state.get_state()
        if cur_state and cur_state != AdminStates.waiting_for_channel_post:
            return

        raw_text = (message.caption or "").strip()
        if not raw_text or not any(k in raw_text.lower() for k in ["$", "usd", "narx", "pro", "iphone", "macbook", "air", "gb"]):
            return

        await state.set_state(AdminStates.waiting_for_channel_post)

        if message.media_group_id:
            mg_id = str(message.media_group_id)
            if mg_id not in _admin_mg_buffers:
                _admin_mg_buffers[mg_id] = []
            _admin_mg_buffers[mg_id].append(message)

            if mg_id in _admin_mg_tasks and not _admin_mg_tasks[mg_id].done():
                _admin_mg_tasks[mg_id].cancel()

            async def _process_debounced_admin_mg(mg: str, uid: int):
                try:
                    await asyncio.sleep(0.8)
                    msgs = _admin_mg_buffers.pop(mg, [])
                    _admin_mg_tasks.pop(mg, None)
                    if msgs:
                        msgs.sort(key=lambda m: m.message_id)
                        await _send_admin_draft_preview(uid, state, msgs)
                except asyncio.CancelledError:
                    pass

            _admin_mg_tasks[mg_id] = asyncio.create_task(_process_debounced_admin_mg(mg_id, message.from_user.id))
            return

        await _send_admin_draft_preview(message.from_user.id, state, [message])

    return router
