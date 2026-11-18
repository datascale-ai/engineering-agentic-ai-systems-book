"""Run from the repository root; no network or credentials required."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "examples"))
from d_shared.project_cli import main

if __name__ == "__main__":
    main("PRJ-2")
