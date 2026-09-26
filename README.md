# fox-kit

**あなた専用のAI秘書を、Macに1行で入れる。**

Claude Code を「その人・その会社専用の秘書」として組み立てるインストーラです。
人格・仕事の作法・資料のチェック役・資料の保存先・Discord/Slack とのやり取りまで、
画面の質問に答えるだけでそろいます。AIに詳しくない人でも入れられるように作っています。

- 手順書（図つき）：https://kinopy0918.github.io/fox-kit/
- 動く環境：macOS ／ Claude の契約（Pro・Max・Team）

## 入れ方

ターミナルに次の1行を貼り付けて return。

```sh
/bin/zsh -c "$(curl -fsSL https://kinopy0918.github.io/fox-kit/get.sh)"
```

最初に「はじめて／慣れている」を選びます。「はじめて」を選ぶと、案内も、入れたあとのAIの話し方も、専門用語を使わなくなります。
途中で止まっても、同じ1行を貼り直せば続きから始まります。

## 入るもの

| 何 | どこ | 更新のとき |
|---|---|---|
| 人格（名前・持ち主・役割） | `~/.claude/CLAUDE.md` | さわらない（持ち主のもの） |
| 仕事の作法 32項目 | `~/.claude/fox-kit/rules/craft.md` | 手を入れていなければ新しくする |
| 初期設定の聞き取り・資料の品質ループ | `~/.claude/skills/fox-setup` ・ `shiryo-review-loop` | 同上（差し戻し一覧 `checklist.md` は育つのでさわらない） |
| 資料のチェック役 | `~/.claude/agents/shiryo-reviewer.md` | 同上 |
| Discord / Slack とつなぐ部品 | `~/Tools/fox-bridge` | 同上 |
| 会社ごとの決まり・話し方・保存先 | `~/.claude/rules/*.md` | さわらない（持ち主のもの） |
| AIの記憶 | 選んだ保存先の `08_AIの記憶/` | さわらない |

## 入れたあと

```sh
fox-kit            # いまの状態（版・ログイン・保存先・Discord/Slack・新しい版があるか）
fox-kit update     # 新しい版に更新（手を入れたファイルは上書きせず、横に .new-版 を置く）
fox-kit setup      # 初期設定の聞き取りをもう一度
fox-kit connect    # Discord / Slack とつなぐ
fox-kit guide      # 手順書を開く
```

## 安全について

このキットは、Claude Code が確認ダイアログを出さずに作業を進める設定（`bypassPermissions`）を入れます。
その代わり、**お金が動くこと・社外に送ること・持ち主しか知らない判断**は必ず人に確認する作法を入れています。
詳しくは [SECURITY.md](SECURITY.md)。

## 変更履歴

[CHANGELOG.md](CHANGELOG.md)

## 困ったとき・要望

- まずは [困ったとき](https://kinopy0918.github.io/fox-kit/trouble.html) を見てください
- 不具合・要望は [Issues](https://github.com/kinopy0918/fox-kit/issues) へ（安全に関わる問題は [SECURITY.md](SECURITY.md) の方法で）

## ライセンス

MIT（[LICENSE](LICENSE)）
