#!/usr/bin/env python3
"""fox-kit の設定画面（ブラウザで進める）。このMacの中だけで動き、外からは見えない。

  python3 server.py            画面を立ち上げてブラウザで開く
  python3 server.py --no-open  立ち上げるだけ（URL を表示）

画面（index.html）が「今やること」を出し、ボタンや入力でこのMacの作業を動かす。
進み具合は ~/.config/fox-kit/wizard.json に残るので、閉じても続きから始められる。
"""
from __future__ import annotations

import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

HERE = Path(__file__).resolve().parent
KIT = HERE.parent
HOME = Path.home()
CONF = HOME / ".config/fox-kit"
WSTATE = CONF / "wizard.json"
ENVSTATE = CONF / "state.env"
LOGDIR = HOME / "Library/Logs/fox-wizard"
LOGDIR.mkdir(parents=True, exist_ok=True)
CONF.mkdir(parents=True, exist_ok=True)
TOKEN = secrets.token_urlsafe(16)
ASKPASS = HERE / "askpass.sh"
sys.path.insert(0, str(KIT / "tools/fox-bridge"))
sys.path.insert(0, str(KIT / "claude/skills/fox-setup"))

STEPS = [  # (id, 題名, 誰がやるか)
    ("level", "はじめに", "you"),
    ("names", "あなたとAIの名前", "you"),
    ("claude", "AIの本体を入れる", "auto"),
    ("login", "AIのアカウントにログイン", "you"),
    ("build", "あなた専用に組み立てる", "auto"),
    ("mac", "パソコンの設定", "you"),
    ("packs", "スキルと道具をそろえる", "auto"),
    ("storage", "資料の保存先", "you"),
    ("channel", "スマホから話せるように", "you"),
    ("talk", "AIと最初のお話", "you"),
    ("done", "完了", "auto"),
]

LOCK = threading.Lock()
JOBS: dict[str, dict] = {}          # 実行中・終わった作業
LOGIN = {"proc": None, "url": ""}   # ログインの途中経過
LAST = [time.time()]                # 最後に画面から操作があった時刻


# ------------------------------------------------------------------ 状態
def load() -> dict:
    try:
        return json.loads(WSTATE.read_text())
    except (OSError, ValueError):
        return {"answers": {}, "done": [], "data": {}}


def save(st: dict):
    tmp = WSTATE.with_suffix(".tmp")
    tmp.write_text(json.dumps(st, ensure_ascii=False, indent=2))
    os.chmod(tmp, 0o600)
    tmp.replace(WSTATE)
    # インストーラ（get.sh）や他の道具と答えを共有する
    a = st["answers"]
    lines = []
    for k, v in (("FOX_LEVEL", a.get("level")), ("FOX_OWNER", a.get("owner")), ("FOX_AGENT", a.get("agent")),
                 ("FOX_MACHINE", a.get("machine")), ("FOX_ROLE", a.get("role"))):
        if v:
            lines.append(f"{k}={shq(v)}")
    old = [l for l in (ENVSTATE.read_text().splitlines() if ENVSTATE.exists() else [])
           if not l.split("=", 1)[0] in {x.split("=", 1)[0] for x in lines}]
    ENVSTATE.write_text("\n".join(old + lines) + "\n")
    os.chmod(ENVSTATE, 0o600)


def shq(v: str) -> str:
    return re.sub(r"([^\w@%+=:,./　-鿿＀-￯-])", r"\\\1", v)


def mark(step: str, **data):
    with LOCK:
        st = load()
        if step not in st["done"]:
            st["done"].append(step)
        st["data"].setdefault(step, {}).update(data)
        save(st)


def env_for(st: dict) -> dict:
    a = st["answers"]
    e = dict(os.environ)
    e.update(FOX_LEVEL=a.get("level", "beginner"), FOX_OWNER=a.get("owner", ""), FOX_AGENT=a.get("agent", "FOX"),
             FOX_MACHINE=a.get("machine", ""), FOX_ROLE=a.get("role", "作業機"), KIT_DIR=str(KIT),
             SUDO_ASKPASS=str(ASKPASS), PATH=f"{HOME}/.local/bin:/opt/homebrew/bin:/usr/local/bin:{e.get('PATH', '')}",
             LOG=str(LOGDIR / "install.log"))
    return e


