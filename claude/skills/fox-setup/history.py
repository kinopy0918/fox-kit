#!/usr/bin/env python3
"""前に使っていたAIの記録から、持ち主が書いた文だけを集める（初期設定の 0.5 で使う）。

  python3 history.py scan                      何が見つかったかだけ（中身は出さない）
  python3 history.py extract [--max 24000]     持ち主が書いた文を新しい順に、上限の文字数まで

探すのはこのパソコンの中だけ。書き換えない。
- Claude Code : ~/.claude/projects/*/*.jsonl
- Codex       : ~/.codex/sessions/**/*.jsonl
- Gemini CLI  : ~/.gemini/tmp/*/logs.json と ~/.gemini/tmp/*/chats/*.json
- 書き出したファイル（ダウンロード・デスクトップ・書類。OneDrive に移されたものも）:
  ChatGPT の zip / conversations*.json、claude.ai の zip、Google Takeout の Gemini アプリ（JSON）
AIの返事・道具の出力・自動要約・自動ジョブの命令文・初期設定そのものの会話は読まない。
代表的な形式の鍵・メール・電話番号は伏せる。
"""
from __future__ import annotations

import json
import re
import sys
import time
import zipfile
from pathlib import Path

HOME = Path.home()
PER_MSG = 300
MAX_FILE = 300 * 1024 * 1024        # これより大きい書き出しファイルは読まない
DEADLINE = time.monotonic() + 240    # 設定画面の会話は1回600秒で打ち切られるので、余裕をもって止める
SECRET = re.compile(
    r"(sk-[\w-]{16,}|sk_(?:live|test)_\w{16,}|rk_live_\w{16,}|xox[abprs]-[\w-]{10,}|gh[pousr]_\w{20,}|github_pat_\w{20,}"
    r"|AIza[\w-]{30,}|AKIA[0-9A-Z]{16}|ya29\.[\w.-]{20,}|secret_\w{20,}|eyJ[\w-]{10,}\.[\w-]{10,}\.[\w-]{10,}"
    r"|[MN][A-Za-z\d]{23,30}\.[\w-]{6}\.[\w-]{27,40}|-----BEGIN [A-Z ]*PRIVATE KEY-----"
    r"|(?i:bearer)\s+[\w.~+/-]{16,}|(?i:password|passwd|pwd)\s*[:=]\s*\S+|パスワード(?:は|：|:)\s*\S+"
    r"|://[^/\s:@]+:[^/\s@]+@|[A-Za-z0-9+/]{120,}={0,2})")
PERSONAL = re.compile(r"([\w.+-]+@[\w-]+\.[\w.-]+|0\d{1,4}-\d{1,4}-\d{3,4}|\+\d{1,3}[ -]?\d{2,4}[ -]?\d{3,4}[ -]?\d{3,4})")
SKIP_START = ("<", "/", "#", "Caveat:", "[Request interrupted", "This session is being continued")
DIRS = ("Downloads", "Desktop", "Documents", "ダウンロード", "デスクトップ", "書類")
PROBLEMS: list[str] = []             # 読めなかったもの（黙って「記録なし」に見せないため）


def late() -> bool:
    return time.monotonic() > DEADLINE


def mtime(p: Path) -> float:
    try:
        return p.stat().st_mtime
    except OSError:
        return 0.0


def day(ts) -> str:
    try:
        if isinstance(ts, (int, float)):
            return time.strftime("%Y-%m-%d", time.localtime(ts)) if ts > 0 else ""
        return str(ts or "")[:10]
    except (OSError, OverflowError, ValueError):
        return ""


def clean(t: str) -> str:
    t = t[:2000].encode("utf-8", "replace").decode("utf-8")          # 壊れた文字を消す・長文で遅くならないよう先に切る
    t = PERSONAL.sub("（伏せました）", SECRET.sub("（鍵は伏せました）", " ".join(t.split())))
    return t[:PER_MSG] + ("…" if len(t) > PER_MSG else "")


