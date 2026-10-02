# Opens SpicyStock run 6's locked evidence on this computer, then prints a price-free summary.
#
#   powershell -ExecutionPolicy Bypass -File .\open-run6.ps1 -Repo "C:\path\to\SpicyStock" -Key "C:\path\to\your\age\key-file"
#
# Keep expected-execution.json and summarize_run6.py in the same folder as this script.
# Nothing here uploads anything. Your key never leaves this computer.
param(
  [Parameter(Mandatory = $true)][string]$Repo,
  [Parameter(Mandatory = $true)][string]$Key,
  [string]$Zip = "$env:USERPROFILE\Downloads\historical-evidence-36815689950-1-real.zip",
  [string]$Work = "$env:USERPROFILE\Documents\Codex\private\SpicyStock\run6-evidence",
  [string]$Python = "python"
)
$ErrorActionPreference = 'Stop'
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path

# Facts read from GitHub for run 36815689950 (artifact 11142297138).
$ExpectedZipSha   = '043AF0B3ABE27FB47CD00C65B601617F23AA7846993D5E5EA02C94267438F1B3'
$ExpectedZipBytes = 107315902
$ReviewedHead     = 'd6d774346015c3d2abfe7b7318316292daab57cb'

function Invoke-Checked([string]$What, [string[]]$Cmd) {
  $rest = $Cmd[1..($Cmd.Count - 1)]
  & $Cmd[0] @rest
  if ($LASTEXITCODE -ne 0) { throw "Stopped at: $What. Nothing was deleted. Send Claude this line." }
}

# 1. The downloaded zip must be byte-for-byte what GitHub recorded.
if (-not (Test-Path $Zip)) { throw "Zip not found at $Zip. Download it from the run page first, or pass -Zip." }
$len  = (Get-Item $Zip).Length
$hash = (Get-FileHash $Zip -Algorithm SHA256).Hash
if ($len -ne $ExpectedZipBytes -or $hash -ne $ExpectedZipSha) {
  throw "This zip is not the one GitHub recorded (size $len, SHA-256 $hash). Do not open it."
}
Write-Host "1/5 Zip matches GitHub: $len bytes, SHA-256 $hash"

# 2. A private work folder that is not inside any git folder.
if (Test-Path "$Work\recovered") { throw "$Work\recovered already exists. Rename it, then run again." }
$probe = $Work
while ($probe) {
  if (Test-Path (Join-Path $probe '.git')) { throw "$Work is inside a git folder ($probe). Pass a different -Work." }
  $probe = Split-Path -Parent $probe
}
New-Item -ItemType Directory -Force -Path $Work | Out-Null
Expand-Archive -Path $Zip -DestinationPath "$Work\artifact" -Force
Copy-Item "$Here\expected-execution.json" "$Work\expected-execution.json" -Force
Write-Host "2/5 Unpacked the box and its receipt into $Work\artifact"

# 3. The repo's recovery tools must be the reviewed ones.
Push-Location $Repo
try {
  Invoke-Checked 'checking the repo is up to date' @('git', 'merge-base', '--is-ancestor', $ReviewedHead, 'HEAD')
  Invoke-Checked 'checking the recovery tools are unchanged' @('git', 'diff', '--quiet', $ReviewedHead, 'HEAD', '--', 'tools')
  Invoke-Checked 'checking Python is 3.12' @($Python, '-c', 'import sys; assert sys.version_info[:2] == (3, 12), sys.version')
  Invoke-Checked 'installing the pinned zstandard' @($Python, '-m', 'pip', 'install', '--quiet', '--require-hashes', '--only-binary=:all:', '-r', 'tools\requirements-historical-archive.txt')
  Invoke-Checked 'installing the historical runtime' @($Python, '-m', 'pip', 'install', '--quiet', '-r', 'tools\requirements-historical.txt')
  if (-not (Test-Path "$Work\age\age.exe")) {
    Invoke-Checked 'installing the pinned age' @($Python, 'tools\install_historical_age.py', '--destination', "$Work\age")
  }
  Write-Host "3/5 Tools ready"

  # 4. Decrypt with your key and verify every file against the receipt and GitHub's identity.
  Invoke-Checked 'decrypting and verifying' @($Python, 'tools\historical_package.py', 'recover',
    '--cipher', "$Work\artifact\evidence.tar.zst.age", '--receipt', "$Work\artifact\receipt.json",
    '--identity', $Key, '--age', "$Work\age\age.exe", '--destination', "$Work\recovered",
    '--expected-execution', "$Work\expected-execution.json")
  Write-Host "4/5 Decrypted and verified into $Work\recovered"
}
finally { Pop-Location }

# 5. Price-free summary you can paste back.
$summary = & $Python "$Here\summarize_run6.py" "$Work\recovered"
if ($LASTEXITCODE -ne 0) { throw "Stopped at: summarizing. The evidence is recovered; send Claude this line." }
$summary | Set-Content -Encoding utf8 "$Work\summary.txt"
$summary | ForEach-Object { Write-Host $_ }
Write-Host "5/5 Summary saved to $Work\summary.txt. It has no prices; paste it to Claude."