def claude_bin() -> str:
    return shutil.which("claude", path=f"{HOME}/.local/bin:/usr/local/bin:/opt/homebrew/bin") or str(HOME / ".local/bin/claude")


def logged_in() -> bool:
    try:
        r = subprocess.run([claude_bin(), "auth", "status"], capture_output=True, text=True, timeout=20)
        return bool(re.search(r'"loggedIn":\s*true', r.stdout))
    except Exception:
        return False


# ------------------------------------------------------------------ 作業（裏で動かす）
def run_job(name: str, cmd, env=None, on_ok=None, cwd=None):
    """作業を裏で動かす。画面は /api/state で進み具合を見る。"""
    with LOCK:
        if JOBS.get(name, {}).get("state") == "running":
            return
        log = LOGDIR / f"{name}.log"
        JOBS[name] = {"state": "running", "log": str(log), "started": time.time()}

    def work():
        with open(log, "w") as f:
            r = subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT, env=env, cwd=cwd or str(HOME),
                               shell=isinstance(cmd, str))
        ok = r.returncode == 0
        if ok and on_ok:
            try:
                on_ok()
            except Exception as e:
                ok = False
                with open(log, "a") as f:
                    f.write(f"\n{e}\n")
        with LOCK:
            JOBS[name].update(state="ok" if ok else "error", ended=time.time())
    threading.Thread(target=work, daemon=True).start()


def tail(name: str, n=12) -> str:
    j = JOBS.get(name)
    if not j:
        return ""
    try:
        txt = Path(j["log"]).read_text(errors="ignore")
    except OSError:
        return ""
    txt = re.sub(r"\x1b\[[0-9;]*m", "", txt)
    return "\n".join(txt.strip().splitlines()[-n:])


