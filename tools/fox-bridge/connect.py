#!/usr/bin/env python3
"""AI と Discord / Slack をつなぐ設定係（対話式）。

  python3 connect.py            … 質問に答えながら進める（または「つなぐ.command」をダブルクリック）
  python3 connect.py --status   … いまの接続の状態を見る
  python3 connect.py --stop     … 常駐を止める

手でやるしかない所（ボットを作る・鍵をコピーする・サーバーに招待する）だけ、
画面を開いて「どこを押すか」を1つずつ出して待つ。それ以外（チャンネル作成・権限・
常駐・往復テスト）は自動。鍵は Mac のキーチェーンに保存し、ファイルには書かない。
"""
from __future__ import annotations

import getpass
import json
import os
import plistlib
import subprocess
import sys
import time
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as c           # noqa: E402
import platforms as pf       # noqa: E402

HERE = Path(__file__).resolve().parent
LABEL = "com.fox-bridge"
PLIST = Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"
B = c.level() == "beginner"
AGENT = c.agent_name()
GUIDE = os.getenv("FOX_GUIDE_URL", "https://kinopy0918.github.io/fox-kit")


def t(beg: str, exp: str) -> str:
    return beg if B else exp


def say(s=""):
    print(s, flush=True)


def head(n, total, s):
    say(f"\n\033[1;36m━━ {n}/{total}  {s}\033[0m")


def ok(s):
    say(f"\033[32m  ✓ {s}\033[0m")


def warn(s):
    say(f"\033[33m  ! {s}\033[0m")


def steps(lines):
    for i, l in enumerate(lines, 1):
        say(f"    {i}. {l}")


def wait(msg=None):
    input(f"  {msg or t('終わったら Enter キーを押してください', 'Enter で続行')} ")


def choose(q, opts):
    say(f"  {q}")
    for i, (_, label) in enumerate(opts, 1):
        say(f"    {i}) {label}")
    while True:
        a = input("  番号: ").strip() or "1"
        if a.isdigit() and 1 <= int(a) <= len(opts):
            return opts[int(a) - 1][0]
        warn("番号で答えてください")


def open_url(u):
    subprocess.run(["open", u])


def ask_secret(q, check, tries=3):
    for _ in range(tries):
        v = getpass.getpass(f"  {q}（貼り付けても画面には出ません）: ").strip()
        err = check(v)
        if not err:
            return v
        warn(err)
    raise SystemExit(t("うまく受け取れませんでした。もう一度「つなぐ」を開くと、最初からやり直せます。", "中止"))


