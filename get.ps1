# fox-kit（AI秘書セットアップ）── Windows 用の1行インストーラ
#
#   PowerShell に次の1行を貼る（手順書 index.html の「Windows」タブにある）:
#   powershell -NoProfile -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol='Tls12';iex ([Text.Encoding]::UTF8.GetString((New-Object Net.WebClient).DownloadData('https://kinopy0918.github.io/fox-kit/get.ps1')))"
#
#   ※ irm | iex にしないのは、配信元が文字コードを名乗らないと日本語が化けるため（バイトで取って UTF-8 で読む）
#
# これ1本で: 準備（Git・Python）→ AI本体（Claude Code）→ キット → 組み立て → ログイン → あいさつ
#            → スキル → パソコンの設定 → 初期設定の聞き取り まで進む。
# 途中で止まっても、同じ1行をもう一度貼れば続きから（答えと進み具合は ~/.config/fox-kit/state-win.json）。
#
# Mac 版との違い: ブラウザで進める設定画面・Discord/Slack の常駐連携・Homebrew の道具・画像づくりの鍵は、まだ入らない。
#
# 聞かずに進めたいときは先に環境変数で渡す: FOX_LEVEL FOX_OWNER FOX_AGENT FOX_MACHINE FOX_ROLE
#   FOX_VERSION=0.3.0（この版を入れる） FOX_RESET=1（最初から） FOX_KIT_URL=<zipのURLかフォルダ>（検証用）

$ErrorActionPreference = 'Continue'   # 'Stop' だと外部コマンドのエラー出力だけで止まる（PowerShell 5.1）
$ProgressPreference = 'SilentlyContinue'
try { [Console]::OutputEncoding = [Text.Encoding]::UTF8 } catch {}
$PSDefaultParameterValues['Out-File:Encoding'] = 'utf8'   # *>> の書き込みもログと同じ UTF-8 に（5.1 の既定は UTF-16）
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$Repo  = 'kinopy0918/fox-kit'
$Conf  = Join-Path $HOME '.config\fox-kit'
$State = Join-Path $Conf 'state-win.json'
$Log   = Join-Path $Conf 'fox-install.log'
$KitDir = Join-Path $HOME 'Tools\fox-kit'
$Total = 9
New-Item -ItemType Directory -Force -Path $Conf | Out-Null

# ------------------------------------------------------------------ 表示の道具
$script:B = $true
function T([string]$b, [string]$e) { if ($script:B) { $b } else { $e } }
function Step($n, $s) { Write-Host ''; Write-Host "━━ $n/$Total  $s" -ForegroundColor Cyan }
function Ok($s)   { Write-Host "  ✓ $s" -ForegroundColor Green }
function Warn($s) { Write-Host "  ! $s" -ForegroundColor Yellow }
function Die($s)  {
  Write-Host ''; Write-Host "  ✕ $s" -ForegroundColor Red
  Write-Host ('  ' + (T 'もう一度、同じ1行を貼り付けると続きから始まります。' '再実行で続きから再開します。'))
  Write-Host "  （記録: $Log）"
  exit 1
}
function LogLine($s) { Add-Content -Path $Log -Value "$(Get-Date -Format s) $s" -Encoding UTF8 }

# ------------------------------------------------------------------ 覚えておく（続きから再開）
if ($env:FOX_RESET) { Remove-Item -Force $State -ErrorAction SilentlyContinue }
$S = @{ done = @() }
$Resumed = $false
if (Test-Path $State) {
  try {
    $j = Get-Content $State -Raw -Encoding UTF8 | ConvertFrom-Json
    foreach ($p in $j.PSObject.Properties) { $S[$p.Name] = $p.Value }
    if (-not $S.done) { $S.done = @() }
    $Resumed = $true
  } catch { $S = @{ done = @() } }
}
function Save { ($S | ConvertTo-Json -Depth 4) | Set-Content -Path $State -Encoding UTF8 }
function Mark($id) { if ($S.done -notcontains $id) { $S.done = @($S.done) + $id }; Save }
function IsDone($id) { return ($S.done -contains $id) }

