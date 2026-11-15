"""Squarified treemap (Bruls, Huizing, van Wijk) in percent of the map area."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Hashable


@dataclass
class Rect:
    key: Hashable
    x: float
    y: float
    w: float
    h: float


def _worst(row: list[float], side: float) -> float:
    s = sum(row)
    return max(side * side * max(row) / (s * s), s * s / (side * side * min(row)))


def squarify(items: list[tuple[Hashable, int]], width: float = 100,
             height: float = 100, min_share: float = 0.06) -> list[Rect]:
    """Rectangles that exactly tile width x height, largest first.

    Items under `min_share` of the total are folded into one "other" item, so
    a sliver of a category never becomes an unreadable tile. When every item
    is that small there is nothing to fold them into and all keep a tile.
    """
    live = [(k, v) for k, v in items if v > 0]
    if not live:
        return []
    total = sum(v for _, v in live)
    big = [(k, v) for k, v in live if v / total >= min_share]
    small = sum(v for _, v in live if v / total < min_share)
    if big and small:
        big.append(("other", small))
    elif not big:
        big = live
    big.sort(key=lambda kv: -kv[1])

    scale = width * height / sum(v for _, v in big)
    queue = [(k, v * scale) for k, v in big]
    out: list[Rect] = []
    x, y, w, h = 0.0, 0.0, float(width), float(height)

    def lay(row: list[tuple[Hashable, float]]) -> None:
        nonlocal x, y, w, h
        s = sum(a for _, a in row)
        if w >= h:                       # a column of full height on the left
            col = s / h
            yy = y
            for k, a in row:
                out.append(Rect(k, x, yy, col, a / col))
                yy += a / col
            x += col
            w -= col
        else:                            # a strip of full width on top
            strip = s / w
            xx = x
            for k, a in row:
                out.append(Rect(k, xx, y, a / strip, strip))
                xx += a / strip
            y += strip
            h -= strip

    row: list[tuple[Hashable, float]] = []
    for item in queue:
        side = min(w, h)
        areas = [a for _, a in row]
        if not row or _worst(areas + [item[1]], side) <= _worst(areas, side):
            row.append(item)
        else:
            lay(row)
            row = [item]
    if row:
        lay(row)
    return out
