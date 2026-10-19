"""Collects the license texts of everything the packaged app ships into one file.

    uv run python packaging/third_party_licenses.py build/THIRD-PARTY-LICENSES.txt

The PyInstaller spec runs it, so every installer carries the notices its libraries ask for. It reads the
installed runtime dependencies (with this platform's markers), Python itself, and the interface's
npm runtime packages. Playwright's driver ships its own license files (Node.js included) in its folder.
See THIRD-PARTY-NOTICES.md for the overview.
"""

from __future__ import annotations

import json
import sys
import sysconfig
import tomllib
from importlib import metadata
from pathlib import Path

from packaging.requirements import Requirement

ROOT = Path(__file__).resolve().parent.parent
LICENSE_NAMES = ("LICEN", "COPYING", "NOTICE")
RULE = "=" * 100


def runtime_distributions() -> list[metadata.Distribution]:
    """The runtime dependencies from pyproject.toml and everything they pull in on this platform."""
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    todo = [Requirement(r) for r in project["dependencies"]]
    found: dict[str, metadata.Distribution] = {}
    while todo:
        req = todo.pop()
        if req.marker and not req.marker.evaluate({"extra": ""}):
            continue
        dist = metadata.distribution(req.name)
        key = dist.metadata["Name"].lower()
        if key in found:
            continue
        found[key] = dist
        todo.extend(Requirement(r) for r in dist.requires or [])
    return sorted(found.values(), key=lambda d: d.metadata["Name"].lower())


def license_texts(dist: metadata.Distribution) -> list[str]:
    files = [
        f
        for f in dist.files or []
        if ".dist-info/" in str(f) and f.name.upper().startswith(LICENSE_NAMES)
    ]
    return [Path(dist.locate_file(f)).read_text(encoding="utf-8", errors="replace") for f in files]


def python_license() -> str | None:
    base = Path(sys.base_prefix)
    for candidate in (Path(sysconfig.get_path("stdlib")) / "LICENSE.txt", base / "LICENSE.txt"):
        if candidate.exists():
            return candidate.read_text(encoding="utf-8", errors="replace")
    return None


def npm_runtime_packages() -> list[tuple[str, str, str, str]]:
    """(name, version, license, text) for the interface's packages that end up in the built bundle."""
    lock = json.loads((ROOT / "ui" / "package-lock.json").read_text(encoding="utf-8"))
    packages = []
    for path, info in lock["packages"].items():
        if not path or info.get("dev"):
            continue
        folder = ROOT / "ui" / path
        texts = [p.read_text(encoding="utf-8") for p in sorted(folder.glob("LICENSE*"))] if folder.exists() else []
        packages.append((path.rsplit("node_modules/", 1)[-1], info["version"], info.get("license", "?"), "\n".join(texts)))
    return packages


def section(title: str, license_name: str, url: str | None, texts: list[str]) -> str:
    head = f"{RULE}\n{title}\nLicense: {license_name}" + (f"\nSource: {url}" if url else "") + f"\n{RULE}\n"
    body = "\n\n".join(t.strip() for t in texts) if texts else "(No license file is shipped with this package; see its source.)"
    return head + "\n" + body + "\n\n"


def project_url(dist: metadata.Distribution) -> str | None:
    for entry in dist.metadata.get_all("Project-URL") or []:
        label, _, url = entry.partition(",")
        if label.strip().lower() in ("source", "homepage", "repository", "source code"):
            return url.strip()
    return dist.metadata.get("Home-page")


def build() -> str:
    parts = [
        "PBI2PPTX bundles the following third-party software. Each part is distributed under its own license,\n"
        "reproduced below. PBI2PPTX itself is under the MIT License (see LICENSE).\n\n"
        "pystray is under the GNU LGPL v3. It ships as plain Python source files inside this app, so it can be\n"
        "replaced with a modified version; the complete source of PBI2PPTX is available to rebuild the app.\n\n"
        "Playwright's driver, including the Node.js runtime, carries its own license files in its folder\n"
        "(playwright/driver/LICENSE, playwright/driver/package/LICENSE, NOTICE and ThirdPartyNotices.txt).\n\n"
    ]
    python = python_license()
    parts.append(section(f"Python {sys.version.split()[0]}", "PSF-2.0", "https://www.python.org/", [python] if python else []))
    for dist in runtime_distributions():
        name = dist.metadata["Name"]
        license_name = dist.metadata.get("License-Expression") or dist.metadata.get("License", "").split("\n")[0] or "see below"
        parts.append(section(f"{name} {dist.version}", license_name, project_url(dist), license_texts(dist)))
    for name, version, license_name, text in npm_runtime_packages():
        parts.append(section(f"{name} {version} (interface)", license_name, f"https://www.npmjs.com/package/{name}", [text] if text else []))
    return "".join(parts)


if __name__ == "__main__":
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "build" / "THIRD-PARTY-LICENSES.txt"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(build(), encoding="utf-8")
    print(f"Wrote {out}")
