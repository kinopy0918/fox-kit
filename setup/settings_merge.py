#!/usr/bin/env python3
"""~/.claude/settings.json に、このキットの設定を足す（Mac の install.sh と Windows の build_win.py の両方から使う）。

  python3 settings_merge.py <キットの settings.json> <~/.claude/settings.json> <知らせの置き場> <控えのフォルダ>

決まり：
・同じ項目は、持ち主が前から決めていた値を残す（キットの値は、無かった項目にだけ入る）。
  ＝自分で「毎回確認する」にしていた人を、黙って「確認なし」に変えない。
・allow と hooks は足し合わせ。deny・ask は持ち主のものがそのまま残る。
・読めない設定ファイルは、さわらずに残して知らせる（空として扱って、持ち主の設定を消さない）。
・変えるときだけ控えを取る（貼り直すたびに控えを増やさない）。
"""
import json, os, re, shutil, sys

MARK = "block-dangerous-ops.py"      # これが入っていれば、もうこのキットの設定が足してある


def loads_lenient(text: str):
    """コメントや末尾のカンマが入った設定ファイルも読む。"""
    try:
        return json.loads(text)
    except ValueError:
        text = re.sub(r'("(?:\\.|[^"\\])*")|//[^\n]*|/\*.*?\*/', lambda m: m.group(1) or "", text, flags=re.S)
        return json.loads(re.sub(r",(\s*[}\]])", r"\1", text))


def deep_merge(base: dict, over: dict) -> dict:
    out = dict(base)
    for k, v in over.items():
        out[k] = deep_merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


def record(path: str, new: dict, cur: dict):
    """このキットが足したものの控え。外すとき（fox-kit uninstall）に、足したものだけを正確に外すために使う。"""
    try:
        rec = json.load(open(path, encoding="utf-8"))
    except (OSError, ValueError):
        rec = {"allow": [], "keys": [], "mode": False}
    if MARK not in json.dumps(cur):                     # まだ足していないとき（＝最初の1回）に、持ち主に無かった項目を控える
        rec["keys"] = sorted(set(rec["keys"]) | {k for k in new if k not in cur and k not in ("permissions", "hooks")})
        rec["mode"] = rec["mode"] or "defaultMode" not in (cur.get("permissions") or {})
    have = set((cur.get("permissions") or {}).get("allow") or [])
    rec["allow"] = sorted(set(rec["allow"]) | {a for a in (new.get("permissions") or {}).get("allow") or [] if a not in have})
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(rec, f, ensure_ascii=False, indent=1)


def merge(new: dict, dest: str, notices: str, backup: str) -> bool:
    """書いたら True。読めなくて触らなかったら False。"""
    def tell(msg):
        print("  ! " + msg)
        os.makedirs(os.path.dirname(notices), exist_ok=True)
        with open(notices, "a", encoding="utf-8") as f:
            f.write(msg + "\n")

    result, before, first, cur = new, None, False, {}
    if os.path.exists(dest):
        before = open(dest, encoding="utf-8-sig").read()
        try:
            cur = loads_lenient(before)
            if not isinstance(cur, dict):
                raise ValueError("形が違います")
        except ValueError:
            tell("前からある設定ファイル（.claude の settings.json）を読めなかったので、さわらずに残しました。"
                 "このキットの安全の見張りと許可の設定は入っていません。渡してくれた人に知らせてください。")
            return False
        first = MARK not in before
        result = deep_merge(new, cur)
        mode = (cur.get("permissions") or {}).get("defaultMode")
        if mode and mode != "bypassPermissions":
            if "skipDangerousModePermissionPrompt" not in cur:
                result.pop("skipDangerousModePermissionPrompt", None)
            if first:
                tell("AIが作業の前に確認するかどうかは、前から使っていた設定のままにしました"
                     "（このキットの既定は「確認なしで進める」。変えたいときはAIに「確認なしで進める設定にして」と頼めます）。")
        a = (cur.get("permissions") or {}).get("allow") or []
        b = (new.get("permissions") or {}).get("allow") or []
        result.setdefault("permissions", {})["allow"] = list(dict.fromkeys(b + a))
        hooks = {}
        for src in ((cur.get("hooks") or {}), (new.get("hooks") or {})):
            for ev, entries in src.items():
                lst = hooks.setdefault(ev, [])
                for e in entries:
                    if json.dumps(e, sort_keys=True) not in {json.dumps(x, sort_keys=True) for x in lst}:
                        lst.append(e)
        if hooks:
            result["hooks"] = hooks
    record(os.path.join(os.path.dirname(notices), "kit-settings.json"), new, cur)
    text = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if text == before:
        print(f"  変更なし: {dest}")
        return True
    if before is not None:
        os.makedirs(backup, exist_ok=True)
        shutil.copyfile(dest, os.path.join(backup, "settings.json"))
        if first:
            tell(f"前から使っていた設定（settings.json）に、このキットの設定を足しました。入れる前の控え：{os.path.join(backup, 'settings.json')}")
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(dest, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"  設定を書きました: {dest}")
    return True


if __name__ == "__main__":
    src, dest, notices, backup = sys.argv[1:5]
    new = json.load(open(src, encoding="utf-8"))
    # 記憶の置き場所を1か所に固定する：どのフォルダを開いても同じ記憶を読む（持ち主が決めていれば、その値が残る）
    new.setdefault("autoMemoryDirectory", "~/.claude/projects/" + re.sub(r"[^A-Za-z0-9-]", "-", os.path.expanduser("~").rstrip("/")) + "/memory")
    merge(new, dest, notices, backup)
