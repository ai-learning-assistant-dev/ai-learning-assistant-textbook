"""一键跑全部用例：python tests/run.py [-v]"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))

if __name__ == "__main__":
    suite = unittest.defaultTestLoader.discover(
        start_dir=str(HERE), pattern="test_*.py", top_level_dir=str(ROOT)
    )
    verbosity = 2 if "-v" in sys.argv or "--verbose" in sys.argv else 1
    result = unittest.TextTestRunner(verbosity=verbosity).run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
