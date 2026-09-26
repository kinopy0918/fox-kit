#!/usr/bin/env python3
"""fox-bridge — Discord / Slack の決めたチャンネルに書かれたことを AI（claude）に渡し、返事を返す常駐。

  python3 bridge.py          常駐（launchd から起動される）
  python3 bridge.py --once   1周だけ見て終わる（確認用）

・見るのは config.json の channels に書いたチャンネルだけ。ボット自身と他のボットの発言は無視。
・allowed_users が空なら、そのチャンネルの人間全員に応える（チャンネル＝会社の中の場所なので）。
・チャンネルごとに会話を続ける。育ちすぎた・6時間空いた会話は新しくし、直前のやりとりを添える（session_guard）。
・返事に [[FILE:/絶対パス]] や [[IMG:/絶対パス]] と書かれていたら、そのファイルを添付して送る。
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
import common as c           # noqa: E402
import platforms as pf       # noqa: E402
import session_guard as sg   # noqa: E402

POLL = float(os.getenv("FOX_BRIDGE_POLL", "4"))
CLAUDE = os.getenv("CLAUDE_BIN") or next((p for p in (Path.home() / ".local/bin/claude", Path("/usr/local/bin/claude"),
                                                    Path("/opt/homebrew/bin/claude")) if p.exists()), None) \
    or shutil.which("claude") or "claude"
TIMEOUT = int(os.getenv("FOX_BRIDGE_TIMEOUT", "1500"))
FILE_RE = re.compile(r"\[\[(?:FILE|IMG|VID):(/[^\]]+)\]\]")
NUDGE_RE = re.compile(r"^(まだ[?？]*|どう[?？]*|ありがとう(ございます)?|了解|うん|はい|OK|ok)[\s\W]*$")


def system_prompt(platform: str) -> str:
    base = [
        f"いまの会話は {'Discord' if platform == 'discord' else 'Slack'} のチャンネル経由。相手はスマホで読んでいることが多い。",
        "返事は結論から短く。見出しと短い箇条書き。",
        "ファイルや画像を相手に届けたいときは、本文に [[FILE:/絶対パス]]（画像は [[IMG:/絶対パス]]）と書く。そう書けば添付して送られる。",
        "相手が送ったファイルは、本文の最後に『添付:』として置き場所が書いてある。",
    ]
    if platform == "discord":
        base.append("Discord は表（| 区切り）を描画しない。表を書かず、ラベル付きの箇条書きにする。")
    return "\n".join(base)


def run_claude(prompt: str, sid: str | None, platform: str):
    cmd = [str(CLAUDE), "-p", prompt, "--output-format", "json", "--permission-mode", "bypassPermissions",
           "--append-system-prompt", system_prompt(platform)]
    if sid:
        cmd += ["--resume", sid]
    env = dict(os.environ)
    env["PATH"] = f"{Path.home()}/.local/bin:/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"
    tok_file = Path.home() / ".config" / "claude" / "token"
    if tok_file.exists() and not env.get("CLAUDE_CODE_OAUTH_TOKEN"):
        env["CLAUDE_CODE_OAUTH_TOKEN"] = tok_file.read_text().strip()   # 常駐でログインが切れないように
    r = subprocess.run(cmd, cwd=str(Path.home()), capture_output=True, text=True, timeout=TIMEOUT, env=env)
    try:
        j = json.loads(r.stdout or "{}")
    except json.JSONDecodeError:
        j = {}
    if r.returncode != 0 or j.get("is_error"):
        return None, sg.claude_error(r)
    return j, ""


def handle(api, platform: str, channel: str, msgs: list[dict], st: dict, cfg: dict):
    ch_state = st.setdefault("channels", {}).setdefault(channel, {})
    texts, files = [], []
    for m in msgs:
        t = m["text"].strip()
        if m.get("reply_to"):
            t = f"（返信先: {m['reply_to'][:200]}）\n{t}"
        texts.append(t)
        for fname, url in m["files"]:
            try:
                dest = c.INBOX / time.strftime("%Y%m%d-%H%M%S") / fname
                files.append(api.download(url, dest))
            except Exception as e:
                c.log("添付を取れませんでした:", fname, e)
    prompt = "\n\n".join(x for x in texts if x)
    if files:
        prompt += "\n\n添付:\n" + "\n".join(f"- {p}" for p in files)
    if not prompt.strip() or (len(msgs) == 1 and not files and NUDGE_RE.match(prompt.strip())):
        return

    sid = ch_state.get("session")
    if not sg.should_resume(sid, ch_state.get("ts", 0), label=channel, log=c.log):
        if sid and ch_state.get("last"):
            prompt = f"（直前のやりとり）\n{ch_state['last']}\n\n（今回）\n{prompt}"
        sid = None

    ind = api.typing(channel)
    try:
        j, err = run_claude(prompt, sid, platform)
    except subprocess.TimeoutExpired:
        j, err = None, "時間がかかりすぎたので止めました。もう少し小さく分けて頼んでください。"
    finally:
        ind.set()
    placeholder = getattr(ind, "placeholder", None)

    if j is None:
        note = sg.limit_note(err) or f"⚠️ うまく動きませんでした：{err[:300] or '理由不明'}"
        if not sg.limit_note(err):
            ch_state.pop("session", None)        # 壊れた会話は捨てる（上限のときは捨てない）
        api.send(channel, note, placeholder=placeholder) if placeholder else api.send(channel, note)
        c.log("失敗:", err[:300])
        return

    reply = (j.get("result") or "").strip() or "（返事が空でした）"
    attach = [Path(p) for p in FILE_RE.findall(reply) if Path(p).is_file()]
    reply = FILE_RE.sub("", reply).strip()
    if placeholder:
        api.send(channel, reply, attach, placeholder=placeholder)
    else:
        api.send(channel, reply, attach)
    ch_state.update(session=j.get("session_id"), ts=time.time(),
                    last=f"相手: {prompt[-600:]}\nあなた: {reply[:600]}")
    c.log(f"返信 {channel}: {len(reply)}字 添付{len(attach)}")


def poll_once(api, cfg, st):
    me = api.me()["id"]
    allowed = set(cfg.get("allowed_users") or [])
    for channel in cfg["channels"]:
        cs = st.setdefault("channels", {}).setdefault(channel, {})
        after = cs.get("after")
        try:
            msgs = api.fetch(channel, after)
        except Exception as e:
            c.log("読めませんでした:", channel, e)
            continue
        if not after:                       # 初回は今より前を読まない（空なら最初から読む）
            cs["after"] = msgs[-1]["id"] if msgs else "0"
            c.save(c.STATE, st)
            continue
        if not msgs:
            continue
        cs["after"] = msgs[-1]["id"]
        c.save(c.STATE, st)
        mine = [m for m in msgs if not m["bot"] and m["user"] != me and (not allowed or m["user"] in allowed)]
        if mine:
            handle(api, cfg["platform"], channel, mine, st, cfg)
            c.save(c.STATE, st)


def main():
    cfg = c.load(c.CONFIG, {})
    if not cfg.get("platform") or not cfg.get("channels"):
        raise SystemExit("まだつながっていません。connect.py を先に実行してください。")
    api = pf.make(cfg["platform"])
    st = c.load(c.STATE, {})
    c.log(f"開始: {cfg['platform']} / チャンネル {len(cfg['channels'])} 本 / {POLL}秒ごと")
    once = "--once" in sys.argv
    while True:
        try:
            poll_once(api, cfg, st)
        except Exception as e:
            c.log("周回でエラー:", repr(e)[:300])
            time.sleep(15)
        if once:
            break
        time.sleep(POLL)


if __name__ == "__main__":
    main()