function Ask-YesNo($q, $default = $true) {
  $hint = if ($default) { '（空欄なら はい）' } else { '（空欄なら いいえ）' }
  for ($i = 0; $i -lt 3; $i++) {
    $a = (Read-Host "  $q [はい=y / いいえ=n]$hint").Trim().ToLower()
    if ($a -eq '') { return $default }
    if ($a -in @('y', 'yes', 'はい', '1')) { return $true }
    if ($a -in @('n', 'no', 'いいえ', '2')) { return $false }
    Warn 'y か n で答えてください'
  }
  return $default
}
function Valid-Name($v) {
  if (-not $v) { return '空欄はできません' }
  if ($v.Length -gt 30) { return "30文字以内にしてください（いま$($v.Length)文字）" }
  if ($v -match '["$`\\|]') { return '記号（" $ ` \ |）は使えません' }
  return $null
}
function Ask-Name($key, $q, $default) {
  $envv = [Environment]::GetEnvironmentVariable($key)
  if ($envv) { $S[$key] = $envv }
  if ($S[$key]) { $err = Valid-Name $S[$key]; if (-not $err) { Save; return } }
  for ($i = 0; $i -lt 3; $i++) {
    $hint = if ($default) { "（空欄なら「$default」）" } else { '' }
    $a = (Read-Host "  $q$hint").Trim()
    if (-not $a) { $a = $default }
    $err = Valid-Name $a
    if (-not $err) { $S[$key] = $a; Save; return }
    Warn $err
  }
  Die "「$q」を受け取れませんでした"
}

function Refresh-Path {
  $m = [Environment]::GetEnvironmentVariable('Path', 'Machine')
  $u = [Environment]::GetEnvironmentVariable('Path', 'User')
  $env:Path = "$HOME\.local\bin;$u;$m"
}
function Has-Winget { return [bool](Get-Command winget -ErrorAction SilentlyContinue) }
function Winget-Install($id) {
  LogLine "winget install $id"
  & winget install --id $id -e --silent --accept-package-agreements --accept-source-agreements *>> $Log
  return ($LASTEXITCODE -eq 0 -or $LASTEXITCODE -eq -1978335189)   # 後者＝もう入っている
}
function Download($url, $dest) { LogLine "GET $url"; (New-Object Net.WebClient).DownloadFile($url, $dest) }

function Find-Python {
  foreach ($c in @(Get-Command python -All -ErrorAction SilentlyContinue)) {
    if ($c.Source -notlike '*WindowsApps*') { return $c.Source }   # WindowsApps のものはストアへの入口で、中身がない
  }
  foreach ($d in @("$env:LOCALAPPDATA\Programs\Python", "$env:ProgramFiles\Python*")) {
    $p = Get-ChildItem -Path $d -Filter python.exe -Recurse -Depth 2 -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($p) { return $p.FullName }
  }
  return $null
}
function Find-Antigravity {
  foreach ($d in @("$env:LOCALAPPDATA\Programs", $env:ProgramFiles)) {
    $hit = Get-ChildItem -Path $d -Directory -Filter 'Antigravity*' -ErrorAction SilentlyContinue | Where-Object { Test-Path "$($_.FullName)\bin" } | Select-Object -First 1
    if ($hit) { return $hit.FullName }
  }
  return $null
}
function Find-GitBash {
  foreach ($p in @("$env:ProgramFiles\Git\bin\bash.exe", "${env:ProgramFiles(x86)}\Git\bin\bash.exe", "$env:LOCALAPPDATA\Programs\Git\bin\bash.exe")) {
    if ($p -and (Test-Path $p)) { return $p }
  }
  return $null
}

# ------------------------------------------------------------------ はじめに
Write-Host 'fox-kit（AI秘書のセットアップ・Windows 版）' -ForegroundColor White
if ($env:OS -ne 'Windows_NT') { Die 'これは Windows 用です。Mac は手順書の「Mac」の1行を使ってください' }

$lv = if ($env:FOX_LEVEL) { $env:FOX_LEVEL } else { $S.FOX_LEVEL }
if (-not $lv) {
  Write-Host '  はじめに1つだけ教えてください。'
  Write-Host '    1) はじめて・よくわからない（言葉をかみくだいて案内します）'
  Write-Host '    2) AIやパソコンの設定に慣れている（短く案内します）'
  $a = (Read-Host '  番号を入力（空欄なら 1）').Trim()
  $lv = if ($a -eq '2') { 'expert' } else { 'beginner' }
}
$S.FOX_LEVEL = $lv; Save
$script:B = ($lv -ne 'expert')

