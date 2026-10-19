"""Read and write .potx files with python-pptx, which only accepts the .pptx content type."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

from pptx import Presentation

CT_PRESENTATION = "application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"
CT_TEMPLATE = "application/vnd.openxmlformats-officedocument.presentationml.template.main+xml"


def _swap_main_content_type(data: bytes, old: str, new: str) -> bytes:
    src = zipfile.ZipFile(io.BytesIO(data))
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as dst:
        for item in src.infolist():
            content = src.read(item.filename)
            if item.filename == "[Content_Types].xml":
                content = content.replace(old.encode(), new.encode())
            dst.writestr(item, content)
    return out.getvalue()


def open_template(path: Path):
    """Open a .potx (or .pptx) as an editable Presentation."""
    data = Path(path).read_bytes()
    return Presentation(io.BytesIO(_swap_main_content_type(data, CT_TEMPLATE, CT_PRESENTATION)))


def save_as_potx(prs, path: Path) -> None:
    buf = io.BytesIO()
    prs.save(buf)
    Path(path).write_bytes(_swap_main_content_type(buf.getvalue(), CT_PRESENTATION, CT_TEMPLATE))
