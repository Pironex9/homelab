import pytest

from app.services.treemap import squarify


def _overlap(a, b):
    return (min(a.x + a.w, b.x + b.w) - max(a.x, b.x) > 1e-9
            and min(a.y + a.h, b.y + b.h) - max(a.y, b.y) > 1e-9)


@pytest.mark.parametrize("values", [
    [50, 30, 20], [40, 30, 15, 10, 5], [100, 1, 1], [7] * 9,
    [300, 250, 200, 180, 120, 90, 60, 40, 30, 10],
])
def test_tiles_exactly_cover_the_area(values):
    rects = squarify([(i, v) for i, v in enumerate(values)], 100, 100, 0.0)
    assert sum(r.w * r.h for r in rects) == pytest.approx(100 * 100, abs=1e-6)
    for r in rects:
        assert -1e-9 <= r.x and r.x + r.w <= 100 + 1e-9
        assert -1e-9 <= r.y and r.y + r.h <= 100 + 1e-9
    for i, a in enumerate(rects):
        for b in rects[i + 1:]:
            assert not _overlap(a, b)


def test_non_square_area_is_tiled_too():
    rects = squarify([("a", 5), ("b", 3), ("c", 2)], 60, 40, 0.0)
    assert sum(r.w * r.h for r in rects) == pytest.approx(60 * 40, abs=1e-6)


def test_largest_first_and_area_proportional():
    rects = squarify([("a", 20), ("b", 50), ("c", 30)], min_share=0.0)
    assert [r.key for r in rects] == ["b", "c", "a"]
    assert rects[0].w * rects[0].h == pytest.approx(5000, abs=1e-6)


def test_small_items_fold_into_other():
    rects = squarify([("a", 60), ("b", 30), ("c", 5), ("d", 5)], min_share=0.06)
    assert sorted(r.key for r in rects) == ["a", "b", "other"]
    other = next(r for r in rects if r.key == "other")
    assert other.w * other.h == pytest.approx(1000, abs=1e-6)


def test_nothing_to_fold_when_all_items_are_small():
    rects = squarify([(i, 1) for i in range(20)], min_share=0.06)
    assert len(rects) == 20


def test_single_item_fills_everything():
    (r,) = squarify([("a", 42)])
    assert (r.key, r.x, r.y, r.w, r.h) == ("a", 0, 0, 100, 100)


def test_zero_and_negative_dropped_and_empty():
    assert squarify([]) == []
    assert squarify([("a", 0), ("b", -5)]) == []
    rects = squarify([("a", 10), ("b", 0), ("c", -1)])
    assert [r.key for r in rects] == ["a"]
