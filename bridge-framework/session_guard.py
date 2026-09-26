#!/usr/bin/env python3
"""claude -p を継ぎ足しで使うボットに、必ず入れる安全弁。

**FOXコピーの標準部品。** この仕組みを他の会社・他の人に配るとき、ボットを新しく
書くなら、このファイルを隣に置いて import すること。依存パッケージは無い。

なぜ要るか（全部、実際に起きた事故）:

1. 2026-06-27 会話の記録が1.9MBまで育ち、claude が実行中に自分で要約を始めた。
   その要約が「言っていない指示」を作り、エージェントはそれに従って動いた。
2. 2026-07-04 会話が切り替わった直後は届くのが最後の1通だけになり、
   やっていない作業を「やった」と答えた。
3. 2026-09-05 使用量の上限に当たったのに、claude は理由を stderr に書かない。
   ボットは「⚠️ エラー:」とだけ返し、原因が誰にも分からなかった。

対策:

1. `should_resume()` … 育ちすぎた／間が空きすぎた会話は継がない
2. 継がないと決めたら、**呼ぶ側が**直前のやりとりを本文の前に付ける（命綱）。
   ここは Discord/Slack など入口ごとに違うので、この部品には入れていない。
3. `claude_error()` … 失敗の理由を stdout の JSON から取る
"""
from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path

# 会話の記録がこのバイト数を超えたら継がない。1.5MB は「事故が起きた1.9MBより下で、
# いちばん長く会話が続く」ところ。小さくすると記憶が頻繁に切れる。
MAX_SESSION_BYTES = int(os.getenv("MAX_SESSION_BYTES", "1500000"))
# この秒数だけ間が空いたら、続きではなく新しい話として始める（既定6時間）
IDLE_RESET = int(os.getenv("IDLE_RESET_SECONDS", "21600"))

# claude は失敗の理由を stderr ではなく stdout の JSON（result）に書く。
LIMIT_RE = re.compile(r"usage limit|session limit|rate limit|上限に達し")
RESETS_RE = re.compile(r"resets ([^\n·]+)")


def claude_error(r) -> str:
    """`claude -p` が失敗したときの、人が読める理由。

    r は subprocess.run の戻り値。**stdout を先に見る**のが要点で、
    stderr だけ読むと理由が空になり、原因の分からないエラーになる。
    """
    try:
        msg = (json.loads(getattr(r, "stdout", "") or "{}").get("result") or "").strip()
    except (json.JSONDecodeError, AttributeError):
        msg = ""
    return msg or (getattr(r, "stderr", "") or "").strip()


def limit_note(err: str) -> str | None:
    """使用量の上限なら、そのまま人に見せられる日本語。違うなら None。

    上限は不具合ではないので、**会話のID（session_id）を捨ててはいけない**。
    捨てて新規で取り直しても同じように弾かれ、回復したあと話が繋がらなくなる。
    """
    if not LIMIT_RE.search(err or ""):
        return None
    when = RESETS_RE.search(err)
    return ("⚠️ Claudeの使用量が上限に当たっていて、いまは答えられません。"
            + (f"\n**{when.group(1).strip()} に回復します。**" if when else "")
            + f"\n（{err[:160]}）")


def transcript_size(sid: str) -> int:
    """その会話の記録が何バイトか。置き場所を組み立てず glob で確実に引き当てる。"""
    if not sid:
        return 0
    try:
        return max((f.stat().st_size for f in
                    Path.home().glob(f".claude/projects/*/{sid}.jsonl")), default=0)
    except OSError:
        return 0


def should_resume(sid: str | None, ts: float = 0, label: str = "",
                  log=print) -> bool:
    """この会話を継いでよいか。継がないときは理由を1行残す。

    ts は最後に話した時刻（epoch秒）。0なら間隔の判定はしない。
    """
    if not sid:
        return False
    if ts and time.time() - ts > IDLE_RESET:
        log(f"!! {label or sid}: {int((time.time() - ts) / 3600)}時間ぶりなので"
            "新しい会話にします")
        return False
    size = transcript_size(sid)
    if size > MAX_SESSION_BYTES:
        log(f"!! {label or sid}: 会話が {size // 1000}KB まで育ったので切り替えます"
            f"（上限 {MAX_SESSION_BYTES // 1000}KB・自動要約による作り話を防ぐため）")
        return False
    return True


if __name__ == "__main__":                      # 自己診断: python3 session_guard.py
    class _R:
        stdout = json.dumps({"is_error": True,
                             "result": "You've hit your session limit "
                                       "· resets 11:50pm (Asia/Tokyo)"})
        stderr = ""
    assert claude_error(_R()).startswith("You've hit"), "stdout から理由を取れていない"
    assert "11:50pm" in (limit_note(claude_error(_R())) or ""), "回復時刻が出ていない"
    assert limit_note("No conversation found") is None, "上限でないものを上限にしている"
    assert should_resume(None) is False
    assert should_resume("x" * 36, ts=time.time() - IDLE_RESET - 1) is False, "放置の判定"
    assert should_resume("存在しないID", ts=time.time()) is True, "無害な会話まで切っている"
    print("session_guard: 全部通りました "
          f"(上限 {MAX_SESSION_BYTES // 1000}KB / 放置 {IDLE_RESET // 3600}時間)")
