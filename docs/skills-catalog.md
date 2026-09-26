# スキル候補カタログ（58本）

Claude Codeのマーケットプレイス・スキルは**FOXの一部ではない**——本体機能。FOX固有なのは
「どれを指示無しで自動発動させるか」という索引（CLAUDE.mdの「スキル発動トリガー索引」）だけ。
mini側の実測（1,636セッション）で分かったこと: **索引に書いていないスキルは死蔵する。
導入しただけでは効果を生まない。書いた瞬間から効く。**

このカタログは「入れる/入れない」を決める一覧ではない。**現場で実際に使いながら、
効いたものだけをCLAUDE.mdの索引に足していく**ための候補メニュー。新しい現場でこの58本を
最初から全部索引に書くと過学習になる（mini自身、24本を棚卸しして無効化した実績あり）。

## 開発・調査系

| スキル | 何をする |
|---|---|
| `ponytail` / `ponytail-review` / `ponytail-audit` | コードを書く/直す前に挟む型（既定full・差分・棚卸し） |
| `last30days` | 「最近どう/評判/流行ってる」の一次情報。WebSearchより先に使う |
| `find-skills` | 未知の作業の前に、自作する前にスキルを探す |
| `watch` | 動画URLを実際に読む（フレーム+字幕、文字起こしを貼らせない） |
| `ego-browser` | ブラウザ操作の既定（開く・入力・クリック・スクショ・抽出） |
| `gcloud` | GCP操作 |
| `archify` | システム構成/データフロー/API順/状態遷移の図解 |
| `skill-creator` | スキルを作る/直す。付属pythonは専用venvで実行 |

## デザイン・文章・ノート系

| スキル | 何をする |
|---|---|
| `design-taste` / `impeccable-design` / `emil-motion` | HP/LP制作の方向決め→土台QA→動き |
| `ip-as-logo-skill` | キャラ・マスコット・ゆるいロゴ |
| `humanizer` | 外向け文章（記事・SNS・LP/HPコピー）を書き終えたら1回通す |
| `eli5` | 「〜って何/わかりやすく/なぜ」に常に図解で答える |
| `obsidian-markdown` / `obsidian-cli` / `obsidian-bases` / `json-canvas` | vaultを触るときは素のWrite/Readで済ませない |
| `defuddle` | Web記事のvault取り込み |
| `graphify` | 任意の入力をナレッジグラフへ |
| `book-to-skill` | 技術書・PDFを使えるスキルにする |

## マーケティング分析（6本）

`ab-testing`（A/B案）`analytics`（計測）`attribution`（流入の帰属）`copywriting`（書く/直す）
`cro`（CVR改善）`google-analytics-data-api-basics`（GA実データ）— LP・広告のあるプロジェクトで使う

## SEO（15本、ルーターは`seo-audit`）

`seo` は共有ランタイムで直接呼ばない。`seo-audit`（全体）`seo-page`（1URL）`seo-google`（実データ）
`seo-geo`（AI検索）`seo-technical`が入口。残り10本（`seo-backlinks` `seo-cluster` `seo-content`
`seo-content-brief` `seo-images` `seo-local` `seo-plan` `seo-schema` `seo-sitemap`）は
`seo-audit`が必要に応じて振る。オウンドメディア運営がある現場向け。

## 動画生成（8本、ルーターは`remotion-best-practices`）

縦動画・字幕付き動画をコードで作る。`remotion-best-practices`が`remotion-create` `remotion-captions`
`remotion-markup` `remotion-render` `remotion-studio` `remotion-docs` `remotion-upgrade`を振る。
定型量産があるなら専用ツールを別途書く方が速いこともある。

## 会議録音（7本、入口は`plaud-shared`）

`plaud-shared`から`plaud-find` `plaud-read` `plaud-digest` `plaud-followup` `plaud-export`
`plaud-browse`へ。**Plaudレコーダーを使う前提**。別の録音サービス（Otter・Zoom録画等）なら
この7本は丸ごと入れ替えになる——スキル名ではなく「会議音声から情報を拾う」という機能要件で考える。

---

## 索引の育て方（CLAUDE.mdへの足し方）

1. 最初は空。このカタログを見て「たぶん要る」で先回りして書かない
2. 実際にその種の相談が来て、該当スキルを手動で呼んで効いた時点で、
   CLAUDE.mdの「スキル発動トリガー索引」に1行足す（トリガー語→スキル名）
3. しばらく使われなかった項目は、棚卸しして消す（無効化ではなく削除でよい。
   マーケットプレイス側には残っているので、必要になればまた索引に書けばよいだけ）
