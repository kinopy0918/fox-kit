#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fox-kit check — 会社でAIを使う前の「入国審査」9項目のうち、このパソコンで確かめられる分を点検する。

○＝大丈夫 / △＝人が確かめる・使い方しだい / ×＝直したほうがいい
パソコンの外（契約の種類・学習の設定・会社の取り決め）は見に行けないので、確かめ方だけ出す。
くわしい理由は docs/AI入国審査_9項目.md。
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

HOME = Path.home()
SETTINGS = HOME / ".claude" / "settings.json"
HOOKS = HOME / ".claude" / "hooks"


def run(*cmd: str) -> str:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=30,
                              encoding="utf-8").stdout
    except Exception:
        return ""


def settings() -> dict:
    try:
        return json.loads(SETTINGS.read_text(encoding="utf-8"))
    except Exception:
        return {}


def main() -> None:
    s = settings()
    rows: list[tuple[str, str, str]] = []

    # 1. 行き先：読ませる場所を絞っているか
    cwd = Path.cwd()
    risky = cwd in (HOME, HOME / "Downloads", HOME / "Desktop")
    rows.append(("1 行き先", "△" if risky else "○",
                 f"いまの起動場所 {cwd}。AIはここから下を読める。ダウンロード・デスクトップに仕事の資料や知らないファイルを置きっぱなしにしない"
                 if risky else "作業用のフォルダで起動しています"))

    # 2. 学習：個人プランは本人の設定しだい（CLIからは見えない）
    rows.append(("2 学習", "△",
                 "個人プラン（Pro/Max）は claude.ai/settings/data-privacy-controls で"
                 "「Claude の改善に協力する（Help improve Claude）」をオフに。オンだと会話は学習に使われ5年残る"))

    # 3. 記録：手元の会話記録（暗号化されずに残る）の日数
    days = s.get("cleanupPeriodDays", 30)
    rows.append(("3 手元の記録", "○" if days <= 14 else "△",
                 f"会話の記録は ~/.claude/projects に暗号化されずに{days}日残る"
                 + ("" if days <= 14 else "（fox-kit update で14日に）")))

    # 4. ログインと権限
    auth = run("claude", "auth", "status")
    logged = '"loggedIn": true' in auth
    bypass = s.get("permissions", {}).get("defaultMode") == "bypassPermissions"
    rows.append(("4 ログイン", "○" if logged else "×",
                 "ログイン済み。会社で使うなら会社の契約（Team/Enterprise）のアカウントか確かめる"
                 if logged else "ログインしていません"))
    rows.append(("4 権限", "△" if bypass else "○",
                 "確認なしで実行する設定（キットの既定）。お金・送信・削除は人に確かめる作法と見張りで止めている"
                 if bypass else "実行の前に確認が出る設定です"))

    # 5. 暗号化：サーバー側はAES-256/TLS1.2+。パソコン側はFileVault
    fv = run("fdesetup", "status")
    on = "FileVault is On" in fv
    rows.append(("5 暗号化", "○" if on else "×",
                 "FileVault はオン" if on else
                 "FileVault がオフ。パソコンを盗まれると会話の記録が読める（システム設定→プライバシーとセキュリティ→FileVault）"))

    # 6〜8. 第三者の認証・委託先・事故のときの約束は契約の話
    rows.append(("6-8 契約", "△",
                 "外部監査・委託先・漏えい時の連絡は会社向け契約（Team/Enterprise・API）の取り決めにある。"
                 "個人プランは対象外。trust.anthropic.com で確かめる"))

    # 9. AI特有：連携ツール・見張り
    mcp = [l.split(": ")[0] for l in run("claude", "mcp", "list").splitlines()
           if ": " in l and not l.startswith("Checking")]
    guards = [h for h in ("block-dangerous-ops.py", "block-secret-commit.py",
                          "guard-output-location.py") if (HOOKS / h).exists()]
    rows.append(("9 連携ツール", "△",
                 f"つないでいる連携 {len(mcp)}個：{', '.join(mcp) or 'なし'}。知らない物は claude mcp remove <名前>"))
    rows.append(("9 見張り", "○" if len(guards) == 3 else "×",
                 f"危ない操作・秘密の持ち出し・置き場の見張り {len(guards)}/3 が入っています"))

    print("AI入国審査（このパソコンで確かめられる分）\n")
    for name, mark, note in rows:
        print(f"{mark} {name}\n    {note}")
    bad = sum(m == "×" for _, m, _ in rows)
    print(f"\n× {bad}件・△ {sum(m == '△' for _, m, _ in rows)}件。"
          "くわしくは https://github.com/kinopy0918/fox-kit/blob/main/docs/AI入国審査_9項目.md")


if __name__ == "__main__":
    main()
