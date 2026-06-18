#!/usr/bin/env python
"""Build the served web page by injecting lesson content into the page template.

The educational prose lives in ``web/lessons.json`` (one entry per section, each with an
``id`` and an ``html`` body). The layout lives in ``web/page_template.html`` with
``<!--LESSON:id-->`` placeholders. This script substitutes each lesson into its placeholder
and writes ``web/static/index.html``.

Run after editing either file:  ``uv run python scripts/build_page.py``
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

WEB = Path(__file__).resolve().parent.parent / "trading_bot" / "web"
TEMPLATE = WEB / "page_template.html"
LESSONS = WEB / "lessons.json"
OUTPUT = WEB / "static" / "index.html"


def build() -> int:
    template = TEMPLATE.read_text()
    lessons = {s["id"]: s["html"] for s in json.loads(LESSONS.read_text())}

    missing = []
    for lid, html in lessons.items():
        marker = f"<!--LESSON:{lid}-->"
        if marker not in template:
            missing.append(lid)
            continue
        template = template.replace(marker, html)

    # Fail loudly if any placeholder was left unfilled or any lesson had no home.
    leftover = [
        line.strip()
        for line in template.splitlines()
        if "<!--LESSON:" in line
    ]
    if missing:
        print(f"ERROR: lessons with no matching placeholder: {missing}", file=sys.stderr)
        return 1
    if leftover:
        print(f"ERROR: unfilled placeholders remain: {leftover}", file=sys.stderr)
        return 1

    OUTPUT.write_text(template)
    print(f"Built {OUTPUT} ({len(lessons)} lessons, {len(template):,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(build())
