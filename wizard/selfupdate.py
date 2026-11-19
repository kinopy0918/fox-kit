#!/usr/bin/env python3
"""設定画面の「更新する」から呼ぶ。新しい版のキットを取ってきて入れ替え、デスクトップの「FoxKit」を作り直す。標準ライブラリだけ。

  python3 selfupdate.py <キットの場所> <版>

入れ替えたあと、設定画面が自分で開き直し、組み立ての段（新しいスキル・作法を配る）をもう一度回す。
前の版は「<キットの場所>.bak-日時」に1つだけ残す。
"""
import io
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.request
from pathlib import Path

REPO = "kinopy0918/fox-kit"
WIN = os.name == "nt"
HOME = Path.home()
DESK = HOME / "Desktop"


def say(s):
    print(s, flush=True)


def swap(kit: Path, ver: str):
    say(f"▶ 新しい版（{ver}）を取ってきます")
    data = urllib.request.urlopen(f"https://codeload.github.com/{REPO}/tar.gz/refs/tags/v{ver}", timeout=180).read()
    tmp = Path(tempfile.mkdtemp(prefix="fox-kit-"))
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tf:
        tf.extractall(tmp)
    root = next(p for p in tmp.iterdir() if p.is_dir())
    if not (root / ("setup/build_win.py" if WIN else "install.sh")).exists():
        raise SystemExit("  ✕ 取ってきた中身がおかしいので、入れ替えませんでした（いまの版のまま使えます）")
    say("▶ 入れ替えます")
    for b in kit.parent.glob(kit.name + ".bak-*"):
        shutil.rmtree(b, ignore_errors=True)
    bak = kit.with_name(kit.name + ".bak-" + time.strftime("%Y%m%d-%H%M%S"))
    kit.rename(bak)
    try:
        shutil.move(str(root), str(kit))
    except Exception:
        if not kit.exists():
            bak.rename(kit)
        raise
    shutil.rmtree(tmp, ignore_errors=True)


def desktop(kit: Path):
    """デスクトップの入口を「FoxKit」に（前の名前「AIの設定画面」は消す）。"""
    try:
        if WIN:
            for old in ("AIの設定画面.lnk",):
                (DESK / old).unlink(missing_ok=True)
            pyw = Path(sys.executable).with_name("pythonw.exe")
            q = lambda x: str(x).replace("'", "''")
            ps = (f"$sc=(New-Object -ComObject WScript.Shell).CreateShortcut('{q(DESK / 'FoxKit.lnk')}');"
                  f"$sc.TargetPath='{q(pyw if pyw.exists() else sys.executable)}';$sc.Arguments='\"{q(kit / 'wizard/server.py')}\"';"
                  f"$sc.WorkingDirectory='{q(HOME)}';$sc.Description='FoxKit（AI秘書の設定と更新）';"
                  f"$sc.IconLocation='{q(kit / 'assets/fox-kit.ico')},0';$sc.Save()")
            subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, creationflags=0x08000000)
            return
        shutil.rmtree(DESK / "AIの設定画面.app", ignore_errors=True)
        app = DESK / "FoxKit.app"
        srv, log = kit / "wizard/server.py", HOME / "Library/Logs/fox-wizard.log"
        src = Path(tempfile.mkstemp(suffix=".applescript")[1])
        src.write_text(f'do shell script "pkill -f " & quoted form of "{srv}" & " ; nohup /usr/bin/python3 " & quoted form of "{srv}"'
                       f' & " > " & quoted form of "{log}" & " 2>&1 &"\n', encoding="utf-8")
        shutil.rmtree(app, ignore_errors=True)
        if subprocess.run(["osacompile", "-o", str(app), str(src)], capture_output=True).returncode == 0:
            res = app / "Contents/Resources"
            shutil.copyfile(kit / "assets/fox-kit.icns", res / "applet.icns")
            (res / "Assets.car").unlink(missing_ok=True)
            subprocess.run(["/usr/libexec/PlistBuddy", "-c", "Delete :CFBundleIconName", str(app / "Contents/Info.plist")], capture_output=True)
            os.utime(app)
        src.unlink(missing_ok=True)
    except Exception as e:   # 入口が作れなくても、更新そのものは済んでいる
        say(f"  ! デスクトップの「FoxKit」を作り直せませんでした（{e}）")


if __name__ == "__main__":
    kit, ver = Path(sys.argv[1]), sys.argv[2]
    swap(kit, ver)
    desktop(kit)
    say(f"  ✓ 新しい版（{ver}）にしました。設定画面を開き直して、新しいスキルと作法を配ります")
