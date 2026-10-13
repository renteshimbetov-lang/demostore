"""
Render Avtomatik Deploy va Boshqaruv Skripti (Standard Library orqali)
Foydalanish:
    python deploy_to_render.py status       # Oxirgi deploy holatini tekshirish
    python deploy_to_render.py deploy       # Yangi deployni ishga tushirish
    python deploy_to_render.py clear-cache  # Keshni tozalab qayta deploy qilish
"""
import json
import os
import ssl
import sys
import time
import urllib.error
import urllib.request
from dotenv import load_dotenv

load_dotenv()

RENDER_API_KEY = os.getenv("RENDER_API_KEY", "").strip()
SERVICE_ID = os.getenv("RENDER_SERVICE_ID", "srv-db71bl0u01pc73bufnm0").strip()
BASE_URL = "https://api.render.com/v1"

if not RENDER_API_KEY:
    print("XATOLIK: .env faylida RENDER_API_KEY topilmadi!")
    sys.exit(1)

_ssl_ctx = ssl._create_unverified_context()

def _request(endpoint, method="GET", data=None):
    url = f"{BASE_URL}{endpoint}"
    req = urllib.request.Request(url, method=method)
    req.add_header("Authorization", f"Bearer {RENDER_API_KEY}")
    req.add_header("Accept", "application/json")
    if data is not None:
        req.add_header("Content-Type", "application/json")
        body = json.dumps(data).encode("utf-8")
    else:
        body = None
    try:
        with urllib.request.urlopen(req, data=body, timeout=20, context=_ssl_ctx) as resp:
            content = resp.read().decode("utf-8")
            if not content.strip():
                return resp.status, {}
            return resp.status, json.loads(content)
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8")
        return e.code, err_body
    except Exception as e:
        return 500, str(e)

def check_status():
    status, res = _request(f"/services/{SERVICE_ID}/deploys?limit=1")
    if status == 200 and isinstance(res, list) and res:
        d = res[0]["deploy"]
        print("====================================")
        print(f"Servis ID:   {SERVICE_ID}")
        print(f"Deploy ID:   {d['id']}")
        print(f"Holati:      {d['status'].upper()}")
        print(f"Commit:      {d.get('commit', {}).get('message')}")
        print(f"Boshlangan:  {d.get('startedAt')}")
        print(f"Tugallangan: {d.get('finishedAt')}")
        print(f"URL:         https://demostore-gu0p.onrender.com")
        print("====================================")
        return d['status']
    else:
        print(f"Holatni tekshirishda xatolik: {status} {res}")
        return None

def trigger_deploy(clear_cache=False):
    payload = {"clearCache": "clear" if clear_cache else "do_not_clear"}
    status, res = _request(f"/services/{SERVICE_ID}/deploys", method="POST", data=payload)
    if status in (200, 201, 202) and isinstance(res, dict):
        dep_id = res.get("id") or res.get("deploy", {}).get("id")
        print(f"Deploy muvaffaqiyatli yuborildi! Deploy ID: {dep_id}")
        print("Deploy jarayoni kuzatilmoqda...")
        for _ in range(60):
            time.sleep(5)
            s_code, s_res = _request(f"/services/{SERVICE_ID}/deploys/{dep_id}")
            if s_code == 200 and isinstance(s_res, dict):
                current_status = s_res.get("status")
                print(f"Joriy holat: {current_status}")
                if current_status == "live":
                    print("TABRIKLAYMIZ! Loyiha muvaffaqiyatli LIVE holatiga o'tdi!")
                    return dep_id
                elif current_status in ("build_failed", "update_failed", "canceled"):
                    print(f"XATOLIK: Deploy muvaffaqiyatsiz tugadi: {current_status}")
                    return dep_id
        return dep_id
    else:
        print(f"Deploy boshlashda xatolik: {status} {res}")
        return None

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    if cmd == "status":
        check_status()
    elif cmd == "deploy":
        trigger_deploy(clear_cache=False)
    elif cmd == "clear-cache":
        trigger_deploy(clear_cache=True)
    else:
        print("Mavjud buyruqlar: status | deploy | clear-cache")
