#!/usr/bin/env node
// Nano Banana Pro (Gemini 3 Pro Image) CLI
// 使い方:
//   node generate.js "プロンプト"                         # 生成
//   node generate.js "編集の指示" -i input.png            # 画像編集 / 合成
//   node generate.js "..." -i a.png -i b.png --size 4K --ar 16:9 -o out/x.png
//
// 主なオプション:
//   -i, --input  <path>   入力画像（複数指定可。最大14枚まで参照）
//   -o, --output <path>   出力先（既定: out/nb-<連番>.png）
//   --ar         <ratio>  アスペクト比 1:1 / 16:9 / 9:16 / 4:3 / 3:4 など（既定 1:1）
//   --size       <res>    解像度 1K / 2K / 4K（既定 2K）
//   --model      <id>     モデルID（既定 gemini-3-pro-image-preview）

import { GoogleGenAI } from "@google/genai";
import { readFile, writeFile, mkdir } from "node:fs/promises";
import { existsSync } from "node:fs";
import { extname, dirname, basename } from "node:path";

// --- .env を最小ロード（依存なし） -------------------------------------------
async function loadDotenv() {
  if (!existsSync(".env")) return;
  const txt = await readFile(".env", "utf8");
  for (const line of txt.split("\n")) {
    const m = line.match(/^\s*([\w.]+)\s*=\s*(.*)\s*$/);
    if (!m || line.trim().startsWith("#")) continue;
    const key = m[1];
    let val = m[2].replace(/^["']|["']$/g, "");
    if (!(key in process.env)) process.env[key] = val;
  }
}

// --- 引数パース --------------------------------------------------------------
function parseArgs(argv) {
  const opts = { inputs: [], ar: "1:1", size: "2K", model: null, output: null };
  const promptParts = [];
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === "-i" || a === "--input") opts.inputs.push(argv[++i]);
    else if (a === "-o" || a === "--output") opts.output = argv[++i];
    else if (a === "--ar") opts.ar = argv[++i];
    else if (a === "--size") opts.size = argv[++i];
    else if (a === "--model") opts.model = argv[++i];
    else if (a === "-p" || a === "--prompt") promptParts.push(argv[++i]);
    else if (a === "-h" || a === "--help") opts.help = true;
    else promptParts.push(a);
  }
  opts.prompt = promptParts.join(" ").trim();
  return opts;
}

const MIME = { ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp" };

async function main() {
  await loadDotenv();
  const opts = parseArgs(process.argv.slice(2));

  if (opts.help || !opts.prompt) {
    console.log(`Nano Banana Pro CLI
  node generate.js "プロンプト" [-i 入力画像 ...] [-o 出力] [--ar 16:9] [--size 4K]`);
    process.exit(opts.prompt ? 0 : 1);
  }

  let apiKey = process.env.GEMINI_API_KEY;
  if (!apiKey) {
    // fox-kit：キーは Mac のキーチェーン（fox-kit / gemini）に置く
    try {
      const { execFileSync } = await import("node:child_process");
      apiKey = execFileSync("security", ["find-generic-password", "-s", "fox-kit", "-a", "gemini", "-w"],
        { encoding: "utf8" }).trim();
    } catch { /* 無ければ下でエラー */ }
  }
  if (!apiKey) {
    console.error("✗ Gemini の API キーがありません。`fox-kit packs key` で登録してください（https://aistudio.google.com/apikey で発行）。");
    console.error("  キー発行: https://aistudio.google.com/apikey");
    process.exit(1);
  }

  const model = opts.model || process.env.MODEL || "gemini-3-pro-image-preview";
  const ai = new GoogleGenAI({ apiKey });

  // contents = テキスト + 入力画像（編集 / 合成用）
  const parts = [{ text: opts.prompt }];
  for (const p of opts.inputs) {
    if (!existsSync(p)) { console.error(`✗ 入力画像が見つかりません: ${p}`); process.exit(1); }
    const data = await readFile(p);
    const mime = MIME[extname(p).toLowerCase()] || "image/png";
    parts.push({ inlineData: { mimeType: mime, data: data.toString("base64") } });
  }

  console.log(`▶ model=${model}  ar=${opts.ar}  size=${opts.size}  inputs=${opts.inputs.length}`);
  console.log(`▶ prompt: ${opts.prompt}`);

  const response = await ai.models.generateContent({
    model,
    contents: [{ role: "user", parts }],
    config: {
      responseModalities: ["Image"],
      imageConfig: { aspectRatio: opts.ar, imageSize: opts.size },
    },
  });

  // 出力画像を取り出して保存
  const out = response.candidates?.[0]?.content?.parts || [];
  let saved = 0;
  for (const part of out) {
    if (part.inlineData?.data) {
      const buf = Buffer.from(part.inlineData.data, "base64");
      let dest = opts.output;
      if (!dest) {
        await mkdir("out", { recursive: true });
        dest = `out/nb-${Date.now().toString(36)}-${saved}.png`;
      } else if (saved > 0) {
        const ext = extname(dest);
        dest = `${dirname(dest)}/${basename(dest, ext)}-${saved}${ext}`;
      } else {
        await mkdir(dirname(dest), { recursive: true });
      }
      await writeFile(dest, buf);
      console.log(`✓ 保存: ${dest}  (${(buf.length / 1024).toFixed(0)} KB)`);
      saved++;
    } else if (part.text) {
      console.log(`ℹ モデル応答: ${part.text}`);
    }
  }

  if (saved === 0) {
    console.error("✗ 画像が返りませんでした。プロンプトやモデルID、安全フィルタを確認してください。");
    console.error(JSON.stringify(response, null, 2).slice(0, 2000));
    process.exit(1);
  }
}

main().catch((e) => {
  console.error("✗ エラー:", e?.message || e);
  process.exit(1);
});
