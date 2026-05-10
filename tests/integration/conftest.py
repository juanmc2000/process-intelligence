"""pytest configuration for integration tests.

Ensures the project root is on sys.path so that both
``packages.*`` and ``services.*`` namespace packages are importable.
"""

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))
