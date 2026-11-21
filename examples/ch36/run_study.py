"""Run from the repository root; no package installation or network needed."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from book_reference.study import main

if __name__ == "__main__":
    raise SystemExit(main())
