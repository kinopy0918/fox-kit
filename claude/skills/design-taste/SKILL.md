---
name: design-taste
description: Feed Claude high-quality design references and a point of view before generating web UI, so output looks modern and intentional instead of generic AI. Use at the START of any website/landing page/web app design task to set direction, or when output looks bland and needs a reference-driven redesign. Triggers on "design a site/landing/UI", "make it modern", "looks generic", picking a visual direction.
---

# Design Taste — 参照駆動でセンスを底上げする

AIのデザインが凡庸になるのは、**良い参照を持っていないから**。生成の前に「どこを目指すか」を決め、具体的な参照の特徴を言語化してから作る。これが一番効く。

## 進め方（デザイン着手時に必ず）

1. **方向性を1つ決める**（下のアーキタイプから選ぶ／ユーザーに確認）。複数を混ぜない。
2. その方向の**参照サイトの特徴を3–5個、具体語で**言語化する（「余白が広い」「モノクロ＋1アクセント」「セリフ見出し」等）。
3. **emil-motion** と **impeccable-design** の規則を併用する。
4. 作ったら参照と並べて「何が足りないか」を1回レビューして詰める。

## デザイン・アーキタイプ（方向性のパレット）

選んだ方向の特徴をそのまま設計指針にする。

- **Linear / Vercel 系（モダンSaaS・テック）**
  ダーク基調、繊細なグラデ／グロー、Geist・Inter、緻密な余白、控えめで上質なモーション、薄い境界線。鋭く知的。
- **Stripe / Mercury 系（信頼・フィンテック）**
  明るく清潔、整然としたグリッド、上品なアクセント色、図解・イラストが丁寧、情報設計が緻密。
- **Apple / プロダクト系**
  大胆な余白と大きなタイポ、製品ビジュアル主役、スクロール演出、中央寄せヒーロー、ミニマル。
- **エディトリアル / ラグジュアリー（ブランド・宿・飲食）**
  セリフ見出し（または上質な明朝）、写真を主役に全面使い、ゆったりした余白、抑えた配色、静かなフェード。**和モダン・宿サイトはここ**。
- **Family / Igloo / 遊び系**
  鮮やかな色、丸み、弾むモーション、手描き・3D要素。個性重視、B2C向け。
- **ブルータリズム / エディトリアルtech**
  モノスペース、強い罫線、高コントラスト、グリッドむき出し。尖った印象。

## 質の高い参照（特徴を盗む対象）

実装を真似るのではなく**「なぜ上質に見えるか」を抽出**する。

- **ギャラリー**: Godly (godly.website)、Land-book、Httpster、Awwwards、SaaS Landing Page、Mobbin（UIパターン）、Refactoring UI（原則）。
- **基準になるサイト**: Linear, Vercel, Stripe, Family.co, Mercury, Arc, Raycast, Vaul/Sonner（emilのデモ）, Apple。
- **和モダン・宿・ブランド系**: 星のや等の旅館サイト、上質なブランドLP、写真主役のエディトリアルサイト。

## 「凡庸」を脱する具体策

- **テンプレ構成を捨てる**: 「ヒーロー→3カラム特徴→CTA」の機械的反復をやめ、リズムに変化をつける。
- **本物のコンテンツで作る**: ダミーの "Lorem ipsum"・"Feature 1" のまま整えない。実際の文言・写真で設計する。
- **1つ尖らせる**: 全部平均点より、タイポか写真かモーションのどれか1点を突き抜けさせる。
- **余白を恐れない**（→ impeccable-design）。
- **写真・画像の質を上げる**: 安いストック感を避ける。トーンを揃える（同じ現像・同じ色温度）。
- **意図を持つ**: 「なぜこの色／この余白／この動き？」に答えられる状態にする。

## アンチパターン（AIっぽさの典型）

- 紫〜青のグラデ多用、絵文字アイコン、3カラム均等カードの連打。
- どこかで見たBootstrap/テンプレ感、意味のない丸グラデの背景。
- フォント・色・余白に一貫した思想がない。
- 参照を見ずにいきなり実装し始める。

## チェック

- [ ] 着手前に方向性を1つ決めたか
- [ ] 参照の特徴を具体語で言語化したか
- [ ] 実コンテンツ（文言・写真）で設計しているか
- [ ] どこか1点を突き抜けさせたか
- [ ] emil-motion / impeccable-design を併用したか
- [ ] 「AIテンプレ」アンチパターンに陥っていないか
