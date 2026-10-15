// Antigravity は起動のたびに右側の帯へ Gemini の「Agent」を必ず開く（設定では止められない作り）。
// 起動が落ち着いたところで Claude Code を開き直し、右側の帯の主役を Claude にする。
const vscode = require("vscode");

async function claudeFirst() {
  if (!vscode.workspace.getConfiguration("foxKit.claudeFirst").get("enabled", true)) return;
  for (const cmd of ["claude-vscode.sidebar.open", "claude-vscode.editor.openLast"]) {
    try { await vscode.commands.executeCommand(cmd); return; } catch (e) { /* 次の手へ */ }
  }
}

function activate(context) {
  // Agent は起動処理の後半で開き直されることがあるので、少し間をおいてもう一度
  setTimeout(claudeFirst, 800);
  setTimeout(claudeFirst, 4000);
}
function deactivate() {}
module.exports = { activate, deactivate };