# ------------------------------------------------------------------ 各段の動き
def act(step: str, body: dict) -> dict:
    st = load()
    a = st["answers"]

    if step == "level":
        a["level"] = "expert" if body.get("level") == "expert" else "beginner"
        save(st); mark("level")
        return {"ok": True}

    if step == "names":
        for k in ("owner", "agent", "machine", "role"):
            v = (body.get(k) or "").strip()
            if k in ("owner", "agent") and not v:
                return {"ok": False, "error": "お名前とAIの名前は必ず入れてください"}
            if len(v) > 30 or re.search(r'["$`\\|]', v):
                return {"ok": False, "error": "30文字以内で、記号（\" $ ` \\ |）は使わないでください"}
            a[k] = v or {"machine": "このMac", "role": "作業機"}.get(k, "")
        save(st); mark("names")
        return {"ok": True}

    if step == "claude":
        if shutil.which("claude", path=f"{HOME}/.local/bin") or (HOME / ".local/bin/claude").exists():
            mark("claude"); return {"ok": True}
        run_job("claude", "curl -fsSL https://claude.ai/install.sh | bash", env=env_for(st), on_ok=lambda: mark("claude"))
        return {"ok": True, "started": True}

    if step == "login":
        if body.get("check"):
            if logged_in():
                if LOGIN["proc"]:
                    LOGIN["proc"].kill()
                mark("login"); return {"ok": True}
            return {"ok": False, "error": "まだログインできていません"}
        if body.get("code"):
            p = LOGIN["proc"]
            if not p or p.poll() is not None:
                return {"ok": False, "error": "ログインの受け付けが切れました。「ログイン画面を開く」からやり直してください"}
            p.stdin.write(body["code"].strip() + "\n"); p.stdin.flush()
            for _ in range(30):
                time.sleep(1)
                if logged_in():
                    mark("login"); return {"ok": True}
            return {"ok": False, "error": "コードを確認できませんでした。もう一度「ログイン画面を開く」からやり直してください"}
        # ログインを始める：URL を拾って画面に返す
        if LOGIN["proc"] and LOGIN["proc"].poll() is None:
            LOGIN["proc"].kill()
        p = subprocess.Popen([claude_bin(), "auth", "login"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT, text=True, env={**env_for(st), "BROWSER": "true"})
        LOGIN.update(proc=p, url="")
        t0 = time.time()
        buf = ""
        while time.time() - t0 < 20 and not LOGIN["url"]:
            line = p.stdout.readline()
            buf += line
            m = re.search(r"https://\S+", line)
            if m:
                LOGIN["url"] = m.group(0)
        return {"ok": bool(LOGIN["url"]), "url": LOGIN["url"], "error": "" if LOGIN["url"] else buf[-300:]}

    if step == "build":
        run_job("build", ["/bin/zsh", str(KIT / "setup/build.sh")], env=env_for(st), on_ok=lambda: mark("build"))
        return {"ok": True, "started": True}

    if step == "mac":
        use = "mobile" if body.get("use") == "mobile" else "office"
        e = {**env_for(st), "FOX_MAC_USE": use, "FOX_LID": "1" if body.get("lid") else "2",
             "FOX_CAPS": "1" if body.get("caps", True) else "2", "FOX_ANTIGRAVITY": "1" if body.get("antigravity", True) else "2"}
        run_job("mac", ["/bin/zsh", str(KIT / "tools/fox-mac/mac.sh")], env=e, on_ok=lambda: mark("mac", use=use))
        return {"ok": True, "started": True}

    if step == "packs":
        if os.getenv("FOX_WIZARD_FAKE_PACKS"):   # 検証用：道具の導入（端末全体に入る）を飛ばす
            run_job("packs", "sleep 3", on_ok=lambda: mark("packs"))
            return {"ok": True, "started": True}
        run_job("packs", ["/usr/bin/python3", str(KIT / "tools/fox-packs/packs.py"), "install"],
                env={**env_for(st), "FOX_NO_KEY": "1"}, on_ok=lambda: mark("packs"))
        return {"ok": True, "started": True}

    if step == "gemini":
        key = (body.get("key") or "").strip()
        try:
            urllib.request.urlopen(f"https://generativelanguage.googleapis.com/v1beta/models?key={key}", timeout=20).read()
        except Exception:
            return {"ok": False, "error": "この鍵ではつながりませんでした。もう一度コピーして貼ってください"}
        subprocess.run(["security", "add-generic-password", "-U", "-s", "fox-kit", "-a", "gemini", "-w", key],
                       check=True, capture_output=True)
        mark("gemini")
        return {"ok": True}

    if step == "storage":
        import storage as sto
        if body.get("detect"):
            import io, contextlib
            f = io.StringIO()
            with contextlib.redirect_stdout(f):
                sto.detect()
            return {"ok": True, **json.loads(f.getvalue())}
        if body.get("open_base"):
            base = st["data"].get("storage", {}).get("base")
            if base and Path(base).is_dir():
                subprocess.run(["open", base])
            return {"ok": True}
        if body.get("install_drive"):
            run_job("drive", ["/usr/bin/python3", str(KIT / "claude/skills/fox-setup/storage.py"), "install-gdrive"],
                    env=env_for(st))
            return {"ok": True, "started": True}
        root = body.get("root")
        if not root or not Path(root).is_dir():
            return {"ok": False, "error": "保存先を選んでください"}
        cmd = ["/usr/bin/python3", str(HOME / ".claude/skills/fox-setup/storage.py"), "apply", "--root", root,
               "--agent", a.get("agent", "FOX"), "--layout", body.get("layout", "fox")]
        if not root.startswith(str(HOME / "Documents")):
            cmd.append("--memory-in-root")
        if body.get("auto_index", True):
            cmd.append("--auto-index")
        r = subprocess.run(cmd, capture_output=True, text=True, env=env_for(st))
        if r.returncode != 0:
            return {"ok": False, "error": (r.stderr or r.stdout)[-300:]}
        base = str(Path(root) / a.get("agent", "FOX"))
        subprocess.run(["open", base])
        mark("storage", base=base)
        return {"ok": True, "base": base}

    if step == "channel":
        return channel(body, st)

    if step == "talk":
        return talk(body, st)

    if step == "skip":
        mark(body.get("target", ""), skipped=True)
        return {"ok": True}

    return {"ok": False, "error": f"知らない段です: {step}"}


# ------------------------------------------------------------------ Discord / Slack
def channel(body: dict, st: dict) -> dict:
    import common as bc
    import platforms as pf
    import connect as cn
    agent = st["answers"].get("agent", "FOX")
    d = st["data"].setdefault("channel", {})
    what = body.get("do")
    if what == "choose":
        d["platform"] = body.get("platform")
        save(st)
        if d["platform"] == "none":
            mark("channel", skipped=True)
        return {"ok": True}
    if what == "token":
        tok = (body.get("token") or "").strip()
        if d.get("platform") == "discord":
            if len(tok) < 50 or tok.count(".") < 2:
                return {"ok": False, "error": "形が違うようです。「Copy」を押してから、もう一度貼り付けてください"}
            try:
                api = pf.Discord(tok); api.me()
            except Exception:
                return {"ok": False, "error": "この鍵ではつながりませんでした。「Reset Token」からやり直して貼ってください"}
            bc.secret_set("discord", tok)
            mc = api.enable_message_content()
            app = api.application()
            d.update(bot=api.me()["username"], app_id=app["id"], mc=mc, guilds_before=[g["id"] for g in api.guilds()])
            save(st)
            return {"ok": True, "bot": d["bot"], "message_content": mc, "invite": api.invite_url(app["id"])}
        if not tok.startswith("xoxb-"):
            return {"ok": False, "error": "「xoxb-」で始まる文字列をコピーしてください（User ではなく Bot の方）"}
        try:
            api = pf.Slack(tok); me = api.me()
        except Exception:
            return {"ok": False, "error": "この鍵ではつながりませんでした。もう一度コピーして貼ってください"}
        bc.secret_set("slack", tok)
        ch = None
        for name in (f"{agent}-相談".lower(), "ai-soudan"):
            try:
                ch = api.ensure_channel(name); break
            except Exception:
                continue
        if not ch:
            return {"ok": False, "error": "チャンネルを作れませんでした（ワークスペースの設定で制限されている可能性）"}
        bc.save(bc.CONFIG, {"platform": "slack", "team": me.get("team_id"), "channels": [ch], "allowed_users": []})
        d.update(team=me.get("team"), link=f"https://app.slack.com/client/{me.get('team_id')}/{ch}")
        save(st)
        cn.install_launchd()
        return {"ok": True, "team": me.get("team"), "link": d["link"]}
    if what == "manifest":
        cn.AGENT = agent
        return {"ok": True, "url": "https://api.slack.com/apps?new_app=1&manifest_json="
                + urllib.parse.quote(json.dumps(cn.slack_manifest(), ensure_ascii=False))}
    if what == "joined":  # Discord：招待されたか確かめて、チャンネルを作って常駐を入れる
        api = pf.make("discord")
        gs = [g for g in api.guilds() if g["id"] not in d.get("guilds_before", [])] or api.guilds()
        if not gs:
            return {"ok": False, "error": "まだサーバーに入っていません。招待の画面で「認証」まで押してください"}
        g = gs[0]
        chans = api.ensure_channels(g["id"], agent, ["相談", "お知らせ", "記録"])
        bc.save(bc.CONFIG, {"platform": "discord", "guild": g["id"], "channels": [chans["相談"]],
                            "notify_channel": chans["お知らせ"], "log_channel": chans["記録"], "allowed_users": []})
        d.update(guild=g["name"], link=f"https://discord.com/channels/{g['id']}/{chans['相談']}")
        save(st)
        api.send(chans["相談"], f"こんにちは、{agent}です。ここに書くと、私が返事をします。試しに「はじめまして」と送ってみてください。")
        cn.install_launchd()
        return {"ok": True, "guild": g["name"], "link": d["link"]}
    if what == "check":  # 常駐が返事をしたら完了
        cfg = bc.load(bc.CONFIG, {})
        state = bc.load(bc.STATE, {})
        replied = any(v.get("session") for v in state.get("channels", {}).values())
        if replied:
            mark("channel", platform=cfg.get("platform"))
            return {"ok": True}
        return {"ok": False, "error": "まだ返事を確認できていません。チャンネルで「はじめまして」と送ってください"}
    return {"ok": False, "error": "?"}


# ------------------------------------------------------------------ 画面の中でAIと話す
TALK = {"sid": None}


def talk(body: dict, st: dict) -> dict:
    msg = (body.get("message") or "").strip()
    if body.get("finish"):
        mark("talk"); return {"ok": True}
    if not msg:
        msg = ("/fox-setup 初期設定をお願いします。保存先（3）とやり取りの場所（5）は設定画面で済ませました。"
               "残りの段を、この画面のチャットで1問ずつ進めてください。")
    cmd = [claude_bin(), "-p", msg, "--output-format", "json", "--permission-mode", "bypassPermissions"]
    sid = st["data"].get("talk", {}).get("sid")
    if sid:
        cmd += ["--resume", sid]
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=str(HOME), env=env_for(st), timeout=600)
    try:
        j = json.loads(r.stdout or "{}")
    except ValueError:
        j = {}
    if not j.get("result"):
        return {"ok": False, "error": "AIから返事がありませんでした。もう一度送ってください"}
    with LOCK:
        s2 = load(); s2["data"].setdefault("talk", {})["sid"] = j.get("session_id"); save(s2)
    return {"ok": True, "reply": j["result"]}


