import sys
from pathlib import Path

here = Path(__file__).resolve().parent
src = here / "src"
if str(src) not in sys.path:
    sys.path.insert(0, str(src))