if ($Resumed) { Ok (T '前回の続きから始めます（答えていただいた内容は覚えています）' "state を読み込みました: $State（最初からは FOX_RESET=1）") }
else {
  Write-Host ('  ' + (T 'あなた専用のAI秘書を、このパソコンに用意します（30分〜1時間）。途中でいくつか質問します。' 'Claude Code を入れ、汎用FOXとして組み立てます。'))
  Write-Host ('  ' + (T '※ 「このアプリがデバイスに変更を加えることを許可しますか？」と何度か出ます。そのたびに「はい」を押してください。' '※ UAC の確認が数回出ます（Git・Python・Google ドライブなど）。'))
  Write-Host ('  ' + (T '※ このAIは、いちいち「実行してよいですか？」と聞かずに作業を進める設定になります。お金・社外への送信などは必ずあなたに確認します。' '※ bypassPermissions が入ります。金銭・対外不可逆・一次情報は人に確認する規則つき。'))
}

# ------------------------------------------------------------------ 1. 質問
Step 1 (T 'いくつか教えてください' '基本情報')
Ask-Name 'FOX_OWNER'   (T 'このパソコンを使う人のお名前（例: 山田さん）' 'オーナー名') ''
Ask-Name 'FOX_AGENT'   (T 'AIの名前（呼びかけるときの名前）' 'エージェント名') 'FOX'
Ask-Name 'FOX_MACHINE' (T 'このパソコンの呼び方（例: 事務所のパソコン）' '端末ラベル') $env:COMPUTERNAME
Ask-Name 'FOX_ROLE'    (T 'このパソコンで主にすること（例: 経理の仕事）' '端末の役割') '作業機'
Ok "$($S.FOX_OWNER) の「$($S.FOX_AGENT)」として組み立てます"

# ------------------------------------------------------------------ 最新にする（部品を入れる前）
$build = [Environment]::OSVersion.Version.Build
if ($build -lt 17763) { Die (T "このパソコンの Windows は古く（ビルド $build）、AIの本体が動きません。設定 →「Windows Update」で新しい版にしてから、同じ1行をもう一度貼ってください" "Windows 10 1809（17763）以上が必要: build $build") }
if (-not (IsDone 'update')) {
  Write-Host ''
  Write-Host ('  ' + (T '先にパソコンを最新にしておくのがおすすめです（古いままだと、AIや道具がうまく動かないことがあります）。' 'Windows Update を先に当てるのを推奨'))
  if (Ask-YesNo (T '「Windows Update」の画面を開いて、更新を確かめますか？' 'Windows Update を開く？') $true) {
    Start-Process 'ms-settings:windowsupdate-action'
    Write-Host ('  ' + (T "開いた画面で「更新プログラムのチェック」→ 出てきたものを「ダウンロードしてインストール」。`n  「今すぐ再起動」が必要と出たら、再起動のあと PowerShell を開いて同じ1行を貼れば、ここから続きます（答えは覚えています）。" 'チェック→インストール。再起動後は同じ1行で再開'))
    [void](Read-Host (T '  更新が終わったら（または、いまは更新しないなら）Enter を押してください' '  Enter で続行'))
    if (Get-Command winget -ErrorAction SilentlyContinue) { & winget source update *>> $Log }   # 部品を入れる道具（winget）の一覧も最新に
  }
  Mark 'update'
}

# ------------------------------------------------------------------ 2. 準備（Git と Python）
Step 2 (T 'AIが使う部品を入れる（Git・Python）' 'Git for Windows / Python')
Refresh-Path
if (Find-GitBash) { Ok (T '部品1（Git）はもう入っています' 'Git: installed') }
else {
  Write-Host ('  ' + (T '部品1（Git）を入れています…（数分）' 'Git for Windows を導入'))
  $okG = $false
  if (Has-Winget) { $okG = Winget-Install 'Git.Git' }
  if (-not (Find-GitBash)) {
    $rel = Invoke-RestMethod 'https://api.github.com/repos/git-for-windows/git/releases/latest'
    $asset = $rel.assets | Where-Object { $_.name -match '^Git-[\d.]+-64-bit\.exe$' } | Select-Object -First 1
    if ($asset) {
      $exe = Join-Path $env:TEMP $asset.name
      Download $asset.browser_download_url $exe
      Start-Process -FilePath $exe -ArgumentList '/VERYSILENT', '/NORESTART', '/SP-' -Wait
    }
  }
  Refresh-Path
  if (Find-GitBash) { Ok (T '部品1（Git）を入れました' 'Git: installed') }
  else { Die (T '部品1（Git）を入れられませんでした。インターネットにつながっているか確かめてください' 'Git for Windows の導入に失敗') }
}

