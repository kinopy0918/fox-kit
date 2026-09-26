#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
汎用型FOX — 引用の機械照合（"唯一の嘘よけ"）

自律ループにLLMで判断させるとき、「終わった」「決まった」のような重い判定は
**LLMの申告を鵜呑みにしない**。判定には出典ファイルからの引用を必須にし、
その引用が本当に出典に存在するかをこの関数で機械照合する。存在しなければ、
その場で判定を棄却する（＝でっち上げが通らない）。

mini の fox-loops（task_close.py / meeting_agent.py）で実運用中のロジックを
そのまま抜き出したもの。抜粋を「…」でつないで渡す運用に合わせ、引用が
その境目をまたいでいてもフラグメントごとに照合する。

使い方:
    ok, why = verify(source_text, quote)
    if not ok:
        # 判定を棄却する。ここを飛ばすとでっち上げが素通りする。
        continue
"""
from __future__ import annotations

import re

_WS_RE = re.compile(r"\s+")
_SPLIT_RE = re.compile(r"…+|\.{3,}|\n\s*\n")


def _norm(s: str) -> str:
    """空白の差でズレて不一致にならないよう正規化する。"""
    return _WS_RE.sub("", s or "")


def verify(source_text: str, quote: str, min_len: int = 6) -> tuple[bool, str]:
    """quote が source_text に実在するかを確かめる。

    source_text: LLMに読ませた出典の生テキスト（ファイル内容・議事録本文など）。
    quote: LLMが判定の根拠として挙げた引用。「…」で複数箇所をつないでいてもよい
           （フラグメントに分割し、それぞれが出典に存在するかを見る）。
    min_len: これより短い引用は「引用になっていない」として不合格にする
             （空文字や1〜2文字だと何にでも一致してしまうため）。

    返り値: (合格したか, 不合格なら理由)
    """
    if not source_text or not quote:
        return False, "出典または引用が空"

    frags = [_norm(x) for x in _SPLIT_RE.split(quote) if _norm(x)]
    if not frags or any(len(f) < min_len for f in frags):
        return False, "引用が短すぎる"

    hay = _norm(source_text)
    missing = [f for f in frags if f not in hay]
    return (not missing), ("" if not missing else "引用が出典に無い")


def quote_exists(quote: str, haystack: str, min_len: int = 6) -> bool:
    """verify() の簡易版。合否だけが要るとき用（meeting_agent.py と同じ形）。"""
    ok, _ = verify(haystack, quote, min_len=min_len)
    return ok


# ---------------------------------------------------------------------------
# LLMへの指示に必ず添えるべき文面（コピーして使う）
# ---------------------------------------------------------------------------
PROMPT_RULE_JA = """- 判定には出典ファイルのパスと、根拠になった一文をそのまま引用すること。
- quote は出典に**実在する文字列**を一字一句コピーすること。要約や言い換えは禁止。
- 前後の事情からの推測で判定しない。quote 自体がその判定を裏付けていること。
- 引用はこちらで機械照合する。出典に存在しない引用を書いた判定はその場で棄却される
  （＝でっち上げても通らない）。存在しないなら判定を出さず、不明のままにすること。"""