def keep(t) -> bool:
    return isinstance(t, str) and bool(t.strip()) and not t.strip().startswith(SKIP_START) and "AGENTS.md" not in t[:200]


def texts(content) -> list[str]:
    if isinstance(content, str):
        return [content]
    return [c["text"] for c in content or [] if isinstance(c, dict) and c.get("type") in ("text", "input_text")
            and isinstance(c.get("text"), str)]


def export_dirs():
    roots = [HOME] + [p for p in HOME.glob("OneDrive*") if p.is_dir()]
    return [r / d for r in roots for d in DIRS if (r / d).is_dir()]


# ------------------------------------------------------------------ Claude Code / Codex
def jsonl_user(path: Path):
    """1つの会話ファイルから持ち主の文。初期設定そのものの会話なら None"""
    out = []
    with open(path, encoding="utf-8", errors="replace") as f:
        for i, ln in enumerate(f):
            if i < 40 and ("fox-setup" in ln or "history.py" in ln):
                return None
            if '"user"' not in ln:
                continue
            try:
                j = json.loads(ln)
            except ValueError:
                continue
            if not isinstance(j, dict) or j.get("entrypoint") == "sdk-cli" or any(
                    j.get(k) for k in ("isMeta", "isCompactSummary", "isSidechain", "isVisibleInTranscriptOnly")):
                continue
            m = None
            if j.get("type") == "user" and isinstance(j.get("message"), dict):              # Claude Code
                m = j["message"]
            elif j.get("type") == "response_item" and isinstance(j.get("payload"), dict):     # Codex（新しい形）
                m = j["payload"]
            elif j.get("type") == "message":                                                 # Codex（古い形）
                m = j
            if isinstance(m, dict) and m.get("role") == "user":
                out += [t.strip() for t in texts(m.get("content")) if keep(t)]
    return out


def session_files(base: Path, pattern: str):
    return sorted(base.glob(pattern), key=mtime, reverse=True) if base.is_dir() else []


def sessions(files):
    for f in files:
        if late():
            PROBLEMS.append("時間がかかりすぎたので、途中で読むのをやめました"); return
        try:
            items = jsonl_user(f)
        except OSError as e:
            PROBLEMS.append(f"{f.name}：{e.__class__.__name__}"); continue
        for t in (items or [])[:8]:      # 1つの会話からは最初の8つまで（同じ話が続くため）
            yield f"- [{day(mtime(f))}] {clean(t)}"


# ------------------------------------------------------------------ Gemini CLI
def gemini_cli():
    base = HOME / ".gemini" / "tmp"
    out = set()
    for f in (list(base.glob("*/logs.json")) + list(base.glob("*/chats/*.json"))) if base.is_dir() else []:
        try:
            d = json.loads(f.read_text(encoding="utf-8", errors="replace"))
        except (OSError, ValueError) as e:
            PROBLEMS.append(f"Gemini CLI {f.name}：{e.__class__.__name__}"); continue
        items = d.get("messages", []) if isinstance(d, dict) else d
        for m in items if isinstance(items, list) else []:
            if not isinstance(m, dict) or m.get("type", m.get("role")) != "user":
                continue
            t = m.get("message") or m.get("content") or ""
            if isinstance(t, list):
                t = " ".join(x.get("text", "") for x in t if isinstance(x, dict) and isinstance(x.get("text"), str))
            if keep(t):
                out.add((str(m.get("timestamp") or ""), t.strip()))
    return sorted(out, reverse=True)


# ------------------------------------------------------------------ 書き出したファイル
def read_member(z: zipfile.ZipFile, name: str):
    if z.getinfo(name).file_size > MAX_FILE:
        PROBLEMS.append(f"{name} は大きすぎるので読みませんでした"); return None
    return z.read(name)


