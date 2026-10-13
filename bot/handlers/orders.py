from aiogram import Router, F
from aiogram.types import Message
from bot.database.db import Database
from bot.utils.helpers import format_price

def setup_orders_router(db: Database) -> Router:
    router = Router()

    @router.message(F.text.in_(["📦 Buyurtmalarim", "Buyurtmalarim"]))
    async def show_user_orders(message: Message):
        user_id = message.from_user.id if message.from_user else 0
        orders = await db.get_user_orders(user_id)
        
        if not orders:
            await message.answer(
                "<b>Sizda hali buyurtmalar mavjud emas.</b>\n\nKatalogdan tovarlarni tanlab, birinchi buyurtmangizni amalga oshirishingiz mumkin!",
                parse_mode="HTML"
            )
            return

        response_lines = ["<b>Sizning buyurtmalaringiz tarixi:</b>\n"]
        for o in orders:
            status_emoji = "🟡"
            if o['status'] == "Yetkazildi":
                status_emoji = "🟢"
            elif o['status'] == "Bekor qilindi":
                status_emoji = "🔴"
            elif o['status'] == "Yetkazilmoqda":
                status_emoji = "🚚"

            response_lines.append(f"━━━━━━━━━━━━━━━━━━")
            response_lines.append(f"🆔 <b>Buyurtma #{o['id']}</b> ({o['created_at'][:16]})")
            response_lines.append(f"{status_emoji} <b>Holat:</b> <i>{o['status']}</i>")
            response_lines.append(f"💳 <b>Toʻlov:</b> {o['payment_method']}")
            response_lines.append("📋 <b>Mahsulotlar:</b>")
            for it in o.get('items', []):
                response_lines.append(f"  • {it['product_name']} ({it['quantity']} dona) — {format_price(it['price'] * it['quantity'])}")
            response_lines.append(f"💰 <b>Jami:</b> <b>{format_price(o['total_amount'])}</b>")

        from aiogram.types import ReplyKeyboardRemove
        await message.answer("\n".join(response_lines), reply_markup=ReplyKeyboardRemove(), parse_mode="HTML")

    return router