$py = Find-Python
if ($py) { Ok (T '部品2（Python）はもう入っています' "Python: $py") }
else {
  Write-Host ('  ' + (T '部品2（Python）を入れています…（数分）' 'Python 3.12 を導入'))
  if (Has-Winget) { Winget-Install 'Python.Python.3.12' | Out-Null }
  Refresh-Path; $py = Find-Python
  if (-not $py) {
    $exe = Join-Path $env:TEMP 'python-3.12.10-amd64.exe'
    Download 'https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe' $exe
    Start-Process -FilePath $exe -ArgumentList '/quiet', 'InstallAllUsers=0', 'PrependPath=1', 'Include_launcher=1' -Wait
    Refresh-Path; $py = Find-Python
  }
  if ($py) { Ok (T '部品2（Python）を入れました' "Python: $py") }
  else { Die (T '部品2（Python）を入れられませんでした' 'Python の導入に失敗') }
}
# キットの道具は「python3」という名前で呼ぶ。Windows の Python には無いので、同じものを横に置く
$py3 = Join-Path (Split-Path $py) 'python3.exe'
if (-not (Test-Path $py3)) { Copy-Item $py $py3 -ErrorAction SilentlyContinue }
# Program Files の Python などでコピーできないときの保険：Git Bash 用の小さな呼び出し口を ~/.local/bin に置く
$lbin = Join-Path $HOME '.local\bin'
New-Item -ItemType Directory -Force -Path $lbin | Out-Null
$shim = "#!/bin/sh`nexec `"$($py -replace '\\', '/')`" `"`$@`"`n"
[IO.File]::WriteAllText((Join-Path $lbin 'python3'), $shim, (New-Object Text.UTF8Encoding $false))
if (-not (Test-Path $py3)) { Warn (T 'Python の呼び名を一部そろえられませんでした（たいていは問題ありません）' "python3.exe を作れませんでした（$py3）。Git Bash 用の呼び出し口で代用") }
# 日本語のファイル名・文章を正しく読み書きさせる
[Environment]::SetEnvironmentVariable('PYTHONUTF8', '1', 'User'); $env:PYTHONUTF8 = '1'
# 画面の動かし方を Python で選ぶ人向けに、Python の場所を PATH の先頭へ（ストアの入口より前）
$pyDir = Split-Path $py
$up = [Environment]::GetEnvironmentVariable('Path', 'User')
if ($up -notlike "*$pyDir*") { [Environment]::SetEnvironmentVariable('Path', "$pyDir;$pyDir\Scripts;$up", 'User') }
Refresh-Path
Mark 'prep'

# ------------------------------------------------------------------ 3. 本体
Step 3 (T 'AIの本体を入れる' 'Claude Code 本体')
if (Get-Command claude -ErrorAction SilentlyContinue) { Ok (T 'もう入っています' "入っています: $(claude --version 2>$null)") }
else {
  Write-Host ('  ' + (T '入れています…（数分かかります）' 'claude.ai/install.ps1'))
  $inst = Join-Path $env:TEMP 'claude-install.ps1'
  Download 'https://claude.ai/install.ps1' $inst
  & powershell -NoProfile -ExecutionPolicy Bypass -File $inst *>> $Log
  $lb = Join-Path $HOME '.local\bin'
  $up = [Environment]::GetEnvironmentVariable('Path', 'User')
  if ($up -notlike "*$lb*") { [Environment]::SetEnvironmentVariable('Path', "$lb;$up", 'User') }
  Refresh-Path
  if (-not (Get-Command claude -ErrorAction SilentlyContinue)) { Die (T 'うまく入りませんでした。インターネットにつながっているか確かめてください' 'Claude Code が入りませんでした') }
  Ok (T '入れました' "入れました: $(claude --version 2>$null)")
}
# AIが Git Bash の場所を迷わないように
$gb = Find-GitBash
if ($gb) { [Environment]::SetEnvironmentVariable('CLAUDE_CODE_GIT_BASH_PATH', $gb, 'User'); $env:CLAUDE_CODE_GIT_BASH_PATH = $gb }
Mark 'claude'

# ------------------------------------------------------------------ 4. キット
Step 4 (T 'AI秘書の部品を取ってくる' 'キットを取得')
if ((IsDone 'kit') -and (Test-Path "$KitDir\setup\build_win.py") -and -not $env:FOX_UPDATE) { Ok (T 'もう取ってあります' "取得済み: $KitDir（取り直しは `$env:FOX_UPDATE=1）") } else {
$tmp = Join-Path $env:TEMP ("fox-kit-" + [guid]::NewGuid().ToString('N').Substring(0, 8))
New-Item -ItemType Directory -Force -Path $tmp | Out-Null
if ($env:FOX_KIT_URL -and (Test-Path $env:FOX_KIT_URL)) {
  Copy-Item -Recurse -Path $env:FOX_KIT_URL -Destination "$tmp\kit"
} else {
  $url = $env:FOX_KIT_URL
  if (-not $url) {
    $ver = $env:FOX_VERSION
    if (-not $ver) { try { $ver = ((Invoke-RestMethod "https://api.github.com/repos/$Repo/releases/latest").tag_name) -replace '^v', '' } catch {} }
    $url = if ($ver) { "https://github.com/$Repo/archive/refs/tags/v$ver.zip" } else { "https://github.com/$Repo/archive/refs/heads/main.zip" }
  }
  try { Download $url "$tmp\kit.zip"; Expand-Archive -Path "$tmp\kit.zip" -DestinationPath "$tmp\x" -Force -ErrorAction Stop }
  catch { Die (T '部品を取ってこられませんでした。インターネットにつながっているか確かめてください' "キットを取得できませんでした: $url") }
  Move-Item -Path (Get-ChildItem "$tmp\x" | Select-Object -First 1).FullName -Destination "$tmp\kit"
}
if (-not (Test-Path "$tmp\kit\setup\build_win.py")) { Die (T '部品の中身がおかしいようです' 'キットの中身が不正です（setup/build_win.py がない）') }
New-Item -ItemType Directory -Force -Path (Split-Path $KitDir) | Out-Null
try {
  if (Test-Path $KitDir) { Rename-Item $KitDir ("fox-kit.bak-" + (Get-Date -Format 'yyyyMMdd-HHmmss')) -ErrorAction Stop }
  Move-Item "$tmp\kit" $KitDir -ErrorAction Stop
} catch { Die (T '前の部品を入れ替えられませんでした。Antigravity などを閉じてから、同じ1行をもう一度貼ってください' "KitDir を入れ替えられません（使用中？）: $KitDir") }
Remove-Item -Recurse -Force $tmp -ErrorAction SilentlyContinue
Ok (T '取ってきました' $KitDir)
Mark 'kit'
}

