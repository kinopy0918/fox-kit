"""Discord と Slack の差を吸収する。どちらも「一定間隔で新着を見に行く」方式
（常時接続の設定や、手作業でしか発行できない接続用トークンが要らない）。"""
from __future__ import annotations

import json
import re
import threading
import time
import urllib.parse
from pathlib import Path

import common as c


# ================================================================== Discord
class Discord:
    API = "https://discord.com/api/v10"
    LIMIT = 1900                      # 1通の上限（2000）より少し小さく

    def __init__(self, token: str):
        self.h = {"Authorization": f"Bot {token}"}
        self._me = None

    def call(self, method, path, **kw):
        return c.request(method, self.API + path, headers=self.h, **kw)

    # --- 接続まわり
    def me(self):
        if not self._me:
            self._me = self.call("GET", "/users/@me")
        return self._me

    def application(self):
        return self.call("GET", "/applications/@me")

    def enable_message_content(self) -> bool:
        """100サーバー未満のボットは『限定版』のメッセージ内容の許可をAPIから入れられる（公式記載）。"""
        GATEWAY_MESSAGE_CONTENT_LIMITED = 1 << 19
        try:
            app = self.application()
            flags = int(app.get("flags", 0))
            if flags & (GATEWAY_MESSAGE_CONTENT_LIMITED | (1 << 18)):
                return True
            self.call("PATCH", "/applications/@me", data={"flags": flags | GATEWAY_MESSAGE_CONTENT_LIMITED})
            return bool(int(self.application().get("flags", 0)) & GATEWAY_MESSAGE_CONTENT_LIMITED)
        except c.HTTPError as e:
            c.log("message content の自動設定に失敗:", e)
            return False

    def invite_url(self, client_id: str, guild_id: str = "") -> str:
        # チャンネルを見る・送る・履歴を読む・ファイル添付・リンク埋め込み・チャンネル管理・リアクション
        perms = (1 << 10) | (1 << 11) | (1 << 16) | (1 << 15) | (1 << 14) | (1 << 4) | (1 << 6)
        q = {"client_id": client_id, "scope": "bot", "permissions": str(perms)}
        if guild_id:
            q.update(guild_id=guild_id, disable_guild_select="true")
        return "https://discord.com/oauth2/authorize?" + urllib.parse.urlencode(q)

    def guilds(self):
        return self.call("GET", "/users/@me/guilds")

    def ensure_channels(self, guild_id: str, category: str, names: list[str]) -> dict:
        """カテゴリとチャンネルを作る（同名があれば作らない）。{名前: id} を返す。"""
        chans = self.call("GET", f"/guilds/{guild_id}/channels")
        cat = next((x for x in chans if x["type"] == 4 and x["name"] == category), None)
        if not cat:
            cat = self.call("POST", f"/guilds/{guild_id}/channels", data={"name": category, "type": 4})
        out = {}
        for n in names:
            ch = next((x for x in chans if x["type"] == 0 and x["name"] == n), None)
            if not ch:
                ch = self.call("POST", f"/guilds/{guild_id}/channels",
                               data={"name": n, "type": 0, "parent_id": cat["id"]})
            out[n] = ch["id"]
        return out

    # --- やり取り
    def fetch(self, channel: str, after: str | None):
        """新しい順に返るので古い順に並べ直す。after が無ければ最新1件の位置だけ返す。"""
        q = f"?limit=50" + (f"&after={after}" if after else "")
        msgs = self.call("GET", f"/channels/{channel}/messages{q}")
        msgs.sort(key=lambda m: int(m["id"]))
        out = []
        for m in msgs:
            a = m.get("author", {})
            out.append({
                "id": m["id"], "user": a.get("id"), "name": a.get("global_name") or a.get("username"),
                "bot": bool(a.get("bot")), "text": m.get("content", ""),
                "files": [(x["filename"], x["url"]) for x in m.get("attachments", [])],
                "reply_to": (m.get("referenced_message") or {}).get("content", ""),
            })
        return out

    def send(self, channel: str, text: str, files: list[Path] = ()):
        chunks = split(text, self.LIMIT) or [""]
        for i, ch in enumerate(chunks):
            last = i == len(chunks) - 1
            if last and files:
                fl = [(f"files[{j}]", p.name, p.read_bytes()) for j, p in enumerate(files[:10])]
                body, ctype = c.multipart({"payload_json": json.dumps({"content": ch})}, fl)
                c.request("POST", f"{self.API}/channels/{channel}/messages",
                          headers={**self.h, "Content-Type": ctype}, raw=body, timeout=120)
            elif ch.strip():
                self.call("POST", f"/channels/{channel}/messages", data={"content": ch})

    def typing(self, channel: str):
        """入力中… を出し続ける。stop.set() で止まる。"""
        stop = threading.Event()

        def loop():
            while not stop.is_set():
                try:
                    self.call("POST", f"/channels/{channel}/typing", retries=1)
                except Exception:
                    pass
                stop.wait(8)
        threading.Thread(target=loop, daemon=True).start()
        return stop

    def download(self, url: str, dest: Path):
        return c.download(url, dest)


