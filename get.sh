#!/bin/zsh
# fox-kit（AI秘書セットアップ）── 1行インストーラ
#
#   /bin/zsh -c "$(curl -fsSL https://kinopy0918.github.io/fox-kit/get.sh)"
#
# これ1本で: AI本体（Claude Code）→ キット → 組み立て（人格・作法・スキル・記憶・設定）
#            → ログイン → あいさつ → 初期設定の聞き取り まで進む。
# 途中で止まっても、同じ1行をもう一度貼れば「続きから」始まる（答えと進み具合を覚えている）。
#
# 聞かずに進めたいときは環境変数で先に渡す（会社で同じ設定を配るとき）:
#   FOX_LEVEL=beginner|expert  FOX_OWNER="山田さん"  FOX_AGENT="ヤマダAI"
#   FOX_MACHINE="事務所のMac"  FOX_ROLE="経理の自動化"
# 追加（任意）:
#   FOX_PROFILE=<URL か フォルダ>  会社ごとの規則（rules/*.md）を足す
#   FOX_REMOTE=1 / FOX_SSH_KEY="ssh-ed25519 …"  遠隔で面倒を見るための Tailscale＋SSH
#   FOX_DEDICATED=1                専用機として、電源接続中はスリープしない
#   FOX_RESET=1                    覚えている答えと進み具合を消して、最初からやり直す
#   FOX_VERSION=0.1.0              この版を入れる（既定は最新の公開版）
#   FOX_UPDATE=1                   更新として動く（fox-kit update から。手を入れたファイルは上書きしない）
# 検証用: FOX_KIT_URL=<URL か フォルダ> / FOX_SKIP_CLAUDE=1 / FOX_SKIP_LOGIN=1 / FOX_NO_INTERVIEW=1
set -euo pipefail

REPO="kinopy0918/fox-kit"
if [[ -n "${FOX_KIT_URL:-}" ]]; then
  KIT_URL="$FOX_KIT_URL"
else
  # 既定は最新の公開版（リリース）。まだ1つも無ければ main
  __ver="${FOX_VERSION:-$(curl -fsSL --max-time 10 "https://api.github.com/repos/$REPO/releases/latest" 2>/dev/null \
    | /usr/bin/sed -n 's/.*"tag_name": *"v\{0,1\}\([^"]*\)".*/\1/p' | head -1)}"
  if [[ -n "$__ver" ]]; then KIT_URL="https://github.com/$REPO/archive/refs/tags/v$__ver.tar.gz"
  else KIT_URL="https://github.com/$REPO/archive/refs/heads/main.tar.gz"; fi
fi
KIT_DIR="$HOME/Tools/portable-fox"
STATE="$HOME/.config/fox-kit/state.env"
LOG="$HOME/Library/Logs/fox-install.log"
mkdir -p "${STATE:h}" "${LOG:h}"
TOTAL=7

# ------------------------------------------------------------------ 表示の道具
c()    { printf '\033[%sm%s\033[0m' "$1" "$2"; }
step() { echo; c "1;36" "━━ $1/$TOTAL  $2"; echo; }
ok()   { c "32" "  ✓ $1"; echo; }
warn() { c "33" "  ! $1"; echo; }
B=""   # 初心者なら 1
t() { if [[ -n "$B" ]]; then print -r -- "$1"; else print -r -- "$2"; fi; }
die()  { echo; c "31" "  ✕ $1"; echo; echo "  $(t "もう一度、同じ1行を貼り付けると続きから始まります。" "再実行で続きから再開します。")"; exit 1; }
has_tty() { { : > /dev/tty; } 2>/dev/null; }
quiet() { if [[ -n "$B" ]]; then "$@" >> "$LOG" 2>&1; else "$@"; fi; }

# ------------------------------------------------------------------ 覚えておく（続きから再開）
save() {  # save 変数名… — 答えと進み具合を覚える
  local v; for v in "$@"; do
    { grep -v "^$v=" "$STATE" 2>/dev/null || true; print -r -- "$v=${(q)${(P)v}}"; } > "$STATE.tmp"
    mv "$STATE.tmp" "$STATE"
  done; chmod 600 "$STATE"
}
mark()  { typeset -g "DONE_$1=1"; save "DONE_$1"; }
done_() { local v="DONE_$1"; [[ -n "${(P)v:-}" ]]; }
[[ -n "${FOX_RESET:-}" ]] && rm -f "$STATE"
RESUMED=""
if [[ -s "$STATE" ]]; then
  # 環境変数で渡された値を優先し、無いものだけ前回の答えで埋める
  for __line in "${(@f)$(<"$STATE")}"; do
    __k="${__line%%=*}"
    [[ "$__k" == (FOX_*|DONE_*) ]] || continue
    [[ -z "${(P)__k:-}" ]] && eval "$__line"
  done
  RESUMED=1
