#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
汎用型FOX — ループ共通ライブラリ

「プロンプトを書くな、ループを設計しろ」を自律ループとして実装するための土台。
mini の fox-loops/common.py（実運用15ループ）から、会社名・vaultパス・特定チャンネルID
に依存しない部分だけを抜き出したもの。中身のループ（会議同期・コードレビュー等）は
含まない——それは現場ごとに書く「実」であって、この種のものではない。

使う前に、下の CONFIG を自分の環境に合わせて埋める（環境変数 or 直接編集）。
"""
from __future__ import annotations

import getpass
import json
import os
import time
import subprocess
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# 設定（環境変数優先。無ければここのデフォルト）
# ---------------------------------------------------------------------------
HOME = Path.home()
CLAUDE_BIN = os.getenv("CLAUDE_BIN", "/opt/homebrew/bin/claude")
TZ = timezone(timedelta(hours=int(os.getenv("LOOP_TZ_OFFSET_HOURS", "9"))))

# vaultを使うループだけ設定する（使わないなら空のままでよい）
VAULT = Path(os.environ["LOOP_VAULT"]) if os.environ.get("LOOP_VAULT") else None


def _read_env_file(path: Path) -> dict:
    out = {}
    try:
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            out[k.strip()] = v.strip().strip('"').strip("'")
    except Exception:
        pass
    return out


def load_config(env_files: list[Path] | None = None) -> dict:
    """複数の .env を後勝ちで統合する。秘密情報を二重管理しないための共通口。
    例: load_config([BRIDGE_DIR/".env", LOOPS_DIR/"loops.env"])"""
    cfg: dict = {}
    for p in (env_files or []):
        cfg.update(_read_env_file(p))
    return cfg


# ---------------------------------------------------------------------------
# 単一書き手の関所
# ---------------------------------------------------------------------------
# 同じ台帳・状態ファイルを複数の機械から書けるようにすると、
# 「どこまでやったか」の記録が枝分かれし、同じ処理を二度実行してしまう
# （投稿なら二重投稿、タスク完了なら二重クローズ）。
# 書き手を1台に固定し、それ以外では起動時に止める。
#
# ★止め方は「違うと分かったときだけ止める」。判定に自信が無いときは通す
# （fail-closed にすると、判定を間違えた瞬間に本来動くはずの常駐が全部止まる。
#   それはデータが取れなくなる方の事故で、二重実行より重い）。
def enforce_single_writer(allowed_users: set[str], allow_env: str = "LOOP_ALLOW_SECONDARY") -> None:
    """呼び出し元スクリプトの先頭で呼ぶ。書き手として許可された機械以外では例外で止める。"""
    if getpass.getuser() in allowed_users:
        return
    if os.environ.get(allow_env) == "1":
        return
    raise SystemExit(
        f"この機械では実行しません（書き手は {sorted(allowed_users)} だけ）。\n"
        f"台帳が枝分かれして同じ処理を二度走らせるおそれがあるため止めています。\n"
        f"読むだけ／どうしても必要なときは {allow_env}=1 を付ける。"
    )


# ---------------------------------------------------------------------------
# Discord 投稿（ボットトークン + REST。Webhookにも対応）
# ---------------------------------------------------------------------------
def post_discord(text: str, token: str, channel: str, prefix: str = "") -> bool:
    """Discordチャンネルへ投稿。2000字制限に合わせて分割送信。
    channel が https:// で始まるときはWebhook宛て（ボットが居ないサーバー向け）。"""
    hook = channel.startswith("https://")
    if not channel or (not hook and not token):
        print("[discord] token/channel 未設定 → 送信スキップ")
        return False

    text = (prefix + text) if prefix else text
    ok = True
    for chunk in _chunks(text, 1900):
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "portable-fox-loops (loop-framework)",
        }
        if not hook:
            headers["Authorization"] = f"Bot {token}"
        req = urllib.request.Request(
            channel if hook else f"https://discord.com/api/v10/channels/{channel}/messages",
            data=json.dumps({"content": chunk}).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                r.read()
        except Exception as e:
            print(f"[discord] 送信失敗: {e}")
            ok = False
    return ok


def _chunks(text: str, size: int):
    text = text or "(空)"
    for i in range(0, len(text), size):
        yield text[i:i + size]


# ---------------------------------------------------------------------------
# Slack 投稿（Bot Token + REST）
# ---------------------------------------------------------------------------
def _slack_api(method: str, payload: dict, token: str) -> dict:
    req = urllib.request.Request(
        f"https://slack.com/api/{method}",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def post_slack(channel: str, text: str, token: str, blocks: list | None = None) -> bool:
    """Slackチャンネルへ投稿。未参加チャンネル(not_in_channel)なら自動joinして再送。
    blocksが原因で弾かれたら素のテキストで再送（沈黙で消えないように）。"""
    if not token:
        print("[slack] token 未設定 → 送信スキップ")
        return False
    payload = {"channel": channel, "text": text[:3000],
               "unfurl_links": False, "unfurl_media": False}
    if blocks:
        payload["blocks"] = blocks
    try:
        res = _slack_api("chat.postMessage", payload, token)
        if not res.get("ok") and res.get("error") == "not_in_channel":
            join = _slack_api("conversations.join", {"channel": channel}, token)
            if join.get("ok"):
                res = _slack_api("chat.postMessage", payload, token)
        if not res.get("ok") and blocks:
            res = _slack_api("chat.postMessage", {
                "channel": channel, "text": text[:3900],
                "unfurl_links": False, "unfurl_media": False}, token)
        if not res.get("ok"):
            print(f"[slack] 送信失敗: {res.get('error')}")
            return False
        return True
    except Exception as e:
        print(f"[slack] 送信失敗: {e}")
        return False


# ---------------------------------------------------------------------------
# claude -p ヘッドレス実行（コスト最適化つき）
# ---------------------------------------------------------------------------
# 用途別にモデルを使い分ける。既定は軽いモデル（要約・整理・トリアージ）、
# 判断やコード生成が要るときだけ明示的に強いモデルへ上げる。
# ★モデルIDは時間とともに変わる。使う直前に `claude --help` 等で現行のエイリアスを確認すること。
MODEL_LIGHT = os.getenv("LOOP_MODEL_LIGHT", "")   # 例: 軽量モデルのID
MODEL_JUDGE = os.getenv("LOOP_MODEL_JUDGE", "")   # 例: 判断・コードレビュー向け
MODEL_HEAVY = os.getenv("LOOP_MODEL_HEAVY", "")   # 例: 必要時のみ明示


_RETRYABLE_STATUS = {429, 500, 502, 503, 529}
_RETRYABLE_HINTS = ("overloaded", "rate limit", "rate_limit",
                    "timeout", "timed out", "connection", "503", "502")


def _is_transient_failure(stdout: str, stderr: str) -> bool:
    """claude CLIの失敗出力が「一時的（リトライで回復しうる）」かを判定。"""
    blob = ((stdout or "") + "\n" + (stderr or "")).lower()
    try:
        data = json.loads(stdout)
        st = data.get("api_error_status")
        if isinstance(st, int):
            return st in _RETRYABLE_STATUS
        if data.get("is_error") and data.get("duration_api_ms") == 0:
            return True  # APIに到達する前に落ちた＝ローカル都合。引き直す価値がある
    except Exception:
        pass
    return any(h in blob for h in _RETRYABLE_HINTS)


def run_claude(prompt: str, cwd: Path | None = None, timeout: int = 900,
              model: str = "", label: str = "claude",
              retries: int = 3, cost_log: Path | None = None,
              now_fn=None) -> str:
    """claude -p をヘッドレスで実行し、最終テキストを返す。
    bypassPermissionsで無人実行するので、**このマシンで確認なく作業してよい前提**が要る
    （個人の作業機で使う。共有機・本番環境ではmodeを見直す）。
    retries: 一時的API障害（529 Overloaded等）の再試行回数。指数バックオフ(15s,30s,60s...)。"""
    cmd = [CLAUDE_BIN, "-p", prompt, "--permission-mode", "bypassPermissions",
           "--output-format", "json"]
    if model:
        cmd += ["--model", model]

    last_err = ""
    for attempt in range(retries + 1):
        try:
            proc = subprocess.run(cmd, cwd=str(cwd or HOME),
                                  capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            return f"⏱ タイムアウト（{timeout}秒）"

        failed = proc.returncode != 0
        if not failed:
            try:
                failed = bool(json.loads(proc.stdout).get("is_error"))
            except Exception:
                failed = False

        if not failed:
            try:
                data = json.loads(proc.stdout)
                if cost_log is not None:
                    _log_cost(cost_log, label, model, data, now_fn)
                return data.get("result", "(空の応答)")
            except Exception:
                return proc.stdout[:4000] or "(空の応答)"

        last_err = (proc.stderr or proc.stdout or "")
        if attempt < retries and _is_transient_failure(proc.stdout, proc.stderr):
            time.sleep(min(120, 15 * (2 ** attempt)))
            continue
        break

    return f"⚠️ claude 実行エラー: {last_err[:1500]}"


def _log_cost(cost_log: Path, label: str, model: str, data: dict, now_fn) -> None:
    try:
        cost = data.get("total_cost_usd")
        u = data.get("usage", {}) or {}
        ts = (now_fn() if now_fn else datetime.now(TZ)).isoformat(timespec="seconds")
        line = (f"{ts}\t{label}\t{model}\t${cost}\tin={u.get('input_tokens')}\t"
                f"out={u.get('output_tokens')}\tturns={data.get('num_turns')}\n")
        with cost_log.open("a", encoding="utf-8") as f:
            f.write(line)
    except Exception as e:
        print(f"[cost] 記録失敗: {e}")


def now_local() -> datetime:
    return datetime.now(TZ)


def today_str() -> str:
    return now_local().strftime("%Y-%m-%d")
