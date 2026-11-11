"""返事の仕組みは、既定でつないだ本人にだけ応える（AIは確認なしでパソコンを動かすため）。 python3 tests/test_bridge_owner.py"""
import os, sys, tempfile
home = tempfile.mkdtemp(); os.environ["HOME"] = os.environ["USERPROFILE"] = home
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools", "fox-bridge"))
import bridge as b, common as c  # noqa: E402

c.CONF_DIR.mkdir(parents=True, exist_ok=True)
sent = []
class Api:
    def send(self, ch, text, *a, **k): sent.append(text)
H = lambda u: {"user": u, "name": u, "bot": False}  # noqa: E731
cfg = {"platform": "slack", "channels": ["C1"], "allowed_users": []}; c.save(c.CONFIG, cfg); cs = {}
assert [m["user"] for m in b.allowed_only(Api(), cfg, "C1", cs, [H("owner")])] == ["owner"]      # 最初の人＝持ち主
assert c.load(c.CONFIG, {})["allowed_users"] == ["owner"] and c.load(c.CONFIG, {})["platform"] == "slack"
assert b.allowed_only(Api(), cfg, "C1", cs, [H("other")]) == [] and len(sent) == 1               # 他人には応えず1回知らせる
assert b.allowed_only(Api(), cfg, "C1", cs, [H("other"), H("owner")]) == [H("owner")] and len(sent) == 1
cfg["everyone"] = True
assert len(b.allowed_only(Api(), cfg, "C1", cs, [H("other"), H("x")])) == 2                      # 全員に開いたとき
cfg["everyone"] = False; cfg["allowed_users"] = ["owner", "other"]
assert len(b.allowed_only(Api(), cfg, "C1", cs, [H("other"), H("x")])) == 1                      # 足した人だけ
print("ok test_bridge_owner")
