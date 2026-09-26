#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成物の置き場ガード（PreToolUse: Write|Edit|NotebookEdit）

エージェントが作ったファイルが ~/Desktop・~/Downloads・ホーム直下に
散らばるのを止める。汎用型FOXの標準装備（portable-fox/claude/hooks/）。

止める場所:
  - ~/Desktop 配下
  - ~/Downloads 配下
  - ホーム直下のファイル（ドットファイルは除く）
  - ホーム直下に新しく作業フォルダを生やす行為（許可リスト外の第1階層）

通す場所は下の ALLOWED_TOP を参照。会社・機械ごとの正式な置き場ルールは
CLAUDE.md の「保管先」セクションに書く（このファイルはガードだけを担当し、
個別の会社名・vaultパスは持たない）。
"""
import json
import os
import sys

HOME = os.path.expanduser("~")

# ホーム直下でファイルを置いてよい第1階層。増やすならここに足す。
ALLOWED_TOP = {
    "Projects",      # コードのローカル作業コピー（正本はGitHub）
    "Tools",         # 常駐・実行系ツール
    "dev",           # 作業ツリー
    "Documents", "Movies", "Music", "Pictures", "Public", "Sites",
    "Workspace", "Applications", "Dropbox",
    "Library",       # CloudStorage（Drive）はこの下
}

GUIDE = """置き場ルール:
  文書・資料・データ・コード → CLAUDE.md の「保管先」を見る
  作業中の中間ファイル → セッションのスクラッチパッド
  常駐・実行系ツール → ~/Tools/
秘密情報（APIキー・サービスアカウント鍵）はDriveにもGitHubにも置かない → ~/.config/ """


def verdict(path):
    """ブロックすべきなら理由を返す。問題なければ None。"""
    p = os.path.abspath(os.path.expanduser(path))
    if not p.startswith(HOME + os.sep):
        return None
    rel = p[len(HOME) + 1:]
    parts = rel.split(os.sep)
    top = parts[0]

    if top in ("Desktop", "Downloads"):
        return f"~/{top} は生成物の置き場ではありません（受信箱／一時表示用）。"
    if top.startswith("."):
        return None                       # 設定ファイル類は対象外
    if len(parts) == 1:
        return "ホーム直下にファイルを置かないでください。"
    if top not in ALLOWED_TOP:
        return f"ホーム直下に新しい作業フォルダ ~/{top}/ を作らないでください。"
    return None


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)                       # 判定できないときは通す

    path = (data.get("tool_input") or {}).get("file_path")
    if not path:
        sys.exit(0)

    why = verdict(path)
    if not why:
        sys.exit(0)

    print(json.dumps({
        "decision": "block",
        "reason": f"{why}\n\n{GUIDE}"
    }))
    sys.exit(0)


if __name__ == "__main__":
    main()
