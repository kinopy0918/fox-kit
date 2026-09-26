#!/usr/bin/env python3
"""fox-kit のスキルと道具をまとめて入れる係。

  python3 packs.py install        すべて入れる（何度実行しても壊さない。入っているものは更新）
  python3 packs.py status         何が入っているか
  python3 packs.py key            Gemini の API キーを登録する（画像生成・意味検索で使う）

入れるもの（第三者のスキルは再配布せず、配布元から直接取ってくる）:
  道具      Homebrew → node / ffmpeg / yt-dlp / poppler / whisper-cpp / uv、Google Chrome、Obsidian
  プラグイン  SEO（AgriciDaniel/claude-seo）・Obsidian（kepano）・マーケティング（coreyhaines31）・
            文書とスキル作り（anthropics/skills）・世間の反応（last30days）・文章の仕上げ（humanizer）
  スキル     動画づくり（remotion-dev）・セキュリティ・構成図・手抜き防止・スキル探し・キャラ画像・
            本をスキルに・Google（gcloud / GA4）
  自作       画像生成（nanobanana）・意味検索（vault-rag）＝ fox-kit に同梱
  MCP       playwright（ブラウザ操作）・vault-rag（意味検索）
"""
from __future__ import annotations

import getpass
import io
import json
import os
import shutil
import subprocess
import sys
import tarfile
import time
import urllib.request
from pathlib import Path

HOME = Path.home()
SKILLS = HOME / ".claude" / "skills"
TOOLS = HOME / "Tools"
RECORD = HOME / ".config" / "fox-kit" / "packs.json"
LOG = HOME / "Library" / "Logs" / "fox-install.log"
B = True
try:
    B = "FOX_LEVEL=expert" not in (HOME / ".config/fox-kit/state.env").read_text()
except OSError:
    pass

BREW = ["node", "ffmpeg", "yt-dlp", "poppler", "whisper-cpp", "uv"]
CASKS = [("google-chrome", "/Applications/Google Chrome.app"), ("obsidian", "/Applications/Obsidian.app")]
PLUGINS = [  # (マーケットプレイス, プラグイン@マーケットプレイス)
    ("AgriciDaniel/claude-seo", "claude-seo@agricidaniel-claude-seo"),
    ("kepano/obsidian-skills", "obsidian@obsidian-skills"),
    ("coreyhaines31/marketingskills", "marketing-skills@marketingskills"),
    ("anthropics/skills", "document-skills@anthropic-agent-skills"),
    ("anthropics/skills", "example-skills@anthropic-agent-skills"),
    ("mvanhorn/last30days-skill", "last30days@last30days-skill"),
    ("blader/humanizer", "humanizer@humanizer"),
]
UPSTREAM = [  # (リポジトリ, リポジトリ内の場所, 入れる名前)。場所の末尾が /* なら中のフォルダを全部
    ("remotion-dev/skills", "skills/*", None),
    ("cloudflare/security-audit-skill", "skills/security-audit", "security-audit"),
    ("tt-a1i/archify", "archify", "archify"),
    ("Leonxlnx/unlazy", ".", "unlazy"),
    ("vercel-labs/skills", "skills/find-skills", "find-skills"),
    ("s1dashu/ip-as-logo-skill", ".", "ip-as-logo-skill"),
    ("virgiliojr94/book-to-skill", ".", "book-to-skill"),
    ("google/skills", "plugins/cloud/google-cloud-developer/skills/gcloud", "gcloud"),
    ("google/skills", "skills/analytics/google-analytics-data-api-basics", "google-analytics-data-api-basics"),
]


def t(b, e):
    return b if B else e


def say(s):
    print(s, flush=True)


def ok(s):
    say(f"\033[32m  ✓ {s}\033[0m")


def warn(s):
    say(f"\033[33m  ! {s}\033[0m")


