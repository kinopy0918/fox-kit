#!/usr/bin/env python3
"""fox-kit を外す／AIが作業の前に毎回確認する設定に戻す。

  uninstall.py               何を外して何を残すかを見せ、確かめてから外す
  uninstall.py --yes         確かめずに外す（AI から呼ぶとき。AI は先に本人に確かめること）
  uninstall.py --dry-run     見せるだけ
  uninstall.py confirm on    AIが作業の前に毎回確認する設定にする（キットは外さない）
  uninstall.py confirm off   確認なしで進める設定に戻す

外したものは消さずに ~/fox-kit-removed-<日時>/ へ移す（中身を確かめてから、そのフォルダごと捨てればよい）。
記憶・資料の保存先・Claude 本体とログイン・Chrome などのアプリには触らない。
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

HOME = Path.home()
WIN = os.name == "nt"
TOOLS = Path(__file__).resolve().parent.parent            # Mac: ~/Tools ／ Windows: ~/Tools/fox-kit/tools
CONF = HOME / ".config" / "fox-kit"
SETTINGS = HOME / ".claude" / "settings.json"
CLAUDE_MD = HOME / ".claude" / "CLAUDE.md"
OLD_MARK = "## 前から書いてあった決まり（このキットを入れる前の CLAUDE.md。そのまま残してあります）"
KIT_HOOKS = ("guard-output-location.py", "block-dangerous-ops.py", "block-secret-commit.py", "chime.py")
SKIP_LAUNCHD = bool(os.environ.get("FOX_SKIP_LAUNCHD"))   # 試運転：常駐・鍵・電源には触らない


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", **kw)


def kit_record() -> dict:
    """入れたときの控え（このキットが足した許可・項目）。古い版で入れた人は控えが無いので、キットの設定から推し量る。"""
    try:
        return json.loads((CONF / "kit-settings.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        pass
    for root in (HOME / "Tools/portable-fox", HOME / "Tools/fox-kit"):
        p = root / "claude" / "settings.json"
        if p.exists():
            kit = json.loads(p.read_text(encoding="utf-8"))
            return {"allow": (kit.get("permissions") or {}).get("allow") or [], "mode": True,
                    "keys": [k for k in kit if k not in ("permissions", "hooks")]}
    return {"allow": [], "keys": ["skipDangerousModePermissionPrompt"], "mode": True}


def load_settings() -> dict | None:
    try:
        return json.loads(SETTINGS.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None


def save_settings(d: dict):
    SETTINGS.write_text(json.dumps(d, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def confirm_mode(on: bool):
    d = load_settings()
    if d is None:
        raise SystemExit("設定ファイル（~/.claude/settings.json）を読めませんでした。")
    p = d.setdefault("permissions", {})
    if on:
        p["defaultMode"] = "default"
        d.pop("skipDangerousModePermissionPrompt", None)
        msg = "AIは、作業の前に毎回あなたに確認するようになりました。"
    else:
        p["defaultMode"] = "bypassPermissions"
        d["skipDangerousModePermissionPrompt"] = True
        msg = "AIは、確認なしで作業を進めるようになりました（お金・社外への送信・取り消せない操作は、先に確かめる決まりです）。"
    save_settings(d)
    ag_mode(on)
    print(msg + " いま開いているAIの会話は、開き直すと新しい設定になります。")


def ag_mode(on: bool):
    """Antigravity の中の Claude Code も、同じ「毎回確認／確認なし」にそろえる。"""
    import glob
    pats = [str(HOME / "Library/Application Support/Antigravity*/User/settings.json")]
    if os.environ.get("APPDATA"):
        pats.append(os.path.join(os.environ["APPDATA"], "Antigravity*", "User", "settings.json"))
    for f in [x for pat in pats for x in glob.glob(pat)]:
        try:
            d = json.loads(Path(f).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue                     # 手書きのコメント入りJSONは触らない
        d["claudeCode.initialPermissionMode"] = "default" if on else "bypassPermissions"
        if on:
            d.pop("claudeCode.allowDangerouslySkipPermissions", None)
        else:
            d["claudeCode.allowDangerouslySkipPermissions"] = True
        Path(f).write_text(json.dumps(d, indent=4, ensure_ascii=False), encoding="utf-8")


def unkit_settings(cur: dict, rec: dict) -> dict:
    """キットが足したものだけを外す。持ち主が決めた項目・足した hook・deny は残す。"""
    out = json.loads(json.dumps(cur))
    hooks = out.get("hooks") or {}
    for ev in list(hooks):
        kept = []
        for e in hooks[ev]:
            hs = [h for h in e.get("hooks", []) if not any(n in h.get("command", "") for n in KIT_HOOKS)]
            if hs:
                kept.append({**e, "hooks": hs})
        if kept:
            hooks[ev] = kept
        else:
            del hooks[ev]
    if not hooks:
        out.pop("hooks", None)
    p = out.get("permissions") or {}
    if "allow" in p:
        p["allow"] = [a for a in p["allow"] if a not in set(rec["allow"])]
        if not p["allow"]:
            del p["allow"]
    if rec["mode"] and p.get("defaultMode") == "bypassPermissions":   # キットが入れた「確認なし」を外す＝毎回確認する（Claude のもとの動き）
        del p["defaultMode"]
        out.pop("skipDangerousModePermissionPrompt", None)
    for k in rec["keys"]:
        if k != "autoMemoryDirectory":                    # 記憶の場所は変えない
            out.pop(k, None)
    if not p:
        out.pop("permissions", None)
    return out


def agents() -> list[Path]:
    d = HOME / "Library/LaunchAgents"
    return sorted(p for p in d.glob("*.plist") if re.match(r"com\.(fox-kit\.|fox-bridge$)", p.stem)) if d.is_dir() else []


def plan() -> dict:
    rec = {}
    try:
        rec = json.loads((CONF / "install.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        pass
    files = [Path(f) for f in rec.get("files", {}) if Path(f).exists()]
    extra = [p for p in (HOME / ".claude/fox-kit", HOME / "Tools/portable-fox", HOME / "Tools/fox-kit", CONF, HOME / ".config/fox-bridge",
                         HOME / ".local/bin/fox-kit", HOME / ".local/bin/vault-rag", HOME / "Desktop/AIの設定画面.lnk", HOME / "Desktop/AIの設定画面.app", HOME / "Desktop/FoxKit.lnk", HOME / "Desktop/FoxKit.app") if p.exists() or p.is_symlink()]
    return {"files": files, "extra": extra, "agents": agents(),
            "daemon": Path("/Library/LaunchDaemons/com.local.capslock-nosleep.plist").exists(),
            "office": "FOX_MAC_USE=office" in ((CONF / "state.env").read_text(encoding="utf-8") if (CONF / "state.env").exists() else "")}


def show(p: dict, dest: Path):
    print("fox-kit を外します。\n\n■ 外すもの（消さずに、次のフォルダへ移します）\n  " + str(dest))
    print(f"  ・AIの人格と作法、キットのスキル・安全の見張り・道具（{len(p['files'])}ファイル）")
    print("  ・「確認なしで進める」設定と、キットが足した許可（設定ファイルは控えを取って書き戻します）")
    if p["agents"] or WIN:
        print("  ・裏で動いているもの（毎朝の点検・毎朝のまとめ・スマホからの返事・記憶の写しなど）"
              + (f"：{len(p['agents'])}本" if p["agents"] else ""))
    print("  ・このパソコンに預けた鍵（Discord／Slack・画像づくり）")
    print("\n■ 残すもの（触りません）\n  ・AIの記憶と、資料の保存先のフォルダ（Google ドライブに写した分も）\n  ・Claude 本体とログイン、Chrome・Antigravity・Google ドライブなどのアプリ"
          "\n  ・あとから入れた追加のスキル（Claude のプラグイン）")
    if p["daemon"] or p["office"]:
        print("\n■ パソコンのパスワードが要るもの（このあと案内します）")
        if p["office"]:
            print("  ・眠らない設定・停電後の自動起動を、もとに戻す")
        if p["daemon"]:
            print("  ・CapsLock で眠らなくする仕組みを外す")


def move(p: Path, dest: Path):
    try:
        rel = p.relative_to(HOME)
    except ValueError:
        rel = Path(p.name)
    to = dest / rel
    to.parent.mkdir(parents=True, exist_ok=True)
    if to.exists():
        return
    shutil.move(str(p), str(to))


def stop_all(p: dict):
    if SKIP_LAUNCHD:
        return
    py = sys.executable
    for script, args in (("fox-bridge/connect.py", ["--stop"]), ("fox-home/home.py", ["uninstall"]),
                         ("fox-morning/morning.py", ["uninstall"]), ("fox-routine/routine.py", ["uninstall"]), ("fox-base/fox_base.py", ["stop"]),
                         ("fox-remote/remote.py", ["uninstall"]), ("fox-connector/connector.py", ["uninstall"])):
        s = TOOLS / script
        if s.exists():
            run([py, str(s), *args], timeout=120)
    if WIN:
        return
    uid = os.getuid()
    for pl in p["agents"]:                                # 取りこぼしが無いよう、名前で拾って止める
        run(["launchctl", "bootout", f"gui/{uid}/{pl.stem}"])
        if pl.exists():
            pl.unlink()
    for svc in ("fox-bridge", "fox-kit"):                 # 預かった鍵を消す（同じ名前に複数あるので、無くなるまで）
        while run(["security", "delete-generic-password", "-s", svc]).returncode == 0:
            pass


def needs_password(p: dict):
    tty = sys.stdin and sys.stdin.isatty() and not SKIP_LAUNCHD
    cmds = []
    if p["daemon"]:
        un = next((x for x in (HOME / "Tools/capslock-nosleep/uninstall.sh",) if x.exists()), None)
        if un:
            cmds.append((f'sudo "{un}"', "CapsLock で眠らなくする仕組みを外す"))
    if p["office"]:
        cmds.append(("sudo pmset restoredefaults", "眠る設定・停電後の自動起動を、買ったときの設定に戻す"))
    for cmd, what in cmds:
        if tty and input(f"\n{what}（パソコンのパスワードを聞かれます）。いま行いますか？ [y/N] ").strip().lower() in ("y", "yes", "はい"):
            subprocess.run(cmd, shell=True)
        else:
            print(f"\n  ・{what}：黒い画面（ターミナル）に次の1行を貼ってください\n      {cmd}")


def uninstall(yes: bool, dry: bool):
    p = plan()
    dest = HOME / f"fox-kit-removed-{time.strftime('%Y%m%d-%H%M%S')}"
    show(p, dest)
    if dry:
        return
    if not yes:
        if not (sys.stdin and sys.stdin.isatty()):
            raise SystemExit("\n確かめる相手がいないので、何もしていません。外してよければ --yes を付けてください。")
        if input("\n外してよいですか？ [y/N] ").strip().lower() not in ("y", "yes", "はい"):
            raise SystemExit("何もしていません。")
    needs_password(p)                                     # 道具を移す前に（外す道具がまだ ~/Tools にあるうちに）
    stop_all(p)
    dest.mkdir(parents=True, exist_ok=True)

    cur = load_settings()
    if cur is not None:
        shutil.copyfile(SETTINGS, dest / "settings.json.外す前")
        save_settings(unkit_settings(cur, kit_record()))
    elif SETTINGS.exists():
        print("  ! 設定ファイル（~/.claude/settings.json）を読めなかったので、そのまま残しました。")

    if CLAUDE_MD.exists():
        text = CLAUDE_MD.read_text(encoding="utf-8")
        if "fox-kit/rules/craft.md" in text:              # キットの人格。入れる前から書いていた分があれば、それだけを戻す
            shutil.copyfile(CLAUDE_MD, dest / "CLAUDE.md.外す前")
            old = text.split(OLD_MARK, 1)[1] if OLD_MARK in text else ""
            old = re.sub(r"\n@~/\.claude/(fox-kit/)?rules/[\w.-]+\n", "\n", old).strip()
            if old:
                CLAUDE_MD.write_text(old + "\n", encoding="utf-8")
            else:
                CLAUDE_MD.unlink()

    for f in p["extra"] + p["files"]:                     # フォルダごと移せるものを先に（中の1つずつは、その後に残っていれば移す）
        if f.exists() or f.is_symlink():
            move(f, dest)
    for root in (HOME / ".claude/skills", HOME / ".claude/hooks", HOME / ".claude/agents", HOME / "Tools"):
        if root.is_dir():                                 # 空になったフォルダを片づける（中身が残っていれば触らない）
            for d in sorted((x for x in root.rglob("*") if x.is_dir()), key=lambda x: -len(x.parts)):
                if not any(x.name not in (".DS_Store", "__pycache__") for x in d.iterdir()):
                    shutil.rmtree(d, ignore_errors=True)
            if not any(root.iterdir()):
                root.rmdir()
    print(f"\n外しました。移したものは {dest} にあります。中身を確かめたら、このフォルダごと捨ててください。")
    print("AIは、作業の前に毎回あなたに確認する、Claude のもとの動きに戻りました。")
    if WIN:
        print("Windows の環境変数（PYTHONUTF8 など）と、ふたの動作の設定は残しています。気になるときは、渡してくれた人に聞いてください。")
    print("もう一度使いたくなったら、手順書の1行を貼り直せば入れ直せます（記憶と資料は残っています）。")


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[:1] == ["confirm"] and a[1:2] in (["on"], ["off"]):
        confirm_mode(a[1] == "on")
    elif not a or set(a) <= {"--yes", "--dry-run"}:
        uninstall("--yes" in a, "--dry-run" in a)
    else:
        print(__doc__)
