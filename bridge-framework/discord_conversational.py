#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
汎用型FOX — Discord会話ボットの既定装備（2点）

ポーリング方式（Gatewayを張らない）でDiscordボットの会話機能を作ると、
素朴に実装した場合ふつうに抜け落ちる2点。実運用の会話ボットで実際に「抜けている」と
指摘されて足したもの。**次に会話ボットを作るときは、最初からこれを使う。**

  ① 返信/引用への対応 — 質問がどのメッセージへの返信かをLLMに明示する。
     直近履歴のウィンドウ（直近8〜12件など）に入っていない過去の発言に
     返信されると、LLMには何に答えればいいのか分からなくなる。
  ② 入力中インジケータ — claude -p などLLM呼び出しの応答待ちは数秒〜数十秒かかる。
     何も出さないと「動いていない」と誤解される（実際に起きた）。
     Discordの「入力中…」表示は約10秒で消えるので、待っている間ずっと
     出し続ける必要がある。

依存はこのファイル単体（標準ライブラリのみ）。呼び出し元が持つ
Discord REST呼び出し関数（`call(method, path, body=None) -> dict`、
`urllib`でBot Token認証を付けてJSONを返す関数）を渡して使う。
"""
from __future__ import annotations

import threading
from typing import Callable, Optional


def referenced_content(call: Callable, channel_id: str, msg: dict,
                       bot_label: str = "(bot)", max_len: int = 500) -> Optional[str]:
    """msgがDiscordの「返信」機能で特定のメッセージに返信しているなら、
    その本文を取って返す。返信でなければ None。

    call: (method, path, body=None) -> dict|None の形のDiscord REST呼び出し関数。
    bot_label: 引用元がボット自身の発言だったときの表示名。
    """
    ref = (msg.get("message_reference") or {}).get("message_id")
    if not ref:
        return None
    try:
        r = call("GET", f"/channels/{channel_id}/messages/{ref}")
    except Exception:
        return None
    if not r:
        return None
    author = r.get("author") or {}
    who = bot_label if author.get("bot") else (
        author.get("global_name") or author.get("username") or "?")
    body = (r.get("content") or "").strip()
    return f"{who}: {body[:max_len]}" if body else None


def quoted_block(text: Optional[str], label: str = "返信/引用している元の発言") -> str:
    """referenced_content()の結果を、プロンプトに埋め込む用のブロックに整形する。
    無ければ空文字（プロンプトのテンプレートに無条件で埋め込んでも崩れない）。"""
    return f"\n【{label}】\n{text}\n" if text else ""


class Typing:
    """with構文で使う。LLM呼び出しの応答待ちの間、Discordの「入力中…」を
    8秒おきに出し続ける（Discordの入力中表示は約10秒で消えるため）。
    失敗しても本処理は止めない（表示できないだけで会話自体は続けてよい）。

    使い方:
        with Typing(call, channel_id):
            result = subprocess.run([...claude -p...], ...)
    """

    def __init__(self, call: Callable, channel_id: str, interval: float = 8.0):
        self.call = call
        self.channel_id = channel_id
        self.interval = interval
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, daemon=True)

    def _loop(self):
        while not self._stop.is_set():
            try:
                self.call("POST", f"/channels/{self.channel_id}/typing")
            except Exception:
                pass
            self._stop.wait(self.interval)

    def __enter__(self):
        self._thread.start()
        return self

    def __exit__(self, *exc):
        self._stop.set()