def sh(cmd, check=False, **kw):
    with open(LOG, "a") as f:
        f.write(f"$ {cmd if isinstance(cmd, str) else ' '.join(map(str, cmd))}\n")
        r = subprocess.run(cmd, shell=isinstance(cmd, str), stdout=f, stderr=subprocess.STDOUT, **kw)
    if check and r.returncode != 0:
        raise RuntimeError(f"失敗: {cmd}")
    return r.returncode == 0


def brew_bin():
    for p in ("/opt/homebrew/bin/brew", "/usr/local/bin/brew"):
        if Path(p).exists():
            return p
    return None


def claude_bin():
    return shutil.which("claude") or str(HOME / ".local/bin/claude")


# ------------------------------------------------------------------ 道具
def tools():
    say(t("  道具を入れます（はじめてのときは10〜20分かかります）", "  Homebrew と CLI"))
    if not brew_bin():
        say(t("  Macのパスワードを聞かれたら入れてください。", "  Homebrew 導入（sudo）"))
        subprocess.run(["sudo", "-v"])
        sh('NONINTERACTIVE=1 /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"')
        if not brew_bin():
            warn(t("道具の土台（Homebrew）を入れられませんでした。あとで fox-kit packs でやり直せます", "Homebrew 導入失敗"))
            return False
        prof = HOME / ".zprofile"
        line = f'eval "$({brew_bin()} shellenv)"'
        if line not in (prof.read_text() if prof.exists() else ""):
            with open(prof, "a") as f:
                f.write("\n" + line + "\n")
    brew = brew_bin()
    os.environ["PATH"] = f"{Path(brew).parent}:{os.environ['PATH']}"
    have = subprocess.run([brew, "list", "--formula", "-1"], capture_output=True, text=True).stdout.split()
    need = [f for f in BREW if f not in have]
    if need:
        sh([brew, "install", *need])
    for cask, app in CASKS:
        if not Path(app).exists():
            sh([brew, "install", "--cask", cask])
    if not shutil.which("defuddle"):
        sh(["npm", "install", "-g", "defuddle"])
    ok(t("道具を入れました（動画・PDF・音声の処理、ブラウザ、ノートアプリ）", f"brew: {', '.join(BREW)} / casks / defuddle"))
    return True


# ------------------------------------------------------------------ プラグイン
def plugins():
    c = claude_bin()
    done = 0
    for repo, plugin in PLUGINS:
        sh([c, "plugin", "marketplace", "add", repo])
        if sh([c, "plugin", "install", plugin, "--scope", "user"]) or sh([c, "plugin", "install", plugin]):
            done += 1
        else:
            warn(f"{plugin} を入れられませんでした（あとで fox-kit packs でやり直せます）")
    ok(t(f"プラグインを {done} 個入れました（SEO・ノート・マーケティング・文書・世間の反応・文章の仕上げ）",
         f"plugins: {done}/{len(PLUGINS)}"))


# ------------------------------------------------------------------ 配布元から取ってくるスキル
def fetch_repo(repo):
    url = f"https://codeload.github.com/{repo}/tar.gz/HEAD"
    data = urllib.request.urlopen(url, timeout=120).read()
    return tarfile.open(fileobj=io.BytesIO(data), mode="r:gz")


