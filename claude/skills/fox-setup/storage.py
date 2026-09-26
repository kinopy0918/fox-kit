#!/usr/bin/env python3
"""保存先を決めて組み立てる（fox-setup スキルから呼ぶ）。

  python3 storage.py detect
      このMacにあるクラウドの同期フォルダ（Googleドライブ・OneDrive・Dropbox・iCloud）を一覧で返す（JSON）
  python3 storage.py install-gdrive
      Google ドライブのパソコン用アプリ（Google Drive for desktop）を入れる。
      Macのパスワードを聞く画面が出る。入れた後のログインは人が行う。
  python3 storage.py apply --root "<親フォルダ>" --agent "<AIの名前>" [--layout fox|simple]
                           [--memory-in-root] [--auto-index] [--dry-run]
      <親フォルダ>/<AIの名前>/ にフォルダ構成を作り、目次を作り、保存と読み方の決まり
      （~/.claude/rules/storage.md）を書き、CLAUDE.md の保管先欄を差し替える。
        --layout fox     … 今のFOXと同じ番号つき11フォルダ（おすすめ）
        --layout simple  … 5フォルダだけの簡単な形
        --memory-in-root … AIの記憶をこのフォルダの中へ移す（Macが壊れても残る・人も見られる）
        --auto-index     … 作業が終わるたびに、中身が変わったフォルダの目次を自動で作り直す
  python3 storage.py index [--root "<AIのフォルダ>"] [--all]
      目次（各フォルダの _目次.md と、いちばん上の _全体の目次.md）を作り直す。
      既定では、目次より新しいファイルがあるフォルダだけ作り直す（速い）。
何度実行しても壊さない（既にあるフォルダ・ファイル・記憶はそのまま。目次の「## メモ」以下は残す）。
"""
import json, os, re, shutil, subprocess, sys, argparse, time, unicodedata
from pathlib import Path

HOME = Path.home()
CONF = HOME / ".config" / "fox-kit" / "storage.json"

LAYOUTS = {
    "fox": [
        ("00_仕組み", "このフォルダの使い方・目次の説明・全体の決まり"),
        ("01_案件", "案件・取引先ごとの資料。案件名のフォルダを作って入れる"),
        ("02_議事録", "会議・打ち合わせの記録（録音の文字起こしもここ）"),
        ("03_記録", "日報・作業ログ・自動処理の記録"),
        ("04_手順と自動化", "仕事の手順書、自動化の設定と説明（動かすプログラム本体は ~/Tools）"),
        ("05_テンプレート", "繰り返し使うひな形（見積・報告書・メール文など）"),
        ("06_タスク", "やることの一覧・進み具合"),
        ("07_メモ・調査", "調べもの・アイデア・単発の資料"),
        ("08_AIの記憶", "AIが覚えていること（人が見て直してもよい）"),
        ("09_目標", "年・四半期・月の目標と振り返り"),
        ("99_保管庫", "終わった案件・古い版（消さずにここへ）"),
    ],
    "simple": [
        ("01_案件", "案件・取引先ごとの資料。案件名のフォルダを作って入れる"),
        ("02_議事録・メモ", "会議の記録、打ち合わせのメモ、日々のメモ"),
        ("03_調査・資料", "調べもの・作った資料・報告書"),
        ("04_仕組み", "自動化の設定や手順書（動かすプログラム本体は ~/Tools）"),
        ("05_受け取った資料", "人からもらったファイルの置き場（原本はここ）"),
    ],
}
MEMORY_FOLDER = {"fox": "08_AIの記憶", "simple": "_AIの記憶"}
INDEX_NAME, TOP_INDEX = "_目次.md", "_全体の目次.md"
SKIP = {INDEX_NAME, TOP_INDEX, ".DS_Store", "Icon\r"}


def nfc(s):
    return unicodedata.normalize("NFC", s)


