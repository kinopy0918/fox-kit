"""前から Claude Code を使っていた人の設定を壊さない。 python3 tests/test_settings_merge.py"""
import json, os, sys, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "setup"))
import settings_merge as sm  # noqa: E402

KIT = json.load(open(os.path.join(os.path.dirname(__file__), "..", "claude", "settings.json"), encoding="utf-8"))
d = tempfile.mkdtemp(); dest, notes, bak = f"{d}/.claude/settings.json", f"{d}/n/notices.txt", f"{d}/bak"
new = lambda: json.loads(json.dumps(KIT))  # noqa: E731
read = lambda: json.load(open(dest, encoding="utf-8"))  # noqa: E731

# 1) 新規：キットの既定がそのまま入る。控えも知らせも無い
assert sm.merge(new(), dest, notes, bak) and read()["permissions"]["defaultMode"] == "bypassPermissions"
assert not os.path.exists(bak) and not os.path.exists(notes)

# 2) 前から使っていた人：決めていた値・deny・自分の hook が残り、キットの allow と hook が足される
mine = {"model": "sonnet", "effortLevel": "medium", "permissions": {"defaultMode": "default", "deny": ["Bash(curl:*)"], "allow": ["Bash(ls:*)"]},
        "hooks": {"Stop": [{"hooks": [{"type": "command", "command": "echo mine"}]}]}}
open(dest, "w").write(json.dumps(mine))
assert sm.merge(new(), dest, notes, bak)
r = read(); p = r["permissions"]
assert (p["defaultMode"], r["effortLevel"], r["model"], p["deny"]) == ("default", "medium", "sonnet", ["Bash(curl:*)"])
assert "skipDangerousModePermissionPrompt" not in r and "Bash(ls:*)" in p["allow"] and len(p["allow"]) > 5
assert any("echo mine" in json.dumps(h) for h in r["hooks"]["Stop"]) and sm.MARK in json.dumps(r["hooks"])
assert json.load(open(f"{bak}/settings.json")) == mine and len(open(notes, encoding="utf-8").read().splitlines()) == 2

# 3) 2回目：何も変わらず、知らせも増えない
before = open(dest).read(); os.remove(notes)
assert sm.merge(new(), dest, notes, f"{d}/bak2") and open(dest).read() == before and not os.path.exists(f"{d}/bak2") and not os.path.exists(notes)

# 4) コメント入り：読めて、決めていた値が残る
open(dest, "w").write('{\n // メモ\n "model": "sonnet", /* x */\n "permissions": {"deny": ["Bash(curl:*)"], "defaultMode": "default", },\n}\n')
assert sm.merge(new(), dest, notes, bak) and read()["model"] == "sonnet" and read()["permissions"]["deny"] == ["Bash(curl:*)"]

# 5) どうしても読めない：さわらずに残して知らせる
open(dest, "w").write("{ これは壊れている"); os.remove(notes)
assert sm.merge(new(), dest, notes, bak) is False and open(dest).read() == "{ これは壊れている" and "さわらずに残しました" in open(notes, encoding="utf-8").read()
print("ok test_settings_merge")
