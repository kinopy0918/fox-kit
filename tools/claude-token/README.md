# claude の長寿命トークンを全端末に配る

## なぜ

`claude` のサブスク認証は定期的に切れる。切れると `claude -p` を使う常駐ジョブが
**黙って止まる**。気づくのは「朝の配信が来ていない」というタイミング。

端末ごとに「何本の常駐が claude に依存しているか」「どのアカウントで動くか」を
表にして管理する。例:

| 端末 | claudeに依存する常駐 | アカウント |
|---|---|---|
| 作業機 | 3本 | 個人アカウント |
| 常駐機 | launchd 21本 ＋ 会話ボット | 個人アカウント |
| 会社用機 | 会社AI本体・セッション監視 | **会社アカウント（別枠）** |

★トークンはアカウントに紐づく。**会社の端末は必ずその会社のアカウントで発行する**。
　他機のトークンを持ち込まないこと（会社の利用が個人の契約枠で回ってしまう）。

## 手順（各端末で1回ずつ）

```sh
claude setup-token          # ブラウザ認証。TTYが要るので画面で実行する
mkdir -p ~/.config/claude
printf '%s' 'sk-ant-oat…' > ~/.config/claude/token
chmod 600 ~/.config/claude/token

~/Tools/claude-token/apply.sh --dry   # 何が変わるか
~/Tools/claude-token/apply.sh         # 配って常駐を読み直す
```

## 何をするか

1. `~/.zshrc` にトークンの読み込みを足す（対話シェル用）
2. `~/Library/LaunchAgents/*.plist` の該当ジョブに
   `EnvironmentVariables.CLAUDE_CODE_OAUTH_TOKEN` を追加
3. 入れたジョブを `launchctl kickstart -k` で読み直す

環境変数名は **`CLAUDE_CODE_OAUTH_TOKEN`**。
`ANTHROPIC_API_KEY` を入れると従量課金のAPI枠に切り替わるので、そちらは使わない。

## 汎用型FOXの必須項目

新しい端末にFOXを入れるときは、**記憶・鍵・ログイン済みプロファイルの前に、これを最初にやる**。
これが無いと、作った常駐が数週間後に静かに全部止まる。