# ------------------------------------------------------------------ detect / install
def detect():
    found = []
    cs = HOME / "Library" / "CloudStorage"
    if cs.is_dir():
        for d in sorted(cs.iterdir()):
            if not d.is_dir():
                continue
            name = d.name
            if name.startswith("GoogleDrive-"):
                acct = name[len("GoogleDrive-"):]
                my = next((d / n for n in ("マイドライブ", "My Drive") if (d / n).is_dir()), d)
                found.append({"kind": "Googleドライブ（マイドライブ）", "account": acct, "path": str(my)})
                sh = next((d / n for n in ("共有ドライブ", "Shared drives") if (d / n).is_dir()), None)
                if sh:
                    for s in sorted(sh.iterdir()):
                        if s.is_dir():
                            found.append({"kind": "Googleドライブ（共有ドライブ）", "account": acct, "path": str(s)})
            elif name.startswith("OneDrive"):
                found.append({"kind": "OneDrive", "account": name.split("-", 1)[-1], "path": str(d)})
            elif name.startswith(("Dropbox", "Box")):
                found.append({"kind": name.split("-")[0], "account": name, "path": str(d)})
    icloud = HOME / "Library" / "Mobile Documents" / "com~apple~CloudDocs"
    if icloud.is_dir():
        found.append({"kind": "iCloud Drive", "account": "", "path": str(icloud)})
    found.append({"kind": "このMacの中だけ（バックアップなし）", "account": "", "path": str(HOME / "Documents")})
    gd_app = Path("/Applications/Google Drive.app").is_dir()
    print(json.dumps({"folders": found, "google_drive_app_installed": gd_app}, ensure_ascii=False, indent=2))


def install_gdrive():
    if Path("/Applications/Google Drive.app").is_dir():
        print("Google ドライブのアプリは入っています。開きます。")
        subprocess.run(["open", "-a", "Google Drive"])
        return
    dmg = Path("/tmp/GoogleDrive.dmg")
    print("Google ドライブのアプリを取ってきます…")
    subprocess.run(["curl", "-fsSL", "-o", str(dmg), "https://dl.google.com/drive-file-stream/GoogleDrive.dmg"], check=True)
    out = subprocess.run(["hdiutil", "attach", "-nobrowse", "-noverify", str(dmg)], capture_output=True, text=True, check=True).stdout
    vol = next((l.split("\t")[-1].strip() for l in out.splitlines() if "/Volumes/" in l), None)
    pkg = next(Path(vol).glob("*.pkg"))
    print("入れます（Macのパスワードを聞く画面が出ます）…")
    script = f'do shell script "installer -pkg " & quoted form of "{pkg}" & " -target /" with administrator privileges'
    r = subprocess.run(["osascript", "-e", script])
    subprocess.run(["hdiutil", "detach", vol, "-quiet"])
    if r.returncode != 0:
        sys.exit("インストールが取り消されたか、失敗しました。")
    subprocess.run(["open", "-a", "Google Drive"])
    print("入れました。開いた画面で、会社のGoogleアカウントでログインしてください。"
          "ログインが済むと、Finder の左側に「Google Drive」が出ます。")


# ------------------------------------------------------------------ index（目次）
def summary_of(p: Path) -> str:
    """ファイルの1行要約：frontmatter の summary/description → 最初の見出し → 最初の本文行。"""
    if p.suffix.lower() not in (".md", ".txt"):
        return ""
    try:
        with open(p, encoding="utf-8", errors="ignore") as f:
            head = f.read(2048)
    except OSError:
        return ""
    m = re.search(r"^(?:summary|description):\s*(.+)$", head, re.M)
    if m:
        return m.group(1).strip().strip('"')[:80]
    body = re.sub(r"\A---.*?---\s*", "", head, flags=re.S)
    for line in body.splitlines():
        line = line.strip().lstrip("#").strip()
        if line and not line.startswith(("<!--", "@", "|", "---")):
            return line[:80]
    return ""


