# スキル発動トリガー索引（fox-kit が入れたスキル）

**持ち主はスキル名を覚えていない前提。指示が無くても、下の言葉が来たら自動で使う。**
根拠：実運用で1,600本超の会話を数えたところ、ここに書いたスキルだけが呼ばれ、書いていないものは使われなかった。

0. **お金の数字を渡す・直す・食い違いを閉じる** — 精算明細・支払額・請求・台帳の金額 → チェック役 `money-auditor` を立てて合格をもらってから（作法34）
1. **資料を作る・直す** — スライド・企画書・提案書・チラシ・HTML資料・事業計画 → `shiryo-review-loop`（言われなくても回す）
2. **HP・LP・サイトを作る** — 「HP作って／LP作って／サイト作って／おしゃれにして」→ `design-taste`（方向決め）→ 制作 → `impeccable-design`（見た目の土台の点検）→ `emil-motion`（動き）＋`apple-design`（ドラッグ・スワイプ・半透明・文字の詰めをApple風の手触りに）
3. **SEO・検索順位・記事** — 検索順位／流入／キーワード／サイトの調子 → `seo-audit`（全体）・`seo-page`（1ページ）・`seo-google`（実データ）・`seo-geo`（AI検索）・`seo-technical`（残りは `seo-audit` が振り分ける）
4. **売れる文章・数字を上げる** — 申込が少ない→`cro`、書く・直す→`copywriting`、計測→`analytics`、どこから来たか→`attribution`、A/Bテスト→`ab-testing`、ほかのマーケ全般は `marketing-skills` の中から選ぶ
5. **外に出る文章の仕上げ** — 記事本文・SNSの文・メール返信案・HP/LPの文は、書き終えたら `humanizer` を1回通す（進捗報告・コード・数字の通知は除く）
6. **世間の直近の反応** — 「最近どう／評判／流行ってる」→ `last30days`（ウェブ検索より先）
7. **図・構成図** — システムの構成・データの流れ・手順の順番 → `archify`
8. **動画を見る** — 動画のURL（YouTube・TikTok・Instagram・X）や動画ファイルを渡されただけでも `watch`。実際にダウンロードして、場面の画像と字幕・音声から中身を読む。持ち主に文字起こしを貼らせない ※Mac のみ（Windows では「いまは Mac 版だけです」と伝え、字幕や文字起こしがあれば貼ってもらう。道具を自分で入れ始めない）
9. **動画を作る** — 「動画作って／縦動画／字幕付き」→ `remotion-best-practices`（ほかの remotion-* はここから振り分ける）
10. **画像を作る・直す** — 「画像作って／この写真を加工して／バナー」→ `nanobanana` コマンド（`nanobanana "指示" -i 元画像 -o 出力先`）。キャラクター・マスコット・ゆるいロゴ → `ip-as-logo-skill`。※nanobanana は Mac のみ
11. **保存先のノートを書く・整える** — `obsidian-markdown`（ノート）・`obsidian-bases`（.base）・`json-canvas`（.canvas）・`obsidian-cli`（操作）・`defuddle`（ウェブページをきれいに取り込む。Mac のみ）
12. **保存先を横断して探す** — 言葉が違っても探したい・「前にどこかに書いた〇〇」→ MCP `vault-rag` の `vault_search`（Mac で Gemini の鍵があるときだけ）。無いとき・Windows・場所の見当がつくときは `_全体の目次.md` から辿る
13. **ブラウザを触る** — 開く・入力・クリック・画面の保存・抜き出し → まず Claude in Chrome（下の「ブラウザで調べる」）。つながらないときの2番手が MCP `playwright`（Mac のみ）。**支払いの確定は代行しない**（持ち主が押す）。ログイン・送信・公開は押す前に持ち主に確認する
14. **セキュリティの確認** — 「セキュリティ確認して／脆弱性チェック」→ `security-audit`
15. **Googleのクラウド・アナリティクス** — gcloud の操作 → `gcloud`、GA4のデータ → `google-analytics-data-api-basics`
16. **本・PDFを身につける** — 「この本を使えるようにして」→ `book-to-skill`
17. **スキルを作る・直す** — 「スキル作って／発動しない」→ `skill-creator`。説明文（description）は1〜2行・「〜するとき」で書く
18. **知らない種類の作業** — 自分で作る前に `find-skills`（`npx skills find <言葉>`）で既にあるスキルを探す
19. **手を抜かずにやり切る** — 長い作業・「最後までやって」→ `unlazy`
20. **Word・Excel・PowerPoint・PDF のファイル** — 作る・読む・直す → `docx`・`xlsx`・`pptx`・`pdf`
21. **ダッシュボード・管理画面を作る** — 「ダッシュボード／管理画面／グラフの見せ方／配色決め」→ `ui-ux-pro-max`（`python3 ~/.claude/skills/ui-ux-pro-max/scripts/search.py "<用途>" --design-system`）。英字フォントの提案は日本語の書体に置き換える
22. **アイデアの壁打ち** — 「一緒に考えて／壁打ち／新しい企画を考えたい」で、何を作るかがまだ決まっていないとき → `brainstorming`（答えを先に出さず1問ずつ聞く）。具体的な指示や「任せる」のときは使わない
23. **不具合・お金や予約のロジック** — 原因の分からない不具合は直す前に `systematic-debugging`、お金・席数などの計算を書く前は `test-driven-development`、「できました／直りました」と言う前は `verification-before-completion`

