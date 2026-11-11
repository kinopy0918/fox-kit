#!/usr/bin/env python3
"""どこで話しても同じ前提にする：基本の1枚（Drive）と、記憶の写し（Drive へ10分おき）。

  fox_base.py install --owner 名前 --agent FOX --machine air
  fox_base.py paste   --owner 名前 --agent FOX     # claude.ai の個人設定に貼る文

Drive が無いパソコンでは、基本の1枚を手元に置くだけにして写しは作らない。
写し先はパソコンごとに別フォルダ（memory-<machine>）。1つの親に両機で同時に作ると、
Drive に同じ名前のフォルダが2つでき、互いに見えなくなるため。
"""
import argparse, glob, os, plistlib, re, subprocess, sys
from pathlib import Path

H = Path.home()
HERE = Path(__file__).resolve().parent
RULE = H / ".claude/rules/fox-base.md"
LABEL = "com.fox.memory-mirror"


def drive_root():
    for m in sorted(glob.glob(str(H / "Library/CloudStorage/GoogleDrive-*"))):
        for n in ("マイドライブ", "My Drive"):
            if (Path(m) / n).is_dir():
                return Path(m) / n
    return None


def memory_dir():
    try:
        import json
        d = json.load(open(H / ".claude/settings.json")).get("autoMemoryDirectory")
        if d:
            return Path(os.path.expanduser(d))
    except Exception:
        pass
    return H / ".claude/projects" / re.sub(r"[^A-Za-z0-9-]", "-", str(H)) / "memory"


def render(owner, agent):
    t = (HERE / "fox-base.md.template").read_text()
    return t.replace("{{OWNER}}", owner).replace("{{AGENT}}", agent)


def paste(owner, agent):
    return (f"あなたは「{agent}」。{owner}さんの秘書。一人称は{agent}、日本語で、結論から短く答える。\n"
            f"{owner}さんのこと・仕事・決まりなど前提が要る話では、答える前に Google ドライブで「fox-base.md」"
            f"（マイドライブ/{agent}/fox-base/）を読むこと。細かい記憶は同じ {agent} フォルダの memory-〇〇/latest/MEMORY.md。推測で答えない。\n"
            "お金が動くこと・社外への送信・取り消せない操作は、必ず先に確認する。")


def install(a):
    D = drive_root()
    RULE.parent.mkdir(parents=True, exist_ok=True)
    if D:
        base = D / a.agent / "fox-base" / "fox-base.md"
        base.parent.mkdir(parents=True, exist_ok=True)
        if not base.exists():                       # 既にあれば（別のパソコンで作った）そのまま使う
            base.write_text(render(a.owner, a.agent))
        if RULE.is_symlink() or not RULE.exists():
            if RULE.is_symlink():
                RULE.unlink()
            RULE.symlink_to(base)
        else:
            print(f"  ! {RULE} が手元のファイルとしてあるので触りません（Drive の {base} と見比べてください）")
    elif not RULE.exists():
        RULE.write_text(render(a.owner, a.agent))
        print("  ! Google ドライブが見つからないので、基本の1枚はこのパソコンの中だけに置きました")

    cm = H / ".claude/CLAUDE.md"
    if cm.exists() and "rules/fox-base.md" not in cm.read_text():
        with open(cm, "a") as f:
            f.write("\n## どこでも共通の基本\n\n@~/.claude/rules/fox-base.md\n")

    if not D or sys.platform != "darwin":
        return
    # 名前が既定のまま（このMac）だと2台目が同じ写し先を上書きするので、そのときはパソコン固有の名前を使う
    label = a.machine if a.machine not in ("", "このMac", "このパソコン") else os.uname().nodename.split(".")[0]
    slug = re.sub(r"[^\w]+", "-", label.lower()).strip("-") or "mac"
    mem = memory_dir()
    dest = D / a.agent / f"memory-{slug}"
    sh = (f'D="{dest}"; mkdir -p "$D/_snapshots" && /usr/bin/rsync -a --delete --exclude .DS_Store '
          f'"{mem}/" "$D/latest/" && f="$D/_snapshots/{slug}-$(date +%G-W%V).tar.gz" && '
          f'{{ [ -f "$f" ] || tar czf "$f" -C "{mem}" . ; }} && date "+%F %T ok"')
    log = str(H / "Library/Logs/memory-mirror.log")
    p = H / f"Library/LaunchAgents/{LABEL}.plist"
    p.parent.mkdir(parents=True, exist_ok=True)
    plistlib.dump({"Label": LABEL, "ProgramArguments": ["/bin/sh", "-c", sh], "StartInterval": 600,
                   "RunAtLoad": True, "ProcessType": "Background",
                   "StandardOutPath": log, "StandardErrorPath": log}, open(p, "wb"))
    dom = f"gui/{os.getuid()}"
    subprocess.run(["launchctl", "bootout", dom, str(p)], capture_output=True)
    subprocess.run(["launchctl", "bootstrap", dom, str(p)], capture_output=True)
    print(f"  記憶の写し: {mem} → {dest}/latest（10分おき）")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["install", "paste"])
    ap.add_argument("--owner", required=True)
    ap.add_argument("--agent", default="FOX")
    ap.add_argument("--machine", default=os.uname().nodename.split(".")[0])
    a = ap.parse_args()
    install(a) if a.cmd == "install" else print(paste(a.owner, a.agent))
