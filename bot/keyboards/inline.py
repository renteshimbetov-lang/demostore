from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from typing import List, Dict, Any
from bot.utils.helpers import format_price

def get_categories_inline(categories: List[Dict[str, Any]]) -> InlineKeyboardMarkup:
    buttons = []
    # 2 tadan qilib joylash
    row = []
    for cat in categories:
        row.append(InlineKeyboardButton(text=f"{cat['icon']} {cat['name']}", callback_data=f"cat_{cat['id']}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    
    buttons.append([InlineKeyboardButton(text="🛒 Savatchaga oʻtish", callback_data="view_cart")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_products_inline(category_id: int, products: List[Dict[str, Any]]) -> InlineKeyboardMarkup:
    buttons = []
    for p in products:
        buttons.append([InlineKeyboardButton(text=f"{p['name']} — {format_price(p['price'])}", callback_data=f"prod_{p['id']}")])
    
    buttons.append([
        InlineKeyboardButton(text="◀️ Kategoriyalarga qaytish", callback_data="back_to_cats"),
        InlineKeyboardButton(text="🛒 Savat", callback_data="view_cart")
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_product_detail_inline(category_id: int, product_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🛒 Savatga qoʻshish", callback_data=f"add_cart_{product_id}")],
            [
                InlineKeyboardButton(text="◀️ Ortga", callback_data=f"cat_{category_id}"),
                InlineKeyboardButton(text="🛒 Savat", callback_data="view_cart")
            ]
        ]
    )

def get_cart_inline(cart_items: List[Dict[str, Any]]) -> InlineKeyboardMarkup:
    buttons = []
    for item in cart_items:
        p_id = item['product_id']
        name = item['name'][:18] + ".." if len(item['name']) > 18 else item['name']
        buttons.append([
            InlineKeyboardButton(text=f"➖", callback_data=f"cart_dec_{p_id}"),
            InlineKeyboardButton(text=f"{name} ({item['quantity']})", callback_data=f"prod_{p_id}"),
            InlineKeyboardButton(text=f"➕", callback_data=f"cart_inc_{p_id}"),
            InlineKeyboardButton(text=f"❌", callback_data=f"cart_del_{p_id}")
        ])
    
    if cart_items:
        buttons.append([InlineKeyboardButton(text="🚖 Buyurtma berish", callback_data="order_checkout")])
        buttons.append([InlineKeyboardButton(text="🗑 Savatni tozalash", callback_data="cart_clear")])
        
    buttons.append([InlineKeyboardButton(text="🛍 Katalogga qaytish", callback_data="back_to_cats")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_payment_inline() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💵 Naqd pul (yetkazilganda)", callback_data="pay_cash")],
            [InlineKeyboardButton(text="💳 Click (Demo toʻlov)", callback_data="pay_click")],
            [InlineKeyboardButton(text="💳 Payme (Demo toʻlov)", callback_data="pay_payme")],
            [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="order_cancel")]
        ]
    )

def get_order_confirm_inline() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Ha, tasdiqlayman", callback_data="order_confirm_yes"),
                InlineKeyboardButton(text="❌ Bekor qilish", callback_data="order_cancel")
            ]
        ]
    )

def get_admin_main_inline() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📊 Statistika", callback_data="admin_stats")],
            [InlineKeyboardButton(text="📦 Oxirgi buyurtmalar", callback_data="admin_orders")],
            [InlineKeyboardButton(text="📢 Xabar tarqatish (Broadcast)", callback_data="admin_broadcast")],
            [InlineKeyboardButton(text="➕ Mahsulot qoʻshish", callback_data="admin_add_product")]
        ]
    )

def get_order_status_inline(order_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Qabul qilindi", callback_data=f"status_{order_id}_Qabul qilindi"),
                InlineKeyboardButton(text="🚚 Yetkazilmoqda", callback_data=f"status_{order_id}_Yetkazilmoqda")
            ],
            [
                InlineKeyboardButton(text="🏁 Yetkazildi", callback_data=f"status_{order_id}_Yetkazildi"),
                InlineKeyboardButton(text="❌ Bekor qilindi", callback_data=f"status_{order_id}_Bekor qilindi")
            ],
            [InlineKeyboardButton(text="◀️ Buyurtmalar roʻyxatiga", callback_data="admin_orders")]
        ]
    )
