#!/usr/bin/env python3
"""Windows 用の組み立て（get.ps1 から呼ぶ）。Mac の install.sh＋setup/build.sh と同じものを置く。

  python setup/build_win.py      環境変数 FOX_OWNER FOX_AGENT FOX_MACHINE FOX_ROLE FOX_LEVEL [FOX_UPDATE] を読む

置くもの: ~/.claude/CLAUDE.md（人格）・settings.json（足し合わせ）・作法/スキル/チェック役/ガード（kit_sync）
         ・記憶の索引・話し方。Mac 専用のもの（常駐・キーチェーン・~/Tools の道具）は置かない。
"""
import json, os, re, shutil, subprocess, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
HOME = Path.home()
CLAUDE = HOME / ".claude"
env = os.environ.get
OWNER, AGENT = env("FOX_OWNER", ""), env("FOX_AGENT", "FOX")
MACHINE, ROLE = env("FOX_MACHINE", os.environ.get("COMPUTERNAME", "このパソコン")), env("FOX_ROLE", "作業機")
BEGINNER = env("FOX_LEVEL", "beginner") == "beginner"
if not OWNER:
    sys.exit("FOX_OWNER がありません")
HOME_POSIX = HOME.as_posix()                       # C:/Users/xxx（Git Bash でもそのまま通る）


def slug(path: str) -> str:
    """Claude Code が記憶のフォルダ名に使う形（英数字以外は - ）。C:\\Users\\yamada → C--Users-yamada"""
    return re.sub(r"[^A-Za-z0-9]", "-", path)


# 1. 人格
mem_rel = f"~/.claude/projects/{slug(str(HOME))}/memory/"
text = (HERE / "claude" / "CLAUDE.md.template").read_text(encoding="utf-8")
for k, v in {"{{AGENT_NAME}}": AGENT, "{{OWNER_NAME}}": OWNER, "{{OWNER_LABEL}}": OWNER, "{{MACHINE_LABEL}}": MACHINE,
             "{{MACHINE_ROLE}}": ROLE, "{{DEV_DIR}}": "~/dev", "{{VAULT_PATH}}": "（未設定。使うなら書く）",
             "{{GITHUB_ORG}}": "（未設定）", "{{MEMORY_PATH}}": mem_rel}.items():
    text = text.replace(k, v)
NEW_WIN = ("- Mac の設定（pmset など）・キーチェーン・Homebrew の道具（動画を見る・画像づくり・意味で探す・ブラウザ操作の playwright）は、この端末には入っていない。\n"
           "- Discord/Slack とつなぐのは設定画面か設定係の窓から（skill-triggers の 27）。鍵は資格情報マネージャー、常駐はタスク スケジューラ。\n"
           "- キットの道具は `~/Tools` ではなく `~/Tools/fox-kit/tools/` にある。\n")
text += ("\n## この端末は Windows\n\n"
         "- コマンドは Git Bash（Bash ツール）か PowerShell で動く。パスは `C:/Users/...` の形で書けば両方で通る。\n"
         "- フォルダやファイルを見せるときは `explorer` で開く（`open` は無い）。\n" + NEW_WIN)
cm = CLAUDE / "CLAUDE.md"
CLAUDE.mkdir(parents=True, exist_ok=True)
OLD_WIN = "- Discord/Slack との常駐連携・Mac の設定・キーチェーンは、この端末には入っていない。\n"
if cm.exists() and OLD_WIN in cm.read_text(encoding="utf-8"):   # 0.5.0 より前にキットが書いた1行だけ新しくする（持ち主の文は触らない）
    cm.write_text(cm.read_text(encoding="utf-8").replace(OLD_WIN, NEW_WIN), encoding="utf-8")
    print("  人格の Windows の注意書きを新しくしました")
NOTICES = HOME / ".config" / "fox-kit" / "notices.txt"       # 前からあった設定をどう扱ったか（設定画面の完了画面に出す）
NOTICES.parent.mkdir(parents=True, exist_ok=True)
BACKUP = HOME / ".config-backup" / time.strftime("%Y%m%d-%H%M%S")
if cm.exists() and "fox-kit/rules/craft.md" in cm.read_text(encoding="utf-8"):
    print("  すでにこのキットの人格が入っています。育てた中身はそのままにします")
