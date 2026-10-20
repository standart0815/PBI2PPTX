"""Entry point for the packaged app (PyInstaller can't start a package module with relative imports)."""

from pbi2pptx.app import main

if __name__ == "__main__":
    main()
