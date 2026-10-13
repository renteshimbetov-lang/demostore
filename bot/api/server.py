import json
import os
from aiohttp import web
from bot.database.db import Database

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
        # Static rasmlar uchun tezkor kesh (scroll paytida qayta yuklanib miltillamasligi uchun)
        if request.path.startswith("/static/products/") or any(request.path.endswith(ext) for ext in [".jpg", ".png", ".jpeg", ".webp"]):
            response.headers["Cache-Control"] = "public, max-age=604800, immutable"
        else:
            # HTML va dinamik API uchun no-cache
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response

    app.middlewares.append(cors_middleware)

    # API Endpoints
    async def get_categories(request: web.Request) -> web.Response:
        categories = await db.get_categories()
        return web.json_response(categories)

    async def get_products(request: web.Request) -> web.Response:
        category_id_param = request.query.get("category_id")
        sort_param = request.query.get("sort", "default")
        search_param = request.query.get("search", "")

        category_id = int(category_id_param) if category_id_param and category_id_param.isdigit() else None
        products = await db.get_active_products(
            category_id=category_id,
            sort_by=sort_param,
            search=search_param
        )
        for p in products:
            raw_g = p.get("gallery_images")
            if isinstance(raw_g, str):
                try:
                    p["gallery_images"] = json.loads(raw_g)
                except Exception:
                    p["gallery_images"] = [p["image_url"]] if p.get("image_url") else []
            elif not raw_g:
                p["gallery_images"] = [p["image_url"]] if p.get("image_url") else []
        return web.json_response(products)

    async def increment_product_click(request: web.Request) -> web.Response:
        product_id = int(request.match_info["id"])
        new_views = await db.increment_views(product_id)
        return web.json_response({
            "success": True,
            "product_id": product_id,
            "views_count": new_views
        })

    async def get_stats(request: web.Request) -> web.Response:
        stats = await db.get_stats()
        top_products = await db.get_top_viewed_products(limit=10)
        return web.json_response({
            **stats,
            "top_products": top_products
        })

    # Marshrutlarni ro'yxatdan o'tkazish
    app.router.add_get("/api/categories", get_categories)
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

        app.router.add_get("/", serve_index)
        app.router.add_get("/webapp", serve_index)
        app.router.add_get("/intro.mp4", serve_intro)

    return app