# ------------------------------------------------------------------ 5. 組み立て
Step 5 (T 'あなた専用に組み立てる' '組み立て（人格・作法・スキル・記憶・設定）')
$env:FOX_OWNER = $S.FOX_OWNER; $env:FOX_AGENT = $S.FOX_AGENT; $env:FOX_MACHINE = $S.FOX_MACHINE
$env:FOX_ROLE = $S.FOX_ROLE; $env:FOX_LEVEL = $S.FOX_LEVEL
& $py "$KitDir\setup\build_win.py" 2>&1 | ForEach-Object { Add-Content -Path $Log -Value "$_" -Encoding UTF8; if (-not $script:B) { Write-Host "    $_" } }
if ($LASTEXITCODE -ne 0) { Die (T '組み立ての途中で止まりました' 'build_win.py 失敗') }
Ok (T '組み立てました（仕事の作法・資料のチェック役・話し方の設定も入りました）' 'build_win.py 完了')
Mark 'build'

$Todo = New-Object System.Collections.ArrayList

# ------------------------------------------------------------------ 6. ログイン
Step 6 (T 'AIのアカウントにログイン' 'Claude にログイン')
function Logged-In { try { return ((claude auth status 2>$null | Out-String) -match '"loggedIn":\s*true') } catch { return $false } }
if (Logged-In) { Ok (T 'ログイン済みです' 'ログイン済み'); Mark 'login' }
else {
  Write-Host ('  ' + (T "インターネットの画面が開きます。AIの契約をしたアカウントで「ログイン」→「許可」を押してください。`n  ★会社のパソコンなら、会社で契約したアカウントを使ってください（Pro 以上の契約が要ります）。`n  画面にコードが出たら、この画面に貼り付けて Enter。" 'ブラウザで OAuth（会社の端末なら会社の契約アカウントで）'))
  try { & claude auth login } catch {}
  if (Logged-In) { Ok (T 'ログインできました' 'ログイン完了'); Mark 'login' }
  else { [void]$Todo.Add((T 'AIのアカウントにログインする → 同じ1行をもう一度貼り付けると、ここから再開します（やらないと、AIが動きません）' 'claude auth login（未完了）')) }
}

