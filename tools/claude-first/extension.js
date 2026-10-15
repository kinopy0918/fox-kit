// Antigravity は起動のたびに右側の帯へ Gemini の「Agent」を必ず開き、左はエクスプローラーになる（設定では変えられない作り）。
// 起動が落ち着いたところで、右側の帯を閉じ、左を Claude の会話一覧にする。会話は真ん中のタブで開く。
const vscode = require("vscode");

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
  // 左：会話一覧（Claude Code の「会話の一覧」が使える版のときだけ出る）
  if (cfg.get("sessionsOnLeft", true)) await run(["workbench.view.extension.claude-sessions-sidebar"]);
}

function activate() {
  // Agent やエクスプローラーは起動処理の後半で開き直されることがあるので、少し間をおいてもう一度
  setTimeout(claudeFirst, 800);
  setTimeout(claudeFirst, 4000);
}
function deactivate() {}
module.exports = { activate, deactivate };
