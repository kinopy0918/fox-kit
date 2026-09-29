#!/bin/zsh
# 組み立て（人格・作法・スキル・記憶・設定・話し方・会社の規則・毎朝の点検・fox-kit コマンド）
# get.sh と設定画面（wizard）の両方から呼ぶ。必要な値は環境変数で受け取る：
#   FOX_OWNER FOX_AGENT FOX_MACHINE FOX_ROLE FOX_LEVEL [FOX_VAULT FOX_PROFILE FOX_UPDATE]
set -uo pipefail
KIT_DIR="${KIT_DIR:-${0:A:h:h}}"
LOG="${LOG:-$HOME/Library/Logs/fox-install.log}"
B=""; [[ "${FOX_LEVEL:-beginner}" == beginner ]] && B=1
t() { if [[ -n "$B" ]]; then print -r -- "$1"; else print -r -- "$2"; fi; }
ok()   { printf '\033[32m  ✓ %s\033[0m\n' "$1"; }
warn() { printf '\033[33m  ! %s\033[0m\n' "$1"; }
die()  { printf '\033[31m  ✕ %s\033[0m\n' "$1"; exit 1; }
quiet() { if [[ -n "$B" ]]; then "$@" >> "$LOG" 2>&1; else "$@"; fi; }
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
quiet "$KIT_DIR/install.sh" --owner "$FOX_OWNER" --agent "$FOX_AGENT" \
  --machine-label "$FOX_MACHINE" --role "$FOX_ROLE" ${FOX_VAULT:+--vault-path "$FOX_VAULT"} \
  || die "$(t "組み立ての途中で止まりました" "install.sh が失敗しました（ログ: $LOG）")"

mkdir -p "$HOME/.claude/rules"
if [[ -n "$B" ]]; then
cat > "$HOME/.claude/rules/talk-style.md" <<'MD'
# 話し方（この方はAIやパソコンの設定に慣れていません）

- **専門用語を使わない。** ターミナル・コマンド・API・トークン・リポジトリ・JSON・ディレクトリ などは、ふだんの言葉に言い換える
  （例: ターミナル→「文字を打ち込む黒い画面」、フォルダの場所→「どこに保存したか」）。どうしても要る言葉は、初回に一言で説明する。
- お願いする操作は「どの画面で・どこを押すか」を1つずつ番号で書く。一度に頼むのは1つまで。
- 作業の中身（どのファイルをどう直したか）は書かず、「何ができるようになったか」だけを伝える。
- 困ったときの逃げ道を必ず添える（「わからなければ、このまま『わからない』と送ってください」）。
- 何段かに分かれる作業のときは、返事の最後に次の2行を付ける：
  **次にやること：** （あなたがすること、または私が次にすること）
  **いまの進み具合：** （全体のうち、どこまで終わったか。例：「5つのうち3つ目まで」）
MD
else
cat > "$HOME/.claude/rules/talk-style.md" <<'MD'
# 話し方（この方はAIやパソコンの設定に慣れています）

- 専門用語はそのまま使ってよい。コマンド・パス・設定名は正確に書く。
- 前置きを省き、結論→根拠→次の一手の順で短く。
- 何段かに分かれる作業のときは、最後に「次のタスク」と「全体の進み具合」を1行ずつ。
MD
fi
grep -qs "rules/talk-style.md" "$HOME/.claude/CLAUDE.md" || printf '\n@~/.claude/rules/talk-style.md\n' >> "$HOME/.claude/CLAUDE.md"

if [[ -n "${FOX_PROFILE:-}" ]]; then
  P="$TMP/profile"; mkdir -p "$P"
  if [[ -d "$FOX_PROFILE" ]]; then cp -R "$FOX_PROFILE/." "$P"
  else curl -fsSL "$FOX_PROFILE" | tar -xz -C "$P" --strip-components 1 || die "$(t "会社の決まりごとを取ってこられませんでした" "FOX_PROFILE を取得できません")"; fi
  for f in "$P"/rules/*.md(N); do
    cp "$f" "$HOME/.claude/rules/"
    name="$(basename "$f")"
    grep -qs "rules/$name" "$HOME/.claude/CLAUDE.md" || printf '\n@~/.claude/rules/%s\n' "$name" >> "$HOME/.claude/CLAUDE.md"
  done
fi
ok "$(t "組み立てました（仕事の作法・資料のチェック役・話し方の設定も入りました）" "install.sh 完了 / talk-style: $FOX_LEVEL${FOX_PROFILE:+ / profile 適用}")"
__kept="$(grep -h '★残した' "$LOG" 2>/dev/null | tail -20 || true)"
if [[ -n "$__kept" ]]; then
  warn "$(t "あなたが手を入れていたファイルは残しました（新しい版は横に「.new-版」で置いてあります）" "modified files kept (see *.new-<ver>)")"
  print -r -- "$__kept" | sed 's/^/    /'
fi
# 毎朝の点検（スキルの見張り・健康診断）を登録
[[ -f "$HOME/Tools/fox-guard/install.py" ]] && quiet /usr/bin/python3 "$HOME/Tools/fox-guard/install.py" ${FOX_UPDATE:+--no-reset}
# fox-kit コマンドを使えるようにする
mkdir -p "$HOME/.local/bin"
ln -sf "$HOME/Tools/fox-kit-cli/fox-kit" "$HOME/.local/bin/fox-kit"
exit 0
