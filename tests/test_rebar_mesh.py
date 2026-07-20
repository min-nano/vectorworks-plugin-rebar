"""餅網配筋(断面)の計算 (rebar.mesh) のテスト。vs 非依存。"""
from __future__ import annotations

import pytest

from vectorworks_plugin_rebar.document import KIND_LINE
from vectorworks_plugin_rebar.rebar.mesh import build_mesh_commands
from vectorworks_plugin_rebar.rebar.spec import NominalPitch, SpecError

PERP = NominalPitch(13, 200.0)


class TestBuildMeshCommands:
    def test_horizontal_line_offset_and_marks(self) -> None:
        lines, profiles, centers = build_mesh_commands(
            [[0.0, 0.0], [1000.0, 0.0]],
            parallel_nominal=10,
            perp=PERP,
            cover=40.0,
            mark_scale=4.0,
            flip=False,
        )
        # オフセット = cover + 平行筋径/2 = 40 + 5 = 45、左側(法線 +Y)へ
        assert lines == [{'start': [0.0, 45.0], 'end': [1000.0, 45.0]}]
        # D13 の記号は × (線 2 本)。プロファイルは原点中心
        assert all(p['kind'] == KIND_LINE for p in profiles)
        assert len(profiles) == 2
        # ピッチ 200: 始端から 100 起点で 100,300,500,700,900 の 5 本
        assert centers == [
            [100.0, 45.0],
            [300.0, 45.0],
            [500.0, 45.0],
            [700.0, 45.0],
            [900.0, 45.0],
        ]

    def test_flip_reverses_offset_side(self) -> None:
        lines, _profiles, centers = build_mesh_commands(
            [[0.0, 0.0], [1000.0, 0.0]],
            parallel_nominal=10,
            perp=PERP,
            cover=40.0,
            mark_scale=4.0,
            flip=True,
        )
        assert lines == [{'start': [0.0, -45.0], 'end': [1000.0, -45.0]}]
        assert centers[0] == [100.0, -45.0]

    def test_vertical_line_offsets_left(self) -> None:
        lines, _profiles, centers = build_mesh_commands(
            [[0.0, 0.0], [0.0, 1000.0]],
            parallel_nominal=10,
            perp=PERP,
            cover=40.0,
            mark_scale=4.0,
            flip=False,
        )
        # d=(0,1) の左法線は (-1,0)。オフセット 45 で x=-45
        assert lines == [{'start': [-45.0, 0.0], 'end': [-45.0, 1000.0]}]
        assert centers[0] == [-45.0, 100.0]

    def test_short_line_single_center(self) -> None:
        _lines, _profiles, centers = build_mesh_commands(
            [[0.0, 0.0], [100.0, 0.0]],
            parallel_nominal=10,
            perp=PERP,
            cover=40.0,
            mark_scale=4.0,
            flip=False,
        )
        # 線長 100 < ピッチ 200 なので中央に 1 本
        assert centers == [[50.0, 45.0]]

    def test_mark_size_scales_with_mark_scale(self) -> None:
        _lines, profiles, _centers = build_mesh_commands(
            [[0.0, 0.0], [1000.0, 0.0]],
            parallel_nominal=10,
            perp=NominalPitch(22, 200.0),
            cover=40.0,
            mark_scale=4.0,
            flip=False,
        )
        # D22 は ○ (輪郭円)。外径 = 22 × 4 = 88、半径 44
        circles = [p for p in profiles if p['kind'] != KIND_LINE]
        assert circles[0]['radius'] == 44.0

    def test_cover_included_in_offset(self) -> None:
        lines, _profiles, _centers = build_mesh_commands(
            [[0.0, 0.0], [1000.0, 0.0]],
            parallel_nominal=16,
            perp=PERP,
            cover=30.0,
            mark_scale=4.0,
            flip=False,
        )
        # 30 + 16/2 = 38
        assert lines[0]['start'][1] == 38.0

    def test_zero_length_raises(self) -> None:
        with pytest.raises(SpecError):
            build_mesh_commands(
                [[5.0, 5.0], [5.0, 5.0]],
                parallel_nominal=10,
                perp=PERP,
                cover=40.0,
                mark_scale=4.0,
                flip=False,
            )