# ================================================================== Discord
def discord_flow():
    T = 7
    head(1, T, t("Discord のアカウント", "アカウント"))
    if choose(t("Discord のアカウントはありますか？", "Discord アカウント"), [("y", "ある"), ("n", "まだない")]) == "n":
        open_url("https://discord.com/register")
        steps([t("開いた画面でメールアドレス・表示名・パスワード・生年月日を入れて「はい」を押す", "登録"),
               t("届いたメールの「メールアドレスを認証」を押す", "メール認証")])
        wait()

    head(2, T, t("AIが住むサーバー（部屋）", "サーバー"))
    kind = choose(t("どのサーバーにAIを入れますか？", "サーバー"),
                  [("new", t("新しく作る（おすすめ・AI専用の部屋になる）", "新規作成")),
                   ("old", t("いま使っているサーバーに入れる", "既存サーバー"))])
    if kind == "new":
        open_url("https://discord.com/channels/@me")
        steps([t("画面の左はしにある「＋」（サーバーを追加）を押す", "左の＋"),
               t("「オリジナルの作成」→「自分と友達のため」を押す", "オリジナルの作成 → 自分と友達のため"),
               t(f"サーバー名に「{AGENT}の部屋」などと入れて「新規作成」", "名前を入れて作成")])
        wait()

    head(3, T, t("AIの分身（ボット）を作る", "Bot 作成"))
    say(t(f"  図つきの手順: {GUIDE}/discord.html", f"  guide: {GUIDE}/discord.html"))
    open_url("https://discord.com/developers/applications")
    steps([t("開いた画面の右上「New Application（新しいアプリ）」を押す", "New Application"),
           t(f"名前に「{AGENT}」と入れ、下の同意にチェックして「Create（作成）」", f"Name: {AGENT} → Create"),
           t("左の一覧から「Bot」を押す", "左メニュー Bot"),
           t("「Reset Token（トークンをリセット）」→「Yes, do it!（はい）」を押す（パスワードや認証を聞かれたら入れる）", "Reset Token"),
           t("出てきた長い文字列の「Copy（コピー）」を押す", "Copy")])

    def check(v):
        if len(v) < 50 or v.count(".") < 2:
            return t("形が違うようです。「Copy」を押してから、もう一度貼り付けてください", "Bot トークンの形式ではありません")
        try:
            pf.Discord(v).me()
        except Exception:
            return t("この鍵ではつながりませんでした。もう一度「Reset Token」からやり直して貼り付けてください", "認証失敗（/users/@me）")
    tok = ask_secret(t("コピーした文字列を貼り付けて Enter", "Bot トークン"), check)
    c.secret_set("discord", tok)
    api = pf.Discord(tok)
    ok(t(f"ボット「{api.me()['username']}」とつながりました（鍵はMacの金庫＝キーチェーンに保管）", f"bot: {api.me()['username']}（Keychain 保存）"))

    head(4, T, t("AIが文章を読めるようにする", "Message Content Intent"))
    if api.enable_message_content():
        ok(t("自動で設定できました", "API で GATEWAY_MESSAGE_CONTENT_LIMITED を有効化"))
    else:
        steps([t("さっきの Bot の画面を下へスクロールし「MESSAGE CONTENT INTENT」をオン（青）にする", "Bot > MESSAGE CONTENT INTENT をオン"),
               t("下に出る「Save Changes（保存）」を押す", "Save Changes")])
        wait()

    head(5, T, t("サーバーに招待する", "招待"))
    app_id = api.application()["id"]
    before = {g["id"] for g in api.guilds()}
    open_url(api.invite_url(app_id))
    steps([t("開いた画面で「サーバーに追加」の欄から、さっきのサーバーを選ぶ", "サーバーを選択"),
           t("「はい」→「認証」を押す（人間かどうかの確認が出たら答える）", "認証")])
    say(t("  招待されるのを待っています…（最大5分）", "  参加待ち…"))
    guild = None
    for _ in range(100):
        gs = api.guilds()
        new = [g for g in gs if g["id"] not in before] or (gs if len(gs) == 1 else [])
        if new:
            guild = new[0] if len(new) == 1 else next(g for g in new if g["id"] == choose(
                "どのサーバー？", [(g["id"], g["name"]) for g in new]))
            break
        time.sleep(3)
    if not guild:
        raise SystemExit(t("招待が確認できませんでした。もう一度「つなぐ」を開いてやり直してください。", "guild が見つかりません"))
    ok(t(f"サーバー「{guild['name']}」に入りました", f"guild: {guild['name']}"))

    head(6, T, t("AI用のチャンネルを作る", "チャンネル作成"))
    chans = api.ensure_channels(guild["id"], AGENT, ["相談", "お知らせ", "記録"])
    ok(t(f"「{AGENT}」の下に #相談・#お知らせ・#記録 を作りました（AIが返事をするのは #相談）", f"category {AGENT}: {list(chans)}"))
    cfg = {"platform": "discord", "guild": guild["id"], "channels": [chans["相談"]],
           "notify_channel": chans["お知らせ"], "log_channel": chans["記録"], "allowed_users": []}
    c.save(c.CONFIG, cfg)
    return api, cfg, f"https://discord.com/channels/{guild['id']}/{chans['相談']}", T


# ================================================================== Slack
def slack_manifest():
    return {
        "display_information": {"name": AGENT, "description": "AI秘書", "background_color": "#1d2433"},
        "features": {"bot_user": {"display_name": AGENT, "always_online": True}},
        "oauth_config": {"scopes": {"bot": [
            "channels:history", "channels:read", "channels:manage", "channels:join", "chat:write",
            "files:read", "files:write", "users:read", "reactions:write"]}},
        "settings": {"org_deploy_enabled": False, "socket_mode_enabled": False, "token_rotation_enabled": False},
    }


