# Applies resource-safety controls before the public Streamlit service starts.
from __future__ import annotations

import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = REPOSITORY_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from evidencecast.public_ui import configure_public_ui


def main() -> int:
    changed = configure_public_ui(REPOSITORY_ROOT)
    if changed:
        for path in changed:
            print(f"Configured public safety controls: {path.relative_to(REPOSITORY_ROOT)}")
    else:
        print("Public heavy-assembly safety controls are not enabled; no page changes made.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
