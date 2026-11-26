#!/usr/bin/env python3
"""FOXコネクタの準備と管理（置きっぱなしのパソコン用・Mac）。標準ライブラリだけ（本体の server.py は専用の venv で動く）。

  python3 connector.py setup [--agent FOX]        本体の部品を入れる（初回だけ・数分）
  python3 connector.py addmail <アドレス> [--label 名前] [--name 差出人名]
                                                   メールを足す。サーバーは自動で調べ、パスワードはキーチェーンへ
  python3 connector.py adduser <人の名前> --accounts A,B [--folders auto|パス,パス]
                                                   使う人を足す（ログイン用のコードを1回だけ表示）
  python3 connector.py users                       使う人と、見えるアカウント・フォルダ
  python3 connector.py removeuser <人の名前>       その人はすぐ入れなくなる
  python3 connector.py start                       常駐させて、Tailscale で外に出す（初回はクリック2回）
  python3 connector.py link                        Claude（Duet）に足すためのリンク
  python3 connector.py status | stop | uninstall

メールの鍵とデータは、このパソコンの中だけ（キーチェーン service=fox-connector）。作った人（IDM）には何も届かない。
"""
from __future__ import annotations

import argparse
import getpass
import hashlib
import imaplib
import json
import os
import plistlib
import re
import secrets
import shutil
import subprocess
import urllib.parse
import urllib.request
from pathlib import Path

H = Path.home()
HERE = Path(__file__).resolve().parent
CONF = H / ".config/fox-connector"
VENV = H / ".local/share/fox-connector/venv"
LABEL = "com.fox-kit.connector"
PLIST = H / f"Library/LaunchAgents/{LABEL}.plist"
TS = "/Applications/Tailscale.app/Contents/MacOS/Tailscale"
PORT = 8790