# ------------------------------------------------------------------ 画面に返す状態
def state() -> dict:
    st = load()
    done = set(st["done"])
    if "gemini" not in done:          # 道具が入り終わっても、鍵を「登録」か「あとで」に決めるまでは次へ進めない
        done.discard("packs")
    cur = next((s for s, _, _ in STEPS if s not in done), "done")
    return {
        "answers": st["answers"], "data": st["data"], "current": cur,
        "steps": [{"id": s, "title": t_, "who": w, "done": s in done} for s, t_, w in STEPS],
        "jobs": {k: {"state": v["state"], "tail": tail(k)} for k, v in JOBS.items()},
        "home": str(HOME),
    }


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        data = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _auth(self):
        q = parse_qs(urlparse(self.path).query)
        return (q.get("t") or [""])[0] == TOKEN or self.headers.get("X-Token") == TOKEN

    def do_GET(self):
        LAST[0] = time.time()
        path = urlparse(self.path).path
        if path == "/":
            if not self._auth():
                return self._send(403, "この画面は、インストーラが開いたURLからだけ見られます".encode(), "text/plain; charset=utf-8")
            return self._send(200, (HERE / "index.html").read_bytes(), "text/html; charset=utf-8")
        if path.startswith("/static/"):
            f = (HERE / path[len("/static/"):]).resolve()
            if HERE in f.parents and f.is_file():
                ctype = {".js": "text/javascript", ".css": "text/css", ".png": "image/png", ".jpg": "image/jpeg",
                         ".svg": "image/svg+xml", ".webp": "image/webp"}.get(f.suffix, "application/octet-stream")
                return self._send(200, f.read_bytes(), ctype + ("; charset=utf-8" if f.suffix in (".js", ".css") else ""))
            return self._send(404, b"")
        if path == "/api/state":
            if not self._auth():
                return self._send(403, {"error": "forbidden"})
            return self._send(200, state())
        self._send(404, b"")

    def do_POST(self):
        if not self._auth():
            return self._send(403, {"error": "forbidden"})
        path = urlparse(self.path).path
        n = int(self.headers.get("Content-Length") or 0)
        try:
            body = json.loads(self.rfile.read(n) or b"{}")
        except ValueError:
            body = {}
        m = re.match(r"^/api/act/([a-z]+)$", path)
        if not m:
            return self._send(404, {"error": "?"})
        try:
            return self._send(200, act(m.group(1), body))
        except Exception as e:
            return self._send(200, {"ok": False, "error": f"うまく動きませんでした：{e}"})


def main():
    port = int(os.getenv("FOX_WIZARD_PORT", "0"))
    srv = ThreadingHTTPServer(("127.0.0.1", port), H)
    url = f"http://127.0.0.1:{srv.server_address[1]}/?t={TOKEN}"
    (CONF / "wizard.url").write_text(url)
    os.chmod(CONF / "wizard.url", 0o600)
    print(f"設定画面：{url}", flush=True)
    if "--no-open" not in sys.argv:
        webbrowser.open(url)

    def reaper():  # 完了から10分、または最後の操作から6時間で自動で閉じる
        while True:
            time.sleep(60)
            st = load()
            idle = time.time() - LAST[0]
            if ("talk" in st["done"] and idle > 600) or idle > 6 * 3600:
                os._exit(0)
    threading.Thread(target=reaper, daemon=True).start()
    srv.serve_forever()


if __name__ == "__main__":
    main()
