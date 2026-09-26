#!/usr/bin/env python3
"""汎用型FOX — 機体をまたぐ実行の配管（fox-dispatchの汎用版）。

「この仕事は別の機械(24h常駐)で回した方がいい」と判断したとき、共有フォルダ
（Drive同期でもNAS共有でもよい）にジョブを投入する(enqueue)。相手側の常駐ワーカー
(worker)がキューを拾って実行し、結果をdone/に書き戻して通知する。
ネット直結網(Tailscale/SSH)に依存せず、フォルダ同期だけで機体を跨ぐ。

判断基準そのもの（どの仕事をどの機体に回すか）はここには無い。それは
`GOVERNANCE.md.template` に書く、現場ごとのルーティング方針。ここは配管だけを担う。

使い方:
  # 手元から常駐機に仕事を渡す
  python3 dispatch.py enqueue --venue mini --label "重バッチ" --cmd 'cd ~/dev/foo && python3 run.py'
  python3 dispatch.py enqueue --venue mini --label "記事強化" --task '○○記事をE-E-A-T強化してpushして'

  # 常駐機側ワーカー（launchd/cronが1分毎に叩く。多重起動はロックで防止）
  python3 dispatch.py worker

  # 状況
  python3 dispatch.py status

使う前に、環境変数 DISPATCH_DIR（共有フォルダ）を設定する。
Discord通知を使うなら DISPATCH_DISCORD_ENV（token/channelを含む.envのパス）も設定する。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import socket
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HOME = Path.home()
DRIVE = Path(os.environ.get("DISPATCH_DIR", str(HOME / "dispatch")))
Q = DRIVE / "queue"
RUNNING = DRIVE / "running"
DONE = DRIVE / "done"
LOGS = DRIVE / "logs"
DISCORD_ENV = Path(os.environ["DISPATCH_DISCORD_ENV"]) if os.environ.get("DISPATCH_DISCORD_ENV") else None
CLAUDE_BIN = os.getenv("CLAUDE_BIN", "/opt/homebrew/bin/claude")
DEFAULT_CHANNEL = os.environ.get("DISPATCH_CHANNEL", "")

# ワーカーが実行を拒否する明白に危険なパターン。
# ジョブに "force": true があれば通す（意図した場合のみ）。
DANGER = [
    r"rm\s+-rf\s+/(?:\s|$)", r"rm\s+-rf\s+~", r"rm\s+-rf\s+\$HOME",
    r":\(\)\s*\{", r"\bmkfs\b", r"\bdd\s+if=", r"\bshutdown\b", r"\breboot\b",
    r"curl[^|]*\|\s*(?:sudo\s+)?(?:ba)?sh", r"wget[^|]*\|\s*(?:ba)?sh",
    r"git\s+push[^\n]*--force", r"git\s+push[^\n]*\s-f\b",
]


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def host() -> str:
    return socket.gethostname().split(".")[0]


def read_env(path: Path) -> dict:
    d = {}
    if path and path.exists():
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                d[k.strip()] = v.strip().strip('"').strip("'")
    return d


def post_discord(text: str, channel: str | None = None) -> bool:
    cfg = read_env(DISCORD_ENV)
    token = cfg.get("DISCORD_TOKEN", "").strip()
    channel = (channel or DEFAULT_CHANNEL).strip()
    if not token or not channel:
        print("[discord] token/channel 未設定 → 通知スキップ")
        return False
    for chunk in [text[i:i + 1900] for i in range(0, len(text), 1900)] or [text]:
        try:
            req = urllib.request.Request(
                f"https://discord.com/api/v10/channels/{channel}/messages",
                data=json.dumps({"content": chunk}).encode("utf-8"),
                headers={"Authorization": f"Bot {token}", "Content-Type": "application/json",
                        "User-Agent": "portable-fox-dispatch (bridge-framework)"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=30) as r:
                r.read()
        except Exception as e:
            print(f"[discord] 送信失敗: {e}")
            return False
    return True


def is_dangerous(cmd: str) -> bool:
    return any(re.search(p, cmd) for p in DANGER)


# ---------- enqueue ----------
def cmd_enqueue(args) -> int:
    for d in (Q, RUNNING, DONE, LOGS):
        d.mkdir(parents=True, exist_ok=True)
    if not args.cmd and not args.task:
        print("--cmd か --task のどちらかが必要", file=sys.stderr)
        return 2
    cmd = args.cmd
    if args.task and not cmd:
        cwd = args.cwd or str(HOME)
        prompt = args.task.replace("'", "'\\''")
        cmd = f"cd '{cwd}' && {CLAUDE_BIN} -p '{prompt}' --permission-mode acceptEdits"
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    jid = f"{stamp}-{os.getpid() % 10000:04d}"
    job = {
        "id": jid, "created": now_iso(), "origin": host(), "venue": args.venue,
        "label": args.label or (args.task or args.cmd)[:60], "cmd": cmd,
        "cwd": args.cwd or "", "timeout": args.timeout, "notify": not args.quiet,
        "channel": args.channel or "", "force": args.force,
    }
    path = Q / f"{jid}.json"
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(job, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.rename(path)  # atomic
    print(f"[enqueue] {jid} → venue={args.venue}  ({job['label']})")
    print(f"          {path}")
    return 0


# ---------- worker ----------
def _claim(path: Path) -> Path | None:
    """renameで原子的にrunning/へ確保。負けたらNone（別ワーカーが先に取った）。"""
    target = RUNNING / path.name
    try:
        path.rename(target)
        return target
    except (FileNotFoundError, OSError):
        return None


def cmd_worker(args) -> int:
    for d in (Q, RUNNING, DONE, LOGS):
        d.mkdir(parents=True, exist_ok=True)
    lock = LOGS / "worker.lock"
    if lock.exists() and (time.time() - lock.stat().st_mtime) < 300:
        return 0  # 多重起動防止（stale lockは5分で無効化）
    lock.write_text(str(os.getpid()))
    me = host()
    try:
        for jp in sorted(Q.glob("*.json")):
            try:
                job = json.loads(jp.read_text(encoding="utf-8"))
            except Exception:
                continue
            if job.get("venue", args.venue) not in (args.venue, "any"):
                continue  # 自分向けでない
            claimed = _claim(jp)
            if claimed:
                _run_job(claimed, job, me)
    finally:
        try:
            lock.unlink()
        except FileNotFoundError:
            pass
    return 0


def _run_job(claimed: Path, job: dict, me: str) -> None:
    jid = job.get("id", claimed.stem)
    cmd = job.get("cmd", "")
    label = job.get("label", jid)
    result = {**job, "worker": me, "started": now_iso()}

    if not cmd:
        result.update(status="error", error="cmd 空", finished=now_iso())
    elif is_dangerous(cmd) and not job.get("force"):
        result.update(status="blocked",
                      error="危険パターン検知。意図的なら enqueue 時に --force",
                      finished=now_iso())
        if job.get("notify"):
            post_discord(f"⛔ [dispatch] ジョブをブロック: {label}\n危険コマンド検知（--force無し）",
                         channel=job.get("channel") or None)
    else:
        logf = LOGS / f"{jid}.log"
        try:
            proc = subprocess.run(cmd, shell=True, cwd=job.get("cwd") or None,
                                  capture_output=True, text=True,
                                  timeout=job.get("timeout", 1800))
            logf.write_text(f"$ {cmd}\n\n[stdout]\n{proc.stdout}\n\n[stderr]\n{proc.stderr}",
                            encoding="utf-8")
            result.update(status="ok" if proc.returncode == 0 else "failed",
                          exit=proc.returncode, stdout_tail=(proc.stdout or "")[-4000:],
                          stderr_tail=(proc.stderr or "")[-2000:], finished=now_iso())
        except subprocess.TimeoutExpired:
            result.update(status="timeout", finished=now_iso())
        except Exception as e:
            result.update(status="error", error=str(e), finished=now_iso())

    (DONE / f"{jid}.json").write_text(json.dumps(result, ensure_ascii=False, indent=2),
                                       encoding="utf-8")
    try:
        claimed.unlink()
    except FileNotFoundError:
        pass

    if job.get("notify"):
        icon = {"ok": "✅", "failed": "⚠️", "timeout": "⏱️",
                "error": "❌", "blocked": "⛔"}.get(result.get("status"), "•")
        msg = f"{icon} [dispatch/{me}] {label}\nstatus={result.get('status')}"
        if result.get("exit") not in (None, 0):
            msg += f" (exit {result.get('exit')})"
        tail = (result.get("stderr_tail") or result.get("stdout_tail") or "").strip()
        if tail:
            msg += f"\n```\n{tail[-500:]}\n```"
        post_discord(msg, channel=job.get("channel") or None)


# ---------- status ----------
def cmd_status(args) -> int:
    for d, name in ((Q, "queue"), (RUNNING, "running"), (DONE, "done")):
        items = sorted(d.glob("*.json"))
        print(f"[{name}] {len(items)}")
        for p in items[-args.limit:]:
            try:
                j = json.loads(p.read_text(encoding="utf-8"))
                print(f"   {j.get('id')}  {j.get('status', j.get('venue', ''))}  {j.get('label','')}")
            except Exception:
                print(f"   {p.name}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(prog="dispatch")
    sub = ap.add_subparsers(dest="cmd", required=True)

    e = sub.add_parser("enqueue", help="ジョブを投入")
    e.add_argument("--venue", default="mini")
    e.add_argument("--label", default="")
    e.add_argument("--cmd", default="", help="実行するシェルコマンド")
    e.add_argument("--task", default="", help="自然言語タスク（headless claudeで実行）")
    e.add_argument("--cwd", default="")
    e.add_argument("--timeout", type=int, default=1800)
    e.add_argument("--quiet", action="store_true")
    e.add_argument("--channel", default="")
    e.add_argument("--force", action="store_true")
    e.set_defaults(func=cmd_enqueue)

    w = sub.add_parser("worker", help="キューを1巡処理（常駐機で1分毎等）")
    w.add_argument("--venue", default="mini", help="自分のvenue名（enqueue時の--venueと対応）")
    w.set_defaults(func=cmd_worker)

    s = sub.add_parser("status", help="状況表示")
    s.add_argument("--limit", type=int, default=5)
    s.set_defaults(func=cmd_status)

    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
