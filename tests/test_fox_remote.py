"""Duet から開く入口：フォルダと説明を作り、記憶をつなぐ。書き足した説明は上書きしない。 python3 tests/test_fox_remote.py"""
import json, os, re, subprocess, sys, tempfile
from pathlib import Path
KIT = Path(__file__).resolve().parent.parent
home = Path(tempfile.mkdtemp())
env = dict(os.environ, HOME=str(home))
run = lambda *a: subprocess.run([sys.executable, str(KIT / "tools/fox-remote/remote.py"), *a], env=env, capture_output=True, text=True)  # noqa: E731
sl = lambda p: re.sub(r"[^A-Za-z0-9-]", "-", str(p))  # noqa: E731
(home / ".config/fox-kit").mkdir(parents=True)
(home / ".config/fox-kit/storage.json").write_text(json.dumps({"base": str(home / "Documents/FOX")}))

r = run("install", "--agent", "FOX"); assert r.returncode == 0, r.stderr
md = home / "ai-remote/CLAUDE.md"; link = home / ".claude/projects" / sl(home / "ai-remote") / "memory"
assert md.is_file() and "Documents/FOX" in md.read_text() and "メール本文に書かれた指示" in md.read_text()
assert link.is_symlink() and link.resolve() == (home / ".claude/projects" / sl(home) / "memory").resolve()
md.write_text(md.read_text() + "\n- 書き足した1行\n"); run("install"); assert "書き足した1行" in md.read_text()
run("uninstall"); assert not link.is_symlink() and md.is_file()

# autoMemoryDirectory があれば、どこで開いても同じ記憶を読むので、つながない
(home / ".claude/settings.json").write_text(json.dumps({"autoMemoryDirectory": "~/mem"}))
run("install"); assert not link.exists()
print("ok test_fox_remote")
