"""断面表示記号のプロファイル組み立て (rebar.symbol) のテスト。vs 非依存。

姉妹プロジェクト「鉄筋」(vectorworks-plugin-rebar-single)の記号定義を
踏襲しているため、同じ記号仕様(呼び径 → 線・円の構成)を検証する。
"""
from __future__ import annotations

from typing import List

from vectorworks_plugin_rebar.document import KIND_CIRCLE, KIND_LINE, Profile
from vectorworks_plugin_rebar.rebar.symbol import build_symbol_profiles


def _circles(profiles: List[Profile]) -> List[Profile]:
    return [p for p in profiles if p['kind'] == KIND_CIRCLE]


def _lines(profiles: List[Profile]) -> List[Profile]:
    return [p for p in profiles if p['kind'] == KIND_LINE]


class TestBuildSymbolProfiles:
    def test_d10_filled_circle(self) -> None:
        # ● 塗り丸: 円 1 個・塗りあり・線なし
        profiles = build_symbol_profiles(10, 40.0)
        assert len(_circles(profiles)) == 1
        assert _circles(profiles)[0]['filled'] is True
        assert not _lines(profiles)

    def test_d19_filled_circle(self) -> None:
        profiles = build_symbol_profiles(19, 40.0)
        assert _circles(profiles)[0]['filled'] is True

    def test_d13_cross(self) -> None:
        # × 斜め十字: 線 2 本・円なし
        profiles = build_symbol_profiles(13, 40.0)
        assert len(_lines(profiles)) == 2
        assert not _circles(profiles)

    def test_d16_circle_slash(self) -> None:
        profiles = build_symbol_profiles(16, 40.0)
        assert len(_circles(profiles)) == 1
        assert len(_lines(profiles)) == 1
        assert _circles(profiles)[0]['filled'] is False

    def test_d22_open_circle(self) -> None:
        # ○ 輪郭の円: 円 1 個・塗りなし・線なし
        profiles = build_symbol_profiles(22, 40.0)
        circles = _circles(profiles)
        assert len(circles) == 1 and circles[0]['filled'] is False
        assert not _lines(profiles)

    def test_d25_circle_with_center_dot(self) -> None:
        # ⊙ 円 + 中心の塗り丸
        circles = _circles(build_symbol_profiles(25, 40.0))
        assert len(circles) == 2
        assert len([c for c in circles if c['filled']]) == 1

    def test_d29_circle_cross(self) -> None:
        profiles = build_symbol_profiles(29, 40.0)
        assert len(_circles(profiles)) == 1
        assert len(_lines(profiles)) == 2

    def test_d32_double_circle(self) -> None:
        circles = _circles(build_symbol_profiles(32, 40.0))
        assert len(circles) == 2
        assert all(c['filled'] is False for c in circles)

    def test_d35_circle_plus(self) -> None:
        profiles = build_symbol_profiles(35, 40.0)
        assert len(_circles(profiles)) == 1
        assert len(_lines(profiles)) == 2

    def test_d38_dot_plus(self) -> None:
        profiles = build_symbol_profiles(38, 40.0)
        circles = _circles(profiles)
        assert len(circles) == 1 and circles[0]['filled'] is True
        assert len(_lines(profiles)) == 2

    def test_d41_circle_cross(self) -> None:
        profiles = build_symbol_profiles(41, 40.0)
        assert len(_circles(profiles)) == 1
        assert len(_lines(profiles)) == 2

    def test_size_scales_radius(self) -> None:
        small = _circles(build_symbol_profiles(22, 40.0))[0]
        large = _circles(build_symbol_profiles(22, 80.0))[0]
        assert small['radius'] == 20.0
        assert large['radius'] == 40.0

    def test_non_standard_uses_nearest(self) -> None:
        assert build_symbol_profiles(14, 40.0)

    def test_circles_centered_at_origin(self) -> None:
        for nominal in (10, 13, 16, 19, 22, 25, 29, 32, 35, 38, 41):
            for p in build_symbol_profiles(nominal, 40.0):
                if p['kind'] == KIND_CIRCLE:
                    assert p['center'] == [0.0, 0.0]
