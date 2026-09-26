"""fox-bridge の共通部品：設定・秘密（キーチェーン）・通信・記録。標準ライブラリだけ。"""
from __future__ import annotations

import json
import os
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

HOME = Path.home()
CONF_DIR = HOME / ".config" / "fox-bridge"
CONFIG = CONF_DIR / "config.json"       # どこにつなぐか（秘密は入れない）
STATE = CONF_DIR / "state.json"         # 読んだ位置・会話のID
LOG = HOME / "Library" / "Logs" / "fox-bridge.log"
INBOX = HOME / "Library" / "Caches" / "fox-bridge" / "inbox"   # 受け取った添付
KC_SERVICE = "fox-bridge"


def log(*a):
    LOG.parent.mkdir(parents=True, exist_ok=True)
    line = time.strftime("%Y-%m-%d %H:%M:%S ") + " ".join(str(x) for x in a)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")
    print(line, flush=True)


def load(p: Path, default):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def save(p: Path, data):
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.chmod(tmp, 0o600)
    tmp.replace(p)


# ------------------------------------------------------------------ 秘密はキーチェーンに
def secret_set(name: str, value: str):
    subprocess.run(["security", "add-generic-password", "-U", "-s", KC_SERVICE, "-a", name, "-w", value],
                   check=True, capture_output=True)


def secret_get(name: str) -> str:
    r = subprocess.run(["security", "find-generic-password", "-s", KC_SERVICE, "-a", name, "-w"],
                       capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else ""


# ------------------------------------------------------------------ 通信
class HTTPError(Exception):
    def __init__(self, status, body):
        super().__init__(f"HTTP {status}: {body[:300]}")
        self.status, self.body = status, body


def request(method: str, url: str, headers: dict | None = None, data=None, raw: bytes | None = None,
            timeout=30, retries=3):
    """JSON を送って JSON を受ける。429 は待って再試行。"""
    headers = dict(headers or {})
    body = raw
    if data is not None:
        body = json.dumps(data).encode()
        headers.setdefault("Content-Type", "application/json; charset=utf-8")
    headers.setdefault("User-Agent", "fox-bridge (https://github.com/kinopy0918/fox-kit, 1.0)")
    for i in range(retries):
        req = urllib.request.Request(url, data=body, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                txt = r.read().decode("utf-8", "replace")
                return json.loads(txt) if txt.strip() else {}
        except urllib.error.HTTPError as e:
            txt = e.read().decode("utf-8", "replace")
            if e.code == 429 and i < retries - 1:
                try:
                    wait = float(json.loads(txt).get("retry_after", 2))
                except (json.JSONDecodeError, AttributeError):
                    wait = float(e.headers.get("Retry-After", 2))
                time.sleep(min(wait, 30) + 0.2)
                continue
            raise HTTPError(e.code, txt)
        except urllib.error.URLError:
            if i < retries - 1:
                time.sleep(2 * (i + 1))
                continue
            raise


def multipart(fields: dict, files: list[tuple[str, str, bytes]]):
    """(フォーム本体, Content-Type) を返す。files は (欄名, ファイル名, 中身)。"""
    boundary = "----foxbridge" + str(int(time.time() * 1000))
    out = bytearray()
    for k, v in fields.items():
        out += f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode()
    for name, fname, content in files:
        out += (f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"; filename=\"{fname}\"\r\n"
                f"Content-Type: application/octet-stream\r\n\r\n").encode() + content + b"\r\n"
    out += f"--{boundary}--\r\n".encode()
    return bytes(out), f"multipart/form-data; boundary={boundary}"


def download(url: str, dest: Path, headers: dict | None = None) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=60) as r, open(dest, "wb") as f:
        f.write(r.read())
    return dest


def level() -> str:
    """インストーラで答えた慣れ度合い（beginner / expert）。"""
    st = HOME / ".config" / "fox-kit" / "state.env"
    try:
        for line in st.read_text().splitlines():
            if line.startswith("FOX_LEVEL="):
                return line.split("=", 1)[1].strip()
    except OSError:
        pass
    return "beginner"


def agent_name() -> str:
    st = HOME / ".config" / "fox-kit" / "state.env"
    try:
        for line in st.read_text().splitlines():
            if line.startswith("FOX_AGENT="):
                return line.split("=", 1)[1].strip().replace("\\ ", " ")
    except OSError:
        pass
    return "FOX"
