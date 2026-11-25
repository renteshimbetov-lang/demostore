# Graph Report - demostore  (2026-11-21)

## Corpus Check
- 52 files · ~61,047 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 11 file(s) not represented in the graph (top: .css 8, .example 1, (none) 1)

## Summary
- 749 nodes · 1963 edges · 22 communities (14 shown, 8 thin omitted)
- Extraction: 94% EXTRACTED · 6% INFERRED · 0% AMBIGUOUS · INFERRED: 119 edges (avg confidence: 0.86)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `8e375805`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- webapp/app.js
- setup_admin_router
- setup_checkout_router
- app.min.js
- admin.js
- admin.py
- admin.min.js
- create_web_app
- os
- Database
- CacheManager
- js/app.js
- services
- package.json
- 🛒 DemoStore — Telegram E-Commerce & Mini App Ekotizimi
- BlurText.jsx
- run.sh
- mini_app_core.js
- mini_app_core.min.js

## God Nodes (most connected - your core abstractions)
1. `Database` - 88 edges
2. `setup_admin_router()` - 57 edges
3. `create_web_app()` - 43 edges
4. `run_full_tests()` - 34 edges
5. `is_admin()` - 27 edges
6. `format_price()` - 26 edges
7. `g()` - 24 edges
8. `setup_channel_router()` - 24 edges
9. `setup_checkout_router()` - 23 edges
10. `full_channel_sync()` - 22 edges

## Surprising Connections (you probably didn't know these)
- `main()` --calls--> `Database`  [EXTRACTED]
  main_store.py → bot/database/db.py
- `sync()` --calls--> `Database`  [EXTRACTED]
  sync_channel_photos_to_neon.py → bot/database/db.py
- `run_full_tests()` --calls--> `CacheManager`  [EXTRACTED]
  test_system.py → bot/utils/cache.py
- `main()` --calls--> `create_web_app()`  [EXTRACTED]
  main_store.py → bot/api/server.py
- `run_full_tests()` --calls--> `create_web_app()`  [EXTRACTED]
  test_system.py → bot/api/server.py

## Import Cycles
- None detected.

## Communities (22 total, 8 thin omitted)

### Community 0 - "webapp/app.js"
Cohesion: 0.08
Nodes (78): animateCartButton(), apiFetch(), applyImgZoom(), applyLanguage(), boot(), calcPanLimits(), changeCartQty(), checkAdminAccess() (+70 more)

### Community 1 - "setup_admin_router"
Cohesion: 0.10
Nodes (33): setup_admin_router(), add_discount_list_callback(), admin_main_callback(), admin_panel_handler(), approve_channel_post_as_discount_callback(), approve_channel_post_callback(), auto_detect_admin_post(), _process_debounced_admin_mg() (+25 more)

### Community 2 - "setup_checkout_router"
Cohesion: 0.06
Nodes (46): Config, load_config(), setup_cart_router(), clear_cart_callback(), decrement_cart_item(), delete_cart_item(), increment_cart_item(), render_cart_content() (+38 more)

### Community 3 - "app.min.js"
Cohesion: 0.08
Nodes (68): ai(), Be(), bn(), bt(), ci(), Ct(), D(), di() (+60 more)

### Community 4 - "admin.js"
Cohesion: 0.18
Nodes (32): activateAllInactive(), apiFetch(), changeOrderStatus(), checkAdminAuth(), closeProductModal(), deleteProduct(), editProduct(), executeActivateAll() (+24 more)

### Community 5 - "admin.py"
Cohesion: 0.05
Nodes (40): switch_channel_product_photo_callback(), setup_channel_router(), build_post_url(), extract_all_photo_file_ids(), extract_photo_file_id(), fetch_channel_embed_photos(), handle_edited_channel_post(), handle_new_channel_post() (+32 more)

### Community 6 - "admin.min.js"
Cohesion: 0.20
Nodes (27): A(), activateAllInactive(), B(), c(), changeOrderStatus(), d(), deleteProduct(), editProduct() (+19 more)

### Community 7 - "create_web_app"
Cohesion: 0.06
Nodes (36): create_web_app(), admin_activate_all_products(), admin_check(), admin_create_product(), admin_dashboard(), admin_delete_product(), admin_get_orders(), admin_get_products() (+28 more)

### Community 9 - "os"
Cohesion: 0.06
Nodes (21): create_fallback_square_image(), create_sticker_effect(), is_cutout_clean_and_quality(), process_and_save_product_image(), remove_background(), check_status(), _request(), trigger_deploy() (+13 more)

### Community 12 - "Database"
Cohesion: 0.05
Nodes (4): Database, migrate(), main(), run_full_tests()

### Community 14 - "js/app.js"
Cohesion: 0.16
Nodes (17): closeAllModals(), closeLinkActionModal(), copyActiveLinkUrl(), copyPageUrl(), copyToClipboard(), fallbackCopyText(), handlePageShare(), initTheme() (+9 more)

### Community 19 - "services"
Cohesion: 0.15
Nodes (12): key, sync, value, services, buildCommand, envVars, name, plan (+4 more)

### Community 20 - "package.json"
Cohesion: 0.18
Nodes (11): description, devDependencies, esbuild@^0.28.0, name, private, scripts, build, build:py (+3 more)

### Community 22 - "🛒 DemoStore — Telegram E-Commerce & Mini App Ekotizimi"
Cohesion: 0.25
Nodes (7): 1. 📱 Zamonaviy Telegram Mini App (Frontend & UI), 2. 📡 Kanal tahlilchisi (Channel Parser & Sync), 3. 👑 Admin panel va Kliklar tahlili, 🛒 DemoStore — Telegram E-Commerce & Mini App Ekotizimi, ⚡️ Ishga tushirish, 📁 Loyiha tuzilmasi, 🌟 Yangilangan va integratsiya qilingan imkoniyatlar

## Knowledge Gaps
- **8 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Database` connect `Database` to `setup_admin_router`, `setup_checkout_router`, `admin.py`, `create_web_app`, `os`?**
  _High betweenness centrality (0.134) - this node is a cross-community bridge._
- **Are the 9 inferred relationships involving `Database` (e.g. with `setup_admin_router()` and `setup_cart_router()`) actually correct?**
  _`Database` has 9 INFERRED edges - model-reasoned connections that need verification._
- **Should `webapp/app.js` be split into smaller, more focused modules?**
  _Cohesion score 0.0774526678141136 - nodes in this community are weakly interconnected._
- **Why does `setup_admin_router()` connect `setup_admin_router` to `setup_checkout_router`, `Database`, `admin.py`, `create_web_app`?**
  _High betweenness centrality (0.061) - this node is a cross-community bridge._
- **Are the 2 inferred relationships involving `setup_admin_router()` (e.g. with `Database` and `AdminStates`) actually correct?**
  _`setup_admin_router()` has 2 INFERRED edges - model-reasoned connections that need verification._
- **Should `setup_admin_router` be split into smaller, more focused modules?**
  _Cohesion score 0.09743589743589744 - nodes in this community are weakly interconnected._
- **Why does `create_web_app()` connect `create_web_app` to `setup_checkout_router`, `Database`?**
  _High betweenness centrality (0.045) - this node is a cross-community bridge._