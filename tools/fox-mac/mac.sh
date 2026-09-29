#!/bin/zsh
# パソコン側の設定（fox-kit のインストーラから呼ばれる。あとから fox-kit mac でもやり直せる）
#   mac.sh            … 質問に答えながら設定する
#   mac.sh status     … いまの設定を見る
# 先に答えを渡すと聞かない：FOX_MAC_USE=office|mobile  FOX_LID=yes|no  FOX_ANTIGRAVITY=yes|no
set -uo pipefail
HERE="${0:A:h}"
STATE="$HOME/.config/fox-kit/state.env"
B=1; grep -qs '^FOX_LEVEL=expert' "$STATE" && B=""
t() { if [[ -n "$B" ]]; then print -r -- "$1"; else print -r -- "$2"; fi; }
ok()   { printf '\033[32m  ✓ %s\033[0m\n' "$1"; }
warn() { printf '\033[33m  ! %s\033[0m\n' "$1"; }
has_tty() { { : > /dev/tty; } 2>/dev/null; }
choose() {  # choose 変数名 "質問" 既定 "1:ラベル" "2:ラベル"…
  local __v="$1" __q="$2" __d="$3"; shift 3
  [[ -n "${(P)__v:-}" ]] && return
  local __a=""
  if has_tty; then
    echo "  $__q"; for o in "$@"; do echo "    ${o%%:*}) ${o#*:}"; done
    printf '  番号（空欄なら %s）: ' "$__d" > /dev/tty; read -r __a < /dev/tty || true
  fi
  typeset -g "$__v"="${__a:-$__d}"
}
save() { mkdir -p "${STATE:h}"; { grep -v "^$1=" "$STATE" 2>/dev/null; print -r -- "$1=${(P)1}"; } > "$STATE.tmp" && mv "$STATE.tmp" "$STATE"; }
# 設定画面から動かすときは、sudo のパスワードを Mac のダイアログで聞く
[[ -n "${SUDO_ASKPASS:-}" ]] && sudo() { command sudo -A "$@"; }
is_laptop() { pmset -g batt 2>/dev/null | grep -q InternalBattery; }

status() {
  echo "パソコンの設定"
  echo "  使い方: $(grep -h '^FOX_MAC_USE=' "$STATE" 2>/dev/null | cut -d= -f2 || echo 未設定)"
  echo "  電源接続中のスリープ: $(pmset -g custom 2>/dev/null | awk '/AC Power/{f=1} f&&/ sleep /{print $2; exit}') 分（0＝眠らない）"
  echo "  ふた閉じで眠らない: $(pmset -g 2>/dev/null | grep -q 'SleepDisabled[[:space:]]*1' && echo はい || echo いいえ)"
  echo "  CapsLockで眠らない仕組み: $([[ -f /Library/LaunchDaemons/com.local.capslock-nosleep.plist ]] && echo 入っています || echo なし)"
  echo "  Antigravity: $([[ -d "/Applications/Antigravity IDE.app" ]] && echo 入っています || echo なし)"
}

# ------------------------------------------------------------------ Antigravity
antigravity() {
  local app="/Applications/Antigravity IDE.app"
  if [[ ! -d "$app" ]]; then
    echo "  $(t "Antigravity を取ってきます（数分かかります）…" "Antigravity IDE をダウンロード")"
    local arch="darwin-arm"; [[ "$(uname -m)" == x86_64 ]] && arch="darwin-x64"
    local page js url=""
    page="$(curl -fsSL --compressed --max-time 30 https://antigravity.google/download 2>/dev/null)"
    url="$(print -r -- "$page" | grep -oE "https://[^\"' ]+/$arch/Antigravity%20IDE\.dmg" | head -1)"
    if [[ -z "$url" ]]; then
      for js in $(print -r -- "$page" | grep -oE '[A-Za-z0-9_./-]+\.js' | sort -u | head -20); do
        [[ $js == http* ]] || js="https://antigravity.google/${js#/}"
        url="$(curl -fsSL --compressed --max-time 30 "$js" 2>/dev/null | grep -oE "https://[^\"' ]+/$arch/Antigravity%20IDE\.dmg" | head -1)"
        [[ -n "$url" ]] && break
      done
    fi
    if [[ -z "$url" ]]; then
      open "https://antigravity.google/download"
      warn "$(t "自動で取れなかったので、公式の画面を開きました。「Download for Mac」を押し、開いたファイルの中の Antigravity IDE をアプリケーションに入れてください" "URL 取得失敗。公式ページを開いたので手動で導入")"
      return
    fi
    local dmg="/tmp/antigravity-ide.dmg" vol
    curl -fsSL -o "$dmg" "$url" || { warn "ダウンロードに失敗しました"; return; }
    vol="$(hdiutil attach -nobrowse -noverify "$dmg" | grep -oE '/Volumes/.+$' | head -1)"
    local src="$(ls -d "$vol"/*.app | head -1)"
    cp -R "$src" /Applications/ 2>/dev/null || osascript -e "do shell script \"cp -R \" & quoted form of \"$src\" & \" /Applications/\" with administrator privileges" >/dev/null
    hdiutil detach "$vol" -quiet; rm -f "$dmg"
    [[ -d "$app" ]] || { warn "入れられませんでした"; return; }
    ok "$(t "Antigravity を入れました" "Antigravity IDE installed")"
  else
    ok "$(t "Antigravity はもう入っています" "Antigravity IDE: installed")"
  fi
  local cli="$app/Contents/Resources/app/bin/antigravity-ide"
  if [[ -x "$cli" ]]; then
    for ext in anthropic.claude-code ms-ceintl.vscode-language-pack-ja; do
      "$cli" --list-extensions 2>/dev/null | grep -qx "$ext" || "$cli" --install-extension "$ext" >/dev/null 2>&1 || true
    done
    # 画面を日本語に
    local argv="$HOME/.antigravity-ide/argv.json"; mkdir -p "${argv:h}"
    if [[ ! -f "$argv" ]]; then print -r -- '{ "locale": "ja" }' > "$argv"
    elif ! grep -q '"locale"' "$argv"; then /usr/bin/sed -i '' '1,/{/s/{/{\n\t"locale": "ja",/' "$argv"; fi
    ok "$(t "Antigravity の中で Claude Code を使えるようにし、画面を日本語にしました" "extensions: claude-code, language-pack-ja / locale=ja")"
  fi
}

