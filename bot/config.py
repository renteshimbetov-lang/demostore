import os
from dataclasses import dataclass
from typing import List
from dotenv import load_dotenv

load_dotenv()

@dataclass
class Config:
    bot_token: str
    admin_ids: List[int]
    db_path: str
    store_name: str
    support_phone: str
    support_username: str
    webapp_url: str
    web_port: int
    usd_rate: int
    channel_id: str
    channel_username: str
    channel_url: str

def load_config() -> Config:
    bot_token = os.getenv("BOT_TOKEN", "").strip()
    admin_ids_raw = os.getenv("ADMIN_IDS", "").strip()
    
    admin_ids: List[int] = []
    if admin_ids_raw:
        for part in admin_ids_raw.split(","):
            part = part.strip()
            if part.isdigit():
                admin_ids.append(int(part))

    db_path = os.getenv("DATABASE_PATH", "demostore.db").strip()
    store_name = os.getenv("STORE_NAME", "Demo Store").strip()
    support_phone = os.getenv("SUPPORT_PHONE", "+998901234567").strip()
    support_username = os.getenv("SUPPORT_USERNAME", "@demostore_support").strip()
    render_external_url = os.getenv("RENDER_EXTERNAL_URL", "").strip()
    webapp_url = os.getenv("WEBAPP_URL", "").strip() or render_external_url or "http://localhost:8080"
    web_port = int(os.getenv("PORT", "8080").strip())
    usd_rate = int(os.getenv("USD_RATE", "12800").strip())
    
    channel_id = os.getenv("CHANNEL_ID", "-1004332313799").strip()
    channel_username = os.getenv("CHANNEL_USERNAME", "shbdbdjdhdjjdhd").strip().lstrip("@")
    channel_url = os.getenv("CHANNEL_URL", "https://t.me/shbdbdjdhdjjdhd").strip()

    return Config(
        bot_token=bot_token,
        admin_ids=admin_ids,
        db_path=db_path,
        store_name=store_name,
        support_phone=support_phone,
        support_username=support_username,
        webapp_url=webapp_url,
        web_port=web_port,
        usd_rate=usd_rate,
        channel_id=channel_id,
        channel_username=channel_username,
        channel_url=channel_url
    )

config = load_config()
