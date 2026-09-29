"""fox-guard の共通部品：通知・記録・claude 呼び出し（標準ライブラリだけ）。"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

HOME = Path.home()
DATA = HOME / ".local/share/fox-kit/guard"
DATA.mkdir(parents=True, exist_ok=True)


def now() -> datetime:
    return datetime.now()


def notify(text: str, title: str = "fox-kit"):
    """Discord/Slack がつながっていればそこへ、無ければ Mac の通知へ。"""
    cfg_p = HOME / ".config/fox-bridge/config.json"
    try:
        cfg = json.loads(cfg_p.read_text())
        sys.path.insert(0, str(HOME / "Tools/fox-bridge"))
        import platforms  # noqa: E402
        api = platforms.make(cfg["platform"])
        ch = cfg.get("notify_channel") or cfg["channels"][0]
        api.send(ch, text)
        return
    except Exception:
        pass
    first = text.strip().splitlines()[0].replace('"', "'")[:180] if text.strip() else title
    subprocess.run(["osascript", "-e", f'display notification "{first}" with title "{title}"'], capture_output=True)


def record(sub: str, name: str, text: str):
    """保存先の 03_記録/ に残す（無ければ ~/.local/share/fox-kit/guard）。"""
    base = None
    try:
        base = Path(json.loads((HOME / ".config/fox-kit/storage.json").read_text())["base"])
    except (OSError, ValueError, KeyError):
        pass
    root = (base / "03_記録" / sub) if base and (base / "03_記録").is_dir() else (DATA / sub)
    root.mkdir(parents=True, exist_ok=True)
    (root / name).write_text(text, encoding="utf-8")


def claude(prompt: str, model: str = "haiku", timeout: int = 240) -> str:
    c = shutil.which("claude") or str(HOME / ".local/bin/claude")
    env = dict(os.environ)
    tok = HOME / ".config/claude/token"
    if tok.exists() and not env.get("CLAUDE_CODE_OAUTH_TOKEN"):
        env["CLAUDE_CODE_OAUTH_TOKEN"] = tok.read_text().strip()
    try:
        r = subprocess.run([c, "-p", prompt, "--model", model, "--output-format", "text"],
                           capture_output=True, text=True, timeout=timeout, cwd=str(HOME), env=env)
        return r.stdout.strip() if r.returncode == 0 else ""
    except Exception:
        return ""
