#!/bin/zsh
# ダブルクリックで、AI と Discord / Slack をつなぐ設定係が開く
cd "$(dirname "$0")" && /usr/bin/python3 connect.py
echo; read -k1 "?何かキーを押すと閉じます"
