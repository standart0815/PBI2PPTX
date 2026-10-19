# PyInstaller build for PBI2PPTX, on macOS (.app) and Windows (folder with PBI2PPTX.exe).
# Build with packaging/build_macos.sh or packaging/build_windows.ps1; the interface must be built first.
import sys
from pathlib import Path

import playwright
from PyInstaller.utils.hooks import collect_submodules

ROOT = Path(SPECPATH).parent
sys.path.insert(0, str(ROOT))
from pbi2pptx import __version__  # noqa: E402

STATIC = ROOT / "pbi2pptx" / "static"
if not (STATIC / "index.html").exists():
    raise SystemExit("Build the interface first: npm --prefix ui ci && npm --prefix ui run build")

# Playwright drives the installed Chrome/Edge through its driver (Node + package); no browser is bundled.
DRIVER = Path(playwright.__file__).parent / "driver"

a = Analysis(
    [str(ROOT / "packaging" / "launch.py")],
    pathex=[str(ROOT)],
    datas=[(str(STATIC), "pbi2pptx/static"), (str(DRIVER), "playwright/driver")],
    hiddenimports=collect_submodules("uvicorn") + collect_submodules("pystray"),  # pystray picks its backend at runtime
    excludes=["tkinter", "pytest", "PyInstaller"],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="PBI2PPTX",
    console=False,  # no terminal window: the interface runs in the browser
    disable_windowed_traceback=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name="PBI2PPTX")

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="PBI2PPTX.app",
        bundle_identifier="app.pbi2pptx",
        version=__version__,
        info_plist={
            "CFBundleShortVersionString": __version__,
            "CFBundleVersion": __version__,
            "LSUIElement": True,  # no Dock window: the interface runs in the browser, quit from there
            "NSHighResolutionCapable": True,
        },
    )