# ------------------------------------------------------------------ 7. あいさつ
Step 7 (T 'AIにあいさつしてもらう' '動作確認')
if (IsDone 'login') {
  Push-Location $HOME
  & claude -p '一言で自己紹介して。あなたの名前と、誰の秘書かを言って' --output-format text
  if ($LASTEXITCODE -eq 0) { Mark 'hello' } else { Warn (T '返事がありませんでした' '応答なし') }
  Pop-Location
} else { Warn (T 'ログインが済んだら、ここであいさつします' 'ログイン後に実行') }

# ------------------------------------------------------------------ 8. スキルとパソコンの設定
Step 8 (T 'スキルとパソコンの設定' 'packs（plugins / upstream skills）・Chrome・電源・Antigravity')
if (IsDone 'packs') { Ok (T 'スキルはそろっています' 'packs: done') }
elseif ((IsDone 'login') -and (Ask-YesNo (T 'SEO・ノート・文書づくりなどのスキルをまとめて入れますか？（5〜10分）' 'packs（plugins＋upstream skills）を入れる？'))) {
  & $py "$KitDir\tools\fox-packs\packs.py" install-win
  if ($LASTEXITCODE -eq 0) { Mark 'packs' } else { Warn (T 'スキルの一部が入りませんでした（あとでやり直せます）' 'packs 一部失敗') }
}

# Chrome（AIがブラウザを操作する公式の機能「Claude in Chrome」は Chrome で動く）
function Find-Chrome { foreach ($p in @("$env:ProgramFiles\Google\Chrome\Application\chrome.exe", "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe", "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe")) { if ($p -and (Test-Path $p)) { return $p } }; return $null }
if (-not (IsDone 'chrome')) {
  if (Ask-YesNo (T 'Chrome（ブラウザ）を入れて、AIがブラウザを操作できるようにしますか？（調べ物や入力の代行に使います）' 'Google Chrome＋Claude in Chrome 拡張') $true) {
    if (-not (Find-Chrome)) {
      Write-Host ('  ' + (T 'Chrome を入れています…（1〜2分）' 'Google Chrome を導入'))
      if (Has-Winget) { Winget-Install 'Google.Chrome' | Out-Null }
      if (-not (Find-Chrome)) {
        $exe = Join-Path $env:TEMP 'chrome_installer.exe'
        try { Download 'https://dl.google.com/chrome/install/latest/chrome_installer.exe' $exe; Start-Process -FilePath $exe -ArgumentList '/silent', '/install' -Wait } catch {}
      }
    }
    $chromeExe = Find-Chrome
    if ($chromeExe) {
      Ok (T 'Chrome が入りました' "Chrome: $chromeExe")
      $ext = Get-ChildItem "$env:LOCALAPPDATA\Google\Chrome\User Data\*\Extensions\fcoeoabgfenejglbffodgkkbkcdhcgfn" -Directory -ErrorAction SilentlyContinue
      if ($ext) { Ok (T 'AIが Chrome を操作するための拡張（Claude）はもう入っています' 'Claude in Chrome: installed') }
      else {
        Start-Process -FilePath $chromeExe -ArgumentList 'https://chromewebstore.google.com/detail/claude/fcoeoabgfenejglbffodgkkbkcdhcgfn'
        Write-Host ('  ' + (T "Chrome に「Claude」の拡張の画面を開きました。`n    1)「Chrome に追加」→「拡張機能を追加」を押す`n    2) 出てきた画面で、AI と同じアカウントでログインする" 'ウェブストアで Claude in Chrome を追加→同じ組織でログイン'))
        [void](Read-Host (T '  終わったら Enter（いまやらないなら、そのまま Enter）' '  Enter で続行'))
      }
      if (Ask-YesNo (T 'Chrome を「いつも使うブラウザ」にしますか？（Windows の決まりで、設定の画面であなたに押してもらいます）' '既定ブラウザを Chrome に（ms-settings:defaultapps）') $true) {
        Start-Process 'ms-settings:defaultapps'
        Write-Host ('  ' + (T '開いた画面で「Google Chrome」を探して押し、いちばん上の「既定値に設定」を押してください。' '既定のアプリ → Google Chrome →「既定値に設定」'))
        [void](Read-Host (T '  終わったら Enter' '  Enter で続行'))
      }
    } else { Warn (T 'Chrome を自動で入れられませんでした。あとで https://www.google.com/chrome/ から入れられます' 'Chrome 導入失敗') }
  }
  Mark 'chrome'
}