def slack_flow():
    T = 5
    head(1, T, t("Slack のワークスペース（会社の部屋）", "ワークスペース"))
    if choose(t("どこにAIを入れますか？", "ワークスペース"),
              [("old", t("いま使っているワークスペース", "既存")), ("new", t("新しく作る", "新規作成"))]) == "new":
        open_url("https://slack.com/get-started#/createnew")
        steps([t("メールアドレスを入れて、届いた確認コードを入れる", "メール確認"),
               t("会社名（ワークスペース名）と自分の名前を入れて進む（「スキップ」でよい所は飛ばしてOK）", "作成")])
        wait()

    head(2, T, t("AIの分身（アプリ）を作る", "App 作成（マニフェスト）"))
    say(t(f"  図つきの手順: {GUIDE}/slack.html", f"  guide: {GUIDE}/slack.html"))
    url = "https://api.slack.com/apps?new_app=1&manifest_json=" + urllib.parse.quote(json.dumps(slack_manifest(), ensure_ascii=False))
    open_url(url)
    steps([t("開いた画面で、AIを入れるワークスペースを選んで「Next（次へ）」", "ワークスペース選択 → Next"),
           t("もう一度「Next」→「Create（作成）」を押す（設定はもう入っています）", "Next → Create"),
           t("「Install to Workspace（ワークスペースにインストール）」→「許可する」を押す", "Install to Workspace → 許可"),
           t("左の一覧の「OAuth & Permissions」を押し、「Bot User OAuth Token」（xoxb- で始まる）の「Copy」を押す", "OAuth & Permissions → Bot User OAuth Token をコピー")])

    def check(v):
        if not v.startswith("xoxb-"):
            return t("「xoxb-」で始まる文字列をコピーしてください（User の方ではなく Bot の方）", "xoxb- で始まるボットトークンではありません")
        try:
            pf.Slack(v).me()
        except Exception:
            return t("この鍵ではつながりませんでした。もう一度コピーして貼り付けてください", "auth.test 失敗")
    tok = ask_secret(t("コピーした文字列を貼り付けて Enter", "Bot User OAuth Token"), check)
    c.secret_set("slack", tok)
    api = pf.Slack(tok)
    me = api.me()
    ok(t(f"「{me['team']}」とつながりました（鍵はMacの金庫＝キーチェーンに保管）", f"team: {me['team']}（Keychain 保存）"))

    head(3, T, t("AI用のチャンネルを作る", "チャンネル作成"))
    ch = None
    for name in (f"{AGENT}-相談".lower(), "ai-soudan"):
        try:
            ch = api.ensure_channel(name); break
        except Exception as e:
            c.log("チャンネル作成に失敗:", name, e)
    if not ch:
        raise SystemExit(t("チャンネルを作れませんでした。", "conversations.create 失敗"))
    ok(t("AI用のチャンネルを作りました", f"channel: {ch}"))
    cfg = {"platform": "slack", "team": me.get("team_id"), "channels": [ch], "allowed_users": []}
    c.save(c.CONFIG, cfg)
    link = f"https://app.slack.com/client/{me.get('team_id')}/{ch}"
    return api, cfg, link, T


# ================================================================== 共通の仕上げ
def install_launchd():
    PLIST.parent.mkdir(parents=True, exist_ok=True)
    home = str(Path.home())
    pl = {"Label": LABEL, "ProgramArguments": ["/usr/bin/python3", str(HERE / "bridge.py")],
          "RunAtLoad": True, "KeepAlive": True, "ThrottleInterval": 20,
          "StandardOutPath": f"{home}/Library/Logs/fox-bridge.out.log",
          "StandardErrorPath": f"{home}/Library/Logs/fox-bridge.out.log",
          "EnvironmentVariables": {"PATH": f"{home}/.local/bin:/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin",
                                   "HOME": home, "LANG": "ja_JP.UTF-8"}}
    with open(PLIST, "wb") as f:
        plistlib.dump(pl, f)
    uid = os.getuid()
    subprocess.run(["launchctl", "bootout", f"gui/{uid}/{LABEL}"], capture_output=True)
    subprocess.run(["launchctl", "bootstrap", f"gui/{uid}", str(PLIST)], capture_output=True)
    subprocess.run(["launchctl", "kickstart", "-k", f"gui/{uid}/{LABEL}"], capture_output=True)