def write_index(folder: Path, desc: str = ""):
    idx = folder / INDEX_NAME
    keep = ""
    if idx.exists():
        t = idx.read_text(encoding="utf-8", errors="ignore")
        if "\n## メモ" in t:
            keep = t[t.index("\n## メモ"):]
    subs, files = [], []
    for c in sorted(folder.iterdir(), key=lambda x: nfc(x.name)):
        if c.name in SKIP or c.name.startswith("."):
            continue
        (subs if c.is_dir() else files).append(c)
    lines = ["---", f"summary: {desc or folder.name + 'の目次'}", f"updated: {time.strftime('%Y-%m-%d')}",
             "生成: 目次は自動で作り直されます（手で書くときは「## メモ」の下に）", "---",
             f"# {folder.name}", ""]
    if desc:
        lines += [desc, ""]
    if subs:
        lines += [f"## フォルダ（{len(subs)}）", ""]
        for s in subs:
            sd = ""
            si = s / INDEX_NAME
            if si.exists():
                m = re.search(r"^summary:\s*(.+)$", si.read_text(encoding="utf-8", errors="ignore")[:1024], re.M)
                sd = m.group(1).strip() if m else ""
            lines.append(f"- `{s.name}/`" + (f" — {sd}" if sd else ""))
        lines.append("")
    if files:
        lines += [f"## ファイル（{len(files)}）", ""]
        for f in files:
            sm = summary_of(f)
            lines.append(f"- `{f.name}`" + (f" — {sm}" if sm else ""))
        lines.append("")
    if not subs and not files:
        lines += ["（まだ何もありません）", ""]
    idx.write_text("\n".join(lines) + (keep or "\n## メモ\n\n"), encoding="utf-8")


def newest_mtime(folder: Path) -> float:
    ts = [folder.stat().st_mtime]
    for c in folder.iterdir():
        if c.name not in SKIP:
            try:
                ts.append(c.stat().st_mtime)
            except OSError:
                pass
    return max(ts)


def index(base: Path, all_=False, descs=None):
    descs = descs or {}
    changed = 0
    # 深い方から作る（親の目次に子の要約を載せるため）
    folders = sorted([p for p in base.rglob("*") if p.is_dir() and not p.name.startswith(".")],
                     key=lambda p: -len(p.parts))
    mem_names = set(MEMORY_FOLDER.values())
    for d in folders:
        if d.is_symlink() or d.name in mem_names or any(x in mem_names for x in d.relative_to(base).parts):
            continue
        idx = d / INDEX_NAME
        if all_ or not idx.exists() or newest_mtime(d) > idx.stat().st_mtime + 1:
            write_index(d, descs.get(d.name, ""))
            changed += 1
    # いちばん上の全体目次
    top = base / TOP_INDEX
    lines = ["---", f"summary: {base.name} の全体の目次（AIはまずここを読む）", f"updated: {time.strftime('%Y-%m-%d')}", "---",
             f"# {base.name} の全体の目次", "",
             "**読み方**：このページで行き先を決める → そのフォルダの `_目次.md` を読む → 必要なファイルだけ開く。",
             "全部を開いて探さない。", ""]
    for c in sorted(base.iterdir(), key=lambda x: nfc(x.name)):
        if c.is_dir() and not c.name.startswith("."):
            ci = c / INDEX_NAME
            sd = ""
            if ci.exists():
                m = re.search(r"^summary:\s*(.+)$", ci.read_text(encoding="utf-8", errors="ignore")[:1024], re.M)
                sd = m.group(1).strip() if m else ""
            n = sum(1 for _ in c.rglob("*") if _.is_file() and _.name not in SKIP)
            lines.append(f"- `{c.name}/`（{n}件）" + (f" — {sd}" if sd else ""))
    top.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return changed


# ------------------------------------------------------------------ apply
def memory_dir():
    return HOME / ".claude" / "projects" / str(HOME).rstrip("/").replace("/", "-") / "memory"


