#!/usr/bin/env python3
"""Stop/Notificationフック：音を「左のセッションの色」と連動させる。

  終わった（オレンジ）   → Glass   本当に手が離れたときだけ
  許可待ち（青）         → Ping    Notification(permission_prompt) から呼ばれる

なぜ要るか（2026-10-12）: 音が鳴ったのにオレンジにならないことがあった。
拡張機能がオレンジにするのは「作業中→待機」に変わったとき。ずれの正体は3つ:
  1. 裏でサブエージェント/バックグラウンド処理を待っている間もターンは終わる → Stopは鳴る、
     拡張機能はまだ作業中扱い。→ 未回収の裏作業があれば鳴らさない（戻ってきた最後の回で鳴る）
  2. ターミナルや `claude -p`（常駐スクリプト）でも鳴っていた＝左に出ないセッション
最終的な決め手: 拡張機能が未読(オレンジ)を state.vscdb の sessionUnread に書くので、
  Stop後に最大8秒それを見て、載ったときだけ鳴らす＝音とオレンジが必ず一致する。
  上の1〜2はその前の足切り（見えているタブは載らないので鳴らない）。
記録: ~/.cache/fox-chime/log
音を変える: 環境変数 FOX_CHIME_DONE / FOX_CHIME_PERM（.aiff のパス）。FOX_CHIME=off で無音。
"""
import json, os, re, subprocess, sys, time

LOG = os.path.expanduser("~/.cache/fox-chime/log")
WIN = os.name == "nt"
# Windows は .wav のパス、無ければ Windows の「一般の警告音」系の名前で鳴らす
DONE_SOUND = os.environ.get("FOX_CHIME_DONE") or ("SystemAsterisk" if WIN else "/System/Library/Sounds/Glass.aiff")
PERM_SOUND = os.environ.get("FOX_CHIME_PERM") or ("SystemExclamation" if WIN else "/System/Library/Sounds/Ping.aiff")

# どれも「文の先頭」でだけ判定する（画面に出した他セッションの記録を読み違えないため）
LAUNCH = re.compile(r"\s*Async agent launched successfully.*?agentId:\s*(\w+)", re.S)
BG_BASH = re.compile(r"\s*Command running in background with ID:\s*(\w+)")
RESUME = re.compile(r'\s*\{"success":\s*true,\s*"message":\s*"Resuming agent[^}]*?"resumedAgentId":\s*"(\w+)"')
NOTIF = re.compile(r"\s*<task-notification>\s*<task-id>(\w+)</task-id>")
HANDBACK = re.compile(r'\s*Another Claude session sent a message:\s*<agent-message from="(\w+)">\s*\[Subagent hand-back\]')


def log(msg):
    try:
        os.makedirs(os.path.dirname(LOG), exist_ok=True)
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%F %T')} {msg}\n")
    except Exception:
        pass


def _first_text(c):
    if isinstance(c, str):
        return c
    if isinstance(c, list):
        for x in c:
            if isinstance(x, dict) and isinstance(x.get("text"), str):
                return x["text"]
    return ""


def pending_background(transcript):
    """起動（または呼び戻し）したのにまだ戻っていない裏作業のID。記録の順に追う。"""
    pending = set()
    try:
        f = open(transcript, encoding="utf-8", errors="ignore")
    except Exception:
        return set()
    with f:
        for line in f:
            if not any(k in line for k in ("background with ID", "task-notification",
                                           "hand-back", "Async agent", "resumedAgentId")):
                continue
            try:
                d = json.loads(line)
            except Exception:
                continue
            starts, ends = [], []
            content = (d.get("message") or {}).get("content")
            if d.get("type") == "user":
                if isinstance(content, str):
                    ends.append(content)                      # 受信メッセージ
                elif isinstance(content, list):
                    for x in content:
                        if not isinstance(x, dict):
                            continue
                        if x.get("type") == "tool_result":
                            starts.append(_first_text(x.get("content")))
                        elif x.get("type") == "text":
                            ends.append(x.get("text") or "")
            elif d.get("type") == "queue-operation" and d.get("operation") == "enqueue":
                ends.append(d.get("content") or "")             # 順番待ち
            elif d.get("type") == "attachment":
                at = d.get("attachment") or {}
                if at.get("type") == "queued_command":
                    ends.append(at.get("prompt") or "")         # 添付
            for t in starts:
                for rx in (LAUNCH, BG_BASH, RESUME):
                    m = rx.match(t)
                    if m:
                        pending.add(m.group(1))
            for t in ends:
                for rx in (NOTIF, HANDBACK):
                    m = rx.match(t if isinstance(t, str) else "")
                    if m:
                        pending.discard(m.group(1))
    return pending


# 拡張機能が未読(オレンジ)を書く場所。Antigravity と VS Code の両方を見る
_APPDIR = os.environ.get("APPDATA", "") if WIN else os.path.expanduser("~/Library/Application Support")
STATE_DBS = [os.path.join(_APPDIR, app, "User", "globalStorage", "state.vscdb")
             for app in ("Antigravity IDE", "Antigravity", "Code")]


def unread_ids():
    """左のセッション一覧でオレンジ（未読）になっているセッションID。読めなければNone。"""
    import sqlite3
    ids, seen = set(), False
    for db in STATE_DBS:
        if not os.path.exists(db):
            continue
        try:
            con = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=1)
            row = con.execute("select value from ItemTable where key='Anthropic.claude-code'").fetchone()
            con.close()
            d = json.loads(row[0]) if row else {}
        except Exception:
            continue
        seen = True
        for k, v in d.items():
            if k.startswith("sessionUnread:") and isinstance(v, list):
                ids.update(x for x in v if isinstance(x, str))
    return ids if seen else None


