import asyncio
import json
import logging
import os
import time
from typing import Dict, Optional, Tuple
import aiohttp
from aiohttp import web
from bot.config import config
from bot.database.db import Database
from bot.api.telegram_auth import extract_and_validate_telegram_user
from bot.utils.cache import cache_manager

logger = logging.getLogger("APIServer")

# Rasmlar bo'yicha bir vaqtda ortiqcha so'rov yuborilmasligini nazorat qiluvchi qulf
_photo_locks: Dict[str, asyncio.Lock] = {}
_cache_lock = asyncio.Lock()

def _get_fallback_image(webapp_dir: str) -> Tuple[bytes, str]:
    """Standart zaxira rasmni (apple_3d_logo.png) yuklash"""
    candidates = [
        os.path.join(webapp_dir, "static", "apple_3d_logo.png"),
        os.path.join(webapp_dir, "apple_3d_logo.png"),
    ]
    for p in candidates:
        if os.path.exists(p):
            try:
                with open(p, "rb") as f:
                    return f.read(), "image/png"
            except Exception:
                pass
    # 1x1 transparent PNG fallback if file is not found
    return (
        b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82',
        "image/png"
    )

_shared_photo_session: Optional[aiohttp.ClientSession] = None

async def _get_photo_session() -> aiohttp.ClientSession:
    global _shared_photo_session
    if _shared_photo_session is None or _shared_photo_session.closed:
        from bot.utils.ssl_context import get_ssl_context
        connector = aiohttp.TCPConnector(ssl=get_ssl_context(), limit=30, ttl_dns_cache=300)
        timeout = aiohttp.ClientTimeout(total=15, connect=5)
        _shared_photo_session = aiohttp.ClientSession(connector=connector, timeout=timeout)
    return _shared_photo_session

async def _fetch_telegram_photo(file_id: str, bot_token: str) -> Optional[Tuple[bytes, str]]:
    """Telegram API orqali rasmni xavfsiz va barqaror yuklab olish (qayta urinish bilan)"""
    if not bot_token or not file_id:
        return None
    api_url = f"https://api.telegram.org/bot{bot_token}/getFile?file_id={file_id}"
    
    for attempt in range(2):
        try:
            session = await _get_photo_session()
            async with session.get(api_url) as resp:
                if resp.status != 200:
                    continue
                data = await resp.json()
                if not data.get("ok"):
                    continue
                file_path = data.get("result", {}).get("file_path")
                if not file_path:
                    continue

            download_url = f"https://api.telegram.org/file/bot{bot_token}/{file_path}"
            async with session.get(download_url) as file_resp:
                if file_resp.status != 200:
                    continue
                img_bytes = await file_resp.read()
                content_type = file_resp.headers.get("Content-Type", "image/jpeg")
                if not content_type.startswith("image/"):
                    content_type = "image/jpeg"
                return img_bytes, content_type
        except Exception as e:
            if attempt == 1:
                logger.warning(f"Telegram rasm olishda xatolik ({file_id}): {e}")
            await asyncio.sleep(0.3)
    return None