def add_stop_hook(cmd: str):
    sp = HOME / ".claude" / "settings.json"
    s = json.loads(sp.read_text()) if sp.exists() else {}
    stops = s.setdefault("hooks", {}).setdefault("Stop", [])
    if any(cmd in h.get("command", "") for e in stops for h in e.get("hooks", [])):
        return False
    stops.append({"hooks": [{"type": "command", "command": cmd, "timeout": 30, "statusMessage": "目次を更新"}]})
    sp.write_text(json.dumps(s, ensure_ascii=False, indent=2) + "\n")
    return True


def apply(root: Path, agent: str, layout: str, memory_in_root: bool, auto_index: bool, dry: bool):
    if not root.is_dir():
        sys.exit(f"親フォルダが見つかりません: {root}")
    base = root / agent
    folders = LAYOUTS[layout]
    descs = dict(folders)
    local_only = str(root).startswith(str(HOME / "Documents"))
    print(f"保存先: {base}（{'FOXと同じ構成' if layout == 'fox' else '簡単な構成'}）")
    if dry:
        print("（dry-run：何も変えていません）"); return

    base.mkdir(parents=True, exist_ok=True)
    for name, _ in folders:
        (base / name).mkdir(exist_ok=True)
    guide = base / ("00_仕組み" if layout == "fox" else ".") / "このフォルダの使い方.md"
    if not guide.exists():
        g = [f"# {agent} の保存先の使い方", "",
             f"{agent}（AI秘書）が作ったもの・受け取ったものを、ここに整理して置きます。", "",
             "## フォルダ", ""] + [f"- **{n}** … {d}" for n, d in folders] + [
             "", "## 目次のしくみ", "",
             f"- いちばん上の `{TOP_INDEX}` と、各フォルダの `{INDEX_NAME}` は自動で作られます。",
             "- AIは目次から行き先を決めて、必要なファイルだけを読みます（全部を読みに行かないので速い）。",
             "- ファイルの1行目（見出し）が目次の説明になります。わかりやすい見出しを付けると、AIも人も探しやすくなります。",
             "- 目次に手で書き足したいときは、目次の中の「## メモ」の下に書いてください（そこは消えません）。", "",
             "デスクトップやダウンロードには置きません。"]
        guide.write_text("\n".join(g) + "\n", encoding="utf-8")

    # 記憶をこのフォルダへ
    mem = memory_dir()
    if memory_in_root:
        dest = base / MEMORY_FOLDER[layout]
        if mem.is_symlink():
            print(f"記憶は既に移してあります: {os.readlink(mem)}")
        else:
            dest.mkdir(parents=True, exist_ok=True)
            if mem.is_dir():
                for f in mem.iterdir():
                    if not (dest / f.name).exists():
                        shutil.move(str(f), str(dest / f.name))
                shutil.rmtree(mem)
            mem.parent.mkdir(parents=True, exist_ok=True)
            mem.symlink_to(dest, target_is_directory=True)
            print(f"記憶を移しました: {dest}")

    # 目次
    n = index(base, all_=True, descs=descs)
    print(f"目次を作りました: {n} フォルダ＋{TOP_INDEX}")

    # 設定の控え（index の既定の場所）
    CONF.parent.mkdir(parents=True, exist_ok=True)
    CONF.write_text(json.dumps({"base": str(base), "layout": layout, "agent": agent}, ensure_ascii=False, indent=2))

    # 作業が終わるたびに目次を更新
    here = Path(__file__).resolve()
    if auto_index and add_stop_hook(f"python3 '{here}' index >/dev/null 2>&1 || true"):
        print("作業が終わるたびに目次を更新する設定を入れました")

    # 保存と読み方の決まり
    rules = HOME / ".claude" / "rules" / "storage.md"
    body = [
        "# 保存と読み方の決まり（常に守る）", "",
        f"作ったもの・受け取ったものの**正本はすべて** `{base}` に置く。",
        "デスクトップ・ダウンロード・一時フォルダには置かない（置いたら、この場所へ移してから伝える）。", "",
        "## 探すとき（全部を読みに行かない）", "",
        f"1. まず `{base}/{TOP_INDEX}` を読んで、行き先のフォルダを決める",
        f"2. そのフォルダの `{INDEX_NAME}` を読み、1行の説明から目当てのファイルを選ぶ",
        "3. 選んだファイルだけ開く。見つからないときだけ、ファイル名で検索する（`mdfind -onlyin` や `grep -rl`）", "",
        "## 置くとき", "", "| 何を | どこへ |", "|---|---|"]
    body += [f"| {d} | `{n}/` |" for n, d in folders]
    body += [
        "| 動かし続けるプログラム本体 | `~/Tools/` |",
        "| パスワード・鍵・トークン | Macのキーチェーン（ファイルに書かない） |", "",
        "- 新しく作る文書には、1行目に内容がわかる見出しを付ける（目次の説明になる）。",
        f"- ファイルを置いたら目次を更新する：`python3 {here} index`" + ("（作業の終わりに自動でも更新される）" if auto_index else ""),
        "- 場所を移したら、記憶やスクリプトに書いた場所も一緒に直す。",
        "- 個人情報（マイナンバー・口座・健康情報・住所）はこの保存先の外へ出さない。"]
    if memory_in_root:
        body += [f"- AIの記憶は `{MEMORY_FOLDER[layout]}/` にある（元の場所からも同じ中身が見える）。"]
    if local_only:
        body += ["", "**注意：この保存先はこのMacの中だけ。** Macが壊れると消える。クラウドの同期フォルダを使えるようになったら移すよう持ち主に勧める。"]
    rules.parent.mkdir(parents=True, exist_ok=True)
    rules.write_text("\n".join(body) + "\n", encoding="utf-8")

    cm = HOME / ".claude" / "CLAUDE.md"
    if cm.exists():
        text = cm.read_text(encoding="utf-8")
        text = re.sub(r"^- ノート / 議事録 / 調査・資料・成果物 … .*$",
                      f"- ノート / 議事録 / 調査・資料・成果物 … `{base}`（探し方・置き方は rules/storage.md）", text, flags=re.M)
        if "@~/.claude/rules/storage.md" not in text:
            text += "\n@~/.claude/rules/storage.md\n"
        cm.write_text(text, encoding="utf-8")
    print("完了")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("detect")
    sub.add_parser("install-gdrive")
    a = sub.add_parser("apply")
    a.add_argument("--root", required=True)
    a.add_argument("--agent", required=True)
    a.add_argument("--layout", choices=["fox", "simple"], default="fox")
    a.add_argument("--memory-in-root", action="store_true")
    a.add_argument("--auto-index", action="store_true")
    a.add_argument("--dry-run", action="store_true")
    i = sub.add_parser("index")
    i.add_argument("--root")
    i.add_argument("--all", action="store_true")
    args = ap.parse_args()
    if args.cmd == "detect":
        detect()
    elif args.cmd == "install-gdrive":
        install_gdrive()
    elif args.cmd == "apply":
        apply(Path(os.path.expanduser(args.root)), args.agent, args.layout, args.memory_in_root, args.auto_index, args.dry_run)
    else:
        if args.root:
            base = Path(os.path.expanduser(args.root))
        elif CONF.exists():
            base = Path(json.loads(CONF.read_text())["base"])
        else:
            sys.exit("保存先がまだ決まっていません（apply を先に）")
        if base.is_dir():
            descs = dict(LAYOUTS.get(json.loads(CONF.read_text()).get("layout", "fox"), [])) if CONF.exists() else {}
            print(f"目次を更新: {index(base, all_=args.all, descs=descs)} フォルダ")
