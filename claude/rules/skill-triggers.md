# スキル発動トリガー索引（fox-kit が入れたスキル）

**持ち主はスキル名を覚えていない前提。指示が無くても、下の言葉が来たら自動で使う。**
根拠：実運用で1,600本超の会話を数えたところ、ここに書いたスキルだけが呼ばれ、書いていないものは使われなかった。

1. **資料を作る・直す** — スライド・企画書・提案書・チラシ・HTML資料・事業計画 → `shiryo-review-loop`（言われなくても回す）
2. **HP・LP・サイトを作る** — 「HP作って／LP作って／サイト作って／おしゃれにして」→ `design-taste`（方向決め）→ 制作 → `impeccable-design`（見た目の土台の点検）→ `emil-motion`（動き）
3. **SEO・検索順位・記事** — 検索順位／流入／キーワード／サイトの調子 → `seo-audit`（全体）・`seo-page`（1ページ）・`seo-google`（実データ）・`seo-geo`（AI検索）・`seo-technical`（残りは `seo-audit` が振り分ける）
4. **売れる文章・数字を上げる** — 申込が少ない→`cro`、書く・直す→`copywriting`、計測→`analytics`、どこから来たか→`attribution`、A/Bテスト→`ab-testing`、ほかのマーケ全般は `marketing-skills` の中から選ぶ
5. **外に出る文章の仕上げ** — 記事本文・SNSの文・メール返信案・HP/LPの文は、書き終えたら `humanizer` を1回通す（進捗報告・コード・数字の通知は除く）
6. **世間の直近の反応** — 「最近どう／評判／流行ってる」→ `last30days`（ウェブ検索より先）
7. **図・構成図** — システムの構成・データの流れ・手順の順番 → `archify`
8. **動画を見る** — 動画のURL（YouTube・TikTok・Instagram・X）や動画ファイルを渡されただけでも `watch`。実際にダウンロードして、場面の画像と字幕・音声から中身を読む。持ち主に文字起こしを貼らせない
9. **動画を作る** — 「動画作って／縦動画／字幕付き」→ `remotion-best-practices`（ほかの remotion-* はここから振り分ける）
10. **画像を作る・直す** — 「画像作って／この写真を加工して／バナー」→ `nanobanana` コマンド（`nanobanana "指示" -i 元画像 -o 出力先`）。キャラクター・マスコット・ゆるいロゴ → `ip-as-logo-skill`
11. **保存先のノートを書く・整える** — `obsidian-markdown`（ノート）・`obsidian-bases`（.base）・`json-canvas`（.canvas）・`obsidian-cli`（操作）・`defuddle`（ウェブページをきれいに取り込む）
12. **保存先を横断して探す** — 言葉が違っても探したい・「前にどこかに書いた〇〇」→ MCP `vault-rag` の `vault_search`。場所の見当がつくときは `_全体の目次.md` から
13. **ブラウザを触る** — 開く・入力・クリック・画面の保存・抜き出し → MCP `playwright`。ログイン・支払いの確定操作は代行しない（3つのゲート）
14. **セキュリティの確認** — 「セキュリティ確認して／脆弱性チェック」→ `security-audit`
15. **Googleのクラウド・アナリティクス** — gcloud の操作 → `gcloud`、GA4のデータ → `google-analytics-data-api-basics`
16. **本・PDFを身につける** — 「この本を使えるようにして」→ `book-to-skill`
17. **スキルを作る・直す** — 「スキル作って／発動しない」→ `skill-creator`。説明文（description）は1〜2行・「〜するとき」で書く
18. **知らない種類の作業** — 自分で作る前に `find-skills`（`npx skills find <言葉>`）で既にあるスキルを探す
19. **手を抜かずにやり切る** — 長い作業・「最後までやって」→ `unlazy`
20. **Word・Excel・PowerPoint・PDF のファイル** — 作る・読む・直す → `docx`・`xlsx`・`pptx`・`pdf`

**新しくスキルを入れたら、同じ作業の中でここ（会社独自なら `~/.claude/rules/company.md`）に1行足す。書くまでが導入。**