def exports():
    """書き出しファイルを (種類, ファイル, 中の名前) で。種類は conv（ChatGPT・claude.ai）/ gemini"""
    found = []
    for d in export_dirs():
        for f in sorted(d.glob("*.zip"), key=mtime, reverse=True)[:200]:
            try:
                with zipfile.ZipFile(f) as z:
                    names = z.namelist()
            except (zipfile.BadZipFile, OSError) as e:
                if any(k in f.name.lower() for k in ("takeout", "chatgpt", "claude", "export")):
                    PROBLEMS.append(f"{f.name}：開けませんでした（{e.__class__.__name__}）")
                continue
            conv = [n for n in names if Path(n).name.startswith("conversations") and n.endswith(".json")]
            gem = [n for n in names if n.endswith(".json") and "Gemini" in n and ("MyActivity" in n or "マイアクティビティ" in n)]
            if conv:
                found.append(("conv", f, conv))
            if gem:
                found.append(("gemini", f, gem[:1]))
        for f in sorted(list(d.glob("conversations*.json")) + list(d.glob("*/conversations*.json")), key=mtime, reverse=True)[:5]:
            found.append(("conv", f, None))
    return sorted(found, key=lambda x: mtime(x[1]), reverse=True)


def load_json(f: Path, names):
    if names is None:
        if f.stat().st_size > MAX_FILE:
            PROBLEMS.append(f"{f.name} は大きすぎるので読みませんでした"); return []
        return [json.loads(f.read_bytes().decode("utf-8", "replace"))]
    out = []
    with zipfile.ZipFile(f) as z:
        for n in names:
            b = read_member(z, n)
            if b is not None:
                out.append(json.loads(b.decode("utf-8", "replace")))
    return out


def conv_lines(data):
    """ChatGPT（mapping）と claude.ai（chat_messages）の両方を読む。(種類, 行の一覧)"""
    titles, msgs, kind = [], [], None
    for convs in data:
        for c in convs if isinstance(convs, list) else []:
            if not isinstance(c, dict):
                continue
            if "mapping" in c:
                kind = kind or "ChatGPT"
                if c.get("title"):
                    titles.append((c.get("create_time") or 0, c["title"]))
                for node in (c.get("mapping") or {}).values():
                    m = (node or {}).get("message") or {}
                    if (m.get("author") or {}).get("role") == "user":
                        t = " ".join(p for p in (m.get("content") or {}).get("parts") or [] if isinstance(p, str))
                        if keep(t):
                            msgs.append((m.get("create_time") or 0, t))
            elif "chat_messages" in c:
                kind = kind or "claude.ai"
                if c.get("name"):
                    titles.append((c.get("created_at") or "", c["name"]))
                for m in c.get("chat_messages") or []:
                    if isinstance(m, dict) and m.get("sender") == "human" and keep(m.get("text")):
                        msgs.append((m.get("created_at") or "", m["text"]))
    titles.sort(key=lambda x: str(x[0]), reverse=True); msgs.sort(key=lambda x: str(x[0]), reverse=True)
    lines = [f"- 題名：{clean(t)}" for _, t in titles[:150]] + [f"- [{day(ts)}] {clean(t)}" for ts, t in msgs]
    return kind, lines


def gemini_lines(data):
    out = []
    for d in data:
        for e in d if isinstance(d, list) else []:
            t = (e.get("title") or "").strip() if isinstance(e, dict) else ""
            if t.startswith("Prompted "):
                t = t[len("Prompted "):]
            elif t.startswith(("Used ", "Gave feedback", "使用", "フィードバック")):
                continue
            if keep(t):
                out.append((str(e.get("time") or ""), t))
    return [f"- [{day(ts)}] {clean(t)}" for ts, t in sorted(out, reverse=True)]


