"""The site's stylesheet uses only the breakpoints listed at its top.

Twelve different widths had grown up in site/src/styles.css, so a layout
could change at 760, 767, 768 or 820 pixels depending on the component. The
list at the top of the file names three; this keeps every media query to them.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
STYLES = REPO / "site" / "src" / "styles.css"
MAP = REPO / "site" / "src" / "components" / "players-clubs-map.tsx"

ALLOWED = {"max-width: 560px", "max-width: 767px", "min-width: 768px", "max-width: 1023px", "min-width: 1024px"}
WIDTH = re.compile(r"(?:min|max)-width:\s*[0-9.]+(?:px|rem|em)")


def test_media_queries_use_the_listed_breakpoints() -> None:
    css = STYLES.read_text(encoding="utf-8")
    queries = re.findall(r"@media[^{]*", css)
    widths = {re.sub(r"\s+", " ", match) for query in queries for match in WIDTH.findall(query)}
    assert widths <= ALLOWED, f"breakpoints not in the list at the top of styles.css: {sorted(widths - ALLOWED)}"
    header = css[: css.index(":root")]
    for width in ALLOWED:
        assert width in header, f"{width} is used but not listed at the top of styles.css"


def test_map_uses_the_tablet_breakpoint() -> None:
    assert '"(max-width: 767px)"' in MAP.read_text(encoding="utf-8")
