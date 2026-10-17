#!/usr/bin/env python3
"""
DemoStore Frontend Asset Minification Script.
HTML/CSS/JS fayllarini esbuild orqali siqadi (minify qiladi).
Agar Node/esbuild mavjud bo'lmasa, ichki Python minifikatoriga o'tadi.
"""

import os
import re
import shutil
import subprocess
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEBAPP_DIR = os.path.join(BASE_DIR, "webapp")

ASSETS = [
    {
        "src": os.path.join(WEBAPP_DIR, "app.js"),
        "dest": os.path.join(WEBAPP_DIR, "app.min.js"),
        "type": "js"
    },
    {
        "src": os.path.join(WEBAPP_DIR, "app.css"),
        "dest": os.path.join(WEBAPP_DIR, "app.min.css"),
        "type": "css"
    },
    {
        "src": os.path.join(WEBAPP_DIR, "mini_app_core.js"),
        "dest": os.path.join(WEBAPP_DIR, "mini_app_core.min.js"),
        "type": "js"
    },
    {
        "src": os.path.join(WEBAPP_DIR, "mini_app_buttons.css"),
        "dest": os.path.join(WEBAPP_DIR, "mini_app_buttons.min.css"),
        "type": "css"
    },
    {
        "src": os.path.join(WEBAPP_DIR, "admin.js"),
        "dest": os.path.join(WEBAPP_DIR, "admin.min.js"),
        "type": "js"
    },
    {
        "src": os.path.join(WEBAPP_DIR, "admin.css"),
        "dest": os.path.join(WEBAPP_DIR, "admin.min.css"),
        "type": "css"
    }
]

def format_size(bytes_len: int) -> str:
    if bytes_len < 1024:
        return f"{bytes_len} B"
    return f"{bytes_len / 1024:.1f} KB"

def python_minify_css(css: str) -> str:
    """Zaxira Python CSS minifikatori"""
    css = re.sub(r'/\*[\s\S]*?\*/', '', css)
    css = re.sub(r'\s+', ' ', css)
    css = re.sub(r'\s*([\{\}:;,>+~])\s*', r'\1', css)
    css = re.sub(r';}', '}', css)
    return css.strip()

def python_minify_js(js: str) -> str:
    """Zaxira Python JS minifikatori (sharhlar va ortiqcha bo'shliqlarni olib tashlash)"""
    # Ko'p qatorli sharhlarni tozalash (/* ... */)
    js = re.sub(r'/\*[\s\S]*?\*/', '', js)
    lines = []
    for line in js.splitlines():
        stripped = line.strip()
        # Bir qatorli sharhlar (// ...)
        if stripped.startswith('//'):
            continue
        if stripped:
            lines.append(stripped)
    return '\n'.join(lines)

def build_with_esbuild(item: dict) -> bool:
    src = item["src"]
    dest = item["dest"]
    if not os.path.exists(src):
        print(f"  [XATO] Fayl topilmadi: {src}")
        return False

    npx_bin = shutil.which("npx")
    if npx_bin:
        cmd = [npx_bin, "--yes", "esbuild", src, "--minify", f"--outfile={dest}"]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return True
        except Exception:
            pass
    return False

def build_with_python_fallback(item: dict):
    src = item["src"]
    dest = item["dest"]
    with open(src, "r", encoding="utf-8") as f:
        content = f.read()

    if item["type"] == "css":
        minified = python_minify_css(content)
    else:
        minified = python_minify_js(content)

    with open(dest, "w", encoding="utf-8") as f:
        f.write(minified)

def main():
    print("🚀 DemoStore Frontend Assetlarini siqish (Minification) boshlandi...")
    has_esbuild = bool(shutil.which("npx"))
    engine = "esbuild" if has_esbuild else "Python Fallback"
    print(f"🔧 Minifikator vositasi: {engine}\n")

    total_orig = 0
    total_mini = 0

    for item in ASSETS:
        src = item["src"]
        dest = item["dest"]
        orig_size = os.path.getsize(src)
        total_orig += orig_size

        success = False
        if has_esbuild:
            success = build_with_esbuild(item)
        if not success:
            build_with_python_fallback(item)

        mini_size = os.path.getsize(dest)
        total_mini += mini_size
        saved_pct = ((orig_size - mini_size) / orig_size) * 100

        rel_src = os.path.basename(src)
        rel_dest = os.path.basename(dest)
        print(f"  ✅ {rel_src:20} ({format_size(orig_size):>8}) -> {rel_dest:24} ({format_size(mini_size):>8}) [-{saved_pct:.1f}%]")

    total_saved_pct = ((total_orig - total_mini) / total_orig) * 100
    print("-" * 65)
    print(f"🎉 JAMI: {format_size(total_orig)} -> {format_size(total_mini)} (Tejaldi: {format_size(total_orig - total_mini)} / -{total_saved_pct:.1f}%)")
    print("⚡ Barcha minifikatsiya qilingan fayllar tayyor!")

if __name__ == "__main__":
    main()
