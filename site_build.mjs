// 手順書を「パスワードを入れたら読める」形にして公開用に書き出す。
//   node site_build.mjs            site/*.html（原稿）→ ./*.html（暗号化した公開用）
// パスワードはこのMacのキーチェーン（service fox-kit-guide / account page）から読む。ファイルには書かない。
// 仕組み：PBKDF2-SHA256（31万回）で鍵を作り、AES-GCM で <body> の中身を暗号化。全ページ同じ鍵なので、
//         1ページで入れれば他のページも開ける（ブラウザに覚えるのは鍵だけ。パスワードそのものは残さない）。
// 原稿は公開リポジトリに入れず（.gitignore）、Drive の vault に控えを置く。
import { readFileSync, writeFileSync, readdirSync, mkdirSync, cpSync, existsSync } from "node:fs";
import { execFileSync } from "node:child_process";
import { webcrypto as C } from "node:crypto";

const ITER = 310000;
const pw = process.env.FOX_GUIDE_PASSWORD ||
  execFileSync("security", ["find-generic-password", "-s", "fox-kit-guide", "-a", "page", "-w"]).toString().trim();
const saltFile = "site/.salt";   // 鍵の作り方の材料（秘密ではない）。変えると皆の「覚えた鍵」が無効になる
const salt = existsSync(saltFile) ? Buffer.from(readFileSync(saltFile, "utf8").trim(), "base64") : Buffer.from(C.getRandomValues(new Uint8Array(16)));
if (!existsSync(saltFile)) writeFileSync(saltFile, salt.toString("base64"));
const base = await C.subtle.importKey("raw", new TextEncoder().encode(pw), "PBKDF2", false, ["deriveKey"]);
const key = await C.subtle.deriveKey({ name: "PBKDF2", salt, iterations: ITER, hash: "SHA-256" }, base, { name: "AES-GCM", length: 256 }, false, ["encrypt"]);

// 原稿の控え先は ~/.config/fox-kit/guide-vault（1行にフォルダの場所）か FOX_GUIDE_VAULT で指定。無ければ控えない
const VAULT = process.env.FOX_GUIDE_VAULT || (existsSync(`${process.env.HOME}/.config/fox-kit/guide-vault`) ? readFileSync(`${process.env.HOME}/.config/fox-kit/guide-vault`, "utf8").trim() : "");
for (const f of readdirSync("site").filter((x) => x.endsWith(".html"))) {
  const src = readFileSync(`site/${f}`, "utf8");
  const body = src.match(/<body[^>]*>([\s\S]*)<\/body>/)[1];
  const title = (src.match(/<title>([\s\S]*?)<\/title>/) || [, "fox-kit"])[1];
  const iv = C.getRandomValues(new Uint8Array(12));
  const ct = Buffer.from(await C.subtle.encrypt({ name: "AES-GCM", iv }, key, new TextEncoder().encode(JSON.stringify({ title, body }))));
  const payload = JSON.stringify({ v: 1, n: ITER, s: salt.toString("base64"), i: Buffer.from(iv).toString("base64"), c: ct.toString("base64") });
  const head = src.match(/<head>([\s\S]*?)<\/head>/)[1].replace(/<title>[\s\S]*?<\/title>/, "<title>fox-kit</title>")
    .replace(/<meta name="description"[^>]*>/, '<meta name="robots" content="noindex">');
  writeFileSync(f, `<!doctype html>
<html lang="ja">
<head>${head}<script src="gate.js" defer></script>
</head>
<body>
<div class="gate"><form class="box" id="gate">
  <div class="logo">AI</div>
  <h1>fox-kit</h1>
  <p>AI秘書セットアップの手順書です。<br>お伝えしたパスワードを入れてください。</p>
  <input type="password" id="pw" autocomplete="current-password" placeholder="パスワード" aria-label="パスワード" autofocus>
  <label class="keep"><input type="checkbox" id="keep" checked>この端末では次から入れなくてよい</label>
  <button id="go">開く</button>
  <div class="err" id="err" role="alert"></div>
  <p class="help">分からないときは、渡した人に聞いてください。</p>
</form></div>
<script type="application/json" id="fx">${payload}</script>
</body>
</html>
`);
  console.log("書き出し:", f);
}
if (VAULT) try { mkdirSync(VAULT, { recursive: true }); cpSync("site", VAULT, { recursive: true }); console.log("原稿の控え:", VAULT); }
catch (e) { console.log("（vault への控えは飛ばしました：" + e.message + "）"); }
