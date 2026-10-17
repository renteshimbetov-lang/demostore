from aiogram.types import ReplyKeyboardRemove, ReplyKeyboardMarkup, KeyboardButton, WebAppInfo
from bot.config import config

def get_main_menu(is_admin: bool = False, cart_count: int = 0):
    """Adminlar uchun qulay boshqaruv tugmasi, oddiy mijozlar uchun esa toza ekran"""
    if is_admin:
        kb = []
        base_url = config.webapp_url.rstrip('/') if config.webapp_url else ""
        store_url = f"{base_url}/?app=store" if base_url else ""
        admin_url = f"{base_url}/admin" if base_url else ""
        top_row = []
        if store_url and store_url.startswith("https://"):
            top_row.append(KeyboardButton(text="🛍 Do'kon", web_app=WebAppInfo(url=store_url)))
        if admin_url and admin_url.startswith("https://"):
            top_row.append(KeyboardButton(text="⚙️ Admin Mini App", web_app=WebAppInfo(url=admin_url)))
        else:
            top_row.append(KeyboardButton(text="⚙️ Admin Panel"))
        kb.append(top_row)
        return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
    return ReplyKeyboardRemove()

def get_phone_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Telefon raqamni yuborish", request_contact=True)],
            [KeyboardButton(text="Bekor qilish")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )

def get_location_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Joylashuvni yuborish", request_location=True)],
            [KeyboardButton(text="Bekor qilish")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )

def get_cancel_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Bekor qilish")]],
        resize_keyboard=True
    )
