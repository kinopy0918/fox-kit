#!/usr/bin/env bash
# GitHubのremoteをHTTPSからSSHへ一括で切り替える。
#
# なぜ: Mac mini には gh が無く、HTTPSのremoteでは認証情報が無いため
# push どころか fetch もできなかった（private repoは取得にも認証が要る）。
# 「ahead N」と出ていたのは実際に先行していたのではなく、**GitHubを一度も
# 見に行けていなかった**ため追跡refが古いまま止まっていた、という状態も含む。
#
# SSH鍵なら機械単位で失効でき、有効期限も無く、launchdの常駐ジョブからも
# 画面ログイン状態に依存せず動く（keychainはそこで詰まる）。
#
# 使い方:  ./switch-remotes-to-ssh.sh [対象ディレクトリ]   既定 ~/dev
#          DRY_RUN=1 を付けると変更せず一覧だけ出す
set -uo pipefail

ROOT="${1:-$HOME/dev}"
DRY="${DRY_RUN:-0}"

# 先に疎通を確かめる。鍵が未登録のまま切り替えると、HTTPSより悪い状態になる。
#
# ★GitHubはSSH疎通に成功しても「シェルは使わせない」ため**必ず終了コード1**を返す。
# `ssh ... | grep -q` を pipefail 下で条件にすると、grepが当たっていてもsshの1を
# 拾って常に失敗扱いになる。出力を一度受け取ってから判定すること。
probe="$(ssh -o StrictHostKeyChecking=accept-new -o ConnectTimeout=10 -T git@github.com 2>&1 || true)"
if ! printf '%s' "$probe" | grep -q "successfully authenticated"; then
    echo "★ GitHubへのSSH認証が通っていません。切り替えを中止します。"
    echo "  この機械の公開鍵を https://github.com/settings/ssh/new に登録してください:"
    echo
    sed 's/^/    /' "$HOME/.ssh/id_ed25519.pub" 2>/dev/null
    exit 1
fi

changed=0 skipped=0
while IFS= read -r g; do
    d="$(dirname "$g")"
    url="$(git -C "$d" remote get-url origin 2>/dev/null)" || continue
    case "$url" in
        https://github.com/*)
            slug="${url#https://github.com/}"
            slug="${slug%.git}"
            new="git@github.com:${slug}.git"
            if [ "$DRY" = "1" ]; then
                echo "  [dry] ${d/#$HOME/~}  →  $new"
            else
                git -C "$d" remote set-url origin "$new"
                echo "  切替 ${d/#$HOME/~}  →  $new"
            fi
            changed=$((changed + 1))
            ;;
        *) skipped=$((skipped + 1)) ;;
    esac
done < <(find "$ROOT" -maxdepth 3 -name .git -type d 2>/dev/null | sort)

echo
echo "切り替え $changed 件 / 対象外(SSH済み・リモート無し等) $skipped 件"
[ "$DRY" = "1" ] && echo "（DRY_RUN=1 のため実際には変更していません）"
