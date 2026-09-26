#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
汎用型FOX — 自律ループの雛形

これは動く「実」ではなく、**型**。mini で15本実運用しているループ
（会議タスク同期・コードレビュー・補助金ウォッチ等）は、すべてこの形をしている:

    ① 収集   … 今回新しく見るべきものだけを集める（前回との差分）
    ② 判断   … LLMに判定させる。ただし根拠の引用を必須にする
    ③ 機械照合 … citation_verify.verify() で引用の実在を確認。落ちたら棄却
    ④ 実行   … 確認が要る行為（金銭・対外送信・不可逆）は承認ゲートへ渡すだけ。
               それ以外の安全な行為だけ、ここで実行してよい
    ⑤ 記録   … 状態ファイルを更新し、Discord/Slackへ結果を投げる

**差分が無ければLLMを呼ばない。** 平常時のコストを0にするのがこの型の要。
「毎回全部読んで毎回LLMに聞く」はコストが線形に伸びて破綻する。

実際のループを書くときは、このファイルをコピーして
①③⑤の中身を自分のドメイン（何を集めて・何を出典にして・どこへ書くか）に置き換える。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import load_config, post_discord, run_claude  # noqa: E402
from citation_verify import verify, PROMPT_RULE_JA  # noqa: E402

STATE_FILE = Path(__file__).parent / "loop_template.state.json"


def load_state() -> dict:
    try:
        return json.loads(STATE_FILE.read_text())
    except Exception:
        return {"seen": []}


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2))


# --------------------------------------------------------------- ① 収集
def collect_new_items(state: dict) -> list[dict]:
    """前回までに見た分を除いた「今回はじめて見るもの」だけを返す。
    ここを自分のドメインに置き換える（新着ファイル・新着議事録・新着PR等）。
    空リストを返せば②以降は一切実行されず、LLM呼び出しコストは0になる。"""
    return []  # 例: [{"id": "...", "source_path": "...", "text": "..."}]


# --------------------------------------------------------------- ② 判断
def build_prompt(items: list[dict]) -> str:
    body = "\n\n".join(f"[{i['id']}]\n{i['text'][:2000]}" for i in items)
    return f"""以下の項目それぞれについて判定してください。

【厳守】
{PROMPT_RULE_JA}

【出力】JSON配列のみ。
[{{"id":"...","verdict":"done|open|unknown","quote":"出典から一字一句コピーした引用"}}]

【対象】
{body}
"""


def judge(items: list[dict]) -> list[dict]:
    if not items:
        return []
    raw = run_claude(build_prompt(items), label="loop_template")
    try:
        start, end = raw.index("["), raw.rindex("]") + 1
        return json.loads(raw[start:end])
    except Exception:
        print(f"  JSONの取り出しに失敗: {raw[:200]}")
        return []


# --------------------------------------------------------------- ③ 機械照合
def verify_verdicts(items: list[dict], verdicts: list[dict]) -> list[dict]:
    by_id = {i["id"]: i for i in items}
    accepted = []
    for v in verdicts:
        item = by_id.get(v.get("id"))
        if not item:
            continue
        if v.get("verdict") != "done":
            accepted.append(v)  # done以外は照合不要（何かを主張していないため）
            continue
        ok, why = verify(item["text"], v.get("quote", ""))
        if ok:
            accepted.append(v)
        else:
            print(f"  棄却 [{v.get('id')}]: {why}（quote={v.get('quote','')[:60]!r}）")
    return accepted


# --------------------------------------------------------------- ④+⑤ 実行・記録
def act(verdicts: list[dict], state: dict) -> None:
    for v in verdicts:
        # ここで実際の反映（台帳更新・ファイル書き込み等）を行う。
        # 金銭・対外送信・不可逆な操作は直接やらず、承認ゲート（bridge-framework側）に渡す。
        state.setdefault("seen", []).append(v["id"])


def main() -> None:
    cfg = load_config([])  # 例: [BRIDGE_DIR/".env"]
    state = load_state()

    items = collect_new_items(state)
    if not items:
        print("差分なし。LLMは呼びません。")
        return

    verdicts = judge(items)
    accepted = verify_verdicts(items, verdicts)
    act(accepted, state)
    save_state(state)

    if accepted:
        post_discord(f"loop_template: {len(accepted)}件処理しました",
                     token=cfg.get("DISCORD_TOKEN", ""),
                     channel=cfg.get("DISCORD_CHANNEL_ID", ""))


if __name__ == "__main__":
    main()
