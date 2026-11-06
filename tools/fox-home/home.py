#!/usr/bin/env python3
"""据え置き機（家・事務所に置きっぱなしのパソコン）の見張り・掃除・点検。標準ライブラリだけ。

  python3 home.py install office|mobile   … 予定に登録する（office＝3つ全部／mobile＝スキルの点検だけ）
  python3 home.py uninstall               … 予定から外す
  python3 home.py watch    … 30分ごと：返事の常駐が止まっていたら起こし直す・空き容量・ログイン切れ
  python3 home.py clean    … 毎日4:40：AIが作り置いた一時ファイルを消す（撮った画面・受け取った添付など）
  python3 home.py skills   … 毎日7:20：スキル・プラグイン・フック・MCPの増減を見て、怪しい書き方があれば知らせる
  python3 home.py status   … いまの登録状況

知らせ先は Discord / Slack（つないでいれば「お知らせ」チャンネル）。つないでいなければ記録に書くだけ。
何も起きていない日は何も送らない。Mac mini の FOX で動いている見張り（self-heal・tmpgc・skill-guard）を
どの家・会社でも動く形に小さくしたもの。
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HOME = Path.home()
HERE = Path(__file__).resolve().parent
WIN = sys.platform == "win32"
STATE = HOME / ".config" / "fox-kit" / "home.json"
LOG = (HOME / ".config/fox-kit/logs/fox-home.log") if WIN else (HOME / "Library/Logs/fox-home.log")
BRIDGE = HERE.parent / "fox-bridge"   # 隣のフォルダ（Mac は ~/Tools、Windows はキットの tools の中）
NOWIN = {"creationflags": 0x08000000} if WIN else {}
JOBS = {  # 名前: (いつ, 何をする)
    "watch": ("30分ごと", "watch"),
    "clean": ("毎日 4:40", "clean"),
    "skills": ("毎日 7:20", "skills"),
}


def log(*a):
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + " ".join(str(x) for x in a) + "\n")


def load() -> dict:
    try:
        return json.loads(STATE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save(st: dict):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")


def bridge():
    sys.path.insert(0, str(BRIDGE))
    import common as c       # noqa: E402
    import connect as cn     # noqa: E402
    import platforms as pf   # noqa: E402
    return c, cn, pf


def notify(text: str):
    """Discord/Slack の「お知らせ」へ。つないでいなければ記録だけ。"""
    log("知らせ:", text.replace("\n", " / "))
    try:
        c, _, pf = bridge()
        cfg = c.load(c.CONFIG, {})
        if not cfg.get("platform"):
            return
        ch = cfg.get("notify_channel") or cfg["channels"][0]
        pf.make(cfg["platform"]).send(ch, text)
    except ImportError:
        return   # Discord/Slack を入れていない＝記録だけ
    except Exception as e:   # 知らせられなくても見張り自体は止めない（記録に残す）
        log("知らせられませんでした:", repr(e))


def once_a_day(st: dict, key: str) -> bool:
    """同じ知らせは1日1回まで。"""
    today = time.strftime("%Y-%m-%d")
    if st.setdefault("told", {}).get(key) == today:
        return False
    st["told"][key] = today
    return True


# ------------------------------------------------------------------ 見張り
def watch():
    st = load()
    try:
        c, cn, _ = bridge()
        cfg = c.load(c.CONFIG, {})
        if cfg.get("platform") and not cfg.get("paused") and not cn.running():
            cn.install_launchd()
            time.sleep(8)
            ok = cn.running()
            log("返事の常駐が止まっていた → 起こし直し", "成功" if ok else "失敗")
            if ok:
                notify("返事の仕組みが止まっていたので、起こし直しました。いまは動いています。")
            elif once_a_day(st, "bridge"):
                notify("返事の仕組みが止まっていて、起こし直せませんでした。パソコンを再起動してみてください。")
    except ImportError:
        pass   # Discord/Slack を入れていない
    free = shutil.disk_usage(HOME).free / 1e9
    if free < 10 and once_a_day(st, "disk"):
        notify(f"パソコンの空きが残り {free:.0f}GB です。大きな動画やダウンロードを整理すると、動きが重くなるのを防げます。"
               "「パソコンの空きを作って」と頼めば、消してよいものの候補を出します。")
    claude = shutil.which("claude") or str(HOME / ".local/bin" / ("claude.exe" if WIN else "claude"))
    try:
        r = subprocess.run([claude, "auth", "status"], capture_output=True, text=True, timeout=60, **NOWIN)
        try:
            logged = json.loads(r.stdout).get("loggedIn") is True
        except ValueError:
            logged = None   # 形が読めないときは知らせない（誤報を出さない）
        if logged is False and once_a_day(st, "login"):
            notify("AIのログインが切れています。このパソコンで Antigravity か黒い画面を開いて、ログインし直してください（返事が止まります）。")
    except (OSError, subprocess.TimeoutExpired) as e:
        log("ログインの確認ができませんでした:", repr(e))
    save(st)


# ------------------------------------------------------------------ 掃除
TMP_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".pdf", ".html", ".mp4", ".mov", ".webm", ".wav", ".m4a"}


def clean():
    """作り置きの一時ファイルを消す。消すのは自分のもの・古いもの・決まった場所だけ。"""
    now, n, size = time.time(), 0, 0
    tmp = Path(os.getenv("FOX_HOME_TMP") or tempfile.gettempdir())   # FOX_HOME_TMP は試験用
    places = [(tmp / "fox-shot", 1), (tmp / "fox-kit", 3)]
    try:
        c, _, _ = bridge()
        places.append((c.INBOX, 14))      # Discord/Slack で受け取った添付
    except ImportError:
        pass
    for d, days in places:
        if d.is_dir():
            for p in d.rglob("*"):
                try:
                    if p.is_file() and now - p.stat().st_mtime > days * 86400:
                        sz = p.stat().st_size; p.unlink(missing_ok=True); size += sz; n += 1
                except OSError:
                    continue   # 使用中（Windows）などは次の回に
    if not WIN and not os.getenv("FOX_HOME_NO_SYSTMP"):   # Mac の /tmp は再起動するまで消えない＝置きっぱなしの機械では溜まり続ける
        for p in Path("/private/tmp").iterdir():
            try:
                s = p.lstat()
                if (p.is_file() and not p.is_symlink() and s.st_uid == os.getuid() and p.suffix.lower() in TMP_EXT
                        and now - s.st_mtime > 3 * 86400):
                    size += s.st_size; p.unlink(); n += 1
            except OSError:
                continue
    log(f"掃除: {n}件 {size / 1e6:.0f}MB")


# ------------------------------------------------------------------ スキルの点検
ROOTS = [HOME / ".claude/skills", HOME / ".claude/plugins", HOME / ".agents/skills", HOME / ".claude/hooks"]
TEXT = {".md", ".py", ".js", ".mjs", ".ts", ".sh", ".zsh", ".ps1", ".json", ".yaml", ".yml", ".toml", ""}
SKIP = {"node_modules", ".git", "__pycache__", ".venv", "cache"}
RULES = {   # 作法33の5つ（外部送信・秘密・難読化・隠す指示・決まりの上書き）
    "外への送信": r"curl\s[^\n|]*(?:-d\b|--data|-F\b|--upload-file|-T\b)|requests\.post|method:\s*['\"]POST|Invoke-RestMethod[^\n]*-Method\s+Post",
    "秘密の読み取り": r"find-generic-password|find-internet-password|\.ssh/id_|Login Data|Cookies\.binarycookies|\.aws/credentials|CredRead",
    "隠して実行": r"base64\s+(?:-d|--decode)[^\n]*\|\s*(?:sh|bash|zsh|python)|b64decode\([^)]*\)\)?\s*\)?\s*$|FromBase64String[^\n]*(?:iex|Invoke-Expression)|eval\s*\(\s*(?:atob|Buffer\.from)",
    "持ち主に隠す指示": r"(?:ユーザー|利用者|持ち主)に(?:は)?(?:言わ|伝え|知らせ|見せ)(?:ない|るな)|(?:do not|don't|never) (?:tell|inform|mention|reveal)[^\n]{0,30}(?:user|human)",
    "決まりの上書き": r"ignore (?:all |the )?(?:previous|prior|above|earlier) (?:instructions|rules)|(?:前|これまで|上記)の(?:指示|ルール)を無視",
}
SELF = {Path(__file__).resolve()}


def snapshot() -> dict:
    files = {}
    for root in ROOTS:
        if not root.is_dir():
            continue
        for p in root.rglob("*"):
            if any(x in SKIP for x in p.parts) or not p.is_file() or p.suffix.lower() not in TEXT or p.resolve() in SELF:
                continue
            try:
                if p.stat().st_size > 1_000_000:
                    continue
                files[str(p)] = hashlib.sha1(p.read_bytes()).hexdigest()
            except OSError:
                continue
    sj = HOME / ".claude/settings.json"
    try:
        s = json.loads(sj.read_text(encoding="utf-8"))
        if s.get("hooks") or s.get("enabledPlugins"):
            files["settings:hooks・プラグイン"] = hashlib.sha1(json.dumps([s.get("hooks"), s.get("enabledPlugins")], sort_keys=True).encode()).hexdigest()
    except (OSError, ValueError):
        pass
    cj = HOME / ".claude.json"
    try:
        mcp = json.loads(cj.read_text(encoding="utf-8")).get("mcpServers")
        if mcp:
            files["settings:MCP"] = hashlib.sha1(json.dumps(mcp, sort_keys=True).encode()).hexdigest()
    except (OSError, ValueError):
        pass
    return files


def name_of(path: str) -> str:
    for root in ROOTS:
        try:
            rel = Path(path).relative_to(root)
            return f"{root.name}/{rel.parts[0]}" if root.name != "plugins" else f"plugins/{'/'.join(rel.parts[:3])}"
        except ValueError:
            continue
    return path


def skills():
    st = load()
    now = snapshot()
    before = st.get("skills")
    st["skills"] = now
    save(st)
    if before is None:
        return log(f"スキルの点検：はじめてなので今の状態（{len(now)}ファイル）を基準として覚えました")
    added = [p for p in now if p not in before]
    changed = [p for p in now if p in before and now[p] != before[p]]
    removed = [p for p in before if p not in now]
    if not (added or changed or removed):
        return log("スキルの点検：変化なし")
    hits = []
    for p in added + changed:
        if p.startswith("settings:"):
            continue
        try:
            txt = Path(p).read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for label, rx in RULES.items():
            m = re.search(rx, txt, re.I | re.M)
            if m:
                line = txt.count("\n", 0, m.start()) + 1
                hits.append(f"・{label}：{name_of(p)}（{Path(p).name} {line}行目「{m.group(0)[:60]}」）")
    names = sorted({name_of(p) for p in added + changed + removed if not p.startswith("settings:")})
    conf = [p.split(":", 1)[1] for p in changed + added if p.startswith("settings:")]
    gone = [p.split(":", 1)[1] for p in removed if p.startswith("settings:")]
    conf += gone
    if not names and not conf:
        return log("スキルの点検：変化なし")
    head = f"スキルの点検：{len(names)}か所が増えた・変わった・消えました" if names else "スキルの点検：スキルは変わっていません"
    msg = [head + (f"（{'・'.join(conf)} の設定が変わっています）" if conf else "")]
    msg += [f"・{n}" for n in names[:10]] + ([f"…ほか{len(names) - 10}か所"] if len(names) > 10 else [])
    if hits:
        msg += ["", "⚠ 気になる書き方がありました。使う前に AI に「このスキルの中身を確かめて」と頼んでください："] + hits[:10]
    else:
        msg += ["気になる書き方は見つかりませんでした。"]
    notify("\n".join(msg))


# ------------------------------------------------------------------ 予定に登録
def py() -> str:
    if WIN:
        w = Path(sys.executable).with_name("pythonw.exe")
        return str(w if w.exists() else sys.executable)
    return "/usr/bin/python3" if Path("/usr/bin/python3").exists() else sys.executable


def install(use: str):
    names = ["watch", "clean", "skills"] if use == "office" else ["skills"]
    uninstall(quiet=True)
    for n in names:
        if WIN:
            trig = ("$t = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(2) -RepetitionInterval (New-TimeSpan -Minutes 30) -RepetitionDuration (New-TimeSpan -Days 3650)"
                    if n == "watch" else f"$t = New-ScheduledTaskTrigger -Daily -At {'4:40' if n == 'clean' else '7:20'}")
            q = lambda x: str(x).replace("'", "''")
            ps = f"""$ErrorActionPreference = 'Stop'
