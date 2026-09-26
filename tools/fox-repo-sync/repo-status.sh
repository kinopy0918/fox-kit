#!/usr/bin/env bash
# 両方の機械のリポジトリを見て「どこかに取り残されている作業」を洗い出す。
#
# 「どちらの機械からでも作業できて、全部共有されている」を保つのに必要なのは、
# 全リポジトリを両機にcloneすることではない（54個も要らない）。必要なのは
#   ① 両機ともGitHubへ読み書きできること
#   ② どこにも未コミット・未pushが溜まっていないこと
# の2つだけ。①は一度直せば済むので、日々見るのは②＝この道具。
#
# 出る記号:
#   未commit N   作業ツリーに保存していない変更（機械が壊れたら消える）
#   未push  N    コミット済みだがGitHubに無い（もう片方の機械から見えない）
#   遅れ    N    GitHubにあるが手元に取り込んでいない（古いコードで作業する事故のもと）
#   ✗接続        GitHubに問い合わせできない＝認証が通っていない
#
# 使い方:  ./repo-status.sh            両機を見る
#          ./repo-status.sh local      この機械だけ
set -uo pipefail

scan() {
    local root="$1"
    find "$root" -maxdepth 3 -name .git -type d 2>/dev/null | sort | while IFS= read -r g; do
        d="$(dirname "$g")"
        name="${d##*/}"
        # _vendor は他人のコードを置く場所。差分が出て当然なので数えない。
        case "$d" in */_vendor/*) continue ;; esac

        dirty="$(git -C "$d" status --porcelain 2>/dev/null | wc -l | tr -d ' ')"
        if ! git -C "$d" remote get-url origin >/dev/null 2>&1; then
            [ "$dirty" != "0" ] && printf '  %-28s 未commit %-4s リモート無し\n' "$name" "$dirty"
            continue
        fi
        # 取得できないなら認証が死んでいる。ここを黙って飛ばすと
        # 「未pushゼロ＝健全」に見えてしまうので、必ず出す。
        if ! git -C "$d" fetch -q origin 2>/dev/null; then
            printf '  %-28s ✗接続（認証が通っていない）\n' "$name"
            continue
        fi
        counts="$(git -C "$d" rev-list --left-right --count '@{upstream}...HEAD' 2>/dev/null)" || counts="0 0"
        behind="$(echo "$counts" | awk '{print $1}')"
        ahead="$(echo "$counts" | awk '{print $2}')"
        if [ "$dirty" != "0" ] || [ "$ahead" != "0" ] || [ "$behind" != "0" ]; then
            printf '  %-28s 未commit %-4s 未push %-4s 遅れ %s\n' "$name" "$dirty" "$ahead" "$behind"
        fi
    done
}

target="${1:-both}"

# 走査するルート。既定は $HOME/dev, $HOME/Projects, $HOME/Tools。
# 増やすなら SCAN_ROOTS="dir1 dir2" ./repo-status.sh のように渡す。
roots="${SCAN_ROOTS:-$HOME/dev $HOME/Projects $HOME/Tools}"

if [ "$target" = "local" ] || [ "$target" = "both" ]; then
    echo "=== $(scutil --get ComputerName 2>/dev/null || hostname) ==="
    for r in $roots; do
        [ -d "$r" ] && scan "$r"
    done
    echo "  （何も出なければ、この機械に取り残しは無い）"
fi

if [ "$target" = "both" ]; then
    echo
    echo "=== もう片方の機械 ==="
    # 相手機の ~/.ssh/config エイリアス名。PEER=<名前> で渡す（既定は未設定＝案内して終わる）。
    peer="${PEER:-}"
    if [ -z "$peer" ]; then
        echo "  PEER が未設定です。相手機の ssh エイリアス名を渡してください:"
        echo "    PEER=mini-fox ./repo-status.sh"
        exit 0
    fi
    if ssh -o ConnectTimeout=8 -o BatchMode=yes "$peer" true 2>/dev/null; then
        ssh "$peer" 'bash -s local' < "$0"
    else
        echo "  $peer に繋がりません（Tailscaleの状態を確認）"
    fi
fi
