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

logger = logging.getLogger("APIServer")

# Telegram rasm proksi uchun server xotirasi keshi (kamida 12 soat)
_photo_cache: Dict[str, Tuple[bytes, str, float]] = {}  # file_id -> (bytes, content_type, expires_at)
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
        connector = aiohttp.TCPConnector(ssl=False, limit=30, ttl_dns_cache=300)
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

def create_web_app(db: Database, webapp_dir: str) -> web.Application:
    app = web.Application()

    # CORS va Keshlashni boshqarish middleware
    @web.middleware
    async def cors_middleware(request, handler):
        if request.method == "OPTIONS":
            response = web.Response(status=200)
        else:
            response = await handler(request)
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"

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

        now = time.time()
        # 1. Tezkor xotira keshi tekshiruvi
        cached = _photo_cache.get(file_id)
        if cached:
            c_bytes, c_type, expires_at = cached
            if now < expires_at:
                return web.Response(
                    body=c_bytes,
                    content_type=c_type,
                    headers={"Cache-Control": "public, max-age=86400, immutable"}
                )

        # 2. Concurrency lock: bir xil rasm uchun Telegramga bittadan ortiq so'rov bormaydi
        async with _cache_lock:
            if file_id not in _photo_locks:
                _photo_locks[file_id] = asyncio.Lock()
            item_lock = _photo_locks[file_id]

        async with item_lock:
            # Lock ichida qayta tekshirish
            cached = _photo_cache.get(file_id)
            if cached:
                c_bytes, c_type, expires_at = cached
                if time.time() < expires_at:
                    return web.Response(
                        body=c_bytes,
                        content_type=c_type,
                        headers={"Cache-Control": "public, max-age=86400, immutable"}
                    )

            # Telegramdan yuklab olish
            res = await _fetch_telegram_photo(file_id, config.bot_token)
            if res:
                img_bytes, ctype = res
                # Kesh hajmini cheklash (maksimal 500 ta rasm)
                if len(_photo_cache) > 500:
                    curr_time = time.time()
                    expired_keys = [k for k, v in _photo_cache.items() if v[2] <= curr_time]
                    for k in expired_keys:
                        _photo_cache.pop(k, None)
                    if len(_photo_cache) > 500:
                        oldest = sorted(_photo_cache.keys(), key=lambda k: _photo_cache[k][2])
                        for k in oldest[:100]:
                            _photo_cache.pop(k, None)

                # 12 soatga keshlaymiz (43200 soniya)
                _photo_cache[file_id] = (img_bytes, ctype, time.time() + 43200)
                return web.Response(
                    body=img_bytes,
                    content_type=ctype,
                    headers={"Cache-Control": "public, max-age=86400, immutable"}
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
        categories = await db.get_categories()
        return web.json_response(categories)

    async def get_currency(request: web.Request) -> web.Response:
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
            p["price_uzs"] = convert_usd_to_uzs(p.get("price", 0), current_rate)

        return web.json_response({
            "products": products,
            "current_usd_rate": current_rate,
            "rate_text": format_rate_compact(current_rate)
        })

    async def increment_product_click(request: web.Request) -> web.Response:
        product_id = int(request.match_info["id"])
        new_views = await db.increment_views(product_id)
        return web.json_response({
            "success": True,
            "product_id": product_id,
            "views_count": new_views
        })

    async def get_stats(request: web.Request) -> web.Response:
        from bot.utils.currency import get_cbu_usd_rate
        stats = await db.get_stats()
        top_products = await db.get_top_viewed_products(limit=10)
        current_rate = await get_cbu_usd_rate()
        return web.json_response({
            **stats,
            "current_usd_rate": current_rate,
            "top_products": top_products
        })

    # Marshrutlarni ro'yxatdan o'tkazish
    app.router.add_get("/api/photo/{file_id}", get_photo_proxy)
    app.router.add_get("/api/categories", get_categories)
    app.router.add_get("/api/currency", get_currency)
    app.router.add_get("/api/products", get_products)
    app.router.add_post("/api/products/{id}/click", increment_product_click)
    app.router.add_get("/api/stats", get_stats)

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

        app.router.add_get("/", serve_index)
        app.router.add_get("/webapp", serve_index)
        app.router.add_get("/intro.mp4", serve_intro)
        app.router.add_get("/demo", serve_demo)
        app.router.add_get("/buttons", serve_demo)
        app.router.add_get("/taplink", serve_taplink)
        app.router.add_get("/links", serve_taplink)
        app.router.add_get("/linktree", serve_taplink)

    return app
