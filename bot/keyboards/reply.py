from aiogram.types import ReplyKeyboardRemove, ReplyKeyboardMarkup, KeyboardButton, WebAppInfo
from bot.config import config

def get_main_menu(is_admin: bool = False, cart_count: int = 0):
    """Adminlar uchun qulay boshqaruv tugmasi, oddiy mijozlar uchun esa toza ekran"""
    if is_admin:
        kb = []
        if config.webapp_url and config.webapp_url.startswith("https://"):
            kb.append([KeyboardButton(text="🛍 Do'konni ochish", web_app=WebAppInfo(url=config.webapp_url))])
        kb.append([KeyboardButton(text="⚙️ Admin Panel")])
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
