#!/bin/zsh
# 版を出す前に必ず回す点検。1つでも失敗したら出さない。   zsh tests/check.sh
# 見るもの：文法（zsh・Python・JavaScript・PowerShell）／未定義の名前／Windows 標準の PowerShell 5.1 で動かない書き方／試験
cd "${0:A:h:h}"; fail=0
say() { printf '\n== %s\n' "$1"; }
bad() { printf '  NG %s\n' "$1"; fail=1; }

say "zsh の文法"
for f in $(git ls-files '*.sh') tools/fox-kit-cli/fox-kit; do
  case "$(head -1 "$f")" in *zsh*) zsh -n "$f" || bad "$f" ;; *bash*) bash -n "$f" || bad "$f" ;; esac
done
say "Python の文法"
for f in $(git ls-files '*.py'); do /usr/bin/python3 -m py_compile "$f" 2>&1 | head -3; [[ ${pipestatus[1]} == 0 ]] || bad "$f"; done
find . -name __pycache__ -not -path './.git/*' -exec rm -rf {} + 2>/dev/null
say "Python の未定義の名前（消してしまった関数・定数を拾う）"
if command -v uvx >/dev/null; then uvx -q ruff check --no-cache --select F821,F811,F823 $(git ls-files '*.py') || bad "ruff"; else echo "  （uvx が無いので飛ばしました）"; fi
say "JavaScript の文法"
for f in wizard/app.js site.js gate.js site_build.mjs; do node --check "$f" || bad "$f"; done
say "PowerShell：文法・5.1 で動かない書き方・未定義の関数"
if command -v pwsh >/dev/null; then
  pwsh -NoProfile -NoLogo -Command '
  $bad = 0
  foreach ($f in (git ls-files "*.ps1")) {
    $t=$null; $e=$null
    $ast=[System.Management.Automation.Language.Parser]::ParseFile((Resolve-Path $f), [ref]$t, [ref]$e)
    $new = @($ast.FindAll({param($n) $n -is [System.Management.Automation.Language.TernaryExpressionAst] -or $n -is [System.Management.Automation.Language.PipelineChainAst]}, $true)).Count +
           @($t | Where-Object { $_.Kind -in "QuestionQuestion","QuestionQuestionEquals","QuestionDot","QuestionLBracket" }).Count
    $def = @($ast.FindAll({param($n) $n -is [System.Management.Automation.Language.FunctionDefinitionAst]}, $true) | ForEach-Object Name)
    $win = "Get-CimInstance","powercfg","winget","schtasks","cmdkey","reg","where","explorer","taskkill","timeout","icacls","wsl"
    $unk = $ast.FindAll({param($n) $n -is [System.Management.Automation.Language.CommandAst]}, $true) | ForEach-Object { $_.GetCommandName() } |
           Where-Object { $_ -and $_ -match "^[A-Za-z]+-[A-Za-z]+$" } | Sort-Object -Unique |
           Where-Object { $_ -notin $def -and $_ -notin $win -and -not (Get-Command $_ -ErrorAction SilentlyContinue) }
    "  {0}: 文法エラー {1} / 5.1 で動かない書き方 {2} / 未定義の関数 {3}" -f $f, $e.Count, $new, (@($unk) -join ",")
    if ($e.Count -or $new -or @($unk).Count) { $bad = 1 }
  }
  exit $bad' || bad "PowerShell"
else echo "  （pwsh が無いので飛ばしました）"; fi
say "試験"
for t in tests/test_*.py; do /usr/bin/python3 "$t" 2>&1 | tail -1; [[ ${pipestatus[1]} == 0 ]] || bad "$t"; done
for t in tests/test_*.sh; do zsh "$t" 2>&1 | tail -1; [[ ${pipestatus[1]} == 0 ]] || bad "$t"; done
echo; [[ $fail == 0 ]] && echo "すべて通りました" || { echo "失敗があります。直してから出してください"; exit 1; }