def roundtrip(api, cfg, link, n, T):
    head(n, T, t("つながったか試す", "往復テスト"))
    ch = cfg["channels"][0]
    first = api.fetch(ch, None)
    after = first[-1]["id"] if first else "0"
    api.send(ch, t(f"こんにちは、{AGENT}です。ここに書くと、私が返事をします。試しに「はじめまして」と送ってみてください。",
                   f"{AGENT} 接続テスト。何か送ってください。"))
    mine = api.fetch(ch, after)
    after = mine[-1]["id"] if mine else after      # 自分の案内文より後を待つ
    open_url(link)
    say(t("  開いた画面のチャンネルで「はじめまして」と送ってください。待っています…（最大5分）", "  メッセージ待ち…"))
    me = api.me()["id"]
    for _ in range(100):
        msgs = [m for m in api.fetch(ch, after) if not m["bot"] and m["user"] != me]
        if msgs:
            cfg["owner"] = msgs[0]["user"]
            c.save(c.CONFIG, cfg)
            api.send(ch, t("届きました！これで、ここに書いたことに私が答えます。仕事のことは何でも、ふだんの言葉で話しかけてください。",
                           "受信OK。以降このチャンネルで応答します。"))
            ok(t("やり取りできることを確かめました", "往復 OK"))
            return True
        time.sleep(3)
    warn(t("メッセージが確認できませんでした。あとで送れば、AIが返事をします。", "受信を確認できず（常駐は起動済み）"))
    return False


def status():
    cfg = c.load(c.CONFIG, {})
    say(json.dumps({k: v for k, v in cfg.items()}, ensure_ascii=False, indent=2) if cfg else "未接続")
    r = subprocess.run(["launchctl", "print", f"gui/{os.getuid()}/{LABEL}"], capture_output=True, text=True)
    say("常駐: " + ("動いています" if "state = running" in r.stdout else "止まっています"))


def main():
    if "--status" in sys.argv:
        return status()
    if "--stop" in sys.argv:
        subprocess.run(["launchctl", "bootout", f"gui/{os.getuid()}/{LABEL}"], capture_output=True)
        return say("止めました")
    say(f"\033[1m{AGENT} を Discord / Slack とつなぐ\033[0m")
    say(t("  スマホからでもAIと話せるようにします（10分ほど）。画面が開いたら、書いてある順に押していくだけです。",
          "  Bot 作成 → 鍵登録 → 招待 → チャンネル作成 → 常駐 → 往復テスト"))
    p = choose(t("どちらでAIと話しますか？", "プラットフォーム"),
               [("discord", t("Discord（無料・スマホでも使いやすい。おすすめ）", "Discord")),
                ("slack", t("Slack（会社で既に使っているなら）", "Slack"))])
    api, cfg, link, T = discord_flow() if p == "discord" else slack_flow()
    head(T - 1 if p == "discord" else T - 1, T, t("いつでも返事ができるようにする", "常駐（launchd）"))
    install_launchd()
    time.sleep(3)
    ok(t("このMacが起きている間は、いつでも返事をします", f"launchd {LABEL} 起動"))
    roundtrip(api, cfg, link, T, T)
    say("\n\033[1;32m" + t("つながりました。", "完了。") + "\033[0m")
    say(t("  ※ Macのふたを閉じたり、電源を切ったりすると返事が止まります。", "  ※ スリープ中は応答しません。"))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        say("\n" + t("中断しました。もう一度「つなぐ」を開くと、最初からやり直せます。", "中断"))
