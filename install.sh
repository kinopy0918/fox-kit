#!/bin/zsh
# 汎用型FOXを、この端末に組み立てる。
#
#   ./install.sh --agent FOX --owner "<持ち主の名前>さん" --machine-label "新しいMac" \
#                 --role "個人の作業機" [--dry-run]
#
# 何をするか（すべて既存ファイルを壊さない。バックアップしてから重ねる）:
#   1. CLAUDE.md.template を埋めて ~/.claude/CLAUDE.md へ（前から自分で書いていた人は、控えを取って後ろにそのまま残す）
#   2. settings.json を ~/.claude/settings.json へマージ（同じ項目は持ち主の値を残す。allow と hooks は足し合わせ）
#   3. 出力先ガードのフックを ~/.claude/hooks/ へ
#   4. 記憶の索引スケルトンを ~/.claude/projects/<場所>/memory/ へ
#   5. 汎用ツール（tools/ 配下）を ~/Tools/ へコピー
#
# やらないこと（各端末で個別に必要な作業。docs/BOOTSTRAP_育て方.md 参照）:
#   - ログイン（claude /login）
#   - 長寿命トークンの発行（claude setup-token）
#   - CLAUDE.md の個別ルール追記（会社名・保存先・スキル索引の中身）
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
DRY=0

AGENT_NAME="FOX"
OWNER_NAME=""
MACHINE_LABEL="$(hostname -s 2>/dev/null || hostname)"
MACHINE_ROLE="個人の作業機"
DEV_DIR="\$HOME/dev"
VAULT_PATH="（未設定。使うなら書く）"
GITHUB_ORG="（未設定）"
MEMORY_HOME="$HOME"     # この場所を基準に ~/.claude/projects/<slug>/memory/ を作る
SKIP_TOOLS=0

say()  { printf '\033[1;36m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[!]\033[0m %s\n' "$*"; }
run()  { if [[ $DRY == 1 ]]; then printf '    (dry-run) %s\n' "$*"; else eval "$@"; fi; }

while [[ $# -gt 0 ]]; do
  case "$1" in
    --agent) AGENT_NAME="$2"; shift 2 ;;
    --owner) OWNER_NAME="$2"; shift 2 ;;
    --machine-label) MACHINE_LABEL="$2"; shift 2 ;;
    --role) MACHINE_ROLE="$2"; shift 2 ;;
    --dev-dir) DEV_DIR="$2"; shift 2 ;;
    --vault-path) VAULT_PATH="$2"; shift 2 ;;
    --github-org) GITHUB_ORG="$2"; shift 2 ;;
    --memory-home) MEMORY_HOME="$2"; shift 2 ;;
    --skip-tools) SKIP_TOOLS=1; shift ;;
    --dry-run) DRY=1; shift ;;
    *) warn "不明な引数: $1"; shift ;;
  esac
done

if [[ -z "$OWNER_NAME" ]]; then
  echo "★ --owner が必須です（例: --owner \"山田太郎さん\"）"
  exit 1
fi

STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP="$HOME/.config-backup-$STAMP"
# 持ち主に伝えること（前からあった設定をどう扱ったか）。組み立ての最後と設定画面の完了画面に出す
NOTICES="$HOME/.config/fox-kit/notices.txt"
[[ $DRY == 1 ]] || mkdir -p "${NOTICES:h}"   # 知らせが出るのは最初に足したときだけなので、消さずに残す（完了画面でいつでも読める）
notice() { warn "$1"; [[ $DRY == 1 ]] || print -r -- "$1" >> "$NOTICES"; }

backup_of() {
  local f="$1"
  [[ -e "$f" ]] || return 0
  local dest="$BACKUP/$(basename "$f").$(echo "$f" | md5 -q | cut -c1-6)"
  run "mkdir -p '$BACKUP'"
  run "cp '$f' '$dest'"
  warn "既存ファイルを退避: $f -> $dest"
}

# ---------------------------------------------------------------- 1. CLAUDE.md
say "人格宣言 (~/.claude/CLAUDE.md)"
RENDERED="$(mktemp -t fox-claude-md)"
python3 - "$HERE/claude/CLAUDE.md.template" "$RENDERED" \
  "$AGENT_NAME" "$OWNER_NAME" "$MACHINE_LABEL" "$MACHINE_ROLE" \
  "$DEV_DIR" "$VAULT_PATH" "$GITHUB_ORG" "$MEMORY_HOME" <<'PY'
import sys
tpl, out, agent, owner, mlabel, mrole, devdir, vault, ghorg, memhome = sys.argv[1:]
slug = memhome.rstrip("/").replace("/", "-")
import re; slug = re.sub(r"[^A-Za-z0-9-]", "-", slug)   # Claude Code と同じ形（英数字以外は - ）
memory_path = f"~/.claude/projects/{slug}/memory/"
text = open(tpl, encoding="utf-8").read()
repl = {
    "{{AGENT_NAME}}": agent,
    "{{OWNER_NAME}}": owner,
    "{{OWNER_LABEL}}": owner,
    "{{MACHINE_LABEL}}": mlabel,
    "{{MACHINE_ROLE}}": mrole,
    "{{DEV_DIR}}": devdir,
    "{{VAULT_PATH}}": vault,
    "{{GITHUB_ORG}}": ghorg,
    "{{MEMORY_PATH}}": memory_path,
}
for k, v in repl.items():
    text = text.replace(k, v)
