"""平面幾何 (rebar.geometry) のテスト。vs モック不要。"""
from __future__ import annotations

import math

from vectorworks_plugin_rebar.rebar.geometry import (
    clip_line_family,
    direction_vectors,
    polygon_centroid,
)

# 2000×3000 の矩形 (原点基準)
RECT = [(0.0, 0.0), (2000.0, 0.0), (2000.0, 3000.0), (0.0, 3000.0)]


class TestPolygonCentroid:
    def test_rectangle(self) -> None:
        cx, cy = polygon_centroid(RECT)
        assert math.isclose(cx, 1000.0)
        assert math.isclose(cy, 1500.0)

    def test_clockwise_rectangle(self) -> None:
        cx, cy = polygon_centroid(list(reversed(RECT)))
        assert math.isclose(cx, 1000.0)
        assert math.isclose(cy, 1500.0)


class TestDirectionVectors:
    def test_zero_degrees(self) -> None:
        d, n = direction_vectors(0.0)
        assert math.isclose(d[0], 1.0) and math.isclose(d[1], 0.0, abs_tol=1e-12)
        assert math.isclose(n[0], 0.0, abs_tol=1e-12) and math.isclose(n[1], 1.0)


class TestClipLineFamily:
    def test_x_direction_lines_in_rectangle(self) -> None:
        # X 方向の線は Y 方向に並ぶ。重心 (y=1500) を基準に @200 で
        # y=100..2900 の 15 本(重心の線を含む)
        segments = clip_line_family(RECT, 0.0, 200.0)
        assert len(segments) == 15
        for (x1, y1), (x2, y2) in segments:
            assert math.isclose(min(x1, x2), 0.0, abs_tol=1e-6)
            assert math.isclose(max(x1, x2), 2000.0, abs_tol=1e-6)
            assert math.isclose(y1, y2, abs_tol=1e-6)
        ys = sorted((s[0][1] + s[1][1]) / 2 for s in segments)
        assert math.isclose(ys[0], 100.0, abs_tol=1e-6)
        assert math.isclose(ys[-1], 2900.0, abs_tol=1e-6)
        # 重心を通る線が含まれる
        assert any(math.isclose(y, 1500.0, abs_tol=1e-6) for y in ys)

    def test_y_direction_lines_in_rectangle(self) -> None:
        segments = clip_line_family(RECT, 90.0, 150.0)
        # 重心 (x=1000) 基準 @150 → x=100..1900 の 13 本
        assert len(segments) == 13
        for (x1, y1), (x2, y2) in segments:
            assert math.isclose(x1, x2, abs_tol=1e-6)
            assert math.isclose(abs(y2 - y1), 3000.0, abs_tol=1e-6)

    def test_concave_polygon_splits_lines(self) -> None:
        # コの字型 (凹): 中央をくり抜いた形。横線は 2 分割される
        concave = [
            (0.0, 0.0),
            (3000.0, 0.0),
            (3000.0, 2000.0),
            (2000.0, 2000.0),
            (2000.0, 1000.0),
            (1000.0, 1000.0),
            (1000.0, 2000.0),
            (0.0, 2000.0),
        ]
        segments = clip_line_family(concave, 0.0, 500.0)
        # 面積重心 y=900 基準 @500 → y=400, 900, 1400, 1900 の 4 本。
        # くり抜き (y>1000) にかかる 2 本は左右 2 線分ずつに分かれ計 6 線分
        assert len(segments) == 6
        upper = [s for s in segments if s[0][1] > 1000.0 + 1e-6]
        assert len(upper) == 4
        for segment in upper:
            span = sorted((segment[0][0], segment[1][0]))
            assert (
                math.isclose(span[0], 0.0, abs_tol=1e-6)
                and math.isclose(span[1], 1000.0, abs_tol=1e-6)
            ) or (
                math.isclose(span[0], 2000.0, abs_tol=1e-6)
                and math.isclose(span[1], 3000.0, abs_tol=1e-6)
            )

    def test_diagonal_direction(self) -> None:
        segments = clip_line_family(RECT, 45.0, 500.0)
        assert segments
        d = (math.cos(math.radians(45.0)), math.sin(math.radians(45.0)))
        for (x1, y1), (x2, y2) in segments:
            length = math.hypot(x2 - x1, y2 - y1)
            # 線分は指定方向を向く
            assert math.isclose(
                abs((x2 - x1) * d[0] + (y2 - y1) * d[1]), length, rel_tol=1e-9
            )

    def test_degenerate_inputs(self) -> None:
        assert clip_line_family([(0.0, 0.0), (1.0, 0.0)], 0.0, 100.0) == []
        assert clip_line_family(RECT, 0.0, 0.0) == []
