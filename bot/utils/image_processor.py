import os
import logging
import subprocess
from pathlib import Path
from typing import Tuple, Optional
from PIL import Image, ImageFilter

logger = logging.getLogger("ImageProcessor")

def remove_background(input_path: Path, output_png_path: Path, timeout: int = 30) -> bool:
    """
    remove_bg (macOS Vision Framework arm64 binary) orqali rasmning fonini tozalash.
    Muvaffaqiyatli bo'lsa True, aks holda False qaytaradi.
    """
    try:
        base_dir = Path(__file__).resolve().parent.parent.parent
        remove_bg_bin = base_dir / "remove_bg"
        
        if not remove_bg_bin.exists():
            logger.warning(f"remove_bg binar fayli topilmadi: {remove_bg_bin}")
            return False

        cmd = [str(remove_bg_bin), str(input_path), str(output_png_path)]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        
        if res.returncode == 0 and output_png_path.exists() and output_png_path.stat().st_size > 0:
            return True
        else:
            logger.info(f"remove_bg fonni ajratolmadi: {res.stdout.strip() or res.stderr.strip()}")
            return False
    except Exception as e:
        logger.warning(f"remove_bg bajarishda xatolik: {e}")
        return False

def is_cutout_clean_and_quality(png_path: Path) -> Tuple[bool, str]:
    """
    Fon tozalash sifatini qat'iy tekshirish filtri:
    - Obyekt mavjudligi (bounding box)
    - Obyekt qamrovi (fg_ratio: 0.08 dan 0.88 gacha)
    - Qirralar tozaligi (kanvas hoshiyasida 20% dan ortiq qoldiq fon qolmasligi)
    - Shovqin va tumanli artefaktlar yo'qligi
    """
    try:
        img = Image.open(png_path)
        if img.mode != "RGBA":
            return False, "Rasm formati RGBA emas"
            
        w, h = img.size
        bbox = img.getbbox()
        if not bbox:
            return False, "Obyekt aniqlanmadi (bo'sh siluet)"
            
        bw = bbox[2] - bbox[0]
        bh = bbox[3] - bbox[1]
        if bw < 80 or bh < 80:
            return False, "Obyekt hajmi juda kichik"
            
        alpha = img.split()[3]
        hist = alpha.histogram()
        total_pixels = w * h
        solid_pixels = hist[255]
        semi_pixels = sum(hist[1:255])
        fg_pixels = sum(hist[30:])
        fg_ratio = fg_pixels / total_pixels
        
        # Juda kam (obyekt yo'qolib ketgan) yoki deyarli butun rasm (fon ajralmagan)
        if fg_ratio < 0.08:
            return False, f"Obyekt maydoni yetarli emas ({fg_ratio:.2f})"
        if fg_ratio > 0.88:
            return False, f"Fon to'liq o'chmadi ({fg_ratio:.2f})"
            
        # Kanvas chetlaridagi qoldiq fonni tekshirish (border solid pixels)
        step = max(1, min(w, h) // 100)
        top = [alpha.getpixel((x, 0)) for x in range(0, w, step)]
        bottom = [alpha.getpixel((x, h - 1)) for x in range(0, w, step)]
        left = [alpha.getpixel((0, y)) for y in range(0, h, step)]
        right = [alpha.getpixel((w - 1, y)) for y in range(0, h, step)]
        border = top + bottom + left + right
        border_solid = sum(1 for p in border if p > 100) / max(1, len(border))
        
        if border_solid > 0.20:
            return False, f"Hoshiyada qoldiq fon mavjud ({border_solid:.2f})"
            
        # Shovqin / loyqa chiziqlar nisbati
        if solid_pixels > 0 and semi_pixels > solid_pixels * 0.85:
            return False, "Qirralar noaniq va loyqa"
            
        return True, "Sifatli fon ajratildi"
    except Exception as e:
        return False, f"Tahlil xatosi: {e}"

def create_sticker_effect(cutout_path: Path, output_png_path: Path, canvas_size: int = 1000) -> bool:
    """
    Sifatli chiqqan mahsulot silueti bo'ylab:
    1. Qalin, tekis oq hoshiya (stroke / border)
    2. Hoshiya orqasiga yengil, yumshoq soya (drop shadow)
    3. 1:1 kvadrat nisbatda markazlashtirilib, shaffof PNG formatda saqlash
    """
    try:
        img = Image.open(cutout_path)
        if img.mode != "RGBA":
            img = img.convert("RGBA")
            
        bbox = img.getbbox()
        if not bbox:
            return False
            
        # Obyektni qirqib olish (Tight crop)
        obj = img.crop(bbox)
        
        # 1:1 kanvas ichiga xavfsiz maydon (padding) bilan sig'dirish
        target_max = int(canvas_size * 0.76) # ~760px
        scale = min(target_max / obj.width, target_max / obj.height)
        new_w = max(10, int(obj.width * scale))
        new_h = max(10, int(obj.height * scale))
        obj_scaled = obj.resize((new_w, new_h), Image.Resampling.LANCZOS)
        
        mask = obj_scaled.split()[3]
        
        # 1. Qalin va tekis oq hoshiya (Stroke Mask)
        stroke_size = 31 # ~15px qalinlik
        stroke_mask = mask.filter(ImageFilter.MaxFilter(stroke_size))
        stroke_mask = stroke_mask.filter(ImageFilter.GaussianBlur(radius=2.5))
        
        white_stroke = Image.new("RGBA", (new_w, new_h), (255, 255, 255, 255))
        white_stroke.putalpha(stroke_mask)
        
        # Markazlashtirish koordinatalari
        offset_x = (canvas_size - new_w) // 2
        offset_y = (canvas_size - new_h) // 2
        shadow_offset_y = offset_y + 16 # Yengil pastga tushgan soya
        
        # 2. Yumshoq soya (Drop shadow on full canvas to avoid clipping)
        full_shadow_mask = Image.new("L", (canvas_size, canvas_size), 0)
        full_shadow_mask.paste(stroke_mask, (offset_x, shadow_offset_y))
        full_shadow_mask = full_shadow_mask.filter(ImageFilter.GaussianBlur(radius=28))
        full_shadow_mask = full_shadow_mask.point(lambda a: int(a * 0.38)) # Nafis shaffoflik (~38%)
        
        shadow_layer = Image.new("RGBA", (canvas_size, canvas_size), (10, 15, 30, 255))
        shadow_layer.putalpha(full_shadow_mask)
        
        # 3. Yakuniy shaffof 1:1 kanvasga birlashtirish
        final_canvas = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
        final_canvas.alpha_composite(shadow_layer)
        final_canvas.alpha_composite(white_stroke, (offset_x, offset_y))
        final_canvas.alpha_composite(obj_scaled, (offset_x, offset_y))
        
        output_png_path.parent.mkdir(parents=True, exist_ok=True)
        final_canvas.save(output_png_path, "PNG", optimize=True)
        return True
    except Exception as e:
        logger.warning(f"Stiker effektini yaratishda xatolik: {e}")
        return False

def create_fallback_square_image(raw_image_path: Path, output_path: Path, canvas_size: int = 1000) -> bool:
    """
    Fon tozalash muvaffaqiyatsiz bo'lsa yoki sifat talabiga javob bermasa:
    Original rasmni 1:1 kvadrat nisbatda sifatli qilib saqlash (zaxira varianti).
    """
    try:
        img = Image.open(raw_image_path)
        if img.mode not in ("RGB", "RGBA"):
            img = img.convert("RGB")
            
        w, h = img.size
        if h > w:
            y_start = int(h * 0.05)
            y_end = y_start + w
            if y_end > h:
                y_end = h
                y_start = max(0, h - w)
            crop_box = (0, y_start, w, y_end)
            cropped = img.crop(crop_box)
        elif w > h:
            x_start = (w - h) // 2
            crop_box = (x_start, 0, x_start + h, h)
            cropped = img.crop(crop_box)
        else:
            cropped = img
            
        resized = cropped.resize((canvas_size, canvas_size), Image.Resampling.LANCZOS)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Agar PNG bo'lsa PNG, aks holda JPEG
        if output_path.suffix.lower() == ".png":
            resized.save(output_path, "PNG", optimize=True)
        else:
            if resized.mode == "RGBA":
                resized = resized.convert("RGB")
            resized.save(output_path, "JPEG", quality=95)
            
        return True
    except Exception as e:
        logger.warning(f"Zaxira rasm yaratishda xatolik: {e}")
        return False

def process_and_save_product_image(raw_image_path: Path, product_id: int, base_dir: Optional[Path] = None) -> str:
    """
    To'liq konveyer (Pipeline):
    1. remove_bg orqali fonni tozalash
    2. Sifat tekshiruvi (is_cutout_clean_and_quality)
    3. Sifatli bo'lsa: Stiker effekti (oq hoshiya + yumshoq soya + 1:1 shaffof PNG)
    4. Sifat talabiga javob bermasa yoki fon ajralmasa: original rasmdan 1:1 zaxira
    5. Mini App va bot uchun tayyor web URL (/static/products/prod_{product_id}.png) qaytarish
    """
    if base_dir is None:
        base_dir = Path(__file__).resolve().parent.parent.parent
        
    products_dir = base_dir / "webapp" / "static" / "products"
    temp_dir = base_dir / "temp_photos"
    products_dir.mkdir(parents=True, exist_ok=True)
    temp_dir.mkdir(parents=True, exist_ok=True)
    
    final_sticker_png = products_dir / f"prod_{product_id}.png"
    temp_cutout_png = temp_dir / f"cutout_{product_id}.png"
    
    # 1. Fonni tozalash
    bg_removed = remove_background(raw_image_path, temp_cutout_png)
    
    # 2. Sifat tekshiruvi
    quality_passed = False
    if bg_removed:
        quality_passed, reason = is_cutout_clean_and_quality(temp_cutout_png)
        if quality_passed:
            logger.info(f"Mahsulot #{product_id}: Fon toza va sifatli ({reason})")
        else:
            logger.info(f"Mahsulot #{product_id}: Fon sifatsiz deb topildi ({reason}) -> Original zaxira ishlatiladi")
    else:
        logger.info(f"Mahsulot #{product_id}: Fon ajralmadi -> Original zaxira ishlatiladi")
        
    # 3. Stiker yoki Zaxira
    if quality_passed:
        sticker_ok = create_sticker_effect(temp_cutout_png, final_sticker_png)
        if sticker_ok:
            logger.info(f"Mahsulot #{product_id}: Premium stiker muvaffaqiyatli tayyorlandi!")
            # Temp cutoutni tozalash
            try:
                if temp_cutout_png.exists():
                    temp_cutout_png.unlink()
            except Exception:
                pass
            return f"/static/products/prod_{product_id}.png"
            
    # Agar stiker bo'lmasa, zaxira rasmni PNG formatda saqlash
    logger.info(f"Mahsulot #{product_id}: Zaxira sifatida original rasm ishlatilmoqda...")
    fallback_ok = create_fallback_square_image(raw_image_path, final_sticker_png)
    if not fallback_ok:
        # Oxirgi chora: JPG ga zaxira
        fallback_jpg = products_dir / f"prod_{product_id}.jpg"
        create_fallback_square_image(raw_image_path, fallback_jpg)
        return f"/static/products/prod_{product_id}.jpg"
        
    return f"/static/products/prod_{product_id}.png"
