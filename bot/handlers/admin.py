from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from bot.config import config
from bot.database.db import Database
from bot.states.states import AdminStates
from bot.utils.helpers import format_price

def setup_admin_router(db: Database, bot: Bot) -> Router:
    router = Router()

    def is_admin(user_id: int) -> bool:
        return user_id in config.admin_ids

    def get_admin_menu_inline() -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="Statistika hisoboti", callback_data="admin_stats")],
                [InlineKeyboardButton(text="Oxirgi buyurtmalar", callback_data="admin_orders")],
                [InlineKeyboardButton(text="Xabar tarqatish (Broadcast)", callback_data="admin_broadcast")],
                [InlineKeyboardButton(text="Yangi mahsulot qo'shish", callback_data="admin_add_product")]
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
            f"<b>Admin Boshqaruv Paneli</b>\n\n"
            f"Foydalanuvchilar: <b>{stats['users_count']}</b> ta\n"
            f"Faol mahsulotlar: <b>{stats['products_count']}</b> ta\n"
            f"Buyurtmalar: <b>{stats['orders_count']}</b> ta\n"
            f"Jami aylanma: <b>{format_price(stats['total_revenue'])}</b>\n\n"
            f"Boshqarish uchun bo'limni tanlang:"
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
            f"<b>Admin Boshqaruv Paneli</b>\n\n"
            f"Foydalanuvchilar: <b>{stats['users_count']}</b> ta\n"
            f"Faol mahsulotlar: <b>{stats['products_count']}</b> ta\n"
            f"Buyurtmalar: <b>{stats['orders_count']}</b> ta\n"
            f"Jami aylanma: <b>{format_price(stats['total_revenue'])}</b>\n\n"
            f"Boshqarish uchun bo'limni tanlang:"
        )
        if callback.message:
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

    return router
