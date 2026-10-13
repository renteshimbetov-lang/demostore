#!/bin/bash
# DemoStore Telegram Botni ishga tushirish skripti

cd "$(dirname "$0")"

if [ ! -d ".venv" ]; then
    echo "Virtual muhit (.venv) yaratilmoqda..."
    python3 -m venv .venv
    .venv/bin/pip install --upgrade pip
    .venv/bin/pip install -r requirements.txt
fi

echo "🚀 DemoStore Telegram Bot ishga tushirilmoqda..."
.venv/bin/python main_store.py
