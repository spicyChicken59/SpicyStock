# Replays SpicyStock's own nightly decision over the run-6 archive you recovered,
# then prints two price-free summaries you can paste back.
#
#   powershell -ExecutionPolicy Bypass -File .\run-backtest.ps1 -Repo "C:\path\to\SpicyStock"
#
# Nothing here uploads anything, calls a data provider or the chart reader, or
# touches your key. It reads the recovered folder and writes two private folders
# under -Output. Expect about fifteen minutes for the first pass and one to two
# hours for the second.
param(
  [Parameter(Mandatory = $true)][string]$Repo,
  [string]$Recovered = "$env:USERPROFILE\Documents\Codex\private\SpicyStock\run6-evidence\recovered",
  [string]$Output = "$env:USERPROFILE\Documents\Codex\private\SpicyStock\run6-evidence\backtest",
  [string]$Python = "python"
)
$ErrorActionPreference = 'Stop'
$env:MPLBACKEND = 'Agg'
$Manifest = Join-Path $Repo 'docs\input-truthfulness\2026-09-28-historical-input-evidence\acquisition-manifest.json'
$Tool = Join-Path $Repo 'tools\historical_backtest.py'

function Invoke-Checked([string]$What, [string[]]$Cmd) {
  $rest = $Cmd[1..($Cmd.Count - 1)]
  & $Cmd[0] @rest
  if ($LASTEXITCODE -ne 0) { throw "Stopped at: $What. Nothing was deleted. Send Claude this line." }
}

# 1. The repo must carry the tool and the frozen manifest; the recovered folder must be the run-6 one.
if (-not (Test-Path $Tool)) { throw "No tools\historical_backtest.py in $Repo. Pull the branch that carries it first." }
if (-not (Test-Path $Manifest)) { throw "No acquisition manifest in $Repo." }
if (-not (Test-Path (Join-Path $Recovered 'ledger.sqlite3'))) { throw "$Recovered has no ledger.sqlite3. Pass -Recovered <the recovered folder>." }
Write-Host "1/4 Repo, manifest and recovered folder found"

# 2. The same runtime the recovery used.
Push-Location $Repo
try {
  Invoke-Checked 'checking Python is 3.12' @($Python, '-c', 'import sys; assert sys.version_info[:2] == (3, 12), sys.version')
  Invoke-Checked 'installing the historical runtime' @($Python, '-m', 'pip', 'install', '--quiet', '-r', 'tools\requirements-historical.txt')
  Write-Host "2/4 Runtime ready"

  # 3. The exact run: every evaluated session carries the run's own lookback (few sessions, no check needed).
  $exact = Join-Path $Output 'lookback-260'
  & $Python $Tool --manifest $Manifest --storage $Recovered --output $exact
  if ($LASTEXITCODE -ne 0) { throw "Stopped at: the exact-lookback replay (exit $LASTEXITCODE). Send Claude this line and the last lines above." }
  Write-Host "3/4 Exact-lookback replay saved to $exact\summary.txt"

  # 4. The longer run: a shortened lookback, held to the exact one on every session both can read.
  $long = Join-Path $Output 'lookback-130'
  & $Python $Tool --manifest $Manifest --storage $Recovered --output $long --lookback 130
  if ($LASTEXITCODE -eq 2) { Write-Host "4/4 The shortened lookback FAILED its equivalence check; its summary is saved but is not the run's own answer. Paste it anyway." }
  elseif ($LASTEXITCODE -ne 0) { throw "Stopped at: the shortened-lookback replay (exit $LASTEXITCODE). Send Claude this line and the last lines above." }
  else { Write-Host "4/4 Shortened-lookback replay saved to $long\summary.txt" }
}
finally { Pop-Location }

Write-Host ""
Write-Host "Paste these two files to Claude (they hold counts and R only, no prices, no tickers):"
Write-Host "  $exact\summary.txt"
Write-Host "  $long\summary.txt"
Write-Host "Keep the backtest.json files private: they carry prices."
