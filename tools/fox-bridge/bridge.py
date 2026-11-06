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
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as c           # noqa: E402
import platforms as pf       # noqa: E402
import session_guard as sg   # noqa: E402

POLL = float(os.getenv("FOX_BRIDGE_POLL", "4"))
MERGE_WAIT = float(os.getenv("FOX_BRIDGE_MERGE_WAIT", "3"))
CLAUDE = os.getenv("CLAUDE_BIN") or next((p for p in (Path.home() / ".local/bin/claude.exe", Path.home() / ".local/bin/claude",
                                                    Path("/usr/local/bin/claude"),
                                                    Path("/opt/homebrew/bin/claude")) if p.exists()), None) \
    or shutil.which("claude") or "claude"
TIMEOUT = int(os.getenv("FOX_BRIDGE_TIMEOUT", "1500"))
FILE_RE = re.compile(r"\[\[(?:FILE|IMG|VID):((?:/|[A-Za-z]:[\\/])[^\]]+)\]\]")   # Windows の C:/… も
NUDGE_RE = re.compile(r"^(まだ[?？]*|どう[?？]*|ありがとう(ございます)?|了解|うん|はい|OK|ok)[\s\W]*$")


def local_path(p: str) -> Path:
    """Windows で AI が書きがちな /C:/… や /c/Users/…（Git Bash 形式）を C:/… に直す。"""
    if c.WIN:
        m = re.match(r"^/([A-Za-z])(?::)?/(.*)$", p)
        if m:
            return Path(f"{m.group(1).upper()}:/{m.group(2)}")
    return Path(p)


def system_prompt(platform: str) -> str:
    base = [
        f"いまの会話は {'Discord' if platform == 'discord' else 'Slack'} のチャンネル経由。相手はスマホで読んでいることが多い。",
        "返事は結論から短く。見出しと短い箇条書き。",
        "ファイルや画像を相手に届けたいときは、本文に [[FILE:/絶対パス]]（画像は [[IMG:/絶対パス]]）と書く。そう書けば添付して送られる。"
        + ("このパソコンは Windows なので、絶対パスは C:/Users/… の形で書く。" if c.WIN else ""),
        "相手が送ったファイルは、本文の最後に『添付:』として置き場所が書いてある。",
    ]
    if platform == "discord":
        base.append("Discord は表（縦棒で区切る表）を描画しない。表を書かず、ラベル付きの箇条書きにする。")
    # Windows で npm 版の claude.cmd を使うと cmd.exe を通る＝改行で命令が切れ、| & < > ^ % を記号として読む。1行にして記号を避ける
    return " ".join(base) if c.WIN else "\n".join(base)


MODEL = os.getenv("FOX_BRIDGE_MODEL", "opus")          # 常駐が勝手に軽いモデルへ落ちないよう固定
BUSY_RE = re.compile(r"overloaded|529|503|temporarily unavailable|Internal server error", re.I)
MODEL_RE = re.compile(r"model.*(not (found|available)|invalid|access)", re.I)


def run_claude(prompt: str, sid: str | None, platform: str, model: str | None = MODEL):
    """混雑（529/503）は待ってやり直す。契約でそのモデルが使えなければ、モデル指定を外してやり直す。"""
    for attempt, wait in enumerate((0, 20, 60)):
        if wait:
            c.log(f"混雑しているので {wait}秒待ってやり直します（{attempt}回目）")
            time.sleep(wait)
        j, err = _run_claude(prompt, sid, platform, model)
        if j is not None:
            return j, ""
        if model and MODEL_RE.search(err or ""):
            c.log("指定のモデルが使えないので、既定のモデルでやり直します:", model)
            model = None
            j, err = _run_claude(prompt, sid, platform, None)
            if j is not None:
                return j, ""
        if not BUSY_RE.search(err or ""):
            break
    return None, err


