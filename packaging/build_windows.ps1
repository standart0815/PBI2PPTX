# Builds dist\PBI2PPTX\PBI2PPTX.exe and dist\PBI2PPTX-<version>-Windows-Setup.exe.
# Needs uv, npm and Inno Setup 6 (iscc on PATH, e.g. `choco install innosetup`).
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

npm --prefix ui ci --no-audit --no-fund
npm --prefix ui run build
uv sync --locked
uv run pyinstaller --noconfirm --clean --distpath dist --workpath build packaging/pbi2pptx.spec

# The packaged app must be able to build a Deck on its own (catches files the packager left out).
# It has no console, so the result comes from its exit code.
$check = Start-Process -FilePath "dist\PBI2PPTX\PBI2PPTX.exe" -ArgumentList "--self-test" -Wait -PassThru
if ($check.ExitCode -ne 0) { throw "Self-test of the packaged app failed (exit code $($check.ExitCode)); see the log in %LOCALAPPDATA%\PBI2PPTX" }

$version = uv run python -c "import pbi2pptx; print(pbi2pptx.__version__)"
iscc /Q "/DAppVersion=$version" packaging\windows\pbi2pptx.iss
Write-Host "Built dist\PBI2PPTX and dist\PBI2PPTX-$version-Windows-Setup.exe"
