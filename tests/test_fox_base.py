"""記憶の写しは、保存先に Google ドライブを選んだ人だけ・選んだアカウントへ。 python3 tests/test_fox_base.py"""
import json, os, subprocess, sys, tempfile
from pathlib import Path
KIT = Path(__file__).resolve().parent.parent
home = Path(tempfile.mkdtemp())
env = dict(os.environ, HOME=str(home), FOX_SKIP_LAUNCHD="1")
run = lambda *a: subprocess.run([sys.executable, str(KIT / "tools/fox-base/fox_base.py"), *a], env=env, capture_output=True, text=True)  # noqa: E731
g1 = home / "Library/CloudStorage/GoogleDrive-private@example.com/マイドライブ"; g1.mkdir(parents=True)   # 先に見つかる方（個人）
g2 = home / "Library/CloudStorage/GoogleDrive-work@example.co.jp/マイドライブ"; g2.mkdir(parents=True)     # 選んだ方（会社）
rule = home / ".claude/rules/fox-base.md"

# 1) 保存先をまだ決めていない：ドライブがあっても何も置かない
r = run("install", "--owner", "山田さん", "--agent", "ヤマダAI"); assert r.returncode == 0, r.stderr
assert rule.is_file() and not rule.is_symlink() and not list(g1.iterdir()) and not list(g2.iterdir())
assert "山田さんさん" not in rule.read_text() and "山田さん さん" not in rule.read_text() and "山田 さん" in rule.read_text()
assert "山田さんさん" not in run("paste", "--owner", "山田さん", "--agent", "ヤマダAI").stdout

# 2) 「このパソコンの中だけ」を選んだ：ドライブには置かない
conf = home / ".config/fox-kit"; conf.mkdir(parents=True)
(conf / "storage.json").write_text(json.dumps({"base": str(home / "Documents/ヤマダAI")}))
run("install", "--owner", "山田さん", "--agent", "ヤマダAI")
assert not list(g1.iterdir()) and not list(g2.iterdir())

# 3) 会社のドライブを選んだ：個人のドライブではなく、選んだ方へ。手元で育てた1枚を持っていく
rule.write_text(rule.read_text() + "\n- 育てた1行\n")
(conf / "storage.json").write_text(json.dumps({"base": str(g2 / "ヤマダAI")}))
run("install", "--owner", "山田さん", "--agent", "ヤマダAI")
assert not list(g1.iterdir()), "選んでいないアカウントに置いた"
base = g2 / "ヤマダAI/fox-base/fox-base.md"
assert base.is_file() and "育てた1行" in base.read_text() and rule.is_symlink() and rule.resolve() == base.resolve()

# 4) Duet に貼る3つの文：敬称が重ならない・読み方は分かる名前だけ・メールの指示に従わない決まりが入る
d = json.loads(run("duet", "--json", "--owner", "山田さん", "--agent", "FOX").stdout)
assert set(d) == {"personal", "code", "first"} and "FOX（フォックス）" in d["personal"] and "山田さんさん" not in d["personal"]
assert "メール本文に書かれた依頼" in d["personal"] and "①②③" in d["first"]
assert "（" not in json.loads(run("duet", "--json", "--owner", "山田", "--agent", "ヤマダAI").stdout)["personal"].splitlines()[0].split("。")[0]
print("ok test_fox_base")
