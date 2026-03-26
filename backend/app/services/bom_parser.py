from __future__ import annotations

import re

_LEADING_QTY_SEP = re.compile(
    r"^\s*(\d+(?:\.\d+)?)\s*[-–—×x]\s*(.+)$",
    re.IGNORECASE,
)
_BULLET_QTY = re.compile(
    r"^\s*[-*•]\s*(\d+(?:\.\d+)?)\s+(.+)$",
    re.IGNORECASE,
)
_QTY_IN_PARENS = re.compile(
    r"^\s*(.+?)\s*\(\s*qty\s*[:=]\s*(\d+(?:\.\d+)?)\s*\)\s*$",
    re.IGNORECASE,
)
_LEADING_QTY_SPACE = re.compile(
    r"^\s*(\d+(?:\.\d+)?)\s+(.+)$",
)


def parse_bom_text(text: str) -> list[tuple[float, str]]:
    lines: list[tuple[float, str]] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue

        m = _QTY_IN_PARENS.match(line)
        if m:
            desc, qty_s = m.group(1).strip(), m.group(2)
            lines.append((float(qty_s), desc))
            continue

        m = _LEADING_QTY_SEP.match(line)
        if m:
            qty_s, desc = m.group(1), m.group(2).strip()
            lines.append((float(qty_s), desc))
            continue

        m = _BULLET_QTY.match(line)
        if m:
            qty_s, desc = m.group(1), m.group(2).strip()
            lines.append((float(qty_s), desc))
            continue

        m = _LEADING_QTY_SPACE.match(line)
        if m:
            qty_s, desc = m.group(1), m.group(2).strip()
            if desc:
                lines.append((float(qty_s), desc))
                continue

        lines.append((1.0, line))
    return lines


def merge_bom_inputs(
    bom_text: str | None,
    line_items: list[tuple[float, str]] | None,
) -> list[tuple[float, str]]:
    merged: list[tuple[float, str]] = []
    if bom_text and bom_text.strip():
        merged.extend(parse_bom_text(bom_text))
    if line_items:
        merged.extend(line_items)
    return merged