def upstream():
    rec = {}
    cache = {}
    n = 0
    for repo, path, name in UPSTREAM:
        try:
            tf = cache.get(repo) or fetch_repo(repo)
            cache[repo] = tf
        except Exception as e:
            warn(f"{repo} を取ってこられませんでした: {e}")
            continue
        members = tf.getmembers()
        root = members[0].name.split("/")[0]
        base = root if path == "." else f"{root}/{path.rstrip('/*')}"
        targets = []
        if path.endswith("/*"):
            subs = {m.name[len(base) + 1:].split("/")[0] for m in members
                    if m.name.startswith(base + "/") and m.name[len(base) + 1:].count("/") >= 1}
            targets = [(f"{base}/{s}", s) for s in sorted(subs)]
        else:
            targets = [(base, name)]
        for src, nm in targets:
            dest = SKILLS / nm
            tmp = SKILLS / f".{nm}.tmp"
            shutil.rmtree(tmp, ignore_errors=True)
            for m in members:
                if m.name == src or m.name.startswith(src + "/"):
                    rel = m.name[len(src):].lstrip("/")
                    if not rel or "/.git/" in m.name or rel.startswith(".git"):
                        continue
                    out = tmp / rel
                    if m.isdir():
                        out.mkdir(parents=True, exist_ok=True)
                    elif m.isfile():
                        out.parent.mkdir(parents=True, exist_ok=True)
                        out.write_bytes(tf.extractfile(m).read())
                        if m.mode & 0o111:
                            out.chmod(0o755)
            if not (tmp / "SKILL.md").exists():
                shutil.rmtree(tmp, ignore_errors=True)
                continue
            shutil.rmtree(dest, ignore_errors=True)
            tmp.rename(dest)
            rec[nm] = repo
            n += 1
    ok(t(f"スキルを {n} 本取ってきました（動画づくり・セキュリティ・構成図・キャラ画像・Google ほか）", f"upstream skills: {n}"))
    return rec


# ------------------------------------------------------------------ 自作の道具（同梱）
def own_tools():
    bin_dir = HOME / ".local/bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    nb = TOOLS / "nanobanana"
    if nb.exists() and shutil.which("npm"):
        sh(["npm", "install", "--silent"], cwd=str(nb))
        w = bin_dir / "nanobanana"
        w.write_text(f'#!/bin/zsh\nexec node "{nb}/generate.js" "$@"\n')
        w.chmod(0o755)
    rag = TOOLS / "vault-rag"
    if rag.exists() and shutil.which("uv"):
        venv = rag / ".venv"
        if not venv.exists():
            sh(["uv", "venv", "--python", "3.12", str(venv)])
        sh(["uv", "pip", "install", "--python", str(venv / "bin/python"), "numpy", "mcp"])
        w = bin_dir / "vault-rag"
        w.write_text(f'#!/bin/zsh\nexec "{venv}/bin/python" "{rag}/rag.py" "$@"\n')
        w.chmod(0o755)
    ok(t("画像づくり（nanobanana）と、意味で探す仕組み（vault-rag）を用意しました", "nanobanana / vault-rag"))


def mcps():
    c = claude_bin()
    rag = TOOLS / "vault-rag"
    added = []
    listing = subprocess.run([c, "mcp", "list"], capture_output=True, text=True).stdout
    if "playwright" not in listing and sh([c, "mcp", "add", "--scope", "user", "playwright", "--",
                                          "npx", "-y", "@playwright/mcp@latest"]):
        added.append("playwright")
    if "vault-rag" not in listing and (rag / ".venv/bin/python").exists() and sh(
            [c, "mcp", "add", "--scope", "user", "vault-rag", "--", str(rag / ".venv/bin/python"), str(rag / "server.py")]):
        added.append("vault-rag")
    ok(t("AIがブラウザを操作する仕組みと、意味で探す仕組みをつなぎました", f"MCP: playwright, vault-rag {added}"))


def daily_index():
    """意味検索の索引を毎日更新する（中身が変わった分だけ）。"""
    rag = TOOLS / "vault-rag"
    if not (rag / ".venv/bin/python").exists():
        return
    label = "com.fox-kit.vault-rag"
    plist = HOME / "Library/LaunchAgents" / f"{label}.plist"
    import plistlib
    plist.parent.mkdir(parents=True, exist_ok=True)
    with open(plist, "wb") as f:
        plistlib.dump({"Label": label, "ProgramArguments": [str(rag / ".venv/bin/python"), str(rag / "rag.py"), "index"],
                       "StartCalendarInterval": {"Hour": 4, "Minute": 10},
                       "StandardOutPath": str(HOME / "Library/Logs/vault-rag.log"),
                       "StandardErrorPath": str(HOME / "Library/Logs/vault-rag.log")}, f)
    uid = os.getuid()
    subprocess.run(["launchctl", "bootout", f"gui/{uid}/{label}"], capture_output=True)
    subprocess.run(["launchctl", "bootstrap", f"gui/{uid}", str(plist)], capture_output=True)