def create_web_app(db: Database, webapp_dir: str, bot=None) -> web.Application:
    app = web.Application()

    # CORS va Keshlashni boshqarish middleware
    @web.middleware
    async def cors_middleware(request, handler):
        if request.method == "OPTIONS":
            response = web.Response(status=200)
        else:
            response = await handler(request)

        origin = request.headers.get("Origin", "").strip()
        allowed = False
        if origin:
            if (
                origin == "https://telegram.org"
                or origin == "https://web.telegram.org"
                or origin.endswith(".telegram.org")
                or origin.endswith(".onrender.com")
                or (config.webapp_url and origin == config.webapp_url.rstrip("/"))
                or origin.startswith("http://localhost:")
                or origin.startswith("http://127.0.0.1:")
            ):
                allowed = True
                response.headers["Access-Control-Allow-Origin"] = origin

        if not allowed:
            # Standart Telegram domeni
            response.headers["Access-Control-Allow-Origin"] = "https://web.telegram.org"

        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, X-Telegram-Init-Data, Authorization"
        response.headers["Access-Control-Max-Age"] = "86400"

        # Rasm proksi va statik resurslar uchun tezkor kesh
        clean_path = request.path.split("?")[0]
        if request.path.startswith("/api/photo/"):
            response.headers["Cache-Control"] = "public, max-age=86400, immutable"
        elif request.path.startswith("/static/products/") or any(clean_path.endswith(ext) for ext in [".jpg", ".png", ".jpeg", ".webp", ".svg", ".ico", ".woff", ".woff2"]):
            response.headers["Cache-Control"] = "public, max-age=604800, immutable"
        elif any(clean_path.endswith(ext) for ext in [".css", ".js"]):
            response.headers["Cache-Control"] = "public, max-age=86400, stale-while-revalidate=604800"
        elif request.path == "/" or request.path.endswith(".html") or request.path.startswith("/api/"):
            # HTML va dinamik API uchun no-cache
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        else:
            response.headers["Cache-Control"] = "public, max-age=86400"
        return response

    app.middlewares.append(cors_middleware)

    # API Endpoints
    async def get_photo_proxy(request: web.Request) -> web.Response:
        """
        Telegram file_id orqali rasmni xavfsiz proksi qilib berish.
        BOT_TOKEN oshkor etilmaydi, rasmlar server xotirasida kamida 12 soat keshlanadi.
        Xatolik bo'lsa 500 emas, standart fallback rasm qaytariladi.
        """
        file_id = request.match_info.get("file_id", "").strip()
        if not file_id:
            fb_bytes, fb_type = _get_fallback_image(webapp_dir)
            return web.Response(
                body=fb_bytes,
                content_type=fb_type,
                headers={"Cache-Control": "public, max-age=86400, immutable"}
            )

        # 1. Tezkor kesh tekshiruvi (L1 RAM + L2 Redis)
        cached = await cache_manager.get_photo(file_id)
        if cached:
            c_bytes, c_type = cached
            return web.Response(
                body=c_bytes,
                content_type=c_type,
                headers={"Cache-Control": "public, max-age=604800, immutable"}
            )

        # 2. Concurrency lock: bir xil rasm uchun Telegramga bittadan ortiq so'rov bormaydi
        async with _cache_lock:
            if file_id not in _photo_locks:
                _photo_locks[file_id] = asyncio.Lock()
            item_lock = _photo_locks[file_id]

        async with item_lock:
            # Lock ichida qayta tekshirish
            cached = await cache_manager.get_photo(file_id)
            if cached:
                c_bytes, c_type = cached
                return web.Response(
                    body=c_bytes,
                    content_type=c_type,
                    headers={"Cache-Control": "public, max-age=604800, immutable"}
                )

            # Telegramdan yuklab olish
            res = await _fetch_telegram_photo(file_id, config.bot_token)
            if res:
                img_bytes, ctype = res
                # 7 kunga keshlaymiz (L1 RAM + L2 Redis)
                await cache_manager.set_photo(file_id, img_bytes, ctype, ttl_seconds=604800)
                return web.Response(
                    body=img_bytes,
                    content_type=ctype,
                    headers={"Cache-Control": "public, max-age=604800, immutable"}
                )
            else:
                # Telegram xatosi yoki yaroqsiz file_id bo'lsa 500 bermasdan zaxira rasm qaytaramiz
                fb_bytes, fb_type = _get_fallback_image(webapp_dir)
                return web.Response(
                    body=fb_bytes,
                    content_type=fb_type,
                    headers={"Cache-Control": "no-cache, no-store, must-revalidate"}
                )

    async def get_categories(request: web.Request) -> web.Response:
        user = extract_and_validate_telegram_user(request)
        if not user:
            return web.json_response({"error": "Unauthorized"}, status=401)
        categories = await db.get_categories()
        return web.json_response(categories)

    async def get_currency(request: web.Request) -> web.Response:
        user = extract_and_validate_telegram_user(request)
        if not user:
            return web.json_response({"error": "Unauthorized"}, status=401)
        from bot.utils.currency import get_cbu_usd_rate, format_rate_compact, CACHE_TTL_SECONDS
        force = request.query.get("force", "").strip().lower() in ("1", "true")
        rate = await get_cbu_usd_rate(force_refresh=force)
        return web.json_response({
            "rate": rate,
            "currency": "USD",
            "formatted": format_rate_compact(rate),
            "cache_ttl_seconds": CACHE_TTL_SECONDS
        })

    async def get_products(request: web.Request) -> web.Response:
        user = extract_and_validate_telegram_user(request)
        if not user:
            return web.json_response({"error": "Unauthorized"}, status=401)
        from bot.utils.currency import get_cbu_usd_rate, convert_usd_to_uzs, format_rate_compact
        category_id_param = request.query.get("category_id")
        sort_param = request.query.get("sort", "default")
        search_param = request.query.get("search", "")
        min_price_param = request.query.get("min_price")
        max_price_param = request.query.get("max_price")

        category_id = int(category_id_param) if category_id_param and category_id_param.isdigit() else None
        min_price = int(min_price_param) if min_price_param and min_price_param.isdigit() else None
        max_price = int(max_price_param) if max_price_param and max_price_param.isdigit() else None

        current_rate = await get_cbu_usd_rate()
        products = await db.get_active_products(
            category_id=category_id,
            sort_by=sort_param,
            search=search_param,
            min_price=min_price,
            max_price=max_price,
            usd_rate=current_rate
        )

        for p in products:
            img = (p.get("image_url") or "").strip()
            if img.startswith("http://") or img.startswith("https://"):
                p["image_url"] = img
            elif p.get("photo_file_id"):
                p["image_url"] = f"/api/photo/{p['photo_file_id']}"
            elif img:
                p["image_url"] = img
            else:
                p["image_url"] = "/static/apple_3d_logo.png"

            raw_g = p.get("gallery_images")
            if isinstance(raw_g, str):
                try:
                    p["gallery_images"] = json.loads(raw_g)
                except Exception:
                    p["gallery_images"] = [p["image_url"]]
            elif not raw_g:
                p["gallery_images"] = [p["image_url"]]

            p["current_usd_rate"] = current_rate
            if p.get("currency") == "UZS" and p.get("price_uzs"):
                p["price_uzs"] = int(p["price_uzs"])
            else:
                p["currency"] = p.get("currency") or "USD"
                p["price_uzs"] = convert_usd_to_uzs(p.get("price", 0), current_rate)

        return web.json_response({
            "products": products,
            "current_usd_rate": current_rate,
            "rate_text": format_rate_compact(current_rate)
        })

    async def increment_product_click(request: web.Request) -> web.Response:
        user = extract_and_validate_telegram_user(request)
        if not user:
            return web.json_response({"error": "Unauthorized"}, status=401)

        try:
            product_id = int(request.match_info["id"])
        except (ValueError, KeyError):
            return web.json_response({"error": "Invalid product ID"}, status=400)

        user_id = int(user.get("id") or 0)
        if user_id <= 0:
            return web.json_response({"error": "User ID not identified"}, status=400)

        incremented, new_views = await db.increment_views_safe(product_id, user_id)
        return web.json_response({
            "success": True,
            "product_id": product_id,
            "views_count": new_views,
            "incremented": incremented
        })

    async def get_stats(request: web.Request) -> web.Response:
        user = extract_and_validate_telegram_user(request)
        if not user:
            return web.json_response({"error": "Unauthorized"}, status=401)
        user_id = int(user.get("id") or 0)
        if not config.admin_ids or user_id not in config.admin_ids:
            return web.json_response({"error": "Forbidden: Admin access required"}, status=403)

        from bot.utils.currency import get_cbu_usd_rate
        stats = await db.get_stats()
        top_products = await db.get_top_viewed_products(limit=10)
        current_rate = await get_cbu_usd_rate()
        return web.json_response({
            **stats,
            "current_usd_rate": current_rate,
            "top_products": top_products
        })

    # =========================================================================
    # ADMIN MINI ILOVA API ENDPOINTLARI
    # =========================================================================
    def _verify_admin(request: web.Request) -> Tuple[Optional[Dict[str, Any]], Optional[web.Response]]:
        # 1. Avval Admin Session Token tekshiriladi (Tashqi Safari/Chrome brauzerlarida Telegram-siz kirish uchun)
        token = (
            request.headers.get("X-Admin-Token")
            or request.query.get("token")
            or request.query.get("admin_token")
        )
        if not token:
            auth_h = request.headers.get("Authorization", "")
            if auth_h.lower().startswith("bearer "):
                token = auth_h[7:].strip()

        if token:
            from bot.api.telegram_auth import verify_admin_token
            verified = verify_admin_token(token, config.bot_token, config.admin_ids)
            if verified:
                return verified, None

        # 2. Telegram WebApp initData tekshiriladi
        user = extract_and_validate_telegram_user(request)
        if not user:
            return None, web.json_response({"error": "Unauthorized: Telegram sessiyasi yoki Admin tokeni topilmadi"}, status=401)
        user_id = int(user.get("id") or 0)
        if not config.admin_ids or user_id not in config.admin_ids:
            return None, web.json_response({"error": "Forbidden: Faqat tizim adminlari uchun"}, status=403)
        return user, None

    async def admin_check(request: web.Request) -> web.Response:
        """Admin ruxsatini va Telegram foydalanuvchisini tasdiqlash hamda brauzer tokenini qaytarish"""
        user, err = _verify_admin(request)
        if err:
            return err
        user_id = int(user.get("id") or 0)
        from bot.api.telegram_auth import generate_admin_session_token
        admin_token = generate_admin_session_token(user_id, config.bot_token)
        return web.json_response({
            "ok": True,
            "is_admin": True,
            "admin_token": admin_token,
            "user": user,
            "store_name": config.store_name
        })

    async def admin_dashboard(request: web.Request) -> web.Response:
        """Admin Boshqaruv paneli umumiy ko'rsatkichlari"""
        user, err = _verify_admin(request)
        if err:
            return err
        from bot.utils.currency import get_cbu_usd_rate, format_rate_compact
        stats = await db.get_stats()
        top_products = await db.get_top_viewed_products(limit=8)
        recent_orders = await db.get_all_orders(limit=8)
        current_rate = await get_cbu_usd_rate()
        return web.json_response({
            "stats": stats,
            "top_products": top_products,
            "recent_orders": recent_orders,
            "current_usd_rate": current_rate,
            "rate_text": format_rate_compact(current_rate),
            "channel": {
                "id": config.channel_id,
                "username": config.channel_username,
                "url": config.channel_url
            }
        })

    async def admin_get_products(request: web.Request) -> web.Response:
        """Admin uchun barcha mahsulotlar (faol, nofaol, chegirmalar)"""
        user, err = _verify_admin(request)
        if err:
            return err
        search = request.query.get("search", "")
        category_id_param = request.query.get("category_id")
        status = request.query.get("status", "all")
        category_id = int(category_id_param) if category_id_param and category_id_param.isdigit() else None

        from bot.utils.currency import get_cbu_usd_rate, convert_usd_to_uzs
        current_rate = await get_cbu_usd_rate()
        products = await db.get_all_products_admin(search=search, category_id=category_id, status=status)

        for p in products:
            img = (p.get("image_url") or "").strip()
            if img.startswith("http://") or img.startswith("https://"):
                p["image_url"] = img
            elif p.get("photo_file_id"):
                p["image_url"] = f"/api/photo/{p['photo_file_id']}"
            elif img:
                p["image_url"] = img
            else:
                p["image_url"] = "/static/apple_3d_logo.png"

            if p.get("currency") == "UZS" and p.get("price_uzs"):
                p["price_uzs"] = int(p["price_uzs"])
            else:
                p["currency"] = p.get("currency") or "USD"
                p["price_uzs"] = convert_usd_to_uzs(p.get("price", 0), current_rate)

        categories = await db.get_categories()
        return web.json_response({
            "products": products,
            "categories": categories,
            "current_usd_rate": current_rate
        })

    async def admin_create_product(request: web.Request) -> web.Response:
        """Admin orqali yangi mahsulot yaratish"""
        user, err = _verify_admin(request)
        if err:
            return err
        try:
            data = await request.json()
        except Exception:
            return web.json_response({"error": "Yaroqsiz JSON"}, status=400)

        name = str(data.get("name", "")).strip()
        if not name:
            return web.json_response({"error": "Mahsulot nomi kiritilishi shart"}, status=400)
        price = int(data.get("price", 0))
        desc = str(data.get("description", "")).strip()
        cat_id = int(data["category_id"]) if data.get("category_id") else None
        img = str(data.get("image_url", "")).strip()
        currency = str(data.get("currency", "USD")).upper()
        price_uzs = int(data["price_uzs"]) if data.get("price_uzs") else None
        is_discount = 1 if data.get("is_discount") else 0
        is_active = 1 if data.get("is_active", 1) else 0

        prod_id = await db.create_product_admin(
            name=name, price=price, description=desc, category_id=cat_id,
            image_url=img, currency=currency, price_uzs=price_uzs,
            is_discount=is_discount, is_active=is_active
        )
        return web.json_response({"success": True, "id": prod_id})

    async def admin_update_product(request: web.Request) -> web.Response:
        """Admin orqali mahsulot ma'lumotlarini to'liq tahrirlash"""
        user, err = _verify_admin(request)
        if err:
            return err
        try:
            product_id = int(request.match_info["id"])
            data = await request.json()
        except Exception:
            return web.json_response({"error": "Yaroqsiz so'rov"}, status=400)

        name = str(data.get("name", "")).strip()
        price = int(data.get("price", 0))
        desc = str(data.get("description", "")).strip()
        cat_id = int(data["category_id"]) if data.get("category_id") else None
        currency = str(data.get("currency", "USD")).upper()
        price_uzs = int(data["price_uzs"]) if data.get("price_uzs") else None
        is_discount = 1 if data.get("is_discount") else 0
        is_active = 1 if data.get("is_active", 1) else 0
        img_url = data.get("image_url")

        await db.update_product_admin(
            product_id=product_id, name=name, price=price, description=desc,
            category_id=cat_id, currency=currency, price_uzs=price_uzs,
            is_discount=is_discount, is_active=is_active, image_url=img_url
        )
        return web.json_response({"success": True, "product_id": product_id})

    async def admin_toggle_active(request: web.Request) -> web.Response:
        """Mahsulotning faol/nofaol holatini almashtirish"""
        user, err = _verify_admin(request)
        if err:
            return err
        product_id = int(request.match_info["id"])
        new_state = await db.toggle_product_active(product_id)
        return web.json_response({"success": True, "product_id": product_id, "is_active": new_state})

    async def admin_activate_all_products(request: web.Request) -> web.Response:
        """Barcha nofaol mahsulotlarni bir vaqtda faollashtirish"""
        user, err = _verify_admin(request)
        if err:
            return err
        count = await db.activate_all_inactive_products()
        return web.json_response({
            "success": True,
            "count": count,
            "message": f"Barcha nofaol mahsulotlar ({count} ta) muvaffaqiyatli faollashtirildi!"
        })

    async def admin_toggle_discount(request: web.Request) -> web.Response:
        """Mahsulotning chegirma holatini almashtirish"""
        user, err = _verify_admin(request)
        if err:
            return err
        product_id = int(request.match_info["id"])
        new_state = await db.toggle_product_discount(product_id)
        return web.json_response({"success": True, "product_id": product_id, "is_discount": new_state})

    async def admin_delete_product(request: web.Request) -> web.Response:
        """Mahsulotni o'chirish"""
        user, err = _verify_admin(request)
        if err:
            return err
        product_id = int(request.match_info["id"])
        await db.delete_product(product_id)
        return web.json_response({"success": True, "product_id": product_id})

    async def admin_get_orders(request: web.Request) -> web.Response:
        """Buyurtmalar ro'yxati"""
        user, err = _verify_admin(request)
        if err:
            return err
        status = request.query.get("status")
        limit = int(request.query.get("limit", 50))
        orders = await db.get_all_orders(limit=limit, status=status)
        return web.json_response({"orders": orders})

    async def admin_update_order_status(request: web.Request) -> web.Response:
        """Buyurtma holatini yangilash"""
        user, err = _verify_admin(request)
        if err:
            return err
        try:
            order_id = int(request.match_info["id"])
            data = await request.json()
            status = str(data.get("status", "")).strip()
        except Exception:
            return web.json_response({"error": "Yaroqsiz so'rov"}, status=400)

        if not status:
            return web.json_response({"error": "Status ko'rsatilmagan"}, status=400)
        await db.update_order_status(order_id, status)
        return web.json_response({"success": True, "order_id": order_id, "status": status})

    async def admin_sync_channel(request: web.Request) -> web.Response:
        """Kanalda o'chirilgan postlarni zudlik bilan aniqlash va sinxronlash"""
        user, err = _verify_admin(request)
        if err:
            return err
        from bot.handlers.channel import sync_deleted_channel_posts
        deleted_ids = await sync_deleted_channel_posts(db, config.channel_username)
        return web.json_response({
            "success": True,
            "deleted_count": len(deleted_ids),
            "deleted_ids": deleted_ids
        })

    async def admin_publish_channel(request: web.Request) -> web.Response:
        """Admin mini ilovadan to'g'ridan-to'g'ri kanalga post chiqarish"""
        user, err = _verify_admin(request)
        if err:
            return err
        if not bot:
            return web.json_response({"error": "Telegram Bot ulanmagan"}, status=503)
        if not config.channel_id:
            return web.json_response({"error": "CHANNEL_ID .env da ko'rsatilmagan"}, status=400)

        try:
            data = await request.json()
        except Exception:
            return web.json_response({"error": "Yaroqsiz JSON"}, status=400)

        name = str(data.get("name", "")).strip()
        price = int(data.get("price", 0))
        desc = str(data.get("description", "")).strip()
        currency = str(data.get("currency", "USD")).upper()
        is_discount = bool(data.get("is_discount", False))
        image_url = str(data.get("image_url", "")).strip()

        price_tag = f"{price:,} so'm" if currency == "UZS" else f"${price:,}"
        caption = f"🔥 <b>{name}</b>\n\n"
        if is_discount:
            caption += f"⚡️ <b>MAXSUS AKSIYA: {price_tag}</b>\n\n"
        else:
            caption += f"💰 <b>Narxi:</b> {price_tag}\n\n"

        if desc:
            caption += f"ℹ️ {desc}\n\n"

        if config.channel_url:
            caption += f"👉 Kanalimiz: {config.channel_url}\n"
        if config.webapp_url:
            caption += f"🛍 Mini Ilova: {config.webapp_url}"

        try:
            if image_url and (image_url.startswith("http://") or image_url.startswith("https://")):
                msg = await bot.send_photo(
                    chat_id=config.channel_id,
                    photo=image_url,
                    caption=caption,
                    parse_mode="HTML"
                )
            else:
                msg = await bot.send_message(
                    chat_id=config.channel_id,
                    text=caption,
                    parse_mode="HTML"
                )

            post_url = f"https://t.me/{config.channel_username}/{msg.message_id}" if config.channel_username else None
            prod_id = await db.upsert_product_from_channel(
                channel_id=config.channel_id,
                message_id=msg.message_id,
                name=name,
                description=desc,
                price=price,
                image_url=image_url,
                post_url=post_url,
                currency=currency,
                price_uzs=price if currency == "UZS" else None
            )
            await db.activate_product_by_id(prod_id, is_discount=1 if is_discount else 0)

            return web.json_response({
                "success": True,
                "product_id": prod_id,
                "message_id": msg.message_id,
                "post_url": post_url
            })
        except Exception as e:
            logger.error(f"Kanalga post chiqarishda xatolik: {e}")
            return web.json_response({"error": f"Telegram xatosi: {str(e)}"}, status=500)

    # Marshrutlarni ro'yxatdan o'tkazish
    app.router.add_get("/api/photo/{file_id}", get_photo_proxy)
    app.router.add_get("/api/categories", get_categories)
    app.router.add_get("/api/currency", get_currency)
    app.router.add_get("/api/products", get_products)
    app.router.add_post("/api/products/{id}/click", increment_product_click)
    app.router.add_get("/api/stats", get_stats)

    # Admin API marshrutlari
    app.router.add_get("/api/admin/check", admin_check)
    app.router.add_get("/api/admin/dashboard", admin_dashboard)
    app.router.add_get("/api/admin/products", admin_get_products)
    app.router.add_post("/api/admin/products", admin_create_product)
    app.router.add_put("/api/admin/products/{id}", admin_update_product)
    app.router.add_post("/api/admin/products/{id}/toggle-active", admin_toggle_active)
    app.router.add_post("/api/admin/products/activate-all", admin_activate_all_products)
    app.router.add_post("/api/admin/products/{id}/toggle-discount", admin_toggle_discount)
    app.router.add_delete("/api/admin/products/{id}", admin_delete_product)
    app.router.add_get("/api/admin/orders", admin_get_orders)
    app.router.add_post("/api/admin/orders/{id}/status", admin_update_order_status)
    app.router.add_post("/api/admin/sync-channel", admin_sync_channel)
    app.router.add_post("/api/admin/publish-channel", admin_publish_channel)

    # Mini-ilova Frontend statik fayllari
    if os.path.exists(webapp_dir):
        app.router.add_static("/static", path=webapp_dir, name="static")

        async def serve_index(request: web.Request) -> web.FileResponse:
            index_path = os.path.join(webapp_dir, "index.html")
            return web.FileResponse(index_path)

        async def serve_intro(request: web.Request) -> web.StreamResponse:
            intro_path = os.path.join(webapp_dir, "intro.mp4")
            if os.path.exists(intro_path):
                return web.FileResponse(intro_path)
            return web.Response(status=404)

        async def serve_demo(request: web.Request) -> web.FileResponse:
            demo_path = os.path.join(webapp_dir, "mini_app_demo.html")
            if os.path.exists(demo_path):
                return web.FileResponse(demo_path)
            return web.FileResponse(os.path.join(webapp_dir, "index.html"))

        async def serve_taplink(request: web.Request) -> web.FileResponse:
            taplink_path = os.path.join(webapp_dir, "taplink.html")
            if os.path.exists(taplink_path):
                return web.FileResponse(taplink_path)
            return web.FileResponse(os.path.join(webapp_dir, "index.html"))

        async def serve_admin(request: web.Request) -> web.FileResponse:
            admin_path = os.path.join(webapp_dir, "admin.html")
            if os.path.exists(admin_path):
                return web.FileResponse(admin_path)
            return web.FileResponse(os.path.join(webapp_dir, "index.html"))

        app.router.add_get("/", serve_index)
        app.router.add_get("/webapp", serve_index)
        app.router.add_get("/admin", serve_admin)
        app.router.add_get("/admin/", serve_admin)
        app.router.add_get("/admin/index.html", serve_admin)
        app.router.add_get("/intro.mp4", serve_intro)
        app.router.add_get("/demo", serve_demo)
        app.router.add_get("/buttons", serve_demo)
        app.router.add_get("/taplink", serve_taplink)
        app.router.add_get("/links", serve_taplink)
        app.router.add_get("/linktree", serve_taplink)

    async def _on_cleanup_app(app_instance: web.Application):
        await cache_manager.close()

    app.on_cleanup.append(_on_cleanup_app)

    return app
