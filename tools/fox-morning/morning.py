#!/usr/bin/env python3
"""秘書とつながる（最初の「分かったこと」）と、毎朝のまとめ。標準ライブラリだけ。

  python3 morning.py discover          予定とメールを読んで「分かったこと」を ~/.config/fox-kit/meet.json へ
  python3 morning.py run               毎朝のまとめを作る（保存先＋Mac の通知・リマインダー＋つないでいれば Discord/Slack）
  python3 morning.py install [HH:MM]   毎朝の予定に登録（既定 8:00）。寝ていたノートPCは、開いたときに1回だけ動く
  python3 morning.py uninstall

予定とメールは claude.ai のコネクタ（Google カレンダー・Gmail）を使う。fox-kit は鍵を預からない。
「分かったこと」を作るときは読むだけの道具しか許さない（予定を作る・消す・送るは使えない）。
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

HOME = Path.home()
HERE = Path(__file__).resolve().parent
CONF = HOME / ".config/fox-kit"
MEET = CONF / "meet.json"
LOG = HOME / "Library/Logs/fox-morning.log"
LABEL = "com.fox-kit.morning"
READ_ONLY = [  # 「分かったこと」で使ってよい道具（読むだけ）
    "mcp__claude_ai_Google_Calendar__list_calendars", "mcp__claude_ai_Google_Calendar__list_events",
    "mcp__claude_ai_Google_Calendar__search_events", "mcp__claude_ai_Google_Calendar__get_event",
    "mcp__claude_ai_Gmail__search_threads", "mcp__claude_ai_Gmail__get_thread",
    "mcp__claude_ai_Gmail__search_messages", "mcp__claude_ai_Gmail__get_message",
]   # ponytail: Gmail の道具名は claude.ai 側の名前に合わせて要確認（未接続で試せていない）
SAY = {"list_events": "予定を読んでいます", "search_events": "予定を探しています", "get_event": "予定の中身を見ています",
       "list_calendars": "カレンダーの一覧を見ています", "search_threads": "メールを読んでいます",
       "get_thread": "メールの中身を見ています", "search_messages": "メールを読んでいます", "get_message": "メールの中身を見ています",
       "ToolSearch": "使える道具を確かめています"}


def claude() -> str:
    return shutil.which("claude", path=f"{HOME}/.local/bin:/opt/homebrew/bin:/usr/local/bin") or str(HOME / ".local/bin/claude")


def say(line: str):
    print("▶ " + line, flush=True)   # 設定画面が最後の「▶ 」行を「いま：」として出す


def wizard() -> dict:
    try:
        return json.loads((CONF / "wizard.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def last_json(text: str) -> dict:
    """返事の最後の { … } を取り出す（前後に文章が付いても読めるように）。"""
    found, i, dec = {}, text.find("{"), json.JSONDecoder()
    while i != -1:
        try:
            obj, end = dec.raw_decode(text, i)
            found, i = obj, text.find("{", end)
        except ValueError:
            i = text.find("{", i + 1)
    return found if isinstance(found, dict) else {}


# ------------------------------------------------------------------ 最初の「分かったこと」
def discover():
    a = wizard().get("answers", {})
    owner = a.get("owner") or "あなた"
    prompt = f"""あなたは {owner} の秘書になったばかりです。つながっている Google カレンダー（過去30日・今後14日）と、
つながっていれば Gmail（直近2週間・多くても50通）を読み、{owner} の仕事の様子をつかんでください。
読むだけにして、予定やメールを作る・変える・送ることはしないでください。

最後に、次の形の JSON だけを出してください（前後に文章を書かない）。
{{"sources": ["calendar" と "gmail" のうち実際に読めたもの],
  "facts": [{{"text": "〜のようです（30字前後）", "why": "根拠：予定やメールから読んだこと（件名や人名の丸写し・金額・住所は書かない）"}}],
  "offers": [{{"label": "押すボタンの文（20字以内・〜します）", "prompt": "押されたときに秘書が実行する依頼文"}}]}}
facts は3〜5個、決めつけず「〜のようです」。offers は {owner} の予定・メールに合わせた、いますぐ数分でできる手伝いを3つ
（例：明日の会議の準備メモ／返事が要るメールの下書き／重なっている予定の洗い出し）。何も読めなかったら facts を空にする。"""
    cmd = [claude(), "-p", "--model", "sonnet", "--output-format", "stream-json", "--verbose", "--permission-mode", "default",
           "--allowedTools", ",".join(READ_ONLY)]
    say("つながっている予定とメールを確かめています")
    t0 = time.time()
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                         encoding="utf-8", errors="replace", cwd=str(HOME))
    p.stdin.write(prompt); p.stdin.close()
    result, cost = "", None
    for line in p.stdout:
        try:
            ev = json.loads(line)
        except ValueError:
            print(line.rstrip()); continue
        if ev.get("type") == "assistant":
            for c in ev.get("message", {}).get("content", []):
                if c.get("type") == "tool_use":
                    say(SAY.get(c.get("name", "").rsplit("__", 1)[-1], "調べています"))
        elif ev.get("type") == "result":
            result, cost = ev.get("result") or "", ev.get("total_cost_usd")
    p.wait()
    say("分かったことをまとめています")
    j = last_json(result)
    facts = [f for f in j.get("facts", []) if isinstance(f, dict) and f.get("text")][:5]
    offers = [o for o in j.get("offers", []) if isinstance(o, dict) and o.get("label") and o.get("prompt")][:3]
    CONF.mkdir(parents=True, exist_ok=True)
    MEET.write_text(json.dumps({"facts": facts, "offers": offers, "sources": j.get("sources", []),
                                "seconds": round(time.time() - t0), "cost_usd": cost, "at": time.strftime("%Y-%m-%d %H:%M")},
                               ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"分かったこと {len(facts)}件・できること {len(offers)}件（{round(time.time() - t0)}秒）")
    if p.returncode != 0 and not facts:
        raise SystemExit("AIから返事がありませんでした")


# ------------------------------------------------------------------ 毎朝のまとめ
def log(*a):
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + " ".join(str(x) for x in a) + "\n")


def run():
    st = wizard()
    a, base = st.get("answers", {}), st.get("data", {}).get("storage", {}).get("base")
    today = time.strftime("%Y-%m-%d")
    out = Path(base or HOME / "Documents") / "毎朝のまとめ" / f"{today}.md"
    if out.exists():
        return log("今日はもう作ってあります", out)   # 起きるたびに重ねて作らない
    goal = a.get("goal")
    prompt = f"""{a.get('owner') or 'あなた'} の、今日（{today}）の1日のまとめを作ってください。
