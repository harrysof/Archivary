"""Allow ``python -m archivary`` to launch the GUI."""

from archivary.app import main

if __name__ == "__main__":
    raise SystemExit(main())