open(out, "w", encoding="utf-8").write(text)
print(f"  下書き: {out}")
print(f"  記憶の場所: {memory_path}")
PY

if [[ -f "$HOME/.claude/CLAUDE.md" ]] && grep -q "fox-kit/rules/craft.md" "$HOME/.claude/CLAUDE.md"; then
  echo "  すでにこのキットの人格が入っています。育てた中身はそのままにします: ~/.claude/CLAUDE.md"
elif [[ -f "$HOME/.claude/CLAUDE.md" ]]; then
  # キットを入れる前から自分で書いていた人：控えを取り、新しい人格の後ろに前の中身をそのまま残す（何も消さない）
  backup_of "$HOME/.claude/CLAUDE.md"
  if [[ $DRY == 0 ]]; then
    { cat "$RENDERED"; printf '\n\n## 前から書いてあった決まり（このキットを入れる前の CLAUDE.md。そのまま残してあります）\n\n'; cat "$HOME/.claude/CLAUDE.md"; } > "$RENDERED.merged"
    mv "$RENDERED.merged" "$HOME/.claude/CLAUDE.md"
    notice "前から使っていたAIへの決まり（CLAUDE.md）は、新しい秘書の決まりの後ろにそのまま残しました。入れる前の控え：$BACKUP"
  fi
else
  run "mkdir -p '$HOME/.claude'"
  run "cp '$RENDERED' '$HOME/.claude/CLAUDE.md'"
  echo "  書きました: ~/.claude/CLAUDE.md"
fi
rm -f "$RENDERED"

# ---------------------------------------------------------------- 2. settings.json
say "Claude Code のグローバル設定 (~/.claude/settings.json)"
if [[ $DRY == 1 ]]; then
  echo "    (dry-run) merge $HERE/claude/settings.json -> ~/.claude/settings.json"
else
  mkdir -p "$HOME/.claude"
  python3 "$HERE/setup/settings_merge.py" "$HERE/claude/settings.json" "$HOME/.claude/settings.json" "$NOTICES" "$BACKUP"
fi

# ---------------------------------------------------------------- 3. キットのファイル（作法・スキル・チェック役・ガード・道具）
say "キットのファイルを置く（手を入れたものは上書きしない）"
if [[ $DRY == 1 ]]; then python3 "$HERE/kit_sync.py" --dry-run; else python3 "$HERE/kit_sync.py"; fi
# 既存の CLAUDE.md（上書きしなかった場合）にも作法の読み込みだけは足す
if [[ $DRY == 0 && -f "$HOME/.claude/CLAUDE.md" ]] && ! grep -q "fox-kit/rules/craft.md" "$HOME/.claude/CLAUDE.md"; then
  printf '\n## 常に守る作法\n\n@~/.claude/fox-kit/rules/craft.md\n' >> "$HOME/.claude/CLAUDE.md"
  echo "  既存の CLAUDE.md に作法の読み込みを追加しました"
fi
if [[ $DRY == 0 && -f "$HOME/.claude/CLAUDE.md" ]] && ! grep -q "fox-kit/rules/skill-triggers.md" "$HOME/.claude/CLAUDE.md"; then
  printf '\n@~/.claude/fox-kit/rules/skill-triggers.md\n' >> "$HOME/.claude/CLAUDE.md"
fi

# ---------------------------------------------------------------- 4. memory
say "記憶の索引スケルトン"
slug=$(python3 -c "import re,sys; print(re.sub(r'[^A-Za-z0-9-]', '-', sys.argv[1].rstrip('/')))" "$MEMORY_HOME")
MEMDIR="$HOME/.claude/projects/$slug/memory"
if [[ -f "$MEMDIR/MEMORY.md" ]]; then
  warn "既に記憶があります。上書きしません: $MEMDIR/MEMORY.md"
elif [[ $DRY == 1 ]]; then
  echo "    (dry-run) mkdir -p '$MEMDIR' && 書く: $MEMDIR/MEMORY.md"
else
  mkdir -p "$MEMDIR"
  python3 - "$HERE/memory/MEMORY.md.template" "$MEMDIR/MEMORY.md" "$AGENT_NAME" <<'PY'
import sys
tpl, out, agent = sys.argv[1:]
text = open(tpl, encoding="utf-8").read().replace("{{AGENT_NAME}}", agent)
open(out, "w", encoding="utf-8").write(text)
PY
  echo "  作成: $MEMDIR/MEMORY.md"
fi

echo
say "完了。次は docs/BOOTSTRAP_育て方.md の手作業を進めてください（ログイン・トークン発行など）。"
say "動作確認: cd ~ && claude -p '自己紹介して' --output-format text  （cd ~ を省かない）"
