#!/usr/bin/env python3
"""どこで話しても同じ前提にする：基本の1枚（Drive）と、記憶の写し（Drive へ10分おき）。

  fox_base.py install --owner 名前 --agent FOX --machine air
  fox_base.py paste   --owner 名前 --agent FOX     # claude.ai の個人設定に貼る文

Drive が無いパソコンでは、基本の1枚を手元に置くだけにして写しは作らない。
写し先はパソコンごとに別フォルダ（memory-<machine>）。1つの親に両機で同時に作ると、
Drive に同じ名前のフォルダが2つでき、互いに見えなくなるため。
"""
import argparse, json, os, platform, plistlib, re, subprocess, sys
from pathlib import Path

H = Path.home()
HERE = Path(__file__).resolve().parent
RULE = H / ".claude/rules/fox-base.md"
LABEL = "com.fox-kit.memory-mirror"


def drive_root():
    """保存先に Google ドライブを選んだ人だけ、選んだアカウントのマイドライブを返す。
    「このパソコンの中だけ」を選んだ人・まだ決めていない人の記憶は、どこにも写さない。"""
    try:
        base = json.loads((H / ".config/fox-kit/storage.json").read_text(encoding="utf-8"))["base"]
    except (OSError, ValueError, KeyError):
        return None
    m = re.match(r"(.*/Library/CloudStorage/GoogleDrive-[^/]+)(/|$)", base)
    for n in ("マイドライブ", "My Drive") if m else ():
        if (Path(m.group(1)) / n).is_dir():
            return Path(m.group(1)) / n
    return None


def stop_mirror():
    p = H / f"Library/LaunchAgents/{LABEL}.plist"
    if p.exists():
        subprocess.run(["launchctl", "bootout", f"gui/{os.getuid()}", str(p)], capture_output=True)
        p.unlink()
        print("  記憶の写しを止めました（Google ドライブに写した分は残してあります）")


def memory_dir():
    try:
        d = json.load(open(H / ".claude/settings.json")).get("autoMemoryDirectory")
        if d:
            return Path(os.path.expanduser(d))
    except Exception:
        pass
    return H / ".claude/projects" / re.sub(r"[^A-Za-z0-9-]", "-", str(H)) / "memory"


def bare(owner):
    """ひな形と貼る文が「さん」を付けるので、名前に付いている敬称は外す（「山田さんさん」にしない）。"""
    return re.sub(r"\s*(さん|様|さま)$", "", owner.strip()) or owner


def render(owner, agent):
    t = (HERE / "fox-base.md.template").read_text(encoding="utf-8")
    return t.replace("{{OWNER}}", bare(owner)).replace("{{AGENT}}", agent)


def paste(owner, agent):
    owner = bare(owner)
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
        local = RULE.read_text(encoding="utf-8") if RULE.is_file() and not RULE.is_symlink() else None
        if not base.exists():                       # 既にあれば（別のパソコンで作った）そのまま使う
            base.write_text(local or render(a.owner, a.agent), encoding="utf-8")   # 手元で育てた1枚があれば、それを持っていく
        if local is None or local == base.read_text(encoding="utf-8"):
            if RULE.is_symlink() or RULE.exists():
                RULE.unlink()
            RULE.symlink_to(base)
        else:
            print(f"  ! {RULE} が手元のファイルとしてあるので触りません（Drive の {base} と見比べてください）")
    elif not RULE.exists():
        RULE.write_text(render(a.owner, a.agent), encoding="utf-8")
        print("  基本の1枚は、このパソコンの中だけに置きました（保存先に Google ドライブを選ぶと、そちらへ移します）")

    cm = H / ".claude/CLAUDE.md"
    if cm.exists() and "rules/fox-base.md" not in cm.read_text(encoding="utf-8"):
        with open(cm, "a", encoding="utf-8") as f:
            f.write("\n## どこでも共通の基本\n\n@~/.claude/rules/fox-base.md\n")

    if sys.platform != "darwin" or os.environ.get("FOX_SKIP_LAUNCHD"):
        return
    if not D:
        return stop_mirror()                        # 保存先を「このパソコンの中だけ」に変えたら、写しも止める
    # 名前が既定のまま（このMac）だと2台目が同じ写し先を上書きするので、そのときはパソコン固有の名前を使う
    label = a.machine if a.machine not in ("", "このMac", "このパソコン") else platform.node().split(".")[0]
    slug = re.sub(r"[^\w]+", "-", label.lower()).strip("-") or "mac"
    mem = memory_dir()
    dest = D / a.agent / f"memory-{slug}"
    sh = (f'D="{dest}"; mkdir -p "$D/_snapshots" && /usr/bin/rsync -a --delete --exclude .DS_Store '
          f'"{mem}/" "$D/latest/" && f="$D/_snapshots/{slug}-$(date +%G-W%V).tar.gz" && '
          f'{{ [ -f "$f" ] || tar czf "$f" -C "{mem}" . ; }} && date "+%F %T ok"')
    log = str(H / "Library/Logs/fox-memory-mirror.log")
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
    ap.add_argument("cmd", choices=["install", "paste", "stop"])
    ap.add_argument("--owner", default="")
    ap.add_argument("--agent", default="FOX")
    ap.add_argument("--machine", default=platform.node().split(".")[0])   # os.uname は Windows に無い
    a = ap.parse_args()
    if a.cmd == "stop":
        stop_mirror()
    elif not a.owner:
        ap.error("--owner が要ります")
    else:
        install(a) if a.cmd == "install" else print(paste(a.owner, a.agent))