def screen_away():
    """画面ロック中か消灯中なら理由を返す。表示中のタブはオレンジにならないが、ロック中は誰も見ていない
    （ロック中に作業が終わっても鳴らない事故があった）。"""
    if WIN:
        return None                       # Windows はオレンジ（未読）を待つ判定だけで鳴らす
    try:
        out = subprocess.run(["ioreg", "-n", "Root", "-d1"], capture_output=True,
                             text=True, timeout=3).stdout
        if re.search(r'"IOConsoleLocked" = Yes', out):
            return "画面ロック中"
    except Exception:
        pass
    try:
        import ctypes, ctypes.util
        cg = ctypes.cdll.LoadLibrary(ctypes.util.find_library("CoreGraphics"))
        cg.CGMainDisplayID.restype = ctypes.c_uint32
        if cg.CGDisplayIsAsleep(cg.CGMainDisplayID()):
            return "画面消灯中"
    except Exception:
        pass
    return None


def wait_orange_then_chime(full_sid, sid):
    """Stopの直後はまだオレンジになっていない。最大8秒、未読リストに載るのを待って鳴らす。
    画面ロック/消灯中は見ている人がいないので、オレンジを待たずに鳴らす。"""
    away = screen_away()
    if away:
        play(DONE_SOUND)
        log(f"{sid} stop  鳴らす ({away})")
        return
    for _ in range(32):
        ids = unread_ids()
        if ids is None:
            break
        if full_sid in ids:
            play(DONE_SOUND)
            log(f"{sid} stop  鳴らす (オレンジ確認)")
            return
        time.sleep(0.25)
    away = screen_away()                      # 待っている8秒の間にロックされた場合
    if away:
        play(DONE_SOUND)
        log(f"{sid} stop  鳴らす ({away})")
        return
    log(f"{sid} stop  鳴らさない (オレンジにならず＝表示中のタブ等)")


DELIV_EXT = r"html?|pdf|pptx?|xlsx?|docx?|key|numbers|pages|csv|md|png|jpe?g|gif|mp4|mov|svg|zip"
CODE_PATH = re.compile(r"`((?:~|/)[^`\n]*?\.(?:%s))`" % DELIV_EXT, re.I)


def unclickable_paths(text):
    """資料ファイルをコード表記で渡している箇所。Antigravityのチャットではコード表記は押せない。"""
    bad = []
    for m in CODE_PATH.finditer(text or ""):
        path = m.group(1)
        absp = os.path.expanduser(path)
        if f"]({absp})" in text or f"](<{absp}>)" in text:
            continue                                  # 同じ物を押せるリンクでも出している
        bad.append(path)
    return list(dict.fromkeys(bad))


def play(sound):
    if os.environ.get("FOX_CHIME") == "off":
        return
    if WIN:
        try:
            import winsound
            flag = winsound.SND_FILENAME if os.path.exists(sound) else winsound.SND_ALIAS
            winsound.PlaySound(sound, flag)
        except Exception:
            pass
        return
    subprocess.Popen(["afplay", sound], stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL, start_new_session=True)


def main() -> int:
    data = sys.stdin.buffer.read()
    try:
        ev = json.loads(data or b"{}")
    except Exception:
        ev = {}
    sid = (ev.get("session_id") or "?")[:8]
    event = ev.get("hook_event_name") or "Stop"
    ide = os.environ.get("CLAUDE_CODE_ENTRYPOINT") == "claude-vscode"

    if event == "Notification":
        kind = ev.get("notification_type") or ""
        if ide and kind in ("permission_prompt", "elicitation_dialog"):
            play(PERM_SOUND)
            log(f"{sid} perm  鳴らす ({kind})")
        else:
            log(f"{sid} notif 鳴らさない ({kind or ev.get('message', '')[:40]})")
        return 0

    if not ev.get("stop_hook_active") and os.environ.get("CLAUDE_CODE_ENTRYPOINT") == "claude-vscode":
        bad = unclickable_paths(ev.get("last_assistant_message") or "")
        if bad:
            log(f"{sid} stop  鳴らさない (資料パスがコード表記{len(bad)}件→書き直し)")
            sys.stderr.write(
                "資料の場所をコード表記(`…`)で書いています。Antigravityのチャットではコード表記は押せません。\n"
                "次の形で、押せるリンクにした返答を出し直してください（~ は使わず絶対パス。空白を含むときは <> で囲む）:\n"
                f"  [ファイル名]({os.path.expanduser('~')}/…/ファイル名.html)\n"
                "対象: " + ", ".join(bad[:5]) + "\n")
            return 2
    if not ide:
        log(f"{sid} stop  鳴らさない (左に出ないセッション)")
        return 0
    waiting = pending_background(ev.get("transcript_path") or "")
    if waiting:
        log(f"{sid} stop  鳴らさない (裏作業{len(waiting)}件待ち)")
        return 0
    # 本体は返してしまい、オレンジ待ちは切り離した子プロセスで行う
    extra = {"creationflags": 0x00000008 | 0x00000200} if WIN else {"start_new_session": True}  # DETACHED_PROCESS | NEW_PROCESS_GROUP
    subprocess.Popen([sys.executable, __file__, "--watch", ev.get("session_id") or ""],
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL, **extra)
    return 0


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--watch":
        wait_orange_then_chime(sys.argv[2], sys.argv[2][:8])
        sys.exit(0)
    sys.exit(main())
