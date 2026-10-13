#!/usr/bin/env python3
"""
CLI Video Generatsiya Skripti — Higgsfield API (bytedance/seedance-2.5/text-to-video)
Telegram Mini App (WebApp) uchun kirish (intro) videosini yaratish va yuklab olish.
"""

import argparse
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
import httpx
import higgsfield_client
from higgsfield_client.exceptions import HiggsfieldClientError

# 1. Muhit o'zgaruvchilarini yuklash (.env.local va .env)
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env.local")
load_dotenv(BASE_DIR / ".env")

MODEL_NAME = "bytedance/seedance-2.5/text-to-video"
DEFAULT_OUTPUT_PATH = BASE_DIR / "webapp" / "intro.mp4"
DEFAULT_PROMPT = (
    "A futuristic luxury Apple store entrance cinematic vertical video, "
    "glowing neon Apple logo and premium smartphones floating in dark ambient light, "
    "golden particle sparkles, smooth camera zoom-in, 8k aesthetic, photorealistic"
)


def on_queue_update(status):
    """Higgsfield navbat holati yangilanganda xabar chiqarish."""
    status_name = status.__class__.__name__
    print(f"⏳ Navbat holati: {status_name}")


def download_video(video_url: str, target_path: Path):
    """Video URL dan MP4 faylni yuklab olib ko'rsatilgan manzilga saqlash."""
    print(f"📥 Video yuklab olinmoqda: {video_url}")
    target_path.parent.mkdir(parents=True, exist_ok=True)

    with httpx.Client(timeout=120.0, follow_redirects=True) as client:
        with client.stream("GET", video_url) as resp:
            resp.raise_for_status()
            total_bytes = int(resp.headers.get("content-length", 0))
            downloaded = 0
            with open(target_path, "wb") as f:
                for chunk in resp.iter_bytes(chunk_size=16384):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_bytes > 0:
                            percent = (downloaded / total_bytes) * 100
                            print(f"\r  Yuklanmoqda: {percent:.1f}% ({downloaded}/{total_bytes} bayt)", end="", flush=True)
                        else:
                            print(f"\r  Yuklanmoqda: {downloaded} bayt", end="", flush=True)

    print(f"\n✅ Video muvaffaqiyatli saqlandi: {target_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Higgsfield API yordamida Telegram Mini App uchun 9:16 formatdagi intro video generatsiya qilish."
    )
    parser.add_argument(
        "--prompt",
        type=str,
        default=DEFAULT_PROMPT,
        help="Video generatsiya qilish uchun matnli so'rov (prompt)",
    )
    parser.add_argument(
        "--duration",
        type=int,
        choices=[3, 4],
        default=4,
        help="Video davomiyligi (soniya): 3 yoki 4 (default: 4)",
    )
    parser.add_argument(
        "--resolution",
        type=str,
        default="720p",
        choices=["720p", "1080p"],
        help="Video o'lchami (default: 720p)",
    )
    parser.add_argument(
        "--aspect_ratio",
        type=str,
        default="9:16",
        help="Tomonlar nisbati: vertikal mobil ekran uchun '9:16'",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=str(DEFAULT_OUTPUT_PATH),
        help=f"Chiqish fayli manzili (default: {DEFAULT_OUTPUT_PATH})",
    )

    args = parser.parse_args()

    # HF_KEY mavjudligini server tomonida xavfsiz tekshirish (qiymatini chop qilmasdan)
    if not os.environ.get("HF_KEY"):
        print("❌ Xatolik: HF_KEY muhit o'zgaruvchisi topilmadi!")
        print("Iltimos, .env.local yoki .env faylida HF_KEY=key-id:key-secret sozlang.")
        sys.exit(1)

    print("🚀 Higgsfield Video Generatsiyasi boshlanmoqda...")
    print(f"📌 Model: {MODEL_NAME}")
    print(f"📝 Prompt: {args.prompt}")
    print(f"⏱  Davomiyligi: {args.duration}s | Sifati: {args.resolution} | Nisbat: {args.aspect_ratio}")
    print(f"🎯 Chiqish fayli: {args.output}")

    arguments = {
        "prompt": args.prompt,
        "duration": args.duration,
        "resolution": args.resolution,
        "aspect_ratio": args.aspect_ratio,
    }

    try:
        result = higgsfield_client.subscribe(
            MODEL_NAME,
            arguments=arguments,
            on_queue_update=on_queue_update,
        )
    except HiggsfieldClientError as e:
        print(f"\n❌ Higgsfield API xatoligi: {e}")
        if "not_enough_credits" in str(e).lower():
            print("⚠️ Hisobingizda generatsiya uchun yetarli kreditlar mavjud emas (not_enough_credits).")
            print("Higgsfield konsolida (https://console.higgsfield.ai) balansingizni to'ldirib qayta urinib ko'ring.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Kutilmagan xatolik yuz berdi: {e}")
        sys.exit(1)

    status = str(result.get("status", "")).lower()

    if status in ("failed", "error"):
        error_msg = result.get("error") or "Noma'lum xatolik"
        print(f"❌ Generatsiya muvaffaqiyatsiz tugadi: {error_msg}")
        sys.exit(1)
    elif status in ("canceled", "cancelled"):
        print("⚠️ So'rov bekor qilindi.")
        sys.exit(1)
    elif status in ("nsfw", "moderated"):
        print("⚠️ So'rov moderatsiya tomonidan rad etildi (taqiqlangan kontent).")
        sys.exit(1)

    # Video URL ni natijadan ajratib olish
    video_url = None
    if isinstance(result.get("video"), dict):
        video_url = result["video"].get("url")
    elif isinstance(result.get("video"), str):
        video_url = result["video"]
    elif result.get("videos") and isinstance(result["videos"], list):
        first = result["videos"][0]
        video_url = first.get("url") if isinstance(first, dict) else str(first)
    elif result.get("url"):
        video_url = result.get("url")

    if not video_url:
        print(f"❌ Generatsiya tugadi, biroq natijada video URL topilmadi: {result}")
        sys.exit(1)

    output_path = Path(args.output).resolve()
    try:
        download_video(video_url, output_path)
    except Exception as e:
        print(f"❌ Video yuklab olishda xatolik: {e}")
        sys.exit(1)

    print("\n✨ Barcha bosqichlar muvaffaqiyatli yakunlandi!")
    print(f"🎬 Telegram Mini App da video foydalanishga tayyor: {output_path}")


if __name__ == "__main__":
    main()
