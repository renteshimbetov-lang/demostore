from aiogram.types import ReplyKeyboardRemove, ReplyKeyboardMarkup, KeyboardButton, WebAppInfo
from bot.config import config

def get_main_menu(is_admin: bool = False, cart_count: int = 0) -> ReplyKeyboardRemove:
    """Chatdagi barcha komanda va klaviatura tugmalarini to'liq olib tashlash"""
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
