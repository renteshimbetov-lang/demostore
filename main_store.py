import asyncio
import logging
import os
import sys
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand

from bot.config import config
from bot.database.db import Database
from bot.api.server import create_web_app
from bot.handlers import (
    setup_common_router,
    setup_catalog_router,
    setup_cart_router,
    setup_checkout_router,
    setup_orders_router,
    setup_admin_router,
    setup_channel_router
)

# Logging sozlash
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("DemoStore")

async def set_bot_commands(bot: Bot):
    # /start komandasini qo'shish va Telegram pastki chap menyu tugmasini sozlash
    try:
        from aiogram.types import BotCommand, MenuButtonWebApp, WebAppInfo
        await bot.set_my_commands([
            BotCommand(command="start", description="Do'konni ochish (Mini App)")
        ])
        if config.webapp_url and config.webapp_url.startswith("https://"):
            await bot.set_chat_menu_button(
                menu_button=MenuButtonWebApp(
                    text="Do'kon",
                    web_app=WebAppInfo(url=config.webapp_url)
                )
            )
        logger.info("/start komandasi va Do'kon menyu tugmasi muvaffaqiyatli sozlandi!")
    except Exception as e:
        logger.warning(f"Komandalarni sozlashda xatolik: {e}")

async def main():
    if not config.bot_token or config.bot_token == "YOUR_BOT_TOKEN_HERE":
        logger.error(
            "\n" + "="*60 + "\n"
            "DIQQAT! Bot tokeni ko'rsatilmagan!\n"
            "Iltimos, '.env' faylini oching va BOT_TOKEN o'zgaruvchisiga\n"
            "@BotFather dan olingan tokenni joylashtiring.\n"
            "="*60 + "\n"
        )
        sys.exit(1)

    logger.info("Ma'lumotlar bazasi initsializatsiya qilinmoqda...")
    db = Database(config.db_path)
    await db.init_db()
    logger.info("Ma'lumotlar bazasi tayyor!")

    bot = Bot(
        token=config.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher()

    # Routerlarni ulash
    dp.include_router(setup_channel_router(db, bot))
    dp.include_router(setup_admin_router(db, bot))
    dp.include_router(setup_checkout_router(db, bot))
    dp.include_router(setup_cart_router(db))
    dp.include_router(setup_catalog_router(db))
    dp.include_router(setup_orders_router(db))
    dp.include_router(setup_common_router(db))

    await set_bot_commands(bot)

    if config.webapp_url and config.webapp_url.startswith("https://"):
        try:
            from aiogram.types import MenuButtonWebApp, WebAppInfo
            await bot.set_chat_menu_button(
                menu_button=MenuButtonWebApp(text="Do'kon", web_app=WebAppInfo(url=config.webapp_url))
            )
            logger.info("Chat MenuButton muvaffaqiyatli 'Do'kon' WebApp ga sozlandi!")
        except Exception as e:
            logger.warning(f"MenuButton sozlashda ogohlantirish: {e}")

    # Mini App va REST API serverini ishga tushirish
    webapp_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "webapp")
    web_app = create_web_app(db, webapp_dir)
    runner = web.AppRunner(web_app)
    await runner.setup()
    
    port = config.web_port
    active_port = None
    for p in range(port, port + 20):
        try:
            site = web.TCPSite(runner, host="0.0.0.0", port=p)
            await site.start()
            active_port = p
            break
        except OSError:
            continue

    if not active_port:
        raise RuntimeError("Port bandligi sababli web server ishga tushmadi!")

    logger.info(f"Mini-ilova va REST API muvaffaqiyatli ishga tushdi: http://localhost:{active_port}")

    logger.info(f"Telegram Bot muvaffaqiyatli ishga tushdi! ({config.store_name})")
    
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    finally:
        await runner.cleanup()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Dastur to'xtatildi.")
