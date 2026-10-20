"""PBI2PPTX: turns a user's choice of Power BI report pages into one PowerPoint Deck."""

__version__ = "0.1.0"


def static_dir():
    """The built interface, inside the package (from source or in the packaged app)."""
    from pathlib import Path

    return Path(__file__).parent / "static"
