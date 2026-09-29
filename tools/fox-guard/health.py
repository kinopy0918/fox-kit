#!/usr/bin/env python3
"""毎朝の健康診断（fox-kit）— 常駐が黙って止まっていないかを見て、直せるものは直してから知らせる。

  python3 health.py            点検して、問題があれば「気づいた→やった→結果」で知らせる（平常時は黙る）
  python3 health.py --dry-run  知らせず画面に出す
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import HOME, notify, now  # noqa: E402

UID = os.getuid()
JOBS = {  # 常駐の名前 → 人向けの呼び名
    "com.fox-bridge": "Discord/Slack の返事",
    "com.fox-kit.vault-rag": "意味で探す索引の更新",
    "com.fox-kit.guard": "毎朝の点検",
}


def job(label: str) -> dict:
    r = subprocess.run(["launchctl", "print", f"gui/{UID}/{label}"], capture_output=True, text=True)
    if r.returncode != 0:
        return {"loaded": False}
    out = r.stdout
    code = re.search(r"last exit code = (-?\d+)", out)
    return {"loaded": True, "running": "state = running" in out,
            "exit": int(code.group(1)) if code else None}


def main():
    dry = "--dry-run" in sys.argv
    issues = []   # (気づいたこと, やったこと, 結果)

    # 1) 常駐
    for label, name in JOBS.items():
        plist = HOME / "Library/LaunchAgents" / f"{label}.plist"
        if not plist.exists():
            continue
        st = job(label)
        if not st["loaded"]:
            subprocess.run(["launchctl", "bootstrap", f"gui/{UID}", str(plist)], capture_output=True)
            ok = job(label)["loaded"]
            issues.append((f"「{name}」が読み込まれていませんでした", "読み込み直しました",
                           "直りました" if ok else "直りませんでした。fox-kit から設定し直してください"))
        elif label == "com.fox-bridge" and not st["running"]:
            subprocess.run(["launchctl", "kickstart", "-k", f"gui/{UID}/{label}"], capture_output=True)
            time.sleep(5)
            ok = job(label).get("running")
            issues.append((f"「{name}」が止まっていました", "起こし直しました",
                           "動いています" if ok else "起きませんでした。ログ ~/Library/Logs/fox-bridge.log を見てください"))
        elif st.get("exit") not in (None, 0) and label != "com.fox-bridge":
            issues.append((f"「{name}」が前回エラーで終わっていました（終了コード {st['exit']}）", "今回は様子を見ます",
                           "続くようなら fox-kit update で直してください"))

    # 2) ログイン
    c = shutil.which("claude") or str(HOME / ".local/bin/claude")
    r = subprocess.run([c, "auth", "status"], capture_output=True, text=True)
    if '"loggedIn": true' not in r.stdout.replace(" ", "").replace('"loggedIn":true', '"loggedIn": true'):
        if not re.search(r'"loggedIn":\s*true', r.stdout):
            issues.append(("AIのログインが切れています", "自分では直せません（本人の承認が要るため）",
                           "ターミナルで  claude auth login  を実行してください"))

    # 3) 保存先
    try:
        base = Path(json.loads((HOME / ".config/fox-kit/storage.json").read_text())["base"])
        if not base.is_dir():
            issues.append((f"保存先が見えません（{base}）", "自分では直せません",
                           "Google ドライブのアプリが起動してログインできているか確かめてください"))
    except (OSError, ValueError, KeyError):
        pass

    # 4) ディスクの空き
    free_gb = shutil.disk_usage(HOME).free / 1e9
    if free_gb < 10:
        issues.append((f"ディスクの空きが {free_gb:.0f}GB しかありません", "何も消していません（消すのは持ち主の判断）",
                       "不要なファイルを整理するか、AIに「容量を空けたい」と相談してください"))

    stamp = now().strftime("%Y-%m-%d %H:%M")
    if not issues:
        print(f"[{stamp}] 異常なし")
        return 0
    lines = [f"**毎朝の点検：{len(issues)}件**"]
    for a, b, c_ in issues:
        lines.append(f"- 気づいたこと：{a}\n  やったこと：{b}\n  結果：{c_}")
    text = "\n".join(lines)
    print(text)
    if not dry:
        notify(text, "毎朝の点検")
    return 0


if __name__ == "__main__":
    sys.exit(main())
