# install.sh のあと、人がやること

自動化していない4つ＋任意の上級項目。理由つき。

## 1. ログイン

```bash
claude /login
```

対話ブラウザ認証。**どのアカウントでログインするかで、この端末の利用がどの契約枠で
回るかが決まる。** 会社が変わるなら、その会社のアカウントでログインすること
（他機のトークンを持ち込むと、その会社の利用が持ち主の個人枠で回ってしまう）。

## 2. 長寿命トークンの発行（常駐ジョブを動かすなら必須）

```bash
claude setup-token
mkdir -p ~/.config/claude
printf '%s' 'sk-ant-oat…（出てきた文字列。前後の空白は付けない）' > ~/.config/claude/token
chmod 600 ~/.config/claude/token
~/Tools/claude-token/apply.sh
```

**なぜ手作業か**: `setup-token` はブラウザ認証を伴う対話コマンドで、SSH越しでもエージェント
経由でも動かない（出力ゼロのまま固まる）。画面のある人が、その場で実行するしかない。

**なぜ要るか**: 通常のログインは定期的に切れる。切れると `claude -p` を使う常駐ジョブが
**黙って**止まる。気づくのは「配信が来ていない」時。長寿命トークンはこれを防ぐ。

`apply.sh` は `~/.config/claude/token` を読んで、`~/.claude/settings.json` の `env` と
`~/.zshrc` と、該当する launchd の plist 全部に配る（`--dry` で確認できる）。

## 3. CLAUDE.md の個別ルールを書き足す

`install.sh` が作る CLAUDE.md はひな形のまま。育てるべき箇所:

- **保管先の実際のパス**（vault・共有ドライブ・GitHub org）— 決まったら埋める
- **兄弟機**（同じ{{AGENT_NAME}}が他にもいるなら）— コメントで書いてある雛形を使う
- **スキル発動トリガー索引**— 最初は空。使ってみて効いたものだけ、都度1行足す。
  導入した時点では効果を生まない。**書いた瞬間から効く**（実運用で実測済みの教訓）。
  候補の全体像は `skills-catalog.md`（58本、カテゴリ別）を見る——**先回りして全部書かない**。
- **個別ルールファイル**（`~/.claude/rules/*.md`）— 会社・取引先ごとの詳しいルールが
  増えてきたら、索引から追い出して分割する（実運用機の `rules/` 構成が実例）。

## 4. 記憶の最初の数件

空の MEMORY.md から始まる。最初の数回の会話で「誰が・何を・なぜ」を教わったら、
その場で書く（後回しにしない）。書き方は Claude Code の memory システムプロンプトに
すでに入っている（type: user / feedback / project / reference）。

## 5.（任意・上級）自律ループとブリッジを足す

確認ダイアログを減らすだけでなく、**自律的に定時実行して報告する**ところまで持っていくなら
`loop-framework/` と `bridge-framework/` を使う。install.shでは配らない（Discordトークン等、
使う前に必ず人が設定を埋める必要があるため）。

1. `loop-framework/README.md` の4原則を読む。特に `citation_verify.py`
   （根拠引用の機械照合）は、**判断を伴うループを1本でも作るなら必ず通す**——
   これが無いループはLLMの自己申告をそのまま信じることになる。
2. Discord/Slack等から `claude -p` を継ぎ足しで叩くボットを書くなら、
   `bridge-framework/session_guard.py` を隣に置いて import する（自前で書き直さない）。
   会話が育ちすぎて自動要約が「言っていない指示」を作った事故、切替直後にやっていない
   作業を「やった」と答えた事故、使用量上限を無言のエラーにした事故——3つとも実際に
   起きたものへの対策が入っている。ここでは `~/.claude/settings.json` の `bypassPermissions`
   ではなく、呼び出しコード側で `claude -p ... --permission-mode bypassPermissions` と
   CLIフラグで渡すのが実例のパターン（`hooks/guard-output-location.py` も対話セッション向けなので
   常駐ボットには紐付けない）。
3. 機体を複数持つなら `bridge-framework/GOVERNANCE.md.template` を埋めて、
   どの仕事をどの機体に回すか・3ゲート（金銭/対外不可逆/一次情報）を明文化する。
4. Discordで「素案→承認→実行」をやるなら `approval-card-pattern.md` の状態機械に沿う。
5. **会話ボットを書くなら `bridge-framework/discord_conversational.py` を使う**——
   ①返信/引用への対応（`referenced_content()`）②入力中インジケータ（`Typing`）の2点。
   実運用中の会話ボットで「メンションしても反応が無い」「返信で拾えていない」と指摘されて足したもので、
   ポーリング方式のDiscordボットで素朴に実装すると両方とも抜け落ちる。1関数・1クラスだけの
   標準ライブラリのみの実装なので、そのままimportして使える。

---

## 動作確認

```bash
cd ~ && claude -p "自己紹介して" --output-format text
```

名乗る名前・言及する記憶の場所が、狙った通りになっているか確認する。
