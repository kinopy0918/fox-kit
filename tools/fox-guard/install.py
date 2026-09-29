#!/usr/bin/env python3
"""毎朝 7:20 にスキルの見張りと健康診断を動かす常駐を登録する（何度実行してもよい）。"""
import os, plistlib, subprocess, sys
from pathlib import Path
HOME = Path.home()
G = Path(__file__).resolve().parent
LABEL = "com.fox-kit.guard"
plist = HOME / "Library/LaunchAgents" / f"{LABEL}.plist"
plist.parent.mkdir(parents=True, exist_ok=True)
sh = G / "run.sh"
sh.write_text(f'#!/bin/zsh\nexport PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"\n'
              f'/usr/bin/python3 "{G}/skill_guard.py"\n/usr/bin/python3 "{G}/health.py"\n')
sh.chmod(0o755)
with open(plist, "wb") as f:
    plistlib.dump({"Label": LABEL, "ProgramArguments": [str(sh)],
                   "StartCalendarInterval": {"Hour": 7, "Minute": 20},
                   "StandardOutPath": str(HOME / "Library/Logs/fox-guard.log"),
                   "StandardErrorPath": str(HOME / "Library/Logs/fox-guard.log")}, f)
if os.getenv("FOX_SKIP_LAUNCHD"):
    print("（検証用：常駐の登録は飛ばしました）"); sys.exit(0)
uid = os.getuid()
subprocess.run(["launchctl", "bootout", f"gui/{uid}/{LABEL}"], capture_output=True)
subprocess.run(["launchctl", "bootstrap", f"gui/{uid}", str(plist)], capture_output=True)
# 初回は「いまの状態」を正として覚える（入れたばかりのスキルを全部『増えた』と騒がないため）
if "--no-reset" not in sys.argv:
    subprocess.run(["/usr/bin/python3", str(G / "skill_guard.py"), "--reset"], capture_output=True)
print("毎朝の点検を登録しました（7:20）")
