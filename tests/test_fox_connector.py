"""FOXコネクタ：サーバーの推し方・フォルダの外へ出られない・コードの照合。ネットにも fastmcp にも頼らない。 python3 tests/test_fox_connector.py"""
import json, os, sys, tempfile
from pathlib import Path
KIT = Path(__file__).resolve().parent.parent
home = Path(tempfile.mkdtemp()); os.environ["HOME"] = str(home)
sys.path.insert(0, str(KIT / "tools/fox-connector"))
import connector as C, server as S  # noqa: E402
C.ispdb = lambda d: None   # 公開の一覧は引かない

assert C.guess("a@gmail.com", [])["imap_host"] == "imap.gmail.com"
assert C.guess("a@example.co.jp", ["aspmx.l.google.com"])["smtp_host"] == "smtp.gmail.com"      # Google Workspace
assert C.guess("a@idm.example", ["www3020.sakura.ne.jp"])["imap_host"] == "www3020.sakura.ne.jp"  # さくら
assert C.guess("a@shop.example", ["sv123.xserver.jp"])["imap_host"] == "sv123.xserver.jp"        # エックスサーバー
assert C.guess("a@x.example", ["mx.other.example"])["imap_host"] == "mail.x.example"
try:
    C.guess("a@corp.example", ["corp-example.mail.protection.outlook.com"]); raise AssertionError("M365 を通した")
except SystemExit:
    pass

share = home / "share"; (share / "sub").mkdir(parents=True); (home / "secret.txt").write_text("x")
u = {"folders": [str(share)]}
assert S.allowed_folder(u, str(share / "sub")) == (share / "sub").resolve()
for bad in (str(share / ".." / "secret.txt"), str(home), "/etc/passwd"):
    try:
        S.allowed_folder(u, bad); raise AssertionError("外に出られた: " + bad)
    except PermissionError:
        pass
(share / "link").symlink_to(home)
try:
    S.allowed_folder(u, str(share / "link" / "secret.txt")); raise AssertionError("リンクで外に出られた")
except PermissionError:
    pass

code = C.new_code(); assert len(code) == 14 and not set(code) & set("0O1I")
(home / ".config/fox-connector").mkdir(parents=True)
(home / ".config/fox-connector/users.json").write_text(json.dumps({"山田": {"code_sha256": C.hashlib.sha256(code.replace("-", "").encode()).hexdigest()}}))
assert S.who_by_code(code.lower()) == "山田" and S.who_by_code(code.replace("-", " ")) == "山田" and S.who_by_code("AAAA-BBBB-CCCC") is None
print("ok test_fox_connector")

# 送信の前は Claude Code でも毎回確認：名前は英数字だけ・二重に足さない
(home / ".claude").mkdir(); (home / ".claude/settings.json").write_text(json.dumps({"permissions": {"defaultMode": "bypassPermissions"}}))
(home / ".config/fox-connector/env.json").write_text(json.dumps({"agent": "ミケ"}))
C.ask_before_send(); C.ask_before_send()
assert json.loads((home / ".claude/settings.json").read_text())["permissions"]["ask"] == ["mcp__claude_ai_Connector__mail_send"]
print("ok test_fox_connector（送信の確認）")