if (-not (IsDone 'power')) {
  if (Ask-YesNo (T 'このパソコンは置きっぱなし（持ち歩かない）ですか？ はいなら、電源につないでいる間は眠らない設定にします' '据え置き？（AC接続中スリープ無効）') $false) {
    & powercfg /change standby-timeout-ac 0 *>> $Log
    & powercfg /change hibernate-timeout-ac 0 *>> $Log
    Ok (T '電源につないでいる間は眠らないようにしました（画面だけは消えます）' 'standby/hibernate AC = 0')
  }
  Mark 'power'
}

$agDir = Find-Antigravity
if (-not $agDir -and -not (IsDone 'antigravity')) {
  if (Ask-YesNo (T 'AIと画面で作業するためのアプリ「Antigravity」を入れますか？（慣れてきたら便利です）' 'Antigravity IDE を入れる？') $true) {
    try {
      $arch = if ($env:PROCESSOR_ARCHITECTURE -eq 'ARM64') { 'windows-arm64' } else { 'windows-x64' }
      $rq = [Net.HttpWebRequest]::Create('https://antigravity.google/download')   # gzip で返るので解凍させて読む
      $rq.AutomaticDecompression = [Net.DecompressionMethods]::GZip -bor [Net.DecompressionMethods]::Deflate
      $page = (New-Object IO.StreamReader($rq.GetResponse().GetResponseStream(), [Text.Encoding]::UTF8)).ReadToEnd()
      $m = [regex]::Match($page, "https://[^`"' ]+/$arch/Antigravity%20IDE\.exe")
      if (-not $m.Success) { throw 'url' }
      $exe = Join-Path $env:TEMP 'AntigravityIDE.exe'
      Write-Host ('  ' + (T 'Antigravity を取ってきます（約230MB。回線によっては10分以上かかります。画面が止まって見えても待ってください）…' 'download Antigravity IDE (~230MB)'))
      Download $m.Value $exe
      Write-Host ('  ' + (T '入れています…（入れ終わると Antigravity が開くことがあります。開いたままで大丈夫です）' 'install (silent)'))
      # -Wait にすると、インストーラが起動した Antigravity が閉じられるまで待ってしまう（PowerShell は子の子まで待つ）。インストーラ本体だけ待つ
      $inst = Start-Process -FilePath $exe -ArgumentList '/VERYSILENT', '/NORESTART', '/SUPPRESSMSGBOXES' -PassThru
      if (-not $inst.WaitForExit(900000)) { throw 'timeout' }
      $agDir = Find-Antigravity
      if ($agDir) { Ok (T 'Antigravity を入れました' 'Antigravity IDE installed') } else { throw 'install' }
    } catch {
      Start-Process 'https://antigravity.google/download'
      Warn (T '自動で入れられなかったので、公式の画面を開きました。「Download for Windows」を押して入れてください' 'URL 取得/導入に失敗。公式ページを開いた')
    }
  }
  Mark 'antigravity'
}
if ($agDir) {
  $cli = Get-ChildItem -Path "$agDir\bin" -Filter '*.cmd' -ErrorAction SilentlyContinue | Select-Object -First 1
  if ($cli) {
    # 拡張の取り込みは、まれに終わらないことがあるので1つ2分で打ち切る（あとで Antigravity の画面から入れ直せる）
    function Install-Ext($arg) {
      $pr = Start-Process -FilePath $cli.FullName -ArgumentList '--install-extension', $arg, '--force' -PassThru -WindowStyle Hidden
      if (-not $pr.WaitForExit(120000)) { try { $pr.Kill() } catch {}; LogLine "extension timeout: $arg" }
    }
    Write-Host ('  ' + (T 'Antigravity に AI の部品を入れています（1〜3分）…' 'install extensions'))
    foreach ($ext in @('anthropic.claude-code', 'ms-ceintl.vscode-language-pack-ja')) { Install-Ext $ext }
    # 起動のたびに Gemini の Agent パネルが開く（設定で止められない）→ 開いた直後に右側の帯を Claude に切り替える
    $vsix = Join-Path $KitDir 'tools\claude-first\claude-first.vsix'
    if (Test-Path $vsix) { Install-Ext $vsix }
    # 画面を日本語に・Claude の最初の案内を出さない・会話は真ん中のタブで開く（持ち主が決めた値は上書きしない）
    $agUser = Join-Path $env:APPDATA ((Split-Path $agDir -Leaf) + '\User\settings.json')
    $agArgv = Join-Path $HOME '.antigravity-ide\argv.json'
    & $py -c "import json,os,sys`nfor p,kv in ((sys.argv[1],{'claudeCode.preferredLocation':'panel','claudeCode.hideOnboarding':True}),(sys.argv[2],{'locale':'ja'})):`n    os.makedirs(os.path.dirname(p),exist_ok=True)`n    try: d=json.load(open(p,encoding='utf-8')) if os.path.exists(p) else {}`n    except Exception: continue`n    [d.setdefault(k,v) for k,v in kv.items()]`n    json.dump(d,open(p,'w',encoding='utf-8'),indent=4,ensure_ascii=False)" $agUser $agArgv *>> $Log
    Ok (T 'Antigravity の中で AI を使えるようにし、画面を日本語にしました' 'extensions: claude-code, language-pack-ja')
  }
}

# ------------------------------------------------------------------ 9. 初期設定の聞き取り
Step 9 (T 'AIと最初のお話（初期設定）' '初期設定の聞き取り（/fox-setup）')
if (IsDone 'interview') { Ok (T '初期設定は済んでいます' 'interview: done') }
elseif (IsDone 'login') {
  Write-Host ('  ' + (T "AIが、あなたの仕事や使っている道具について質問します。答えるだけで設定が進みます。`n  AIが「初期設定が終わりました」と言ったら、キーボードの Ctrl を押しながら C を2回押すと終われます。" '/fox-setup を起動（終了: Ctrl+C 2回）'))
  Push-Location $HOME
  & claude '/fox-setup'
  Pop-Location
  # 初期設定の最後に会社の決まり（company.md）が書かれる＝そこまで行けば済み。途中でやめたら次回また続きから
  if (Test-Path (Join-Path $HOME '.claude\rules\company.md')) { Mark 'interview' }
  else { [void]$Todo.Add((T '初期設定のお話が途中です → 同じ1行をもう一度貼ると、続きから再開します' '/fox-setup 未完了（再実行で再開）')) }
} else { [void]$Todo.Add((T 'ログインが済んだら、同じ1行をもう一度貼ると AI との最初のお話（初期設定）に進みます' 'ログイン後に /fox-setup')) }

# ------------------------------------------------------------------ 仕上げ
Write-Host ''
if ($Todo.Count -eq 0) {
  Write-Host (T 'すべて完了しました。' '完了。') -ForegroundColor Green
  Write-Host ('  ' + (T "これからは、スタートメニューで「PowerShell」を開いて  claude  と打てば、いつでも$($S.FOX_AGENT)と話せます。`n  Antigravity を入れた場合は、左の Claude のマークから話しかけるのがいちばん楽です。" '使い方: ホーム（~）で claude。Antigravity なら Claude Code 拡張から'))
} else {
  Write-Host (T 'あと少しです。残りの作業：' '残作業：') -ForegroundColor Yellow
  $i = 1; foreach ($x in $Todo) { Write-Host "  $i. $x"; $i++ }
}
Write-Host (T "  （うまくいかなかったときの記録: $Log）" "  log: $Log")
