"""Generate platform icon files for Archivary from ``assets/IA_logo.svg``.

Run once (and after changing the logo) with the project virtualenv:

    .venv\\Scripts\\python.exe packaging\\make_icons.py

PyInstaller wants a multi-size ``.ico`` on Windows and an ``.icns`` on macOS.
Qt renders both, so the files can be produced on any platform.  The app itself
draws the SVG directly at runtime, so these files only matter for the built
executable's icon.
"""

from __future__ import annotations

import struct
import sys
from pathlib import Path

from PySide6.QtCore import QBuffer, QIODevice, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPixmap
from PySide6.QtWidgets import QApplication

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from archivary.ui.widgets import logo_pixmap  # noqa: E402

ASSETS = ROOT / "assets"
ICO_FILE = ASSETS / "Archivary.ico"
ICNS_FILE = ASSETS / "Archivary.icns"
LOGO_PNG = ASSETS / "logo.png"

BG = "#1e1f22"
FG = "#e6e6e6"
RADIUS = 0.22
LOGO_SCALE = 0.66


def badge(size: int) -> QPixmap:
    """A rounded dark tile with the light logo centred on it."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(BG))
    radius = size * RADIUS
    painter.drawRoundedRect(QRectF(0, 0, size, size), radius, radius)
    logo = logo_pixmap(int(size * LOGO_SCALE), FG)
    painter.drawPixmap(
        (size - logo.width()) // 2, (size - logo.height()) // 2, logo
    )
    painter.end()
    return pixmap


def _png_bytes(size: int) -> bytes:
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    badge(size).toImage().save(buffer, "PNG")
    return bytes(buffer.data())


def write_ico(path: Path, sizes: tuple[int, ...]) -> None:
    """Assemble a multi-resolution .ico from PNG frames."""
    frames = [(size, _png_bytes(size)) for size in sizes]
    header = struct.pack("<HHH", 0, 1, len(frames))
    entries = b""
    payload = b""
    offset = 6 + 16 * len(frames)
    for size, data in frames:
        dimension = 0 if size >= 256 else size
        entries += struct.pack(
            "<BBBBHHII", dimension, dimension, 0, 0, 1, 32, len(data), offset
        )
        offset += len(data)
        payload += data
    path.write_bytes(header + entries + payload)


def write_icns(path: Path) -> None:
    """Write a .icns using Qt's ICNS encoder (512 and 1024 px frames)."""
    for size in (1024, 512, 256, 128):
        if badge(size).save(str(path), "ICNS"):
            return
    raise RuntimeError("Qt could not encode an ICNS file")


def main() -> int:
    if QApplication.instance() is None:
        QApplication(sys.argv)
    ASSETS.mkdir(parents=True, exist_ok=True)
    write_ico(ICO_FILE, (16, 24, 32, 48, 64, 128, 256))
    write_icns(ICNS_FILE)
    badge(256).save(str(LOGO_PNG), "PNG")
    print(f"wrote {ICO_FILE.name}, {ICNS_FILE.name} and {LOGO_PNG.name} to {ASSETS}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
