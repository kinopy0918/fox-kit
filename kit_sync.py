#!/usr/bin/env python3
"""fox-kit の配置係：キットのファイルを所定の場所へ置き、更新のときは「手を入れていないものだけ」新しくする。

  python3 kit_sync.py            置く／更新する
  python3 kit_sync.py --dry-run  何が起きるかだけ見る

ファイルは3種類に分けて扱う（The Harness の「本体と独自拡張を分ける」考え方）:
  managed … キットが持ち主。前回置いたときから手が入っていなければ、新しい版で置き換える。
            手が入っていたら置き換えず、横に「<名前>.new-<版>」を置いて知らせる。
  seed    … 使うほど育つファイル（資料の差し戻し一覧など）。無いときだけ置き、あとは一切さわらない。
  （対象外）… その会社のもの（~/.claude/rules/ の company.md・storage.md・talk-style.md、記憶、
            ~/.claude/skills/ のキット以外のスキル）。キットは読みも書きもしない。

置いた記録は ~/.config/fox-kit/install.json（版・日時・ファイルごとの指紋）。
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
HOME = Path.home()
RECORD = HOME / ".config" / "fox-kit" / "install.json"
VERSION = (HERE / "VERSION").read_text().strip() if (HERE / "VERSION").exists() else "0.0.0"

# (キット内の場所, 置き先, 種類)。フォルダは中身を再帰で扱う。
MAP = [
    ("claude/rules", HOME / ".claude" / "fox-kit" / "rules", "managed"),
    ("claude/skills", HOME / ".claude" / "skills", "managed"),
    ("claude/agents", HOME / ".claude" / "agents", "managed"),
    ("claude/hooks", HOME / ".claude" / "hooks", "managed"),
    ("tools", HOME / "Tools", "managed"),
]
# 使うほど育つので、最初の1回だけ置くもの（キット内の相対パス）
SEED = {
    "claude/skills/shiryo-review-loop/checklist.md",
}
SKIP_NAMES = {".DS_Store", "__pycache__"}


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def items():
    for src_rel, dest_root, kind in MAP:
        src_root = HERE / src_rel
        if not src_root.exists():
            continue
        for p in sorted(src_root.rglob("*")):
            if p.is_dir() or any(part in SKIP_NAMES for part in p.parts):
                continue
            rel = p.relative_to(HERE).as_posix()
            dest = dest_root / p.relative_to(src_root)
            yield p, dest, ("seed" if rel in SEED else kind)


def main(dry=False):
    rec = json.loads(RECORD.read_text()) if RECORD.exists() else {}
    before = rec.get("files", {})
    prev_ver = rec.get("version")
    files, report = {}, {"new": [], "updated": [], "same": [], "kept": [], "seed_kept": []}
    for src, dest, kind in items():
        key = str(dest)
        new_hash = sha(src)
        if not dest.exists():
            action = "new"
        elif kind == "seed":
            action = "seed_kept"
        else:
            cur = sha(dest)
            if cur == new_hash:
                action = "same"
            elif before.get(key) and cur == before[key]:
                action = "updated"          # 前回置いたまま＝手が入っていない
            elif not before.get(key) and not prev_ver:
                action = "kept"             # 記録の無い既存ファイル＝持ち主のものかもしれない
            else:
                action = "kept"             # 手が入っている
        report[action].append(key)
        if dry:
            files[key] = before.get(key, new_hash)
            continue
        if action in ("new", "updated"):
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
            if os.access(src, os.X_OK):
                os.chmod(dest, 0o755)
            files[key] = new_hash
        elif action == "kept":
            side = dest.with_name(f"{dest.name}.new-{VERSION}")
            shutil.copy2(src, side)
            files[key] = before.get(key, "")      # 持ち主の版を尊重（記録は前回のまま）
        elif action == "seed_kept":
            files[key] = before.get(key, sha(dest))
        else:  # same
            files[key] = new_hash

    if not dry:
        RECORD.parent.mkdir(parents=True, exist_ok=True)
        rec.update(version=VERSION, previous_version=prev_ver, updated_at=time.strftime("%Y-%m-%d %H:%M:%S"),
                   files=files)
        rec.setdefault("installed_at", rec["updated_at"])
        RECORD.write_text(json.dumps(rec, ensure_ascii=False, indent=2))
        os.chmod(RECORD, 0o600)

    home = str(HOME)
    short = lambda k: k.replace(home, "~")
    label = "（dry-run）" if dry else ""
    print(f"fox-kit {prev_ver or '（新規）'} → {VERSION} {label}")
    print(f"  新しく置いた {len(report['new'])} / 更新 {len(report['updated'])} / 変わらず {len(report['same'])}"
          f" / 手が入っていたので残した {len(report['kept'])} / 育つファイルなので触らず {len(report['seed_kept'])}")
    for k in report["updated"]:
        print(f"  更新: {short(k)}")
    for k in report["kept"]:
        print(f"  ★残した: {short(k)}  （新しい版は {short(k)}.new-{VERSION} に置いた。見比べて必要なら取り込む）")
    return report


if __name__ == "__main__":
    main("--dry-run" in sys.argv)