elif cm.exists():
    # キットを入れる前から自分で書いていた人：控えを取り、新しい人格の後ろに前の中身をそのまま残す（何も消さない）
    BACKUP.mkdir(parents=True, exist_ok=True)
    shutil.copy2(cm, BACKUP / cm.name)
    old = cm.read_text(encoding="utf-8")
    cm.write_text(text + "\n\n## 前から書いてあった決まり（このキットを入れる前の CLAUDE.md。そのまま残してあります）\n\n" + old, encoding="utf-8")
    msg = f"前から使っていたAIへの決まり（CLAUDE.md）は、新しい秘書の決まりの後ろにそのまま残しました。入れる前の控え：{BACKUP}"
    print("  ! " + msg)
    with open(NOTICES, "a", encoding="utf-8") as f:
        f.write(msg + "\n")
else:
    cm.write_text(text, encoding="utf-8")
    print("  人格を書きました: ~/.claude/CLAUDE.md")

# 2. 設定（足し合わせ）。フックはフルパス、Bash と PowerShell の両方に効かせる
new = json.loads((HERE / "claude" / "settings.json").read_text(encoding="utf-8"))
for ev, entries in (new.get("hooks") or {}).items():
    for e in entries:
        if e.get("matcher") == "Bash":
            e["matcher"] = "Bash|PowerShell"
        for h in e.get("hooks", []):
            # ~ をフルパスにし、名前に空白があっても通るように引用符で囲む
            h["command"] = re.sub(r"~/(\.claude/\S+)", lambda m: f'"{HOME_POSIX}/{m.group(1)}"', h["command"])
            # python3 という呼び名に頼らず、組み立てに使った Python の実体を直接指す（ストアの入口に当たって黙って効かなくなるのを防ぐ）
            h["command"] = re.sub(r"^python3 ", lambda m: f'"{Path(sys.executable).as_posix()}" ', h["command"])
new["permissions"]["allow"] = [a for a in new["permissions"]["allow"] if not a.startswith(("Bash(osascript", "Bash(open"))]
new.setdefault("env", {})["PYTHONUTF8"] = "1"
# 記憶の置き場所を1か所に固定する：どのフォルダで開いても同じ記憶を読む
new["autoMemoryDirectory"] = f"~/.claude/projects/{slug(str(HOME))}/memory"
sys.path.insert(0, str(HERE / "setup"))
import settings_merge  # noqa: E402  Mac と同じ合流（持ち主が決めていた値は残す・読めなければ触らない・変えるときだけ控え）
settings_merge.merge(new, str(CLAUDE / "settings.json"), str(NOTICES), str(BACKUP))

# 3. 作法・スキル・チェック役・ガード
subprocess.run([sys.executable, str(HERE / "kit_sync.py")], check=True)
for name in ("craft.md", "skill-triggers.md"):
    t = cm.read_text(encoding="utf-8")
    if f"fox-kit/rules/{name}" not in t:
        cm.write_text(t + f"\n@~/.claude/fox-kit/rules/{name}\n", encoding="utf-8")

# 4. 記憶の索引
md = HOME / ".claude" / "projects" / slug(str(HOME)) / "memory"
if not (md / "MEMORY.md").exists():
    md.mkdir(parents=True, exist_ok=True)
    (md / "MEMORY.md").write_text((HERE / "memory" / "MEMORY.md.template").read_text(encoding="utf-8")
                                  .replace("{{AGENT_NAME}}", AGENT), encoding="utf-8")
    print(f"  記憶の場所を作りました: {md}")

# 5. 話し方（Mac の build.sh と同じ文面）
build_sh = (HERE / "setup" / "build.sh").read_text(encoding="utf-8")
blocks = re.findall(r"<<'MD'\n(.*?)\nMD\n", build_sh, re.S)
rules = CLAUDE / "rules"
rules.mkdir(parents=True, exist_ok=True)
(rules / "talk-style.md").write_text((blocks[0] if BEGINNER else blocks[1]) + "\n", encoding="utf-8")
t = cm.read_text(encoding="utf-8")
if "rules/talk-style.md" not in t:
    cm.write_text(t + "\n@~/.claude/rules/talk-style.md\n", encoding="utf-8")
print("  組み立てました（仕事の作法・資料のチェック役・話し方）")
