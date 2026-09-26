---
name: emil-motion
description: Apply Emil Kowalski–style motion design to web UI — natural easing, spring physics, and tasteful micro-interactions. Use when building or polishing animations, transitions, hovers, drawers, modals, toasts, page transitions, or any motion in a website/web app. Triggers on requests about animation, easing, transitions, "feels smooth", motion polish.
---

# Emil Motion — モーション設計の作法

Emil Kowalski（Sonner / Vaul / animations.dev の作者）流の「気持ちいい動き」を再現するための規則。
動きは**装飾ではなく情報**。状態変化を伝え、操作に応答し、空間を理解させるために使う。意味のないアニメーションは入れない。

## 大原則

1. **transform と opacity だけをアニメートする**。`width`/`height`/`top`/`left`/`margin` は使わない（レイアウト再計算で重く・カクつく）。サイズ変化は `scale`、移動は `translate` で表現。
2. **enter は ease-out、exit は ease-in、移動は ease-in-out / spring**。
   - 登場（フェードイン・スライドイン）: `ease-out`（最初速く、最後ゆっくり止まる＝自然）
   - 退場（消える）: `ease-in`（さっと引いていく）
   - 位置移動・レイアウト変化: spring か `ease-in-out`
3. **`ease`（CSSデフォルト）と `linear` を避ける**。`linear` は移動には機械的でNG（ただし opacity のみのフェードや無限ループ＝スピナーには linear が正解）。
4. **時間は短く**。
   - hover・小さな state変化: 100–200ms
   - 通常のUI遷移（modal, dropdown, drawer）: 200–350ms
   - 大きな移動・ページ遷移: 350–500ms
   - 「長い＝高級」ではない。**遅いUIはイライラする**。迷ったら速め。
5. **`prefers-reduced-motion` を必ず尊重する**。該当時は transform を切り、opacity のみ or 即時表示にする。

## 推奨イージング（cubic-bezier）

```css
/* enter / 登場・展開 */
--ease-out: cubic-bezier(0.16, 1, 0.3, 1);      /* expo-out 系。最も汎用、上質 */
--ease-out-quad: cubic-bezier(0.25, 1, 0.5, 1);

/* exit / 退場 */
--ease-in: cubic-bezier(0.7, 0, 0.84, 0);

/* 双方向の移動 */
--ease-in-out: cubic-bezier(0.65, 0, 0.35, 1);

/* spring 風（CSSのみで弾みを出す） */
--ease-spring: cubic-bezier(0.34, 1.56, 0.64, 1); /* オーバーシュートあり。アイコン・バッジ等の小要素に */
```

## springを使う（推奨）

Framer Motion / Motion One が使えるなら、UI移動・ドラッグ追従・ドロワーは**バネ物理**で。`duration` ベースより自然。

```tsx
// Framer Motion
transition={{ type: "spring", stiffness: 400, damping: 30 }}      // キビキビ（ボタン・トグル）
transition={{ type: "spring", stiffness: 200, damping: 26 }}      // ゆったり（パネル・ドロワー）
```
ポイント: **stiffness で速さ、damping で揺れの収まり**。bounce が欲しければ damping を下げる（が、やりすぎない）。

## マイクロインタラクション

- **ボタン押下**: `active` で `scale(0.97)`＋短い transition（100ms ease-out）。押した感触を返す。
- **hover**: `translateY(-2px)` や軽い影の変化。150ms。派手にしない。
- **アイコントグル**（♡など）: spring でわずかにオーバーシュート（`scale 1 → 1.2 → 1`）。
- **リスト出現**: stagger（1要素ずつ 30–50ms ずらして登場）。全部同時よりリッチに見える。
- **数値カウント・プログレス**: linear か ease-out で。

## レイアウト・遷移

- 要素の追加/削除/並べ替えは **FLIP**（または Framer の `layout` prop / `AnimatePresence`）で滑らかに。
- モーダル/ドロワー: 背景を `opacity` でフェード、本体を `translateY`＋`scale` で。Vaul のように**ドラッグで閉じられる**と上質。
- ページ遷移: opacity ＋ わずかな translate（8–16px）。大きく動かさない。

## やってはいけない

- 全部に同じ 0.3s ease を付ける（＝generic の典型）。
- バウンス・回転・派手なeasingを実用UIに多用する。
- スクロール連動で要素が大量にフワフワ動く（酔う・安っぽい）。
- ローディング以外で `linear`、移動で `linear`。
- reduced-motion 無視。

## 仕上げのチェック

- [ ] transform/opacity のみで動かしているか
- [ ] enter=ease-out / exit=ease-in になっているか
- [ ] 時間は速すぎ・遅すぎないか（体感で「待たされない」か）
- [ ] hover/active のフィードバックがあるか
- [ ] `prefers-reduced-motion` 対応があるか
- [ ] 動きに「意味」があるか（無意味なら消す）
