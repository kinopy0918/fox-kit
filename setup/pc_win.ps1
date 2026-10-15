# Windows のパソコンの設定（設定画面の「パソコンの設定」から裏で呼ぶ。質問はしない）
#   FOX_PC_USE=office|mobile   office なら電源につないでいる間は眠らない
#   FOX_CHROME=1|2             1 なら Chrome を入れる（既定のブラウザ・拡張は設定画面で本人が押す）
#   FOX_ANTIGRAVITY=1|2        1 なら Antigravity を入れ、Claude Code・日本語・同梱の拡張を入れる
$ErrorActionPreference = 'Continue'
$ProgressPreference = 'SilentlyContinue'
try { [Console]::OutputEncoding = [Text.Encoding]::UTF8 } catch {}
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$KitDir = if ($env:KIT_DIR) { $env:KIT_DIR } else { Split-Path $PSScriptRoot }

function Say($s) { Write-Host $s }
function Has-Winget { return [bool](Get-Command winget -ErrorAction SilentlyContinue) }
function Winget-Install($id) {
  & winget install --id $id -e --silent --accept-package-agreements --accept-source-agreements | Out-Null
  return ($LASTEXITCODE -eq 0 -or $LASTEXITCODE -eq -1978335189)
}
function Download($url, $dest) { (New-Object Net.WebClient).DownloadFile($url, $dest) }
function Find-Chrome { foreach ($p in @("$env:ProgramFiles\Google\Chrome\Application\chrome.exe", "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe", "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe")) { if ($p -and (Test-Path $p)) { return $p } }; return $null }
function Find-Antigravity {
  foreach ($d in @("$env:LOCALAPPDATA\Programs", $env:ProgramFiles)) {
    $hit = Get-ChildItem -Path $d -Directory -Filter 'Antigravity*' -ErrorAction SilentlyContinue | Where-Object { Test-Path "$($_.FullName)\bin" } | Select-Object -First 1
    if ($hit) { return $hit.FullName }
  }
  return $null
}
$py = (Get-Command python -ErrorAction SilentlyContinue | Where-Object { $_.Source -notlike '*WindowsApps*' } | Select-Object -First 1).Source

# ---------------------------------------------------------------- 電源
if ($env:FOX_PC_USE -eq 'office') {
  & powercfg /change standby-timeout-ac 0 | Out-Null
  & powercfg /change hibernate-timeout-ac 0 | Out-Null
  Say '電源につないでいる間は眠らないようにしました（画面だけは消えます）'
}

# ---------------------------------------------------------------- Chrome
if ($env:FOX_CHROME -ne '2') {
  if (-not (Find-Chrome)) {
    Say 'Chrome を入れています（1〜2分）…'
    if (Has-Winget) { Winget-Install 'Google.Chrome' | Out-Null }
    if (-not (Find-Chrome)) {
      $exe = Join-Path $env:TEMP 'chrome_installer.exe'
      try { Download 'https://dl.google.com/chrome/install/latest/chrome_installer.exe' $exe; $p = Start-Process -FilePath $exe -ArgumentList '/silent', '/install' -PassThru; [void]$p.WaitForExit(600000) } catch {}
    }
  }
  if (Find-Chrome) { Say 'Chrome が入りました' } else { Say '! Chrome を自動で入れられませんでした（あとで https://www.google.com/chrome/ から入れられます）' }
}

# ---------------------------------------------------------------- Antigravity
if ($env:FOX_ANTIGRAVITY -ne '2') {
  $agDir = Find-Antigravity
  if (-not $agDir) {
    try {
      $arch = if ($env:PROCESSOR_ARCHITECTURE -eq 'ARM64') { 'windows-arm64' } else { 'windows-x64' }
      $rq = [Net.HttpWebRequest]::Create('https://antigravity.google/download')   # gzip で返るので解凍させて読む
      $rq.AutomaticDecompression = [Net.DecompressionMethods]::GZip -bor [Net.DecompressionMethods]::Deflate
      $page = (New-Object IO.StreamReader($rq.GetResponse().GetResponseStream(), [Text.Encoding]::UTF8)).ReadToEnd()
      $m = [regex]::Match($page, "https://[^`"' ]+/$arch/Antigravity%20IDE\.exe")
      if (-not $m.Success) { throw 'url' }
      Say 'Antigravity を取ってきています（約230MB。回線によっては10分以上かかります）…'
      $exe = Join-Path $env:TEMP 'AntigravityIDE.exe'
      Download $m.Value $exe
      Say 'Antigravity を入れています…'
      # -Wait だとインストーラが起動した Antigravity が閉じられるまで待ってしまうので、本体だけ待つ
      $inst = Start-Process -FilePath $exe -ArgumentList '/VERYSILENT', '/NORESTART', '/SUPPRESSMSGBOXES' -PassThru
      [void]$inst.WaitForExit(900000)
      $agDir = Find-Antigravity
    } catch { Say "! Antigravity を自動で入れられませんでした（$($_.Exception.Message)）。あとで https://antigravity.google/download から入れられます" }
  }
  if ($agDir) {
    Say 'Antigravity に AI の部品を入れています（1〜3分）…'
    $cli = Get-ChildItem -Path "$agDir\bin" -Filter '*.cmd' -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($cli) {
      $vsix = Join-Path $KitDir 'tools\claude-first\claude-first.vsix'
      foreach ($arg in @('anthropic.claude-code', 'ms-ceintl.vscode-language-pack-ja', $vsix)) {
        if ($arg -like '*.vsix' -and -not (Test-Path $arg)) { continue }
        $pr = Start-Process -FilePath $cli.FullName -ArgumentList '--install-extension', "`"$arg`"", '--force' -PassThru -WindowStyle Hidden
        if (-not $pr.WaitForExit(120000)) { try { $pr.Kill() } catch {} ; Say "! 時間切れ: $arg" }
      }
    }
    # 画面を日本語に・Claude の最初の案内を出さない・会話は真ん中のタブで開く（持ち主が決めた値は上書きしない）
    if ($py) {
      $agUser = Join-Path $env:APPDATA ((Split-Path $agDir -Leaf) + '\User\settings.json')
      $agArgv = Join-Path $HOME '.antigravity-ide\argv.json'
      & $py -c "import json,os,sys`nfor p,kv in ((sys.argv[1],{'claudeCode.preferredLocation':'panel','claudeCode.hideOnboarding':True}),(sys.argv[2],{'locale':'ja'})):`n    os.makedirs(os.path.dirname(p),exist_ok=True)`n    try: d=json.load(open(p,encoding='utf-8')) if os.path.exists(p) else {}`n    except Exception: continue`n    [d.setdefault(k,v) for k,v in kv.items()]`n    json.dump(d,open(p,'w',encoding='utf-8'),indent=4,ensure_ascii=False)" $agUser $agArgv
    }
    Say 'Antigravity の中で AI を使えるようにし、画面を日本語にしました'
  }
}
exit 0
