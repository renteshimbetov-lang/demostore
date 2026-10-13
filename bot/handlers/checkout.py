from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from bot.config import config
from bot.database.db import Database
from bot.states.states import CheckoutStates
from bot.keyboards.reply import get_main_menu, get_phone_keyboard, get_location_keyboard
from bot.keyboards.inline import get_payment_inline, get_order_confirm_inline, get_order_status_inline
from bot.utils.helpers import format_price, format_order_summary

def setup_checkout_router(db: Database, bot: Bot) -> Router:
    router = Router()

    @router.callback_query(F.data == "order_checkout")
    async def start_checkout(callback: CallbackQuery, state: FSMContext):
        user_id = callback.from_user.id
        items = await db.get_cart(user_id)
        if not items:
            await callback.answer("Savatingiz boʻsh! Avval mahsulot qoʻshing.", show_alert=True)
            return

        total = sum(item['subtotal'] for item in items)
        await state.update_data(items=items, total=total)
        await state.set_state(CheckoutStates.waiting_for_name)

        suggested_name = callback.from_user.full_name or ""
        msg_text = (
            f"📝 <b>Buyurtmani rasmiylashtirish (1/4)</b>\n\n"
            f"Iltimos, ism va familiyangizni kiriting:\n"
            f"(Masalan: <i>{suggested_name}</i>)"
        )

        if callback.message:
            await callback.message.delete()
            await callback.message.answer(msg_text, parse_mode="HTML")
        await callback.answer()

    @router.message(CheckoutStates.waiting_for_name)
    async def process_name(message: Message, state: FSMContext):
        name = message.text.strip() if message.text else ""
        if len(name) < 2:
            await message.answer("Iltimos, ismingizni toʻliqroq kiriting:")
            return

        await state.update_data(full_name=name)
        await state.set_state(CheckoutStates.waiting_for_phone)

        await message.answer(
            f"📞 <b>Telefon raqamingiz (2/4)</b>\n\n"
            f"Pastdagi tugmani bosing yoki raqamingizni yozib yuboring:\n"
            f"(Masalan: <i>+998901234567</i>)",
            reply_markup=get_phone_keyboard(),
            parse_mode="HTML"
        )

    @router.message(CheckoutStates.waiting_for_phone, F.contact)
    @router.message(CheckoutStates.waiting_for_phone, F.text)
    async def process_phone(message: Message, state: FSMContext):
        if message.contact:
            phone = message.contact.phone_number
            if not phone.startswith("+"):
                phone = f"+{phone}"
        else:
            phone = (message.text or "").strip()
            if len(phone) < 7:
                await message.answer("Iltimos, toʻgʻri telefon raqam kiriting (masalan: +998901234567):")
                return

        await state.update_data(phone=phone)
        await state.set_state(CheckoutStates.waiting_for_address)

        await message.answer(
            f"📍 <b>Yetkazib berish manzili (3/4)</b>\n\n"
            f"Pastdagi <b>'Joylashuvni yuborish'</b> tugmasini bosing yoki manzilingizni matn koʻrinishida yozing:\n"
            f"(Masalan: <i>Toshkent sh., Chilonzor tumani, 9-mavze, 12-uy</i>)",
            reply_markup=get_location_keyboard(),
            parse_mode="HTML"
        )

    @router.message(CheckoutStates.waiting_for_address, F.location)
    @router.message(CheckoutStates.waiting_for_address, F.text)
    async def process_address(message: Message, state: FSMContext):
        if message.location:
            address = f"Geo-lokatsiya: {message.location.latitude:.6f}, {message.location.longitude:.6f}"
        else:
            address = (message.text or "").strip()
            if len(address) < 4:
                await message.answer("Iltimos, manzilingizni aniqroq yozing:")
                return

        await state.update_data(address=address)
        await state.set_state(CheckoutStates.waiting_for_payment)

        # Reply keyboardni olib tashlash va inline to'lov turini ko'rsatish
        is_admin = message.from_user.id in config.admin_ids if message.from_user else False
        await message.answer(
            "💳 <b>Toʻlov turini tanlang (4/4):</b>",
            reply_markup=get_payment_inline(),
            parse_mode="HTML"
        )

    @router.callback_query(CheckoutStates.waiting_for_payment, F.data.startswith("pay_"))
    async def process_payment_choice(callback: CallbackQuery, state: FSMContext):
        data_choice = callback.data
        if data_choice == "pay_cash":
            payment_name = "💵 Naqd pul (qabul qilinganda)"
        elif data_choice == "pay_click":
            payment_name = "💳 Click (Demo toʻlov)"
        else:
            payment_name = "💳 Payme (Demo toʻlov)"

        await state.update_data(payment_method=payment_name)
        data = await state.get_data()
        
        summary_text = (
            f"📋 <b>Buyurtmangiz maʼlumotlarini tasdiqlang:</b>\n\n"
            f"👤 <b>Qabul qiluvchi:</b> {data['full_name']}\n"
            f"📞 <b>Telefon:</b> {data['phone']}\n"
            f"📍 <b>Manzil:</b> {data['address']}\n"
            f"💳 <b>Toʻlov turi:</b> {payment_name}\n"
            f"💰 <b>Jami summa:</b> <b>{format_price(data['total'])}</b>\n\n"
            f"Barcha maʼlumotlar toʻgʻrimi?"
        )

        await state.set_state(CheckoutStates.waiting_for_confirm)
        if callback.message:
            await callback.message.edit_text(summary_text, reply_markup=get_order_confirm_inline(), parse_mode="HTML")
        await callback.answer()

    @router.callback_query(CheckoutStates.waiting_for_confirm, F.data == "order_confirm_yes")
    async def confirm_order(callback: CallbackQuery, state: FSMContext):
        data = await state.get_data()
        user_id = callback.from_user.id

        order_id = await db.create_order(
            user_id=user_id,
            full_name=data['full_name'],
            phone=data['phone'],
            address=data['address'],
            payment_method=data['payment_method'],
            total_amount=data['total'],
            items=data['items']
        )

        await state.clear()

        is_admin = user_id in config.admin_ids
        success_text = (
            f"🎉 <b>Buyurtmangiz muvaffaqiyatli qabul qilindi!</b>\n\n"
            f"🆔 <b>Buyurtma raqami:</b> #{order_id}\n"
            f"📞 Tez orada operatorlarimiz siz bilan bogʻlanishadi.\n\n"
            f"Xaridingiz uchun tashakkur! 😊"
        )

        if callback.message:
            await callback.message.delete()
            await callback.message.answer(
                success_text,
                reply_markup=get_main_menu(is_admin=is_admin, cart_count=0),
                parse_mode="HTML"
            )

        # Adminlarga xabar yuborish
        admin_order_text = (
            f"🚨 <b>YANGI BUYURTMA #{order_id}!</b>\n\n" +
            format_order_summary(
                order_id=order_id,
                full_name=data['full_name'],
                phone=data['phone'],
                address=data['address'],
                payment_method=data['payment_method'],
                items=data['items'],
                total=data['total']
            )
        )

        for admin_id in config.admin_ids:
            try:
                await bot.send_message(
                    chat_id=admin_id,
                    text=admin_order_text,
                    reply_markup=get_order_status_inline(order_id),
                    parse_mode="HTML"
                )
            except Exception:
                pass

        await callback.answer()

    @router.callback_query(F.data == "order_cancel")
    async def cancel_order_callback(callback: CallbackQuery, state: FSMContext):
        await state.clear()
        user_id = callback.from_user.id
        is_admin = user_id in config.admin_ids
        cart_items = await db.get_cart(user_id)

        if callback.message:
            await callback.message.delete()
            await callback.message.answer(
                "❌ Buyurtma jarayoni bekor qilindi.",
                reply_markup=get_main_menu(is_admin=is_admin, cart_count=len(cart_items))
            )
        await callback.answer("Bekor qilindi")

    return router