def _run_claude(prompt: str, sid: str | None, platform: str, model: str | None):
    # 頼みごとは標準入力で渡す：Windows のコマンドの長さの上限（約3.2万字）と、
    # npm 版 claude.cmd が cmd.exe を通るときに本文の " & | を命令として読む危険を、両方避ける
    cmd = [str(CLAUDE), "-p", "--output-format", "json", "--permission-mode", "bypassPermissions",
           "--append-system-prompt", system_prompt(platform)]
    if model:
        cmd += ["--model", model]
    if sid:
        cmd += ["--resume", sid]
    env = dict(os.environ)
    if not c.WIN:
        env["PATH"] = f"{Path.home()}/.local/bin:/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"
    else:
        env["PATH"] = str(Path.home() / ".local" / "bin") + os.pathsep + env.get("PATH", "")
        env.setdefault("PYTHONUTF8", "1")
    tok_file = Path.home() / ".config" / "claude" / "token"
    if tok_file.exists() and not env.get("CLAUDE_CODE_OAUTH_TOKEN"):
        env["CLAUDE_CODE_OAUTH_TOKEN"] = tok_file.read_text(encoding="utf-8").strip()   # 常駐でログインが切れないように
    r = subprocess.run(cmd, input=prompt, cwd=str(Path.home()), capture_output=True, text=True, encoding="utf-8", errors="replace",
                       timeout=TIMEOUT, env=env, **({"creationflags": 0x08000000} if c.WIN else {}))
    try:
        j = json.loads(r.stdout or "{}")
    except json.JSONDecodeError:
        j = {}
    if r.returncode != 0 or j.get("is_error"):
        return None, sg.claude_error(r)
    return j, ""


VIDEO = {".mp4", ".mov", ".m4v", ".webm", ".avi"}
AUDIO = {".m4a", ".mp3", ".wav", ".aac", ".caf"}


def readable(p: Path) -> list:
    """AIが読める形にして返す。HEIC→jpg、動画→最大8枚のコマ画像（元の動画も残す）。"""
    ext = p.suffix.lower()
    if ext in (".heic", ".heif") and not c.WIN:
        jpg = p.with_suffix(".jpg")
        if subprocess.run(["sips", "-s", "format", "jpeg", str(p), "--out", str(jpg)], capture_output=True).returncode == 0:
            return [jpg]
        return [p]
    if ext in VIDEO:
        ff = shutil.which("ffmpeg") or next((x for x in ("/opt/homebrew/bin/ffmpeg", "/usr/local/bin/ffmpeg") if Path(x).exists()), None)
        if ff:
            out = p.parent / (p.stem + "_frames")
            out.mkdir(exist_ok=True)
            subprocess.run([ff, "-v", "error", "-i", str(p), "-vf", "fps=1/3,scale=768:-1", "-frames:v", "8",
                            str(out / "f_%02d.jpg")], capture_output=True)
            frames = sorted(out.glob("f_*.jpg"))
            if frames:
                return [p, *frames]
        return [p, f"（{p.name} は動画です。コマ画像を作れなかったので中身は見ていません）"]
    if ext in AUDIO:
        return [p, f"（{p.name} は音声です。文字起こしが要るなら whisper-cli で起こしてから答えること）"]
    return [p]


def audit(api, cfg: dict, channel: str, msgs: list[dict], reply: str, attach: list):
    """誰に・どこで・何を返したかを #記録 に1行（監査ログ）。"""
    ch = cfg.get("log_channel")
    if not ch:
        return
    who = "、".join(sorted({m.get("name") or m.get("user") or "?" for m in msgs}))
    head = reply.strip().splitlines()[0][:60] if reply.strip() else ""
    try:
        api.send(ch, f"{time.strftime('%m/%d %H:%M')}｜相手：{who}｜返事 {len(reply)}字"
                     + (f"・添付 {len(attach)}" if attach else "") + f"｜{head}")
    except Exception as e:
        c.log("監査ログを書けませんでした:", e)


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
                files += readable(api.download(url, dest))      # 期限付きのURLなので受け取った時点で落とす
            except Exception as e:
                c.log("添付を取れませんでした:", fname, e)
                files.append(f"（{fname} は受け取れませんでした。中身を見ていないので、見たことにしないこと）")
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
    except OSError as e:
        c.log("claude を起動できませんでした:", repr(e))
        j, err = None, ("AIを起動できませんでした。パソコンで AI のアプリ（Antigravity か黒い画面の claude）が"
                        "動くか確かめてください。直らなければ「新しい版に更新して」と頼んでください。")
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
    wanted = [local_path(p) for p in FILE_RE.findall(reply)]
    attach = [q for q in wanted if q.is_file()]
    missing = [str(q) for q in wanted if not q.is_file()]
    reply = FILE_RE.sub("", reply).strip()
    if missing:
        reply += "\n\n（添付できなかったファイル：" + "、".join(missing[:5]) + "）"
    reply = reply or "（添付だけです）"
    kw = {"placeholder": placeholder} if placeholder else {}
    try:
        api.send(channel, reply, attach, **kw)
    except Exception as e:  # noqa: BLE001  添付が大きすぎる等 → 本文だけでも届ける
        c.log("添付つきで送れませんでした:", repr(e)[:200])
        api.send(channel, reply + "\n\n（添付を送れませんでした。大きすぎるかもしれません）", **kw)
    ch_state.update(session=j.get("session_id"), ts=time.time(),
                    last=f"相手: {prompt[-600:]}\nあなた: {reply[:600]}")
    c.log(f"返信 {channel}: {len(reply)}字 添付{len(attach)}")
    audit(api, cfg, channel, msgs, reply, attach)


