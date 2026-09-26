#!/usr/bin/env python3
"""マークダウンの表 → 読める PNG（Discord/Slack添付用）。依存パッケージなし（Chromeのみ）。

使い方:
    python3 table2png.py --title "連載5本" -o /tmp/t.png <<'EOF'
    | 柱 | マガジン | 中身 |
    |---|---|---|
    | A | 第1章のタイトル | 章の要点を1行で |
    EOF

    → 標準出力に PNG の絶対パスを1行返す。そのまま添付やIMGリンクで送れる。

なぜ要るか: DiscordはMarkdownの表を描画しない（`|柱|マガジン|中身|`が生のまま出る）。
コードブロックに入れても日本語は桁が揃わないので同じ。行×列の表は画像で出す。

区切りは半角 | でも全角 ｜ でもよい。ヘッダ区切り行(---)は省略可。
セル内改行は <br>。サイズはヘッドレスChromeで実測してから撮るので、余白の切り落としは不要。
"""
import argparse
import html
import os
import re
import subprocess
import sys
import tempfile

CHROME = os.environ.get(
    "TABLE2PNG_CHROME",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
)
PAD = 28          # bodyの余白（CSSと合わせる）
MAX_W = 1800      # これ以上は横に伸ばさず折り返す

CSS = """
* { box-sizing: border-box; }
body { margin: 0; padding: %(pad)spx; background: #fff;
       font-family: "Hiragino Sans", "Hiragino Kaku Gothic ProN", system-ui, sans-serif;
       -webkit-font-smoothing: antialiased; }
.wrap { display: inline-block; max-width: %(maxw)spx; }
h1 { font-size: 30px; margin: 0 0 18px; color: #14161a; letter-spacing: .02em; }
table { border-collapse: separate; border-spacing: 0; font-size: 26px; line-height: 1.5;
        border: 1px solid #e3e6ea; border-radius: 14px; overflow: hidden; }
th { background: #1f2a37; color: #fff; font-weight: 600; text-align: left;
     padding: 16px 22px; white-space: nowrap; font-size: 25px; }
td { padding: 15px 22px; color: #1c1f24; border-top: 1px solid #eceef1;
     vertical-align: top; max-width: 560px; }
tr:nth-child(even) td { background: #f7f8fa; }
td:first-child { font-weight: 600; color: #0b0d10; white-space: nowrap; }
.note { margin-top: 14px; font-size: 20px; color: #6b7280; }
""" % {"pad": PAD, "maxw": MAX_W}

MEASURE = (
    "<script>addEventListener('load',function(){"
    "var r=document.querySelector('.wrap').getBoundingClientRect();"
    "document.title=Math.ceil(r.right+%d)+'x'+Math.ceil(r.bottom+%d);});</script>" % (PAD, PAD)
)


def parse_rows(text: str):
    rows = []
    for line in text.splitlines():
        s = line.strip().replace("｜", "|")
        if not s.startswith("|"):
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if cells and all(c and set(c) <= set("-: ") for c in cells):
            continue  # ヘッダ区切り行
        rows.append(cells)
    return rows


def build_html(rows, title, note):
    width = max(len(r) for r in rows)
    head, body = rows[0], rows[1:]

    def cell(c):
        return html.escape(c).replace("&lt;br&gt;", "<br>")

    out = ["<meta charset='utf-8'><style>%s</style>%s<div class='wrap'>" % (CSS, MEASURE)]
    if title:
        out.append("<h1>%s</h1>" % html.escape(title))
    out.append("<table><tr>")
    for c in head + [""] * (width - len(head)):
        out.append("<th>%s</th>" % cell(c))
    out.append("</tr>")
    for r in body:
        out.append("<tr>")
        for c in r + [""] * (width - len(r)):
            out.append("<td>%s</td>" % cell(c))
        out.append("</tr>")
    out.append("</table>")
    if note:
        out.append("<div class='note'>%s</div>" % html.escape(note))
    out.append("</div>")
    return "".join(out)


def _chrome(*args):
    return subprocess.run(
        [CHROME, "--headless", "--disable-gpu", "--hide-scrollbars",
         "--no-first-run", "--no-default-browser-check", *args],
        check=True, capture_output=True, text=True)


def shoot(html_text, out_png, scale=2):
    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8") as f:
        f.write(html_text)
        src = "file://" + f.name
    try:
        # 1回目＝寸法の実測（titleにWxHを書かせて読む）
        dom = _chrome("--dump-dom", "--virtual-time-budget=3000",
                      f"--window-size={MAX_W + PAD * 2},2000", src).stdout
        m = re.search(r"<title>(\d+)x(\d+)</title>", dom)
        w, h = (int(m.group(1)), int(m.group(2))) if m else (MAX_W, 2000)
        # 2回目＝その寸法で撮る
        _chrome(f"--force-device-scale-factor={scale}",
                f"--window-size={w},{h}", f"--screenshot={out_png}", src)
    finally:
        os.unlink(f.name)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-o", "--out", default="")
    ap.add_argument("-t", "--title", default="")
    ap.add_argument("-n", "--note", default="")
    ap.add_argument("-i", "--input", default="", help="表を書いたファイル（省略時は標準入力）")
    a = ap.parse_args()

    text = open(a.input, encoding="utf-8").read() if a.input else sys.stdin.read()
    rows = parse_rows(text)
    if len(rows) < 2:
        sys.exit("表として読める行が2行未満です（| 区切りで渡してください）")

    out = a.out or tempfile.mktemp(prefix="table-", suffix=".png", dir="/tmp")
    shoot(build_html(rows, a.title, a.note), out)
    print(out)


if __name__ == "__main__":
    main()