[[ "${1:-}" == status ]] && { status; exit 0; }

echo
echo "  $(t "このMacの使い方に合わせて、眠る・眠らないの設定をします。" "電源・スリープ設定と Antigravity")"
choose FOX_MAC_USE "$(t "このMacはどう使いますか？" "用途")" 1 \
  "1:$(t "事務所などに置いて、AIにいつでも働いてもらう（おすすめ：Discord/Slackの返事も止まらない）" "据え置きの専用機")" \
  "2:$(t "持ち歩いて、自分が使うときだけ動けばよい" "持ち歩くノートPC")"
[[ "$FOX_MAC_USE" == 2 || "$FOX_MAC_USE" == mobile ]] && FOX_MAC_USE=mobile || FOX_MAC_USE=office
save FOX_MAC_USE

if [[ "$FOX_MAC_USE" == office ]]; then
  echo "  $(t "設定を変えるので、Macのパスワードを聞かれます。" "sudo pmset")"
  if sudo pmset -c sleep 0 disksleep 0 displaysleep 10 >/dev/null; then
    ok "$(t "電源につないでいる間は眠らないようにしました（画面だけ10分で消えます）" "pmset -c sleep 0 disksleep 0 displaysleep 10")"
  fi
  sudo pmset -a autorestart 1 >/dev/null 2>&1 && ok "$(t "停電のあと電気が戻ったら、自動で起動するようにしました" "pmset autorestart 1")"
  sudo pmset -a womp 1 >/dev/null 2>&1 && ok "$(t "ネットワーク越しに起こせるようにしました" "pmset womp 1")"
  if fdesetup status 2>/dev/null | grep -q "On"; then
    warn "$(t "このMacはディスクが暗号化（FileVault）されています。停電のあと自動では立ち上がりきらず、パスワードの入力で止まります。暗号化を解く「復旧キー」が手元に控えてあるか、必ず確かめてください（無くすとMacが開けなくなります）" "FileVault On：再起動後はログイン画面で止まる。復旧キーの控えを確認")"
  else
    warn "$(t "停電のあと自動でAIが動き出すには「自動ログイン」も必要です：システム設定 → ユーザとグループ →「自動ログイン」でこのユーザーを選んでください" "自動ログイン：システム設定 > ユーザとグループ")"
  fi
  if is_laptop; then
    choose FOX_LID "$(t "ふたを閉じたまま置いておきますか？" "ふた閉じで稼働")" 2 \
      "1:$(t "はい（ふたを閉じても眠らない。電源につないでおく）" "disablesleep 1")" "2:$(t "いいえ（ふたは開けておく）" "開けておく")"
    if [[ "$FOX_LID" == 1 || "$FOX_LID" == yes ]]; then
      sudo pmset -a disablesleep 1 >/dev/null && ok "$(t "ふたを閉じても眠らないようにしました（熱がこもらない場所に置いてください）" "pmset -a disablesleep 1")"
    fi
  fi
else
  choose FOX_CAPS "$(t "作業中だけ眠らない仕組みを入れますか？（CapsLockのランプが点いている間はふたを閉じても眠らない／Antigravity を開いている間は勝手に眠らない）" "capslock-nosleep を入れる")" 1 \
    "1:$(t "入れる（おすすめ）" "入れる")" "2:$(t "入れない" "入れない")"
  if [[ "$FOX_CAPS" == 1 && -x "$HOME/Tools/capslock-nosleep/install.sh" ]]; then
    echo "  $(t "Macのパスワードを聞かれます。" "sudo install.sh")"
    sudo "$HOME/Tools/capslock-nosleep/install.sh" >/dev/null && ok "$(t "入れました。CapsLock を押してランプを点けると、ふたを閉じても作業が止まりません" "capslock-nosleep installed")"
  fi
fi

choose FOX_ANTIGRAVITY "$(t "Antigravity（AIと画面で一緒に作業する編集ソフト。中で Claude Code も使えます）を入れますか？" "Antigravity IDE を入れる")" 1 \
  "1:$(t "入れる（おすすめ）" "入れる")" "2:$(t "入れない" "入れない")"
[[ "$FOX_ANTIGRAVITY" == 1 || "$FOX_ANTIGRAVITY" == yes ]] && antigravity
exit 0
