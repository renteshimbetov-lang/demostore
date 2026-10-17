from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from bot.config import config
from bot.database.db import Database
from bot.keyboards.reply import get_main_menu
from bot.states.states import SearchStates
from bot.keyboards.inline import get_products_inline

def setup_common_router(db: Database) -> Router:
    router = Router()

    @router.message(CommandStart())
    async def start_handler(message: Message, state: FSMContext):
        await state.clear()
        user = message.from_user
        if user:
            await db.add_user(user.id, user.full_name, user.username)
        
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
        from bot.keyboards.reply import get_main_menu
        
        is_admin_user = bool(user and user.id in config.admin_ids)
        reply_kb = get_main_menu(is_admin=is_admin_user)

        # 1. Salomlashish
        await message.answer(
            f"Assalomu alaykum, <b>{user.first_name if user else 'Qadrli mijoz'}</b>!\n"
            f"<b>{config.store_name}</b> rasmiy do'koniga xush kelibsiz!",
            reply_markup=reply_kb,
            parse_mode="HTML"
        )
        
        buttons = []
        base_url = config.webapp_url.rstrip('/') if config.webapp_url else ""
        if base_url and base_url.startswith("https://"):
            buttons.append([InlineKeyboardButton(text="🛍 Do'konni ochish (Mini App)", web_app=WebAppInfo(url=f"{base_url}/?app=store"))])
        
        if is_admin_user:
            admin_url = f"{config.webapp_url.rstrip('/')}/admin" if config.webapp_url else ""
            if admin_url.startswith("https://"):
                buttons.append([InlineKeyboardButton(text="⚙️ Admin Mini App", web_app=WebAppInfo(url=admin_url))])
            else:
                buttons.append([InlineKeyboardButton(text="⚙️ Admin Boshqaruv Paneli", callback_data="admin_main")])

        inline_kb = InlineKeyboardMarkup(inline_keyboard=buttons) if buttons else None
        
        welcome_text = (
            f"Barcha tovarlar, aksiyalar va buyurtma berish xizmati mini ilovamizda mavjud.\n\n"
            f"Xarid qilish uchun quyidagi tugmani bosing 👇"
        )
        if is_admin_user:
            welcome_text += (
                f"\n\n⚙️ <b>Siz tizim adminisiz!</b>\n"
                f"Kanal postlari moderatsiyasi va boshqaruv uchun <b>Admin Panel</b> tugmasidan foydalaning."
            )
        
        await message.answer(
            welcome_text,
            reply_markup=inline_kb,
            parse_mode="HTML"
        )

    @router.message(F.text.in_(["❌ Bekor qilish", "Bekor qilish"]))
    async def cancel_action(message: Message, state: FSMContext):
        await state.clear()
        from aiogram.types import ReplyKeyboardRemove
        await message.answer(
            "Amal bekor qilindi.",
            reply_markup=ReplyKeyboardRemove()
        )

    @router.message(F.text.in_(["ℹ️ Biz haqimizda", "Biz haqimizda"]))
    async def about_us_handler(message: Message):
        from aiogram.types import ReplyKeyboardRemove
        text = (
            f"<b>{config.store_name} haqida</b>\n\n"
            f"Biz sizga faqat 100% original va kafolatlangan texnika mahsulotlarini taqdim etamiz!\n\n"
            f"Yetkazib berish: Butun O'zbekiston bo'ylab 24 soat ichida\n"
            f"Kafolat: Barcha qurilmalarga 1 yil rasmiy kafolat\n"
            f"To'lov: Naqd pul, Click, Payme orqali\n\n"
            f"Biz bilan xaridingiz doimo qulay va ishonchli!"
        )
        await message.answer(text, reply_markup=ReplyKeyboardRemove(), parse_mode="HTML")

    @router.message(F.text.in_(["📞 Bogʻlanish", "Bog'lanish", "Bogʻlanish"]))
    async def contact_handler(message: Message):
        from aiogram.types import ReplyKeyboardRemove
        text = (
            f"<b>Mijozlarni qo'llab-quvvatlash xizmati:</b>\n\n"
            f"Telefon: {config.support_phone}\n"
            f"Telegram: {config.support_username}\n"
            f"Ish vaqti: Har kuni 09:00 dan 21:00 gacha\n\n"
            f"Savol yoki takliflaringiz bo'lsa, biz bilan bog'lanishingiz mumkin."
        )
        await message.answer(text, reply_markup=ReplyKeyboardRemove(), parse_mode="HTML")

    @router.message(F.text.in_(["🔍 Qidiruv", "Qidiruv"]))
    async def start_search(message: Message, state: FSMContext):
        await state.set_state(SearchStates.waiting_for_query)
        await message.answer(
            "Qidirmoqchi bo'lgan mahsulot nomini yoki kalit so'zni yozing (masalan: <i>iPhone</i>, <i>MacBook</i>):",
            parse_mode="HTML"
        )

    @router.message(SearchStates.waiting_for_query)
    async def process_search(message: Message, state: FSMContext):
        query = message.text or ""
        await state.clear()
        
        results = await db.search_products(query)
        if not results:
            await message.answer(
                f"Afsuski, <b>'{query}'</b> bo'yicha hech qanday mahsulot topilmadi.\nBoshqa so'z bilan qidirib ko'ring.",
                parse_mode="HTML"
            )
            return

        await message.answer(
            f"<b>'{query}'</b> so'rovi bo'yicha topilgan mahsulotlar ({len(results)} ta):",
            reply_markup=get_products_inline(0, results),
            parse_mode="HTML"
        )

    return router
