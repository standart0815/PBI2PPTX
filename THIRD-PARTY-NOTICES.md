# Third-party notices

PBI2PPTX is under the [MIT License](LICENSE). It uses the open-source software below, each under its own license. All of these licenses allow use in an MIT-licensed project and in the distributed installers.

Every installer also contains `LICENSE` and a `THIRD-PARTY-LICENSES.txt` with the full license texts of what it bundles. [packaging/third_party_licenses.py](packaging/third_party_licenses.py) collects them during the build.

## Bundled in the app

| Package | License | Used for |
|---|---|---|
| [Python](https://www.python.org/) 3.12 | PSF-2.0 | the runtime, bundled by PyInstaller |
| [playwright](https://github.com/microsoft/playwright-python) | Apache-2.0 | driving the installed Chrome or Edge |
| ↳ Playwright driver, with [Node.js](https://nodejs.org/) | Apache-2.0; Node.js: MIT and others | ships its own `LICENSE`, `NOTICE` and `ThirdPartyNotices.txt` |
| ↳ [greenlet](https://github.com/python-greenlet/greenlet) | MIT AND PSF-2.0 | |
| ↳ [pyee](https://github.com/jfhbrook/pyee) | MIT | |
| [python-pptx](https://github.com/scanny/python-pptx) | MIT | building the Deck |
| ↳ [lxml](https://github.com/lxml/lxml) (with libxml2, libxslt) | BSD-3-Clause | |
| ↳ [XlsxWriter](https://github.com/jmcnamara/XlsxWriter) | BSD-2-Clause | |
| [Pillow](https://github.com/python-pillow/Pillow) (with the image libraries it bundles) | MIT-CMU | images, the tray icon |
| [Starlette](https://github.com/Kludex/starlette) | BSD-3-Clause | the local server |
| ↳ [AnyIO](https://github.com/agronholm/anyio), [idna](https://github.com/kjd/idna) | MIT, BSD-3-Clause | |
| [Uvicorn](https://github.com/Kludex/uvicorn) | BSD-3-Clause | the local server |
| ↳ [Click](https://github.com/pallets/click), [h11](https://github.com/python-hyper/h11) | BSD-3-Clause, MIT | |
| [typing_extensions](https://github.com/python/typing_extensions) | PSF-2.0 | |
| [pystray](https://github.com/moses-palmer/pystray) | **LGPL-3.0** | the menu bar / tray icon |
| ↳ [six](https://github.com/benjaminp/six) | MIT | |
| ↳ [PyObjC](https://github.com/ronaldoussoren/pyobjc) (macOS only) | MIT | |
| [React](https://react.dev/), React DOM, scheduler | MIT | the interface |

**pystray (LGPL-3.0).** PBI2PPTX uses pystray unmodified, as a separate library. The installers ship it as plain Python source files, so it can be replaced with a modified version, and the full source of PBI2PPTX is available here to rebuild the app. pystray's source is at <https://github.com/moses-palmer/pystray>.

**No browser is bundled.** The Power BI Window uses the Chrome or Edge already installed on the computer.

## Used only for development and building

These are not part of the installers.

| Package | License |
|---|---|
| [PyInstaller](https://pyinstaller.org/) | GPL-2.0-or-later with the PyInstaller bootloader exception, which allows bundling programs under any license |
| [pytest](https://pytest.org/), [httpx2](https://github.com/pydantic/httpx2) | MIT, BSD-3-Clause |
| [Vite](https://vite.dev/), [@vitejs/plugin-react](https://github.com/vitejs/vite-plugin-react), esbuild, Rollup, Babel | MIT |
| [TypeScript](https://www.typescriptlang.org/) | Apache-2.0 |
| [caniuse-lite](https://github.com/browserslist/caniuse-lite) (browser data used by the build) | CC-BY-4.0 |
| Other npm build dependencies | MIT, ISC, BSD-3-Clause, Apache-2.0 |
| [Inno Setup](https://jrsoftware.org/isinfo.php) (Windows installer) | Inno Setup License (free, also for commercial use) |

## Trademarks

Power BI, PowerPoint and Microsoft Edge are trademarks of Microsoft Corporation. Google Chrome is a trademark of Google LLC. PBI2PPTX is not affiliated with, endorsed by or supported by either company.