24. **自分（AI）の設定・点検を頼まれた** — 持ち主にターミナルを打たせず、自分で実行して結果を日本語で返す。
    **Mac**：「調子を見て」→ `fox-kit status`／「新しい版に更新して」→ `fox-kit update`／「画像づくりの鍵を登録したい」→ `python3 ~/Tools/fox-packs/packs.py key --dialog`（Macの画面に鍵を貼る窓が出る、と先に伝える。鍵を会話に貼らせない）。
    **Windows**（`fox-kit` コマンドは無い）：「調子を見て」→ 下の 27 の状態確認と `claude auth status` を見て返す／「新しい版に更新して」→ 「PowerShell に入れ方の1行をもう一度貼ってください（手を入れたファイルは上書きしません）」と案内する／画像づくりの鍵は Windows では使えない。
    「名前（呼び方）を変えて」→ `~/.claude/CLAUDE.md` の名前と、Mac は `~/.config/fox-kit/state.env` の `FOX_OWNER`・`FOX_AGENT`、Windows は `~/.config/fox-kit/state-win.json` の `FOX_OWNER`・`FOX_AGENT`（設定画面で入れたときは `~/.config/fox-kit/wizard.json` の `answers` の `owner`・`agent`）を書き換える（AIの名前を変えても Slack/Discord の表示名と資料フォルダ名は変わらない、と添えて、変えたいなら手順を案内）／
    「見張り番を入れて」→ 置きっぱなしなら Mac は `python3 ~/Tools/fox-home/home.py install office`、Windows は PowerShell で `$py = (Get-Command python -All | Where-Object Source -notlike '*WindowsApps*' | Select-Object -First 1).Source; & $py "$HOME\Tools\fox-kit\tools\fox-home\home.py" install office`（持ち歩きなら office を mobile に）／
    「初期設定の続きをして」→ `fox-setup`／「Antigravity の使い方を教えて」→ 開き方・フォルダの開き方（ホーム）・Claude のマーク（✳）から話しかける、を1つずつ案内

25. **「設定画面を開いて／あとでやる にした設定をやりたい／スキップしたのを入れたい」** — 設定画面を開き直す。Mac は `fox-kit settings`。
    **いま設定画面の中の会話で頼まれたときは、何も開かずに**「左の一覧から選んでください」とだけ伝える（もう開いている）。
    Windows は PowerShell で、`~/.config/fox-kit/wizard.json` があれば設定画面を開く：`$py = (Get-Command pythonw -All | Where-Object Source -notlike '*WindowsApps*' | Select-Object -First 1).Source; Start-Process -FilePath $py -ArgumentList ('"' + "$HOME\Tools\fox-kit\wizard\server.py" + '"')`。無ければ（黒い画面で入れた人）設定画面は使わず、Discord/Slack は設定係の窓で：`$py = (Get-Command python -All | Where-Object Source -notlike '*WindowsApps*' | Select-Object -First 1).Source; Start-Process -FilePath $py -ArgumentList ('"' + "$HOME\Tools\fox-kit\tools\fox-bridge\connect.py" + '"')`（新しい黒い窓で設定係が開く）。
    「左の一覧で ↩ が付いている段を押すと、そこへ戻れます」と1行添える

26. **「何ができる？／何を頼めばいい？／おすすめは？」と聞かれた** — `~/.claude/skills/fox-setup/secretary-menu.md` を読み、記憶（役割・道具・`project_wishlist.md`）から**3つだけ**選んで、話しかけ方の例つきで勧める。全部を並べない。「全部見せて」と言われたときだけ一覧を出す

27. **「スマホから頼めるようにしたい／Discord（Slack）とつなぎたい」** — Mac は `fox-kit connect`（設定係の窓が開く）。Windows は 25 と同じ（設定画面があれば「左の一覧の『スマホから話せるように』を押して、画面の案内どおりに進めてください」、無ければ設定係の窓を開いて「窓の案内どおりに進めてください」と伝える）。
    つないだかどうかの確認：Mac は `python3 ~/Tools/fox-bridge/connect.py --status`、Windows は PowerShell で
    `$py = (Get-Command python -All | Where-Object Source -notlike '*WindowsApps*' | Select-Object -First 1).Source; & $py "$HOME\Tools\fox-kit\tools\fox-bridge\connect.py" --status`
    鍵（トークン）は画面にだけ貼ってもらい、会話には貼らせない

- **ブラウザで調べる・ログインした画面で入力する・ページを見て確かめる**依頼 → Claude in Chrome（Chrome の公式拡張）を使う。つながっていなければ、持ち主に「この画面で `/chrome` と打ち、『Enabled by default』を選んでください」と1回だけ案内する（拡張が無ければ Chrome ウェブストアの「Claude」を「Chrome に追加」→ 同じアカウントでログイン）。**支払いの確定は代行しない**（持ち主が押す）。ログインが要る画面・送信・公開は、押す前に必ず持ち主に確認する
- 「パソコンを最新にして」「更新を確かめて」→ Mac は `softwareupdate -l` で一覧を見せ、`open "x-apple.systempreferences:com.apple.Software-Update-Settings.extension"` で更新の画面を開く／Windows は `start ms-settings:windowsupdate-action`。再起動が要る更新は、押す前に持ち主に確認する（作業中のものが消えるため）

**新しくスキルを入れたら、同じ作業の中で `~/.claude/rules/my-skills.md`（持ち主のファイル。無ければ作り、`~/.claude/CLAUDE.md` に `@~/.claude/rules/my-skills.md` を足す）に1行足す。書くまでが導入。**このファイル（`~/.claude/fox-kit/rules/`）はキットの更新で新しくなるので書き足さない
