#!/bin/zsh
# 長寿命トークンを、この端末の常駐ジョブ全部に配る。
#
#   ~/Tools/claude-token/apply.sh            この端末のlaunchdジョブに入れる
#   ~/Tools/claude-token/apply.sh --dry      何が変わるかだけ出す
#
# ★なぜ要るか
#   claude のサブスク認証は定期的に切れる。切れると `claude -p` を使う常駐が
#   黙って止まる（Mac miniでは21本が該当）。気づくのは「朝の配信が来ない」時。
#   `claude setup-token` で発行した長寿命トークンを渡しておけば、これが起きない。
#
# ★トークンの置き場所（全端末で同じ）
#   ~/.config/claude/token   （600）
#   環境変数は CLAUDE_CODE_OAUTH_TOKEN。
set -e
TOKEN_FILE="$HOME/.config/claude/token"
DRY=0
[[ "$1" == "--dry" ]] && DRY=1

if [[ ! -s "$TOKEN_FILE" ]]; then
  echo "トークンがありません: $TOKEN_FILE"
  echo "  claude setup-token を実行し、出てきた sk-ant-oat... を保存してください:"
  echo "    mkdir -p ~/.config/claude"
  echo "    printf '%s' 'トークン' > ~/.config/claude/token && chmod 600 ~/.config/claude/token"
  exit 1
fi
# ★貼り付けのときに前後へ空白や改行が混じることがある。必ず削ってから使う。
TOKEN=$(tr -d " \t\r\n" < "$TOKEN_FILE")
case "$TOKEN" in
  sk-ant-oat*) ;;
  *) echo "トークンの形が違います（sk-ant-oat… で始まるはず）。中身を確認してください"; exit 1;;
esac

# 1) 対話シェル用。新しいターミナルから claude が素で使える
if ! grep -q "CLAUDE_CODE_OAUTH_TOKEN" "$HOME/.zshrc" 2>/dev/null; then
  if (( DRY )); then
    echo "[dry] ~/.zshrc に読み込み行を足す"
  else
    cat >> "$HOME/.zshrc" <<'SH'

# claude の長寿命トークン（~/Tools/claude-token/apply.sh が入れた）
[ -r "$HOME/.config/claude/token" ] && \
  export CLAUDE_CODE_OAUTH_TOKEN="$(cat "$HOME/.config/claude/token")"
SH
    echo "~/.zshrc に読み込み行を足しました"
  fi
else
  echo "~/.zshrc は設定済み"
fi

# 2) launchd のジョブ。GUIセッションの環境変数は継がないので1本ずつ入れる
n=0
for p in "$HOME"/Library/LaunchAgents/*.plist; do
  [[ -e "$p" ]] || continue
  # claude を呼ぶジョブだけが対象。呼び出し先のスクリプトまでは追わず、
  # plist 内に claude の文字があるものを拾う。plist に claude の字が出ない
  # 常駐（ラッパー経由など）がある現場では、そのラベルの一部を
  # CLAUDE_TOKEN_EXTRA_MATCH に grep のパターンとして足す（例: "mybot\|foo-"）
  MATCH="claude${CLAUDE_TOKEN_EXTRA_MATCH:+\\|$CLAUDE_TOKEN_EXTRA_MATCH}"
  if ! grep -qi "$MATCH" "$p" 2>/dev/null; then continue; fi
  if /usr/libexec/PlistBuddy -c "Print :EnvironmentVariables:CLAUDE_CODE_OAUTH_TOKEN" "$p" >/dev/null 2>&1; then
    continue                      # すでに入っている
  fi
  label=$(/usr/libexec/PlistBuddy -c "Print :Label" "$p" 2>/dev/null || basename "$p")
  if (( DRY )); then
    echo "[dry] $label"
  else
    /usr/libexec/PlistBuddy -c "Add :EnvironmentVariables dict" "$p" >/dev/null 2>&1 || true
    /usr/libexec/PlistBuddy -c "Add :EnvironmentVariables:CLAUDE_CODE_OAUTH_TOKEN string $TOKEN" "$p"
    echo "入れました: $label"
  fi
  n=$((n+1))
done
echo "対象 $n 本"
(( DRY )) && exit 0

# 3) 入れたぶんを読み直させる
for p in "$HOME"/Library/LaunchAgents/*.plist; do
  [[ -e "$p" ]] || continue
  /usr/libexec/PlistBuddy -c "Print :EnvironmentVariables:CLAUDE_CODE_OAUTH_TOKEN" "$p" >/dev/null 2>&1 || continue
  label=$(/usr/libexec/PlistBuddy -c "Print :Label" "$p" 2>/dev/null) || continue
  launchctl kickstart -k "gui/$(id -u)/$label" >/dev/null 2>&1 || true
done
echo "常駐を読み直しました"