# ------------------------------------------------------------------ Gemini のキー
def key():
    say(t("\n  画像づくりと「意味で探す」には、Google の AI（Gemini）の鍵が1つ要ります（無料枠あり）。",
          "\n  Gemini API キー（画像生成・埋め込み）"))
    cur = subprocess.run(["security", "find-generic-password", "-s", "fox-kit", "-a", "gemini", "-w"],
                         capture_output=True, text=True).stdout.strip()
    if cur and "--force" not in sys.argv:
        ok(t("鍵はもう登録されています", "登録済み"))
        return True
    subprocess.run(["open", "https://aistudio.google.com/apikey"])
    for i, s in enumerate([t("開いた画面で Google アカウントにログイン（会社で使うなら会社のアカウント）", "ログイン"),
                           t("「APIキーを作成」→ できた長い文字列の横のコピーを押す", "Create API key → コピー")], 1):
        say(f"    {i}. {s}")
    for _ in range(3):
        v = getpass.getpass(t("  コピーした鍵を貼り付けて return（画面には出ません。あとでやるなら空のまま return）: ", "  API key: ")).strip()
        if not v:
            warn(t("あとで fox-kit packs key で登録できます", "skip"))
            return False
        try:
            urllib.request.urlopen(f"https://generativelanguage.googleapis.com/v1beta/models?key={v}", timeout=20).read()
        except Exception:
            warn(t("この鍵ではつながりませんでした。もう一度コピーして貼ってください", "invalid key"))
            continue
        subprocess.run(["security", "add-generic-password", "-U", "-s", "fox-kit", "-a", "gemini", "-w", v],
                       check=True, capture_output=True)
        ok(t("鍵を登録しました（Macの金庫＝キーチェーンに保管）", "Keychain: fox-kit/gemini"))
        return True
    return False


def first_index():
    w = HOME / ".local/bin/vault-rag"
    if w.exists():
        say(t("  保存先の中身から、意味で探すための索引を作ります（数分）…", "  vault-rag index"))
        sh([str(w), "index"])


# ------------------------------------------------------------------ 入口
def install():
    t0 = time.time()
    st = json.loads(RECORD.read_text()) if RECORD.exists() else {}
    if tools():
        own_tools()
        mcps()
        daily_index()
    plugins()
    st["upstream"] = upstream()
    st["plugins"] = [p for _, p in PLUGINS]
    st["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    RECORD.parent.mkdir(parents=True, exist_ok=True)
    RECORD.write_text(json.dumps(st, ensure_ascii=False, indent=2))
    if key():
        first_index()
    ok(t(f"スキルと道具をそろえました（{int(time.time() - t0) // 60}分）", f"done in {int(time.time() - t0)}s"))


def status():
    st = json.loads(RECORD.read_text()) if RECORD.exists() else {}
    say(f"  取ってきたスキル: {len(st.get('upstream', {}))} 本 / プラグイン: {len(st.get('plugins', []))} 個（{st.get('updated_at', '未導入')}）")
    k = subprocess.run(["security", "find-generic-password", "-s", "fox-kit", "-a", "gemini"], capture_output=True).returncode == 0
    say(f"  Gemini の鍵: {'登録済み' if k else 'まだ（fox-kit packs key）'}")


if __name__ == "__main__":
    LOG.parent.mkdir(parents=True, exist_ok=True)
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    {"install": install, "status": status, "key": key}.get(cmd, status)()
