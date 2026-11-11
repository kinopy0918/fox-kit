#!/bin/zsh
# 入れる → 外す を偽の HOME で通す。前から使っていた人の設定と人格が元に戻り、記憶が残ること。 zsh tests/test_uninstall.sh
set -euo pipefail
KIT="${0:A:h:h}"; H="$(mktemp -d)"; trap 'rm -rf "$H"' EXIT
export HOME="$H" FOX_SKIP_LAUNCHD=1
mkdir -p "$H/.claude"
print -r -- '{"model":"sonnet","permissions":{"defaultMode":"default","deny":["Bash(curl:*)"],"allow":["Bash(ls:*)"]},"hooks":{"Stop":[{"hooks":[{"type":"command","command":"echo mine"}]}]}}' > "$H/.claude/settings.json"
print -r -- '返事は英語で。' > "$H/.claude/CLAUDE.md"
/bin/zsh "$KIT/install.sh" --owner "山田さん" --agent "ヤマダAI" --machine-label "事務所のMac" --role "カフェの経営" > "$H/install.log" 2>&1
MEM="$(print -r -- "$H"/.claude/projects/*/memory/MEMORY.md(N[1]))"; [[ -f "$MEM" ]] || { echo "記憶が作られていない"; exit 1; }
print -r -- '- 大事な記憶' >> "$MEM"
grep -q "ヤマダAI" "$H/.claude/CLAUDE.md" && [[ -f "$H/Tools/fox-kit-cli/uninstall.py" && -f "$H/.claude/hooks/block-dangerous-ops.py" ]]
# 毎回確認する／確認なしの切り替え（新規に入れた人を想定して一度 off→on）
/usr/bin/python3 "$H/Tools/fox-kit-cli/uninstall.py" confirm off > /dev/null
/usr/bin/python3 -c "import json;assert json.load(open('$H/.claude/settings.json'))['permissions']['defaultMode']=='bypassPermissions'"
/usr/bin/python3 "$H/Tools/fox-kit-cli/uninstall.py" confirm on > /dev/null
/usr/bin/python3 -c "import json;d=json.load(open('$H/.claude/settings.json'));assert d['permissions']['defaultMode']=='default' and 'skipDangerousModePermissionPrompt' not in d"
# 確かめる相手がいなければ何もしない
/usr/bin/python3 "$H/Tools/fox-kit-cli/uninstall.py" < /dev/null > /dev/null 2>&1 && { echo "確かめずに外した"; exit 1; }
[[ -f "$H/.claude/hooks/block-dangerous-ops.py" ]]
# 外す
/usr/bin/python3 "$H/Tools/fox-kit-cli/uninstall.py" --yes > "$H/uninstall.log"
/usr/bin/python3 - "$H" <<'PY'
import json, sys, glob, os
H = sys.argv[1]
d = json.load(open(f"{H}/.claude/settings.json"))
assert d["model"] == "sonnet" and d["permissions"] == {"defaultMode": "default", "deny": ["Bash(curl:*)"], "allow": ["Bash(ls:*)"]}, d
assert d["hooks"] == {"Stop": [{"hooks": [{"type": "command", "command": "echo mine"}]}]}, d["hooks"]
assert open(f"{H}/.claude/CLAUDE.md", encoding="utf-8").read().strip() == "返事は英語で。"
assert "大事な記憶" in open(glob.glob(f"{H}/.claude/projects/*/memory/MEMORY.md")[0], encoding="utf-8").read()
for gone in (".claude/hooks/block-dangerous-ops.py", ".claude/fox-kit", "Tools", ".config/fox-kit", ".claude/skills"):
    assert not os.path.exists(f"{H}/{gone}"), gone + " が残っている"
r = glob.glob(f"{H}/fox-kit-removed-*")[0]
assert os.path.exists(f"{r}/Tools/fox-kit-cli/uninstall.py") and os.path.exists(f"{r}/settings.json.外す前") and os.path.exists(f"{r}/CLAUDE.md.外す前")
print("ok test_uninstall")
PY