1. 今日の予定と、それぞれの準備（Google カレンダー）
2. 返事が要りそうなメール（Gmail がつながっていれば。直近2日）
3. 覚えている「やり残し」があれば
{'4. 目標「' + goal + '」に向けて、今日やれる小さな一歩を1つ' if goal else ''}
短く、スマホで読める長さ（見出し＋箇条書き）で。今日やることは Mac の「リマインダー」にも1件ずつ入れてください
（osascript。同じ名前が今日すでにあれば入れない）。予定やメールを変える・送ることはしないでください。
最後に1行だけ、通知に出す要約（40字以内）を「通知：」で始めて書いてください。"""
    for i in range(3):   # 起きた直後はネットがまだつながっていないことがある
        r = subprocess.run([claude(), "-p", "--output-format", "json", "--permission-mode", "bypassPermissions"],
                           input=prompt, capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=str(HOME), timeout=900)
        try:
            body = json.loads(r.stdout or "{}").get("result") or ""
        except ValueError:
            body = ""
        if body:
            break
        log("まとめを作れませんでした。", i + 1, "回目", (r.stdout + r.stderr)[-300:])
        time.sleep(300)
    else:
        return notify_mac("毎朝のまとめを作れませんでした。ネットとログインを確かめてください")
    head = re.search(r"^通知[:：]\s*(.+)$", body, re.M)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(f"# {today} のまとめ\n\n" + re.sub(r"^通知[:：].*$", "", body, flags=re.M).strip() + "\n", encoding="utf-8")
    notify_mac(head.group(1) if head else "今日のまとめができました")
    try:   # Discord / Slack につないでいれば、お知らせへ（fox-home と同じ送り方）
        sys.path.insert(0, str(HERE.parent / "fox-home"))
        import home
        home.notify(f"おはようございます。{today} のまとめです\n\n" + out.read_text(encoding="utf-8")[:1800])
    except Exception as e:
        log("お知らせに送れませんでした:", repr(e))
    log("作りました", out)


def notify_mac(text: str):
    log(text)
    subprocess.run(["osascript", "-e", f'display notification {json.dumps(text)} with title "毎朝のまとめ"'], capture_output=True)


# ------------------------------------------------------------------ 毎朝の予定に登録
def install(at: str = "8:00"):
    import plistlib
    h, m = (int(x) for x in at.split(":"))
    py = "/usr/bin/python3" if Path("/usr/bin/python3").exists() else sys.executable
    pl = {"Label": LABEL, "ProgramArguments": [py, str(HERE / "morning.py"), "run"],
          "StartCalendarInterval": {"Hour": h, "Minute": m},   # 寝ていた分は、起きたときに1回だけ動く（StartInterval は飛ぶので使わない）
          "StandardOutPath": str(LOG), "StandardErrorPath": str(LOG),
          "EnvironmentVariables": {"PATH": f"{HOME}/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin",
                                   "HOME": str(HOME), "LANG": "ja_JP.UTF-8"}}
    uninstall()
    f = HOME / "Library/LaunchAgents" / f"{LABEL}.plist"
    f.parent.mkdir(parents=True, exist_ok=True)
    with open(f, "wb") as fh:
        plistlib.dump(pl, fh)
    for _ in range(2):   # bootout の直後は失敗することがあるので1回だけ待つ（fox-home と同じ）
        r = subprocess.run(["launchctl", "bootstrap", f"gui/{os.getuid()}", str(f)], capture_output=True, text=True)
        if r.returncode == 0:
            return print(f"毎朝 {h}:{m:02d} のまとめを登録しました")
        time.sleep(2)
    raise SystemExit("毎朝の予定に登録できませんでした：" + r.stderr[-200:])


def uninstall():
    subprocess.run(["launchctl", "bootout", f"gui/{os.getuid()}/{LABEL}"], capture_output=True)
    (HOME / "Library/LaunchAgents" / f"{LABEL}.plist").unlink(missing_ok=True)


if __name__ == "__main__":
    if sys.argv[1:2] == ["test"]:   # 返事の取り出しだけ確かめる
        assert last_json('はい\n{"facts":[{"text":"a"}]}') == {"facts": [{"text": "a"}]}
        assert last_json('{"a":1} と {"b":{"c":2}}') == {"b": {"c": 2}}
        assert last_json("なし") == {}
        print("ok"); sys.exit()
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    {"discover": discover, "run": run, "uninstall": uninstall}.get(cmd, lambda: None)() if cmd != "install" else install(*sys.argv[2:3])
    if cmd not in ("discover", "run", "install", "uninstall"):
        print(__doc__)