fi

# ------------------------------------------------------------------ 入力を確かめる
valid_name() {  # 空でない・30文字以内・壊れる記号なし
  local v="$1"
  [[ -n "$v" ]] || { echo "空欄はできません"; return 1; }
  (( ${#v} <= 30 )) || { echo "30文字以内にしてください（いま${#v}文字）"; return 1; }
  [[ "$v" != *[\"\$\`\\\|]* ]] || { echo "記号（\" \$ \` \\ |）は使えません"; return 1; }
}
ask() {  # ask 変数名 "質問" "既定値" — 答えを確かめ、だめなら3回まで聞き直す
  local __v="$1" __q="$2" __d="${3:-}" __a="" __err="" __i
  if [[ -n "${(P)__v:-}" ]]; then
    __err="$(valid_name "${(P)__v}")" || die "「$__q」の値が使えません: $__err"
    save "$__v"; return
  fi
  for __i in 1 2 3; do
    __a=""
    if has_tty; then
      printf '  %s%s: ' "$__q" "${__d:+（空欄なら「$__d」）}" > /dev/tty
      read -r __a < /dev/tty || true
    fi
    __a="${__a:-$__d}"
    if __err="$(valid_name "$__a")"; then typeset -g "$__v"="$__a"; save "$__v"; return; fi
    warn "$__err"
    has_tty || break
  done
  die "「$__q」を受け取れませんでした"
}

c "1" "fox-kit（AI秘書のセットアップ）"; echo
[[ "$(uname -s)" == "Darwin" ]] || die "いまはMac専用です"

# ------------------------------------------------------------------ 0. 慣れているか
if [[ -z "${FOX_LEVEL:-}" ]]; then
  echo "  はじめに1つだけ教えてください。"
  echo "    1) はじめて・よくわからない（言葉をかみくだいて案内します）"
  echo "    2) AIやパソコンの設定に慣れている（短く案内します）"
  __lv=""
  for __i in 1 2 3; do
    has_tty && { printf '  番号を入力（空欄なら 1）: ' > /dev/tty; read -r __lv < /dev/tty || true; }
    __lv="${__lv:-1}"; [[ "$__lv" == [12] ]] && break
    warn "1 か 2 で答えてください"; __lv=""; has_tty || break
  done
  [[ "${__lv:-1}" == 2 ]] && FOX_LEVEL=expert || FOX_LEVEL=beginner
fi
[[ "$FOX_LEVEL" == (beginner|expert) ]] || die "FOX_LEVEL は beginner か expert です"
save FOX_LEVEL
[[ "$FOX_LEVEL" == beginner ]] && B=1

if [[ -n "${FOX_UPDATE:-}" && -f "$HOME/.config/fox-kit/install.json" ]]; then
  ok "$(t "新しい版に更新します。あなたが手を入れたファイルや、育ててきた設定はそのまま残します" "update mode: managed files only / modified files are kept")"
elif [[ -n "$RESUMED" ]]; then
  ok "$(t "前回の続きから始めます（答えていただいた内容は覚えています）" "state を読み込みました: $STATE（最初からは FOX_RESET=1）")"
else
  t "  あなた専用のAI秘書を、このMacに用意します（15分ほど）。途中でいくつか質問します。" \
    "  Claude Code を入れ、汎用FOXとして組み立てます（15分ほど）。"
  t "  ※ このAIは、いちいち「実行してよいですか？」と聞かずに作業を進める設定になります。お金・社外への送信などは必ずあなたに確認します。" \
    "  ※ bypassPermissions（確認ダイアログなし）が入ります。3ゲート（金銭・対外不可逆・一次情報）は人に確認する規則を入れます。"
fi

# ------------------------------------------------------------------ 1. 質問
step 1 "$(t "いくつか教えてください" "基本情報")"
ask FOX_OWNER   "$(t "このMacを使う人のお名前（例: 山田さん）" "オーナー名（呼び方）")" ""
ask FOX_AGENT   "$(t "AIの名前（呼びかけるときの名前）" "エージェント名")" "FOX"
ask FOX_MACHINE "$(t "このMacの呼び方（例: 事務所のMac）" "端末ラベル")" "$(scutil --get ComputerName 2>/dev/null || hostname -s)"
ask FOX_ROLE    "$(t "このMacで主にすること（例: 経理の仕事）" "端末の役割")" "作業機"
ok "$FOX_OWNER の「$FOX_AGENT」として組み立てます"

# ------------------------------------------------------------------ 2. 本体
step 2 "$(t "AIの本体を入れる" "Claude Code 本体")"
export PATH="$HOME/.local/bin:$PATH"
if [[ -n "${FOX_SKIP_CLAUDE:-}" ]]; then
  warn "飛ばしました（検証用）"
elif command -v claude >/dev/null 2>&1; then
  ok "$(t "もう入っています" "入っています: $(claude --version 2>/dev/null | head -1)")"
else
  t "  入れています…（数分かかります）" ""
  quiet zsh -c "curl -fsSL https://claude.ai/install.sh | bash" || true
  command -v claude >/dev/null 2>&1 || die "$(t "うまく入りませんでした。インターネットにつながっているか確かめてください" "Claude Code が入りませんでした（ログ: $LOG）")"
  ok "$(t "入れました" "入れました: $(claude --version 2>/dev/null | head -1)")"
fi
grep -qs 'HOME/.local/bin' "$HOME/.zshrc" || echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$HOME/.zshrc"
mark claude

# ------------------------------------------------------------------ 3. キット
step 3 "$(t "AI秘書の部品を取ってくる" "キットを取得")"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
if [[ -d "$KIT_URL" ]]; then
  cp -R "$KIT_URL/." "$TMP/kit"
else
  mkdir -p "$TMP/kit"
  curl -fsSL "$KIT_URL" | tar -xz -C "$TMP/kit" --strip-components 1 \
    || die "$(t "部品を取ってこられませんでした。インターネットにつながっているか確かめてください" "キットを取得できませんでした: $KIT_URL")"
fi
[[ -f "$TMP/kit/install.sh" ]] || die "$(t "部品の中身がおかしいようです" "キットの中身が不正です（install.sh がない）")"
mkdir -p "$HOME/Tools"
[[ -d "$KIT_DIR" ]] && mv "$KIT_DIR" "$KIT_DIR.bak-$(date +%Y%m%d-%H%M%S)"
rm -rf "$TMP/kit/.git"; mv "$TMP/kit" "$KIT_DIR"; chmod +x "$KIT_DIR/install.sh"
ok "$(t "取ってきました" "$KIT_DIR")"
mark kit

# 組み立てには Apple の開発ツール（中の python3）が要る。素のMacには無いので先に入れる
if ! /usr/bin/xcode-select -p >/dev/null 2>&1 || ! /usr/bin/python3 -c 1 >/dev/null 2>&1; then
  t "  Appleの追加部品が必要です。画面に「インストールしますか？」と出たら「インストール」を押してください（10〜20分ほど）。" \
    "  Command Line Tools が無いので xcode-select --install を起動します（python3 用）。"
  /usr/bin/xcode-select --install >/dev/null 2>&1 || true
  if has_tty; then
    __w=0
    until /usr/bin/xcode-select -p >/dev/null 2>&1 && /usr/bin/python3 -c 1 >/dev/null 2>&1; do
      (( __w += 1 )); (( __w > 120 )) && die "$(t "追加部品のインストールが終わりませんでした" "CLT の導入待ちがタイムアウト")"
      (( __w % 6 == 1 )) && echo "  $(t "インストールが終わるのを待っています…" "CLT 待機中…")"
      sleep 10
    done
    ok "$(t "追加部品が入りました" "CLT 導入済み")"
  else
    die "$(t "追加部品のインストールが終わってから、同じ1行をもう一度貼り付けてください" "CLT 導入後に再実行してください")"
  fi
fi

# ------------------------------------------------------------------ 4. 組み立て
step 4 "$(t "あなた専用に組み立てる" "組み立て（人格・作法・スキル・記憶・設定）")"
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
# fox-kit コマンドを使えるようにする
mkdir -p "$HOME/.local/bin"
ln -sf "$HOME/Tools/fox-kit-cli/fox-kit" "$HOME/.local/bin/fox-kit"
mark build

# 遠隔（任意）
TODO=()   # 最後に出す「残りの作業」
if [[ -n "${FOX_REMOTE:-}" ]]; then
  if [[ -n "${FOX_SSH_KEY:-}" ]]; then
    [[ "$FOX_SSH_KEY" == ssh-* ]] || die "FOX_SSH_KEY が公開鍵の形ではありません（ssh- で始まるはず）"
    mkdir -p "$HOME/.ssh" && chmod 700 "$HOME/.ssh"
    touch "$HOME/.ssh/authorized_keys" && chmod 600 "$HOME/.ssh/authorized_keys"
    grep -qF "$FOX_SSH_KEY" "$HOME/.ssh/authorized_keys" || echo "$FOX_SSH_KEY" >> "$HOME/.ssh/authorized_keys"
  fi
  if [[ ! -d /Applications/Tailscale.app ]]; then
    echo "  $(t "遠隔サポート用のアプリを入れます（Macのパスワードを聞かれます）" "Tailscale を導入（sudo）")"
    curl -fsSL -o "$TMP/ts.pkg" https://pkgs.tailscale.com/stable/Tailscale-latest-macos.pkg
    sudo installer -pkg "$TMP/ts.pkg" -target / >/dev/null
  fi
  open -a Tailscale || true
  TODO+=("$(t "画面右上に出た Tailscale のアイコンを押し、サポート担当から聞いたアカウントでログインする（やらないと、遠くからのサポートができません）" "Tailscale にログイン（サポート側の tailnet）")")
  if ! sudo systemsetup -setremotelogin on >/dev/null 2>&1; then
    open "x-apple.systempreferences:com.apple.Sharing-Settings.extension" || true
    TODO+=("$(t "開いた設定画面で「リモートログイン」をオンにする" "システム設定 > 一般 > 共有 > リモートログイン をオン")")
  fi
fi
if [[ -n "${FOX_DEDICATED:-}" ]]; then
  sudo pmset -c sleep 0 disksleep 0 >/dev/null && ok "$(t "電源につないでいる間は眠らない設定にしました" "pmset -c sleep 0")"
fi

# ------------------------------------------------------------------ 5. ログイン
step 5 "$(t "AIのアカウントにログイン" "Claude にログイン")"
logged_in() { claude auth status 2>/dev/null | grep -qi '"loggedIn": *true'; }
if [[ -n "${FOX_SKIP_LOGIN:-}${FOX_SKIP_CLAUDE:-}" ]]; then
  warn "飛ばしました（検証用）"
elif logged_in; then
  ok "$(t "ログイン済みです" "ログイン済み")"; mark login
else
  t "  インターネットの画面が開きます。AIの契約をしたアカウントで「ログイン」→「許可」を押してください。
  ★会社のMacなら、会社で契約したアカウントを使ってください。終わったらこの画面に戻ってきます。" \
    "  ブラウザでOAuthします。会社の端末なら会社の契約アカウントで。"
  { has_tty && claude auth login < /dev/tty; } || true
  if logged_in; then ok "$(t "ログインできました" "ログイン完了")"; mark login
  else TODO+=("$(t "AIのアカウントにログインする → 同じ1行をもう一度貼り付けると、ここから再開します（やらないと、AIが動きません）" "claude auth login（未完了）")"); fi
fi

# ------------------------------------------------------------------ 6. あいさつ
step 6 "$(t "AIにあいさつしてもらう" "動作確認")"
if done_ login; then
  if (cd ~ && claude -p "一言で自己紹介して。あなたの名前と、誰の秘書かを言って" --output-format text); then
    mark hello
  else
    warn "$(t "返事がありませんでした" "応答なし")"
  fi
else
  warn "$(t "ログインが済んだら、ここであいさつします" "ログイン後に実行")"
fi

# ------------------------------------------------------------------ 7. 初期設定の聞き取り
step 7 "$(t "AIと最初のお話（初期設定）" "初期設定の聞き取り")"
if done_ interview; then
  ok "$(t "初期設定は済んでいます（やり直すときは fox-kit setup）" "interview: done")"
elif done_ login && [[ -z "${FOX_NO_INTERVIEW:-}" ]] && [[ -d "$HOME/.claude/skills/fox-setup" ]] && has_tty; then
  t "  AIが、あなたの仕事や使っている道具について質問します。答えるだけで設定が進みます。
  終わったら「おわり」と打つか、キーボードの control を押しながら C を2回押してください。" \
    "  /fox-setup を起動します（終了: Ctrl+C 2回）。"
  (cd ~ && claude "/fox-setup" < /dev/tty) || true
  mark interview
elif done_ login; then
  TODO+=("$(t "AIと最初のお話をする：この黒い画面で  cd ~ && claude  と打ってEnter →「初期設定をお願いします」と話しかける" "cd ~ && claude → /fox-setup")")
else
  warn "$(t "ログインが済んだら、ここで初期設定のお話をします" "ログイン後に実行")"
fi

# ------------------------------------------------------------------ 仕上げ
echo
if (( ${#TODO} == 0 )); then
  c "1;32" "$(t "すべて完了しました。" "完了。")"; echo
  t "  これからは、この黒い画面で  cd ~ && claude  と打てば、いつでも${FOX_AGENT}と話せます。
  状態を見る・新しい版にする・Discordとつなぐ は、  fox-kit  と打つと案内が出ます。" \
    "  使い方: cd ~ && claude（ホームで開く＝記憶はそこ）。常駐させるなら $KIT_DIR/docs/BOOTSTRAP_育て方.md の長寿命トークンへ"
else
  c "1;33" "$(t "あと少しです。残りの作業：" "残作業：")"; echo
  i=1; for x in "${TODO[@]}"; do echo "  ${i}. $x"; (( i++ )) || true; done
  t "  終わったら、同じ1行をもう一度貼り付けると、続きから仕上げます。" "  完了後に再実行すると続きから確認します。"
fi
[[ -n "$B" ]] && echo "  （うまくいかなかったときの記録: $LOG）"
exit 0
