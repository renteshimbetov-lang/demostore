from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, FSInputFile
from pathlib import Path
from bot.config import config
from bot.database.db import Database
from bot.keyboards.inline import (
    get_categories_inline,
    get_products_inline,
    get_product_detail_inline
)
from bot.utils.helpers import format_price

def setup_catalog_router(db: Database) -> Router:
    router = Router()

    @router.message(F.text.in_(["🛍 Mahsulotlar katalogi", "Mahsulotlar katalogi"]))
    async def show_categories_message(message: Message):
        from aiogram.types import ReplyKeyboardRemove
        categories = await db.get_categories()
        text = "📁 <b>Mahsulotlar katalogi</b>\n\nQuyidagi kategoriyalardan birini tanlang:"
        await message.answer("Katalog yuklanmoqda...", reply_markup=ReplyKeyboardRemove())
        await message.answer(text, reply_markup=get_categories_inline(categories), parse_mode="HTML")

    @router.callback_query(F.data == "back_to_cats")
    async def back_to_categories_callback(callback: CallbackQuery):
        categories = await db.get_categories()
        text = "📁 <b>Mahsulotlar katalogi</b>\n\nQuyidagi kategoriyalardan birini tanlang:"
        
        if callback.message:
            # Agar oldingi xabar rasm bo'lsa yoki matn bo'lsa
            try:
                await callback.message.edit_text(text, reply_markup=get_categories_inline(categories), parse_mode="HTML")
            except Exception:
                await callback.message.delete()
                await callback.message.answer(text, reply_markup=get_categories_inline(categories), parse_mode="HTML")
        await callback.answer()

    @router.callback_query(F.data.startswith("cat_"))
    async def show_category_products(callback: CallbackQuery):
        cat_id = int(callback.data.split("_")[1])
        category = await db.get_category(cat_id)
        if not category:
            await callback.answer("Kategoriya topilmadi!", show_alert=True)
            return

        products = await db.get_products_by_category(cat_id)
        if not products:
            text = f"📁 <b>{category['icon']} {category['name']}</b>\n\nUshbu boʻlimda hozircha mahsulotlar mavjud emas."
        else:
            text = f"📁 <b>{category['icon']} {category['name']}</b>\n\nKerakli mahsulotni tanlang:"

        if callback.message:
            try:
                await callback.message.edit_text(text, reply_markup=get_products_inline(cat_id, products), parse_mode="HTML")
            except Exception:
                await callback.message.delete()
                await callback.message.answer(text, reply_markup=get_products_inline(cat_id, products), parse_mode="HTML")
        await callback.answer()

    @router.callback_query(F.data.startswith("prod_"))
    async def show_product_detail(callback: CallbackQuery):
        prod_id = int(callback.data.split("_")[1])
        product = await db.get_product(prod_id)
        if not product:
            await callback.answer("Mahsulot topilmadi!", show_alert=True)
            return

        caption = (
            f"📦 <b>{product['name']}</b>\n\n"
            f"📝 <b>Tavsif:</b>\n{product['description']}\n\n"
            f"💵 <b>Narxi:</b> <b>{format_price(product['price'])}</b>\n"
            f"✅ <b>Holati:</b> Omborda mavjud"
        )

        reply_markup = get_product_detail_inline(product['category_id'], product['id'])

        if callback.message:
            await callback.message.delete()
            photo_obj = None
            raw_url = product.get('image_url') or ""
            if raw_url:
                if raw_url.startswith("/static/"):
                    local_p = Path(__file__).resolve().parent.parent.parent / "webapp" / raw_url.lstrip("/")
                    if local_p.exists():
                        photo_obj = FSInputFile(str(local_p))
                    elif config.webapp_url and config.webapp_url.startswith("http"):
                        photo_obj = f"{config.webapp_url.rstrip('/')}{raw_url}"
                elif raw_url.startswith("http"):
                    photo_obj = raw_url

            if photo_obj:
                try:
                    await callback.message.answer_photo(
                        photo=photo_obj,
                        caption=caption,
                        reply_markup=reply_markup,
                        parse_mode="HTML"
                    )
                except Exception:
                    # Agar rasm yuklanmasa oddiy matn sifatida yuborish
                    await callback.message.answer(caption, reply_markup=reply_markup, parse_mode="HTML")
            else:
                await callback.message.answer(caption, reply_markup=reply_markup, parse_mode="HTML")

        await callback.answer()

    @router.callback_query(F.data.startswith("add_cart_"))
    async def add_to_cart_callback(callback: CallbackQuery):
        prod_id = int(callback.data.split("_")[2])
        user_id = callback.from_user.id
        
        product = await db.get_product(prod_id)
        if not product:
            await callback.answer("Mahsulot topilmadi!", show_alert=True)
            return

        await db.add_to_cart(user_id, prod_id, quantity=1)
        await callback.answer(f"✅ {product['name']} savatchaga qoʻshildi!", show_alert=False)

    return router