def poll_once(api, cfg, st):
    me = api.me()["id"]
    allowed = set(cfg.get("allowed_users") or [])
    for channel in cfg["channels"]:
        cs = st.setdefault("channels", {}).setdefault(channel, {})
        after = cs.get("after")
        try:
            msgs = api.fetch(channel, after)
            cs.pop("fail_since", None)
        except Exception as e:  # noqa: BLE001
            c.log("読めませんでした:", channel, e)
            first = cs.setdefault("fail_since", time.time())
            if time.time() - first > 60 and time.time() - cs.get("alerted", 0) > 3600:   # 1分続いたら知らせる（1時間に1回）
                cs["alerted"] = time.time(); c.save(c.STATE, st)
                alert(f"Discord/Slack を読めない状態が続いています（{str(e)[:120]}）。鍵の期限切れか、ネットの不調かもしれません。"
                      "AIに「スマホから頼めるようにしたい」と言うと、つなぎ直せます。")
            continue
        if not after:                       # 初回は今より前を読まない（空なら最初から読む）
            cs["after"] = msgs[-1]["id"] if msgs else "0"
            c.save(c.STATE, st)
            continue
        if not msgs:
            continue
        time.sleep(MERGE_WAIT)                 # 長文が分割されて届くので、続きを少し待つ
        try:
            more = api.fetch(channel, msgs[-1]["id"])
            msgs += [m for m in more if m["id"] not in {x["id"] for x in msgs}]
        except Exception:
            pass
        cs["after"] = msgs[-1]["id"]
        c.save(c.STATE, st)
        mine = [m for m in msgs if not m["bot"] and m["user"] != me and (not allowed or m["user"] in allowed)]
        if mine:
            cs["pending"] = time.time()          # 途中で止まったら、次に動き出したとき本人に知らせる
            c.save(c.STATE, st)
            try:
                handle(api, cfg["platform"], channel, mine, st, cfg)
            except Exception as e:  # noqa: BLE001  落ちても黙らない：本人に知らせる
                c.log("処理の途中で失敗:", channel, traceback.format_exc()[-800:])
                try:
                    api.send(channel, f"⚠️ うまく処理できませんでした（{e.__class__.__name__}）。もう一度送ってください。")
                except Exception:  # noqa: BLE001
                    pass
            cs.pop("pending", None)
            c.save(c.STATE, st)


def alert(msg: str):
    """パソコンに知らせる（Discord/Slack が使えないとき用）。記録にも必ず残す"""
    c.log("知らせ:", msg)
    try:
        if os.name == "nt":
            subprocess.run(["msg", "*", "/TIME:3600", "fox-kit: " + msg[:250]], capture_output=True, timeout=20)
        else:
            subprocess.run(["osascript", "-e", f'display notification "{msg[:180].replace(chr(34), chr(39))}" with title "fox-kit"'],
                           capture_output=True, timeout=20)
    except (OSError, subprocess.TimeoutExpired):
        pass


def main():
    cfg = c.load(c.CONFIG, {})
    if not cfg.get("platform") or not cfg.get("channels"):
        c.log("まだつながっていません。connect.py を先に実行してください。（5分待ってから終わります）")
        time.sleep(300)                      # 起こし直しを20秒ごとに繰り返さない
        raise SystemExit(1)
    api = pf.make(cfg["platform"])
    st = c.load(c.STATE, {})
    for ch, cs in st.get("channels", {}).items():   # 前回、頼みごとの途中で止まっていたら知らせる
        if cs.pop("pending", None):
            try:
                api.send(ch, "⚠️ 前の頼みごとの途中で止まりました（パソコンの再起動など）。お手数ですが、もう一度送ってください。")
            except Exception as e:  # noqa: BLE001
                c.log("途中で止まったことを知らせられませんでした:", repr(e)[:200])
    c.save(c.STATE, st)
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
    try:
        main()
    except SystemExit:
        raise
    except BaseException:  # noqa: BLE001  Windows（pythonw）は画面が無いので、落ちた理由を必ず記録に残す
        c.log("止まりました:", traceback.format_exc()[-1500:])
        time.sleep(60)
        raise
