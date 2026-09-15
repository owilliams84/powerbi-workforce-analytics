"""Inject real figures into the Year on Year page mockup.

    python design/build_mockup.py

Runs etl/yoy_expected.py for every state the page can show and writes design/yoy-mockup.html
from design/yoy-mockup.src.html.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATES = [(y, c) for y in range(2019, 2024) for c in ("prior", "two")]


def main() -> None:
    data = {}
    for year, comp in STATES:
        out = subprocess.run([sys.executable, str(ROOT / "etl" / "yoy_expected.py"), str(year), comp],
                             check=True, capture_output=True, text=True).stdout
        data[f"{year}_{comp}"] = json.loads(out)
    src = (ROOT / "design" / "yoy-mockup.src.html").read_text(encoding="utf-8")
    (ROOT / "design" / "yoy-mockup.html").write_text(src.replace("/*DATA*/", json.dumps(data)),
                                                     encoding="utf-8", newline="\n")
    print(f"design/yoy-mockup.html  ({len(STATES)} states)")


if __name__ == "__main__":
    main()