# ================================================================== Slack
class Slack:
    API = "https://slack.com/api/"
    LIMIT = 3500

    def __init__(self, token: str):
        self.token = token
        self.h = {"Authorization": f"Bearer {token}"}
        self._me = None

    def call(self, method, data=None, get=False):
        if get:
            r = c.request("GET", self.API + method + "?" + urllib.parse.urlencode(data or {}), headers=self.h)
        else:
            r = c.request("POST", self.API + method, headers=self.h, data=data or {})
        if not r.get("ok"):
            raise c.HTTPError(200, json.dumps(r))
        return r

    def me(self):
        if not self._me:
            r = self.call("auth.test")
            self._me = {"id": r["user_id"], "team": r.get("team"), "team_id": r.get("team_id"), "url": r.get("url")}
        return self._me

    def ensure_channel(self, name: str) -> str:
        """公開チャンネルを作る（あれば使う）。ボットは作った時点でメンバー。"""
        try:
            return self.call("conversations.create", {"name": name})["channel"]["id"]
        except c.HTTPError as e:
            if "name_taken" not in e.body:
                raise
        cur = None
        while True:
            r = self.call("conversations.list", {"limit": 1000, "exclude_archived": "true",
                                                  **({"cursor": cur} if cur else {})}, get=True)
            for ch in r["channels"]:
                if ch["name"] == name:
                    if not ch.get("is_member"):
                        self.call("conversations.join", {"channel": ch["id"]})
                    return ch["id"]
            cur = r.get("response_metadata", {}).get("next_cursor")
            if not cur:
                raise RuntimeError(f"チャンネル {name} が見つかりません")

    def fetch(self, channel: str, after: str | None):
        q = {"channel": channel, "limit": 50}
        if after:
            q["oldest"] = after
        r = self.call("conversations.history", q, get=True)
        out = []
        for m in sorted(r.get("messages", []), key=lambda m: float(m["ts"])):
            if after and float(m["ts"]) <= float(after):
                continue
            if m.get("subtype") not in (None, "file_share", "thread_broadcast"):
                continue
            out.append({
                "id": m["ts"], "user": m.get("user"), "name": m.get("user"),
                "bot": bool(m.get("bot_id")), "text": m.get("text", ""),
                "files": [(f.get("name", "file"), f.get("url_private_download") or f.get("url_private"))
                          for f in m.get("files", [])],
                "reply_to": "",
            })
        return out

    def send(self, channel: str, text: str, files: list[Path] = (), placeholder: str | None = None):
        chunks = split(to_mrkdwn(text), self.LIMIT) or [""]
        for i, ch in enumerate(chunks):
            if i == 0 and placeholder:
                self.call("chat.update", {"channel": channel, "ts": placeholder, "text": ch or "（完了）"})
            elif ch.strip():
                self.call("chat.postMessage", {"channel": channel, "text": ch})
        for p in files:
            data = p.read_bytes()
            u = self.call("files.getUploadURLExternal", {"filename": p.name, "length": len(data)}, get=True)
            c.request("POST", u["upload_url"], headers={"Content-Type": "application/octet-stream"}, raw=data, timeout=120)
            self.call("files.completeUploadExternal", {"files": [{"id": u["file_id"], "title": p.name}],
                                                        "channel_id": channel})

    def typing(self, channel: str):
        """Slack のボットには『入力中』が無いので、考え中の仮の1通を出して後で書き換える。"""
        r = self.call("chat.postMessage", {"channel": channel, "text": "…考えています"})
        ev = threading.Event()
        ev.placeholder = r["ts"]
        return ev

    def download(self, url: str, dest: Path):
        return c.download(url, dest, headers=self.h)


def to_mrkdwn(text: str) -> str:
    """AIの返事（Markdown）を Slack の書き方に直す。そのままだと **太字** や見出しの # が記号のまま出る。"""
    out, code = [], False
    for line in (text or "").splitlines():
        if line.lstrip().startswith("```"):
            code = not code; out.append(line); continue
        if not code:
            line = re.sub(r"^#{1,6}\s+(.+)$", r"*\1*", line)                 # 見出し → 太字
            line = re.sub(r"\*\*(.+?)\*\*", r"*\1*", line)                   # **太字** → *太字*
            line = re.sub(r"\[([^\]]+)\]\((https?://[^)]+)\)", r"<\2|\1>", line)  # [文字](URL) → <URL|文字>
            line = re.sub(r"^(\s*)[-*]\s+", r"\1• ", line)                    # 箇条書き
        out.append(line)
    return "\n".join(out)


def split(text: str, n: int) -> list[str]:
    """改行の切れ目で n 文字以内に分ける。"""
    out, cur = [], ""
    for line in (text or "").splitlines(keepends=True):
        while len(line) > n:
            if cur:
                out.append(cur); cur = ""
            out.append(line[:n]); line = line[n:]
        if len(cur) + len(line) > n:
            out.append(cur); cur = ""
        cur += line
    if cur:
        out.append(cur)
    return out


def make(platform: str):
    tok = c.secret_get(platform)
    if not tok:
        raise SystemExit(f"{platform} の接続用の鍵がキーチェーンにありません（connect.py を先に）")
    return Discord(tok) if platform == "discord" else Slack(tok)
