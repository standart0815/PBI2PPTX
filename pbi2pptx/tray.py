"""The menu bar icon (macOS) / tray icon (Windows): the way back to the interface, and Quit.

macOS doesn't start an app that is already running a second time, and PBI2PPTX has no window of
its own, so after the interface tab is closed this icon is the only way back. The icon's loop must
run on the main thread (macOS requires it); the server runs beside it in its own thread.
"""

from __future__ import annotations

import threading
from typing import Callable

from PIL import Image, ImageDraw


def icon_image(size: int = 64) -> Image.Image:
    """Three bars on a blue tile: report pages becoming a deck."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle([2, 2, size - 3, size - 3], radius=size // 6, fill=(31, 95, 191, 255))
    bar = size // 7
    floor = size - size // 4
    for i, height in enumerate((0.30, 0.50, 0.40)):
        left = size // 4 + i * (bar + bar // 2)
        draw.rectangle([left, floor - int(size * height), left + bar, floor], fill=(255, 255, 255, 255))
    return img


def run(on_open: Callable[[], None], on_quit: Callable[[], None], server_thread: threading.Thread) -> None:
    """Show the icon until the server thread ends (quit from the interface or from this menu)."""
    import pystray  # imported here: it needs a desktop session

    def watch(icon: "pystray.Icon") -> None:  # pystray runs this in its own thread once the icon loop is up
        icon.visible = True
        server_thread.join()
        icon.stop()

    icon = pystray.Icon(
        "PBI2PPTX",
        icon_image(),
        "PBI2PPTX",
        menu=pystray.Menu(
            pystray.MenuItem("Open PBI2PPTX", lambda: on_open(), default=True),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit PBI2PPTX", lambda: on_quit()),
        ),
    )
    icon.run(setup=watch)