$a = New-ScheduledTaskAction -Execute '{q(py())}' -Argument '"{q(HERE / "home.py")}" {n}' -WorkingDirectory '{q(HOME)}'
{trig}
$s = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 20)
Register-ScheduledTask -TaskName 'fox-home-{n}' -Action $a -Trigger $t -Settings $s -Force | Out-Null"""
            r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps],
                               capture_output=True, text=True, encoding="utf-8", errors="replace", **NOWIN)
            if r.returncode != 0:
                log("予定に登録できませんでした:", n, r.stderr[-300:])
                raise SystemExit(f"予定に登録できませんでした（{n}）: {r.stderr.strip()[-200:]}")
        else:
            import plistlib
            label = f"com.fox-kit.home.{n}"
            pl = {"Label": label, "ProgramArguments": [py(), str(HERE / "home.py"), n],
                  "StandardOutPath": str(LOG), "StandardErrorPath": str(LOG),
                  "EnvironmentVariables": {"PATH": f"{HOME}/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin",
                                           "HOME": str(HOME), "LANG": "ja_JP.UTF-8"}}
            if n == "watch":
                pl["StartInterval"] = 1800
            else:
                pl["StartCalendarInterval"] = {"Hour": 4, "Minute": 40} if n == "clean" else {"Hour": 7, "Minute": 20}
            f = HOME / "Library/LaunchAgents" / f"{label}.plist"
            f.parent.mkdir(parents=True, exist_ok=True)
            with open(f, "wb") as fh:
                plistlib.dump(pl, fh)
            r = subprocess.run(["launchctl", "bootstrap", f"gui/{os.getuid()}", str(f)], capture_output=True, text=True)
            if r.returncode != 0:
                log("予定に登録できませんでした:", n, r.stderr[-300:])
                raise SystemExit(f"予定に登録できませんでした（{n}）: {r.stderr.strip()[-200:]}")
    if "skills" in names and "skills" not in load():
        skills()   # 今の状態を基準として覚える（知らせない）
    st = load(); st["installed"] = names; st["use"] = use; save(st)
    print("登録しました：" + "・".join(f"{JOBS[n][0]}の{ {'watch': '見張り', 'clean': '掃除', 'skills': 'スキルの点検'}[n] }" for n in names))


def uninstall(quiet=False):
    for n in JOBS:
        if WIN:
            subprocess.run(["powershell", "-NoProfile", "-Command",
                            f"Unregister-ScheduledTask -TaskName 'fox-home-{n}' -Confirm:$false -ErrorAction SilentlyContinue"],
                           capture_output=True, **NOWIN)
        else:
            label = f"com.fox-kit.home.{n}"
            subprocess.run(["launchctl", "bootout", f"gui/{os.getuid()}/{label}"], capture_output=True)
            (HOME / "Library/LaunchAgents" / f"{label}.plist").unlink(missing_ok=True)
    if not quiet:
        st = load(); st["installed"] = []; save(st)
        print("予定から外しました")


def status():
    st = load()
    names = st.get("installed") or []
    print("据え置きの見張り: " + ("・".join(names) if names else "入っていません") + f"（{st.get('use', '-')}）")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    if cmd == "install":
        install("mobile" if (sys.argv[2:] or ["office"])[0] == "mobile" else "office")
    elif cmd in ("watch", "clean", "skills", "uninstall", "status"):
        {"watch": watch, "clean": clean, "skills": skills, "uninstall": uninstall, "status": status}[cmd]()
    else:
        print(__doc__)
