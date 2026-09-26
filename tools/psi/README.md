# psi — PageSpeed Insights CLI

いつでも「今この瞬間」のPageSpeed Insightsスコアを叩くコマンド。
pagespeed.web.dev の画面と同じもの（Google側でLighthouseを実行した結果）を返す。

## 使い方

```bash
psi https://www.getc.co.jp/                 # モバイル + デスクトップ
psi https://www.getc.co.jp/ --mobile        # モバイルだけ
psi https://www.getc.co.jp/ --desktop
psi https://www.getc.co.jp/ --full          # 改善項目つき
psi https://a.com/ https://b.com/           # 複数URLまとめて
psi https://www.getc.co.jp/ --json > r.json # 生レスポンス
```

出力にはラボスコア（FCP/LCP/TBT/CLS/Speed Index・総バイト・サーバー応答）と、
データがあれば実ユーザーデータ（CrUX p75・FAST/AVERAGE/SLOW判定）が並ぶ。

## 認証

`~/Tools/psi/.api_key`（mode 600）のAPIキーを使う。

- キー: GCPプロジェクト `main-presence-337307` の APIキー「PageSpeed Insights CLI」
  （`pagespeedonline.googleapis.com` のみに制限済み）
- キーファイルが無い場合は `gcloud auth print-access-token` ＋ `x-goog-user-project` ヘッダーに自動フォールバック

キーを作り直す場合:

```bash
gcloud services api-keys create --display-name="PageSpeed Insights CLI" \
  --api-target=service=pagespeedonline.googleapis.com --project main-presence-337307
NAME=$(gcloud services api-keys list --project main-presence-337307 \
  --filter="displayName='PageSpeed Insights CLI'" --format="value(name)" | head -1)
gcloud services api-keys get-key-string "$NAME" --format="value(keyString)" > ~/Tools/psi/.api_key
chmod 600 ~/Tools/psi/.api_key
```

## ハマりどころ

- **キーなしで叩くと即クォータ切れ**。匿名は全世界共有の枠なので、`key=` を付けない呼び方は基本使えない。
- **AI Studio のキー（Gemini用に別で作ったもの）は使えない**。別プロジェクトかつ generativelanguage 専用で、
  `API keys are not supported by this API` になる。
- **ADCのOAuthトークン単体でも通らない**。`x-goog-user-project` でクォータプロジェクトを明示しないと
  `requires a quota project` エラー。
- **スコアは実行ごとに数ポイントぶれる**（Google側の負荷次第）。モバイルは59〜65あたりを行き来する。
  CrUXのフィールドデータ側はぶれない。
- CrUXは標本が足りないと出ない。モバイル単体のURL別データが出ないサイトもある（PC中心のB2B等）。

## 設置

`/usr/local/bin/psi` → `~/Tools/psi/psi` のsymlink。Python標準ライブラリのみでvenv不要。
