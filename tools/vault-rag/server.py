#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
vault-rag MCP サーバ（fox-kit）— どのセッションからでも保存先を「意味」で引けるようにする

  - vault_search: 言い換えに強い。「子ども連れが来られる喫茶店」→ キッズカフェの調査ノート。
                  何が書いてあったか本文が欲しいとき。
  - 目次（_全体の目次.md → 各フォルダの _目次.md）: 場所の見当がつくときはこちらが速い。
"""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

from mcp.server.fastmcp import FastMCP

import rag

mcp = FastMCP("vault-rag")


@mcp.tool()
def vault_search(question: str, k: int = 5) -> str:
    """vault のノートを意味で検索する（言葉が一致しなくても引ける）。

    Args:
        question: 自然文の質問。ノートに書かれている用語と違う言い方でよい。
        k: 返す抜粋の数（既定5・多くても10程度に）。
    """
    try:
        return rag.format_hits(rag.search(question, k=max(1, min(k, 20))))
    except Exception as e:
        return f"検索に失敗しました: {e}"


@mcp.tool()
def vault_rag_stats() -> str:
    """索引の規模と最終更新を返す（索引が古い・空のときの切り分け用）。"""
    import datetime
    try:
        vecs, meta = rag.load_index()
        files = {m["file"] for m in meta}
        when = "不明"
        if rag.INDEX.exists():
            when = datetime.datetime.fromtimestamp(
                rag.INDEX.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
        return (f"chunk {len(meta)}件 / ノート {len(files)}本 / "
                f"次元 {vecs.shape[1] if len(vecs) else 0} / 索引の更新 {when}")
    except Exception as e:
        return f"統計を取得できません: {e}"


if __name__ == "__main__":
    mcp.run()
