from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from bot.database.db import Database
from bot.keyboards.inline import get_cart_inline
from bot.utils.helpers import format_price

def setup_cart_router(db: Database) -> Router:
    router = Router()

    async def render_cart_content(user_id: int):
        items = await db.get_cart(user_id)
        if not items:
            text = "🛒 <b>Sizning savatingiz hozircha boʻsh!</b>\n\nKatalogdan oʻzingizga maʼqul mahsulotlarni tanlab, savatga qoʻshishingiz mumkin."
            return text, get_cart_inline([])

        total = sum(item['subtotal'] for item in items)
        lines = ["🛒 <b>Sizning savatingiz:</b>\n"]
        for i, item in enumerate(items, 1):
            lines.append(
                f"{i}. <b>{item['name']}</b>\n"
                f"   {item['quantity']} dona × {format_price(item['price'])} = <b>{format_price(item['subtotal'])}</b>"
            )
        lines.append("\n━━━━━━━━━━━━━━━━━━")
        lines.append(f"💰 <b>Jami toʻlov summasi:</b> <b>{format_price(total)}</b>")
        lines.append("━━━━━━━━━━━━━━━━━━\nPastdagi tugmalar orqali miqdorni oʻzgartirishingiz mumkin:")
        
        return "\n".join(lines), get_cart_inline(items)

    @router.message(F.text.startswith("🛒 Savat") | F.text.startswith("Savat"))
    async def show_cart_message(message: Message):
        from aiogram.types import ReplyKeyboardRemove
        user_id = message.from_user.id if message.from_user else 0
        text, reply_markup = await render_cart_content(user_id)
        await message.answer("Savat:", reply_markup=ReplyKeyboardRemove())
        await message.answer(text, reply_markup=reply_markup, parse_mode="HTML")

    @router.callback_query(F.data == "view_cart")
    async def show_cart_callback(callback: CallbackQuery):
        user_id = callback.from_user.id
        text, reply_markup = await render_cart_content(user_id)
        
        if callback.message:
            try:
                await callback.message.edit_text(text, reply_markup=reply_markup, parse_mode="HTML")
            except Exception:
                await callback.message.delete()
                await callback.message.answer(text, reply_markup=reply_markup, parse_mode="HTML")
        await callback.answer()

    @router.callback_query(F.data.startswith("cart_inc_"))
    async def increment_cart_item(callback: CallbackQuery):
        prod_id = int(callback.data.split("_")[2])
        user_id = callback.from_user.id
        await db.update_cart_item(user_id, prod_id, change=1)
        
        text, reply_markup = await render_cart_content(user_id)
        if callback.message:
            try:
                await callback.message.edit_text(text, reply_markup=reply_markup, parse_mode="HTML")
            except Exception:
                pass
        await callback.answer("+1 qoʻshildi")

    @router.callback_query(F.data.startswith("cart_dec_"))
    async def decrement_cart_item(callback: CallbackQuery):
        prod_id = int(callback.data.split("_")[2])
        user_id = callback.from_user.id
        await db.update_cart_item(user_id, prod_id, change=-1)
        
        text, reply_markup = await render_cart_content(user_id)
        if callback.message:
            try:
                await callback.message.edit_text(text, reply_markup=reply_markup, parse_mode="HTML")
            except Exception:
                pass
        await callback.answer("-1 ayrildi")

    @router.callback_query(F.data.startswith("cart_del_"))
    async def delete_cart_item(callback: CallbackQuery):
        prod_id = int(callback.data.split("_")[2])
        user_id = callback.from_user.id
        await db.remove_from_cart(user_id, prod_id)
        
        text, reply_markup = await render_cart_content(user_id)
        if callback.message:
            try:
                await callback.message.edit_text(text, reply_markup=reply_markup, parse_mode="HTML")
            except Exception:
                pass
        await callback.answer("Mahsulot savatdan oʻchirildi")

    @router.callback_query(F.data == "cart_clear")
    async def clear_cart_callback(callback: CallbackQuery):
        user_id = callback.from_user.id
        await db.clear_cart(user_id)
        
        text, reply_markup = await render_cart_content(user_id)
        if callback.message:
            try:
                await callback.message.edit_text(text, reply_markup=reply_markup, parse_mode="HTML")
            except Exception:
                pass
        await callback.answer("Savat tozalandi")

    return router
