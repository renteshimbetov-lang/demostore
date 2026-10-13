import json
from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
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
    @router.callback_query(F.data == "admin_create_post")
    async def start_create_post(callback: CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            return

        await state.set_state(AdminStates.waiting_for_channel_post)
        text = (
            "📢 <b>KANALGA YANGI POST TAYYORLASH</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "Mahsulot <b>rasmini</b> va <b>tavsifini</b> (nomi, narxi, parametrlari) yuboring.\n\n"
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

        raw_text = (message.caption or message.text or "").strip()
        if not raw_text:
            await message.answer(
                "⚠️ Iltimos, mahsulot rasmi bilan birga uning nomi va narxini ham yozib yuboring.\n"
                "Bekor qilish uchun <code>/cancel</code> deb yozing.",
                parse_mode="HTML"
            )
            return

        name, description, price = parse_channel_post_content(raw_text)
        photo_file_id = message.photo[-1].file_id if message.photo else None
        price_uzs = format_price(price * config.usd_rate)

        await state.update_data(
            name=name,
            description=description,
            price=price,
            raw_text=raw_text,
            photo_file_id=photo_file_id
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

        if photo_file_id:
            await message.answer_photo(photo=photo_file_id, caption=preview_text, reply_markup=confirm_kb, parse_mode="HTML")
        else:
            await message.answer(preview_text, reply_markup=confirm_kb, parse_mode="HTML")

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

        try:
            if data.get("photo_file_id"):
                sent = await bot.send_photo(
                    chat_id=channel_target,
                    photo=data["photo_file_id"],
                    caption=channel_caption,
                    parse_mode="HTML"
                )
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
            img_url = f"/api/photo/{data['photo_file_id']}" if data.get("photo_file_id") else "/static/apple_3d_logo.png"
            await db.upsert_product_from_channel(
                channel_id=str(channel_target),
                message_id=chan_msg_id,
                name=data["name"],
                description=data["description"],
                price=data["price"],
                image_url=img_url,
                post_url=post_url,
                photo_file_id=data.get("photo_file_id"),
                gallery_images=json.dumps([img_url])
            )

            res_text = (
                f"✅ <b>POST KANALGA VA DO'KONGA MUVAFFAQIYATLI JOYLANDI!</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"📱 <b>Model:</b> {data['name']}\n"
                f"💵 <b>Narxi:</b> ${data['price']}\n"
                f"🔗 <b>Kanal posti:</b> <a href=\"{post_url}\">Kanalda ko'rish</a>\n"
                f"🛍 <i>Mini ilovada (do'konda) mijozlar uchun darhol faol bo'ldi!</i>"
            )
            if callback.message:
                if callback.message.photo:
                    await callback.message.edit_caption(caption=res_text, parse_mode="HTML")
                else:
                    await callback.message.edit_text(text=res_text, parse_mode="HTML")
            await callback.answer("✅ Muvaffaqiyatli kanalga joylandi!")
        except Exception as e:
            await callback.answer(f"Kanalga yuborishda xatolik: {e}", show_alert=True)

    @router.callback_query(F.data == "admin_cancel_channel_post")
    async def cancel_channel_post_callback(callback: CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            return

        await state.clear()
        cancel_text = "❌ <b>Post bekor qilindi. Kanalga yoki do'konga joylanmadi.</b>"
        if callback.message:
            if callback.message.photo:
                await callback.message.edit_caption(caption=cancel_text, parse_mode="HTML")
            else:
                await callback.message.edit_text(text=cancel_text, parse_mode="HTML")
        await callback.answer("Bekor qilindi.")

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
        price = prod["price"] if prod else 0

        res_text = (
            f"✅ <b>MAHSULOT TASDIQLANDI VA DO'KONGA JOYLANDI!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📱 <b>Model:</b> {name}\n"
            f"💵 <b>Narxi:</b> ${price}\n\n"
            f"🛍 <i>Mahsulot mini ilovada (do'konda) mijozlar uchun muvaffaqiyatli faollashtirildi!</i>"
        )
        if callback.message:
            if callback.message.photo:
                await callback.message.edit_caption(caption=res_text, parse_mode="HTML")
            else:
                await callback.message.edit_text(text=res_text, parse_mode="HTML")
        await callback.answer("✅ Do'konga joylandi!")

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
            [InlineKeyboardButton(text="↩️ Qayta faollashtirish", callback_data=f"chan_approve_{prod_id}")]
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
                res_text = (
                    f"🗑 <b>POST TELEGRAM KANALIDAN HAM O'CHIRILDI!</b>\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"📱 <b>Model:</b> {prod['name']}\n"
                    f"Post kanaldan va do'kondan butunlay tozalab tashlandi."
                )
                if callback.message:
                    if callback.message.photo:
                        await callback.message.edit_caption(caption=res_text, parse_mode="HTML")
                    else:
                        await callback.message.edit_text(text=res_text, parse_mode="HTML")
                await callback.answer("🗑 Kanaldan o'chirildi!", show_alert=True)
            except Exception as e:
                await callback.answer(f"O'chirishda xatolik: {e}", show_alert=True)
        else:
            await callback.answer("Post ma'lumotlari topilmadi.", show_alert=True)

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

        name, description, price = parse_channel_post_content(raw_text)
        photo_file_id = message.photo[-1].file_id
        price_uzs = format_price(price * config.usd_rate)

        await state.set_state(AdminStates.waiting_for_channel_post)
        await state.update_data(
            name=name,
            description=description,
            price=price,
            raw_text=raw_text,
            photo_file_id=photo_file_id
        )

        preview_text = (
            f"✨ <b>YANGI POST TAYYORLANDI</b>\n"
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
        await message.reply(preview_text, reply_markup=confirm_kb, parse_mode="HTML")

    return router