# ------------------------------------------------------------------ 集める
def collect(cap: int):
    """種類ごとに (見出し, 行の一覧)。どの種類も cap 文字分まで先に取っておく"""
    def take(it):
        out, n = [], 0
        for x in it:
            if n > cap:
                break
            out.append(x); n += len(x) + 1
        return out

    got = []
    for name, get in (("Claude Code（新しい会話から）", lambda: sessions(session_files(HOME / ".claude" / "projects", "*/*.jsonl"))),
                      ("Codex（新しい会話から）", lambda: sessions(session_files(HOME / ".codex" / "sessions", "**/*.jsonl"))),
                      ("Gemini CLI（新しい順）", lambda: (f"- [{day(ts)}] {clean(t)}" for ts, t in gemini_cli()))):
        try:
            lines = take(get())
        except Exception as e:  # noqa: BLE001  1つの種類が読めなくても、ほかの種類は出す
            PROBLEMS.append(f"{name}：{e.__class__.__name__}: {e}"); continue
        if lines:
            got.append((name, lines))
    seen = set()
    for kind, f, names in exports():
        try:
            data = load_json(f, names)
            if kind == "conv":
                k, lines = conv_lines(data)
                label = f"{k or '会話の書き出し'}（{f.name}・新しい順）"
                if not lines:
                    PROBLEMS.append(f"{f.name}：開けましたが、持ち主の文はありませんでした")
            else:
                k, lines, label = "Gemini", gemini_lines(data), f"Gemini アプリ（{f.name}・新しい順）"
        except Exception as e:  # noqa: BLE001
            PROBLEMS.append(f"{f.name}：{e.__class__.__name__}"); continue
        if lines and (k or kind) not in seen:      # 種類ごとに、いちばん新しい書き出しだけ
            seen.add(k or kind); got.append((label, take(lines)))
    return got


def extract(limit: int):
    got = collect(limit)
    if not got:
        print("（前のAIの記録は見つかりませんでした）")
    else:
        # 少ない種類から順に必要なだけ渡し、余りを多い種類へ回す（多い1つで埋まらないように）
        size = {i: sum(len(x) + 1 for x in ls) for i, (_, ls) in enumerate(got)}
        budget, left = {}, limit - 40 * len(got)
        for n, i in enumerate(sorted(size, key=size.get)):
            budget[i] = min(size[i], left // (len(got) - n)); left -= budget[i]
        out = []
        for i, (name, lines) in enumerate(got):
            out.append(f"\n## {name}"); used = 0
            for x in lines:
                if used + len(x) + 1 > budget[i]:
                    break
                out.append(x); used += len(x) + 1
        print("\n".join(out).strip())
    if PROBLEMS:
        print("\n## 読めなかったもの\n" + "\n".join(f"- {p}" for p in PROBLEMS[:10]))


def scan():
    res = {}
    for key, fn in (("claude_code", lambda: session_files(HOME / ".claude" / "projects", "*/*.jsonl")),
                    ("codex", lambda: session_files(HOME / ".codex" / "sessions", "**/*.jsonl"))):
        try:
            fs = fn()
            ts = [t for t in map(mtime, fs) if t]
            res[key] = {"sessions": len(fs), "period": f"{day(min(ts))}〜{day(max(ts))}" if ts else ""}
        except Exception as e:  # noqa: BLE001
            res[key] = {"error": f"{e.__class__.__name__}: {e}"}
    try:
        res["gemini_cli"] = len(gemini_cli())
    except Exception as e:  # noqa: BLE001
        res["gemini_cli"] = {"error": str(e)}
    try:
        res["exports"] = [str(f) for _, f, _ in exports()][:5]
    except Exception as e:  # noqa: BLE001
        res["exports"] = {"error": str(e)}
    res["skipped"] = PROBLEMS[:10]
    print(json.dumps(res, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")   # Windows（cp932）で絵文字が落ちないように
    except (AttributeError, ValueError):
        pass
    import argparse
    ap = argparse.ArgumentParser(description="前に使っていたAIの記録から、持ち主が書いた文だけを集める")
    ap.add_argument("cmd", choices=["scan", "extract"])
    ap.add_argument("--max", type=int, default=24000, help="出す文字数の上限（既定 24000。Bash の出力は約3万字で切られる）")
    a = ap.parse_args()
    if a.cmd == "scan":
        scan()
    else:
        extract(max(2000, a.max))
