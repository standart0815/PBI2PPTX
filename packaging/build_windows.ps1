# Builds dist\PBI2PPTX\PBI2PPTX.exe and dist\PBI2PPTX-<version>-Windows-Setup.exe.
# Needs uv, npm and Inno Setup 6 (iscc on PATH, e.g. `choco install innosetup`).
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

npm --prefix ui ci --no-audit --no-fund
npm --prefix ui run build
uv sync --locked
uv run pyinstaller --noconfirm --clean --distpath dist --workpath build packaging/pbi2pptx.spec

$version = uv run python -c "import pbi2pptx; print(pbi2pptx.__version__)"
iscc /Q "/DAppVersion=$version" packaging\windows\pbi2pptx.iss
Write-Host "Built dist\PBI2PPTX and dist\PBI2PPTX-$version-Windows-Setup.exe"
