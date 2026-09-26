# STEP 0 — 素のMacに、ここから始める

`install.sh` はキットを**組み立てる**だけで、Claude Code 本体は入れません。
このページはその手前、**何も入っていないMac**から始める人のためのものです。

所要 15〜30分。作業する人にエンジニアの知識は要りません。

---

## 用意するもの

| いるもの | 補足 |
|---|---|
| macOS のPC | Apple Silicon / Intel どちらでも |
| Claude の契約 | Pro / Max / Team。会社で使うなら Team。<br>料金は claude.ai/pricing を見る（変わります） |
| そのアカウントのメールとパスワード | ログインで使う |

**GitHub アカウントは不要です**（キットを zip で受け取る場合）。

---

## 1. ターミナルを開く

`command + スペース` → `ターミナル` と打って Enter。
黒い（または白い）文字だけの窓が開きます。以降、**この窓に貼り付けて Enter** を繰り返します。

## 2. Claude Code を入れる

```bash
curl -fsSL https://claude.ai/install.sh | bash
```

Node.js も Homebrew も要りません（本体が同梱されています）。
終わったら**ターミナルを一度閉じて開き直し**、入ったか確認します。

```bash
claude --version
```

`2.x.x (Claude Code)` のように出れば成功です。
`command not found` と出たら、ターミナルを開き直していないか、下を実行します。

```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc && source ~/.zshrc
```

## 3. ログイン

```bash
claude
```

初回はブラウザが開きます。**その端末を使う人の契約アカウント**でログインしてください。

> ★ここが分岐点です。会社の業務で使う端末なら、**会社のアカウント**でログインします。
> 個人アカウントでログインすると、会社の利用が個人の契約枠で回ってしまいます。

ログインできたら `/exit` で一度抜けます。

## 4. キットを取ってくる

**（a）zip で受け取った場合**

Finder で zip をダブルクリックして展開し、できたフォルダを `~/Tools/` に入れます。
ターミナルからやるなら:

```bash
mkdir -p ~/Tools
mv ~/Downloads/portable-fox ~/Tools/portable-fox
chmod +x ~/Tools/portable-fox/install.sh
```

**（b）GitHub から取る場合**（リポジトリに招待されている人）

```bash
mkdir -p ~/Tools && cd ~/Tools
git clone <リポジトリのURL> portable-fox
```

## 5. 組み立てる

まず**何も変えずに、何が起きるかだけ見ます**（`--dry-run`）。

```bash
cd ~/Tools/portable-fox
./install.sh --owner "<この端末を使う人の名前>さん" --agent "<エージェントの呼び名>" --dry-run
```

表示を見て問題なければ、`--dry-run` を外して本番実行します。

```bash
./install.sh --owner "<この端末を使う人の名前>さん" --agent "<エージェントの呼び名>"
```

よく使う引数（詳しくは README.md の表）:

| 引数 | 何を決めるか |
|---|---|
| `--owner` | 持ち主の名前（**必須**）。エージェントはこの人の秘書として振る舞う |
| `--agent` | 呼び名・一人称。既定は `FOX` |
| `--machine-label` | CLAUDE.md の冒頭に出る端末の呼び方（例: 「会社のMacBook」） |
| `--role` | この端末の役割（例: 「◯◯部の業務機」） |
| `--vault-path` | 資料・議事録の置き場（決まっていれば） |
| `--github-org` | コードの置き先（決まっていれば） |

**既存の設定は壊しません。** `~/.claude/CLAUDE.md` が既にあれば下書きを別名で置くだけ、
`settings.json` は和集合マージ、記憶は既にあれば触りません。

## 6. 動いたか確認する

```bash
cd ~ && claude -p "自己紹介して。あなたは誰で、記憶はどこにありますか" --output-format text
```

**狙った名前で名乗り、記憶の場所を言えば成功です。**

> ★ `cd ~` を省かないでください。Claude Code の記憶は**開いた場所ごと**に分かれていて、
> ホーム以外で開くと記憶が1件も載りません。「名乗るのに何も知らない」の原因はほぼこれです。

## 7. 次にやること

- `BOOTSTRAP.md` — 長寿命トークンの発行、CLAUDE.md の育て方、自律ループの足し方
- 最初の数回の会話で「誰が・何を・なぜ」を教える。**その場で記憶に書かせる**
  （後回しにすると、また同じ説明をすることになります）

---

## つまずいたら

| 症状 | 原因と対処 |
|---|---|
| `command not found: claude` | ターミナルを開き直す。それでも駄目なら STEP 2 の最後の `export PATH` を実行 |
| ログインのブラウザが開かない | 表示されたURLを手でブラウザに貼る |
| 確認ダイアログが毎回出る | `install.sh` が `bypassPermissions` を入れます。入っているか `cat ~/.claude/settings.json` で確認 |
| 名乗るが何も知らない | ホーム（`cd ~`）以外で開いている。記憶は場所ごとに別 |
| 常駐ジョブが黙って止まった | ログインが切れている。`BOOTSTRAP.md` の長寿命トークンを発行する |

---

## 渡す人へ：先に伝えること

このキットは `defaultMode: bypassPermissions` を入れます。
**確認ダイアログを出さずにファイル操作やコマンド実行が走る設定です。**
渡す相手には、これを**必ず先に伝えてください**。速さと引き換えに、
「止めて考える」機会が減ります。

歯止めとして同梱しているもの:

- `hooks/guard-output-location.py` — Desktop / Downloads / ホーム直下への書き捨てを止める
- `tools/fox-git-guard/pre-commit` — 秘密情報を GitHub に上げさせない
- `bridge-framework/GOVERNANCE.md.template` — 3ゲート（金銭・対外不可逆・一次情報は必ず人に）
