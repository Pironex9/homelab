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

    Two or more items under `min_share` of the total are folded into one
    "other" item, and that tile (or a lone small item's) is weighted up to at
    least `min_share` of the area, so no tile is an unreadable sliver. When
    every item is that small nothing is folded.
    """
    live = [(k, v) for k, v in items if v > 0]
    if not live:
        return []
    total = sum(v for _, v in live)
    big = [(k, v) for k, v in live if v / total >= min_share]
    small = [(k, v) for k, v in live if v / total < min_share]
    if not big:
        big = live
    elif small:
        # Laid out with a floor weight so its tile gets min_share of the
        # area, however little the small items add up to. The caller labels
        # it with the true amount. One small item keeps its own key.
        floor = min_share * sum(v for _, v in big) / (1 - min_share)
        if len(small) == 1:
            big.append((small[0][0], max(small[0][1], floor)))
        else:
            big.append(("other", max(sum(v for _, v in small), floor)))
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
