// fox-kit：Antigravity を Claude 中心にする小さな拡張機能
//  1) 起動時：右側の帯（Gemini の Agent。設定では止められない）を閉じ、左を Claude の会話一覧にする
//  2) ⌘⇧2（Windows は Ctrl+Shift+2）：範囲を選んで画面を撮る → Claude の入力欄に画像と「この画面を見て」を貼って送る
//     外からも呼べる：open "antigravity-ide://fox-kit.claude-first/shot"（Stream Deck などのボタン用）
const vscode = require("vscode");
const cp = require("child_process");
const fs = require("fs");
const os = require("os");
const path = require("path");
const exec = (cmd, args) => new Promise((res) => cp.execFile(cmd, args, (err, out) => res({ ok: !err, out: String(out || "") })));
const wait = (ms) => new Promise((r) => setTimeout(r, ms));

async function run(cmds) {
  for (const cmd of cmds) {
    try { await vscode.commands.executeCommand(cmd); return true; } catch (e) { /* 次の手へ */ }
  }
  return false;
}

async function claudeFirst() {
  const cfg = vscode.workspace.getConfiguration("foxKit.claudeFirst");
  if (!cfg.get("enabled", true)) return;
  await run(["workbench.action.closeAuxiliaryBar"]);
  // 会話は真ん中のタブで開く。Claude Code は一度右の小窓で開くと「次からも右」と覚えてしまうので、起動のたびに戻す
  if (cfg.get("keepCenter", true)) {
    const cc = vscode.workspace.getConfiguration("claudeCode");
    if (cc.get("preferredLocation") !== "panel") {
      try { await cc.update("preferredLocation", "panel", vscode.ConfigurationTarget.Global); } catch (e) {}
    }
  }
  // 左：会話一覧（Claude Code の「会話の一覧」が使える版のときだけ出る）
  if (cfg.get("sessionsOnLeft", true)) await run(["workbench.view.extension.claude-sessions-sidebar"]);
}

// ---------------------------------------------------------------- 画面を撮って Claude に見せる
function shotDir() {
  const d = path.join(os.tmpdir(), "fox-shot");
  fs.mkdirSync(d, { recursive: true });
  for (const f of fs.readdirSync(d)) {            // 1日より古い撮影は消す（写り込みを残さない）
    const p = path.join(d, f);
    try { if (Date.now() - fs.statSync(p).mtimeMs > 864e5) fs.unlinkSync(p); } catch (e) {}
  }
  return d;
}

async function shotToClaude() {
  const cfg = vscode.workspace.getConfiguration("foxKit.shot");
  const msg = cfg.get("message", "この画面を見て");
  const send = cfg.get("autoSend", true);
  if (process.platform === "darwin") {
    const file = path.join(shotDir(), `shot-${Date.now()}.png`);
    await exec("/usr/sbin/screencapture", ["-i", file]);           // 範囲を選ぶ（スペースで窓ごと・Esc でやめる）
    if (!fs.existsSync(file)) return;                                // やめたときは何もしない
    await exec("/usr/bin/osascript", ["-e", `set the clipboard to (read (POSIX file "${file}") as «class PNGf»)`]);
    await run(["claude-vscode.focus"]);
    const script = [
      'tell application "Antigravity IDE" to activate',
      "delay 0.4",
      'tell application "System Events" to keystroke "v" using command down',
      "delay 0.9",
      `set the clipboard to ${JSON.stringify(msg)}`,
      'tell application "System Events" to keystroke "v" using command down',
      "delay 0.4",
    ];
    if (send) script.push('tell application "System Events" to key code 36');
    const r = await exec("/usr/bin/osascript", script.flatMap((l) => ["-e", l]));
    if (!r.ok) vscode.window.showWarningMessage("画面は撮れましたが、Claude に貼れませんでした。システム設定 →「プライバシーとセキュリティ」→「アクセシビリティ」で Antigravity をオンにしてください。");
  } else if (process.platform === "win32") {
    // Windows：範囲を選ぶ画面（Win+Shift+S と同じ）を出し、撮れたら Claude に貼って送る
    await exec("explorer.exe", ["ms-screenclip:"]);
    const ps = `
Add-Type -AssemblyName System.Windows.Forms
for ($i = 0; $i -lt 120; $i++) { Start-Sleep -Milliseconds 500; if ([System.Windows.Forms.Clipboard]::ContainsImage()) { exit 0 } }
exit 1`;
    await exec("powershell", ["-NoProfile", "-Sta", "-Command", "Set-Clipboard -Value $null; " + ps]).then(async (r) => {
      if (!r.ok) return;
      await run(["claude-vscode.focus"]);
      await wait(400);
      const keys = `
Add-Type -AssemblyName System.Windows.Forms
[System.Windows.Forms.SendKeys]::SendWait('^v'); Start-Sleep -Milliseconds 900
Set-Clipboard -Value ${JSON.stringify(msg).replace(/"/g, "'")}
[System.Windows.Forms.SendKeys]::SendWait('^v'); Start-Sleep -Milliseconds 400
${send ? "[System.Windows.Forms.SendKeys]::SendWait('{ENTER}')" : ""}`;
      await exec("powershell", ["-NoProfile", "-Sta", "-Command", keys]);
    });
  }
}

function activate(context) {
  context.subscriptions.push(vscode.commands.registerCommand("foxKit.shotToClaude", shotToClaude));
  context.subscriptions.push(vscode.window.registerUriHandler({ handleUri(uri) { if (uri.path === "/shot") shotToClaude(); } }));
  // Agent やエクスプローラーは起動処理の後半で開き直されることがあるので、少し間をおいてもう一度
  setTimeout(claudeFirst, 800);
  setTimeout(claudeFirst, 4000);
}
function deactivate() {}
module.exports = { activate, deactivate };