def rd(name, default):
    try:
        return json.loads((CONF / name).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def wr(name, data):
    CONF.mkdir(parents=True, exist_ok=True)
    os.chmod(CONF, 0o700)
    p = CONF / name
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.chmod(p, 0o600)


# ---------------------------------------------------------------- メールのサーバーを調べる
GOOGLE = {"imap_host": "imap.gmail.com", "imap_port": 993, "smtp_host": "smtp.gmail.com", "smtp_port": 465}


def mx(domain: str) -> list[str]:
    try:
        out = subprocess.run(["dig", "+short", "MX", domain], capture_output=True, text=True, timeout=10).stdout
    except (OSError, subprocess.TimeoutExpired):
        return []
    rows = sorted((int(p[0]), p[1].rstrip(".").lower()) for p in (l.split() for l in out.splitlines()) if len(p) == 2 and p[0].isdigit())
    return [h for _, h in rows]


def ispdb(domain: str) -> dict | None:
    """Thunderbird の公開の一覧（autoconfig.thunderbird.net）から、IMAP と SMTP（SSL）のサーバーを引く。"""
    try:
        x = urllib.request.urlopen(f"https://autoconfig.thunderbird.net/v1.1/{urllib.parse.quote(domain)}", timeout=10).read().decode()
    except Exception:
        return None
    im = re.search(r'<incomingServer type="imap">.*?<hostname>(.*?)</hostname>\s*<port>993</port>', x, re.S)
    sm = re.search(r'<outgoingServer type="smtp">.*?<hostname>(.*?)</hostname>\s*<port>465</port>', x, re.S)
    if im and sm:
        return {"imap_host": im.group(1), "imap_port": 993, "smtp_host": sm.group(1), "smtp_port": 465}
    return None


def guess(addr: str, mxs: list[str] | None = None) -> dict:
    """アドレスからサーバーを推す（試してから使う）。Google → 公開の一覧 → MX の名前（さくら・エックスサーバー）→ mail.<ドメイン>。"""
    dom = addr.split("@")[-1].lower()
    mxs = mx(dom) if mxs is None else mxs
    if dom in ("gmail.com", "googlemail.com") or any(h.endswith(("google.com", "googlemail.com")) for h in mxs):
        return dict(GOOGLE)
    if any("outlook.com" in h or "office365" in h for h in mxs):
        raise SystemExit("Microsoft 365（Outlook）のメールは、パスワードでつなぐ方式が止められていて、いまは扱えません")
    hit = ispdb(dom)
    if hit:
        return hit
    for h in mxs:
        if h.endswith((".sakura.ne.jp", ".xserver.jp", ".lolipop.jp", ".heteml.jp")) or re.match(r"^(sv|www)\d+\.", h):
            return {"imap_host": h, "imap_port": 993, "smtp_host": h, "smtp_port": 465}
    return {"imap_host": f"mail.{dom}", "imap_port": 993, "smtp_host": f"mail.{dom}", "smtp_port": 465}


def addmail(a):
    addr = a.address.strip()
    label = a.label or addr.split("@")[0] + "@" + addr.split("@")[-1].split(".")[0]
    srv = guess(addr)
    print(f"  サーバー: {srv['imap_host']}（受信）／{srv['smtp_host']}（送信）")
    if srv["imap_host"] == "imap.gmail.com":
        print("  Gmail・Google Workspace は「アプリパスワード」を使います（普段のパスワードは通りません）。\n"
              "  作り方：https://myaccount.google.com/apppasswords （2段階認証をオンにしてから）")
    pw = os.environ.get("FOX_CONNECTOR_PASSWORD") or getpass.getpass("  パスワード（画面には出ません）: ")
    if os.environ.get("FOX_CONNECTOR_SKIP_LOGIN") != "1":
        try:
            c = imaplib.IMAP4_SSL(srv["imap_host"], srv["imap_port"], timeout=30)
            c.login(addr, pw.replace(" ", "") if srv["imap_host"] == "imap.gmail.com" else pw)
            c.logout()
        except Exception as e:
            raise SystemExit(f"  ✕ ログインできませんでした（{e}）。パスワードか、サーバー名（{srv['imap_host']}）を確かめてください")
        if "\n" in pw:
            raise SystemExit("  ✕ パスワードに改行が入っています")
        # パスワードは引数に載せない（ps で同じパソコンのほかの人から見えるため）。-w を最後に置くと標準入力から2回読む
        subprocess.run(["security", "add-generic-password", "-U", "-s", "fox-connector", "-a", addr, "-w"],
                       input=f"{pw}\n{pw}\n", text=True, capture_output=True, check=True, timeout=60)
    accts = [x for x in rd("accounts.json", []) if x["user"] != addr]
    accts.append({"label": label, "user": addr, "name": a.name or "", **srv})
    wr("accounts.json", accts)
    print(f"  ✓ {label}（{addr}）を足しました。使う人に見せるには adduser か、users.json の accounts に {label} を足します")


# ---------------------------------------------------------------- 使う人
def synced_folders() -> list[str]:
    """このパソコンに同期しているドライブ（パソコン版 Google ドライブの各アカウント・共有ドライブ）。"""
    cs = H / "Library/CloudStorage"
    out = []
    for d in sorted(cs.glob("GoogleDrive-*")) if cs.is_dir() else []:
        for sub in ("マイドライブ", "My Drive", "共有ドライブ", "Shared drives"):
            if (d / sub).is_dir():
                out.append(str(d / sub))
    return out


def new_code() -> str:
    abc = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"   # 見間違えやすい 0O1I は使わない
    return "-".join("".join(secrets.choice(abc) for _ in range(4)) for _ in range(3))


def adduser(a):
    accts = {x["label"] for x in rd("accounts.json", [])}
    want = [s for s in (a.accounts or "").split(",") if s]
    miss = [s for s in want if s not in accts]
    if miss:
        raise SystemExit(f"  ✕ そのアカウントはまだありません: {', '.join(miss)}（先に addmail で足してください。いまあるもの: {', '.join(sorted(accts)) or 'なし'}）")
    folders = synced_folders() if a.folders in ("", "auto") else [s for s in a.folders.split(",") if s]
    code = new_code()
    users = rd("users.json", {})
    users[a.who] = {"code_sha256": hashlib.sha256(code.replace("-", "").encode()).hexdigest(), "accounts": want, "folders": folders}
    wr("users.json", users)
    print(f"  ✓ {a.who} さんを足しました。ログインのコード（この1回だけ表示します・人に見せない）:\n\n      {code}\n")
    print(f"  見えるメール: {', '.join(want) or 'なし'}\n  見えるフォルダ: " + ("\n    ".join([""] + folders) if folders else "なし"))


def users_cmd(_):
    for n, u in rd("users.json", {}).items():
        print(f"- {n}：メール {', '.join(u.get('accounts', [])) or 'なし'}／フォルダ {len(u.get('folders', []))}つ")


def removeuser(a):
    users = rd("users.json", {})
    if users.pop(a.who, None) is None:
        raise SystemExit(f"  {a.who} さんはいません")
    wr("users.json", users)
    print(f"  ✓ {a.who} さんを外しました（つないでいた Duet も、次の操作から入れなくなります）")


# ---------------------------------------------------------------- 入れる・動かす・外に出す
def setup(a):
    py = next((p for p in ("/opt/homebrew/bin/python3.12", "/opt/homebrew/bin/python3.13", "/opt/homebrew/bin/python3", "/usr/local/bin/python3")
               if Path(p).exists() and subprocess.run([p, "-c", "import sys;sys.exit(sys.version_info<(3,10))"]).returncode == 0), None)
    if not py:
        raise SystemExit("  ✕ Python 3.10 以上が要ります（Homebrew の python）。「fox-kit packs」で道具をそろえてから、もう一度")
    if not (VENV / "bin/python").exists():
        subprocess.run([py, "-m", "venv", str(VENV)], check=True)
    subprocess.run([str(VENV / "bin/pip"), "install", "-q", "--upgrade", "fastmcp>=4.2,<5"], check=True)
    env = rd("env.json", {})
    env.setdefault("agent", a.agent)
    env.setdefault("port", PORT)
    wr("env.json", env)
    print("  ✓ 部品を入れました。次は addmail でメールを足し、adduser で使う人を足して、start")


def ts_host() -> str:
    r = subprocess.run([TS, "status", "--json"], capture_output=True, text=True, timeout=20)
    return json.loads(r.stdout)["Self"]["DNSName"].rstrip(".")


def start(_):
    if not Path(TS).exists():
        raise SystemExit("  ✕ Tailscale のアプリが要ります（無料）。https://tailscale.com/download から入れて、ログインしてから、もう一度")
    host = ts_host()
    env = rd("env.json", {})
    env["base_url"] = f"https://{host}"
    wr("env.json", env)
    log = str(H / "Library/Logs/fox-connector.log")
    PLIST.parent.mkdir(parents=True, exist_ok=True)
    plistlib.dump({"Label": LABEL, "ProgramArguments": [str(VENV / "bin/python"), str(HERE / "server.py")],
                   "WorkingDirectory": "/tmp", "RunAtLoad": True, "KeepAlive": True,
                   "StandardOutPath": log, "StandardErrorPath": log}, open(PLIST, "wb"))
    dom = f"gui/{os.getuid()}"
    subprocess.run(["launchctl", "bootout", dom, str(PLIST)], capture_output=True)
    subprocess.run(["launchctl", "bootstrap", dom, str(PLIST)], check=True)
    r = subprocess.run([TS, "funnel", "--bg", str(env.get("port", PORT))], capture_output=True, text=True, timeout=60)
    out = (r.stdout + r.stderr).strip()
    if "login.tailscale.com" in out:
        url = re.search(r"https://login\.tailscale\.com/\S+", out).group(0)
        print(f"  あと1回だけ、ブラウザで「許可」を押してください:\n    {url}\n  押したら、もう一度 start")
        return
    if "TLS" in out or "certificate" in out.lower() or "GUI failed" in out:
        print("  あと1回だけ：https://login.tailscale.com/admin/dns の一番下「HTTPS Certificates」を有効にしてから、もう一度 start")
        return
    ask_before_send()
    print(f"  ✓ 外から使えるようになりました: https://{host}/mcp")
    link(None)


def cname() -> str:
    """Claude に足すときの名前。道具の名前（mcp__claude_ai_<名前>__…）に入るので英数字だけにする。"""
    a = rd("env.json", {}).get("agent", "FOX")
    return a if re.fullmatch(r"[A-Za-z0-9]+", a) else "Connector"


def ask_before_send():
    """Claude Code（確認なしで動かしていても）でメールを送る前は、毎回確認を出す。Duet は自分で承認を求める。"""
    p = H / ".claude/settings.json"
    try:
        s = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return
    rule = f"mcp__claude_ai_{cname()}__mail_send"
    ask = s.setdefault("permissions", {}).setdefault("ask", [])
    if rule not in ask:
        ask.append(rule)
        p.write_text(json.dumps(s, ensure_ascii=False, indent=2), encoding="utf-8")


def link(_):
    env = rd("env.json", {})
    if not env.get("base_url"):
        raise SystemExit("  まだ start していません")
    u = urllib.parse.urlencode({"modal": "add-custom-connector", "connectorName": cname(), "connectorUrl": env["base_url"] + "/mcp"})
    print(f"  Claude（Duet）に足すリンク（使う人それぞれが開いて「追加」→「接続」→ コードでログイン）:\n    https://claude.ai/customize/connectors?{u}")


def status(_):
    env = rd("env.json", {})
    run = subprocess.run(["launchctl", "print", f"gui/{os.getuid()}/{LABEL}"], capture_output=True, text=True).stdout
    print(f"本体: {'動いています' if 'state = running' in run else '止まっています'}　入口: {env.get('base_url', '未設定')}/mcp")
    print(f"メール: {len(rd('accounts.json', []))}つ　使う人: {len(rd('users.json', {}))}人")


def stop(_):
    subprocess.run(["launchctl", "bootout", f"gui/{os.getuid()}", str(PLIST)], capture_output=True)
    if Path(TS).exists():
        subprocess.run([TS, "funnel", "--bg", "--https=443", "off"], capture_output=True, timeout=30)
    print("  止めました（設定とメールの鍵は残しています。もう一度 start で再開）")


def uninstall(_):
    stop(None)
    PLIST.unlink(missing_ok=True)
    for x in rd("accounts.json", []):
        subprocess.run(["security", "delete-generic-password", "-s", "fox-connector", "-a", x["user"]], capture_output=True)
    shutil.rmtree(VENV.parent, ignore_errors=True)
    print(f"  外しました（メールの鍵は消しました。設定の控えは {CONF} に残しています）")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("setup"); p.add_argument("--agent", default="FOX")
    p = sp.add_parser("addmail"); p.add_argument("address"); p.add_argument("--label", default=""); p.add_argument("--name", default="")
    p = sp.add_parser("adduser"); p.add_argument("who"); p.add_argument("--accounts", default=""); p.add_argument("--folders", default="auto")
    p = sp.add_parser("removeuser"); p.add_argument("who")
    for c in ("users", "start", "link", "status", "stop", "uninstall"):
        sp.add_parser(c)
    a = ap.parse_args()
    {"setup": setup, "addmail": addmail, "adduser": adduser, "users": users_cmd, "removeuser": removeuser, "start": start,
     "link": link, "status": status, "stop": stop, "uninstall": uninstall}[a.cmd](a)
