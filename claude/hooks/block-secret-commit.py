#!/usr/bin/env python3
# PreToolUse(Bash) hook: 機密ファイルが git add / commit / push に混入するのを機械的に阻止する。
# 作法「パスワード・鍵・トークンをGitHubに上げない」を実行時に強制する（fox-kit）。
# 終了コード2 = ブロック（理由をstderrへ）。0 = 許可。stdinからPreToolUseのJSONを受け取る。
import sys, json, os, subprocess, re, fnmatch

try:
    data = json.load(sys.stdin)
except Exception:
    sys.exit(0)  # JSON取れなければ素通り（フックが作業を止めない）

cmd = (data.get("tool_input") or {}).get("command", "") or ""
cwd = data.get("cwd") or os.getcwd()

if not re.search(r'\bgit\b', cmd):
    sys.exit(0)
ops = re.findall(r'\bgit\s+(?:-[^\s]+\s+)*(add|commit|push)\b', cmd)
if not ops:
    sys.exit(0)

# 機密とみなすファイル名パターン（basename一致, 大小無視）。誤検知を避け高確度のものに限定。
SECRET = [
    ".env", ".env.*",
    "*.pem", "*.key", "*.p12", "*.pfx", "*.keystore", "*.jks",
    "id_rsa", "id_dsa", "id_ecdsa", "id_ed25519",
    "service-account*.json", "*-credentials.json", "credentials.json",
    "*.mobileprovision", "*.cer",
]
# 明示的に安全なもの（テンプレ類）は除外
SAFE = [".env.example", ".env.sample", ".env.template", ".env.dist", ".env.defaults", "*.pub"]

def is_secret(path):
    b = os.path.basename(path).lower()
    if any(fnmatch.fnmatch(b, s) for s in SAFE):
        return False
    return any(fnmatch.fnmatch(b, p) for p in SECRET)

def git(args):
    try:
        return subprocess.run(["git"] + args, cwd=cwd, capture_output=True,
                              text=True, timeout=10).stdout.splitlines()
    except Exception:
        return []

flagged = set()

# 1) 既にステージ済みのファイル（commit/push直前の検査）
for f in git(["diff", "--cached", "--name-only"]):
    if f and is_secret(f):
        flagged.add(f)

# 2) push の場合: 追跡対象に機密が含まれていないか（過去commitの混入を検知）
if "push" in ops:
    for f in git(["ls-files"]):
        if f and is_secret(f):
            flagged.add(f)

# 3) `git add <file>` の引数に直接機密が指定された場合
if "add" in ops:
    m = re.search(r'\bgit\s+add\b(.*)', cmd)
    if m:
        for tok in re.split(r'\s+', m.group(1).strip()):
            tok = tok.strip('"\'')
            if not tok or tok.startswith("-"):
                continue
            if is_secret(tok):
                flagged.add(tok)
            elif tok in (".", "*", "-A", "--all"):
                # `git add .` 等: 未追跡の機密が巻き込まれないかチェック
                for u in git(["ls-files", "--others", "--exclude-standard"]):
                    if u and is_secret(u):
                        flagged.add(u)

if flagged:
    files = "\n  - ".join(sorted(flagged))
    sys.stderr.write(
        "🚫 秘密のファイルがGitHubに上がりそうだったので止めました（作法の決まり）。\n"
        "対象:\n  - " + files + "\n\n"
        "対処:\n"
        "  1) .gitignore に追加する\n"
        "  2) 既に追跡済みなら: git rm --cached <file> で追跡解除\n"
        "  3) どうしても必要な場合のみ、持ち主に確認の上で手動実行\n"
    )
    sys.exit(2)  # ブロック

sys.exit(0)
