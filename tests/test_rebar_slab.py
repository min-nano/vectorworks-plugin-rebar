"""スラブモード (rebar.slab / rebar.build_document) のテスト。vs モック不要。"""
from __future__ import annotations

import json
import math
from typing import Any, Dict, List

import pytest

from vectorworks_plugin_rebar.document import (
    TARGET_FRONT_BACK,
    TARGET_LEFT_RIGHT,
    validate_document,
)
from vectorworks_plugin_rebar.rebar import build_document
from vectorworks_plugin_rebar.rebar.spec import SpecError

# 2000×3000 の矩形スラブ (天端 z=0)
RECT_PATH = [
    [0.0, 0.0, 0.0],
    [2000.0, 0.0, 0.0],
    [2000.0, 3000.0, 0.0],
    [0.0, 3000.0, 0.0],
]


def make_params(**overrides: Any) -> Dict[str, Any]:
    params: Dict[str, Any] = {
        'mode': 'slab',
        'path': [list(v) for v in RECT_PATH],
        'main_bar': 'D10@200',
        'dist_bar': 'D13@150',
        'main_angle': 0.0,
        'double_layer': False,
        'slab_thickness': 150.0,
        'cover': 40.0,
        'mark_scale': 4.0,
    }
    params.update(overrides)
    return params


class TestSingleLayer:
    def test_document_is_valid_and_serializable(self) -> None:
        document = build_document(make_params())
        validate_document(json.loads(json.dumps(document)))

    def test_plan_line_counts(self) -> None:
        document = build_document(make_params())
        # 主筋 (X 方向 @200, Y 幅 3000, 重心基準) 15 本 + 配力筋
        # (Y 方向 @150, X 幅 2000) 13 本
        assert len(document['plan_lines']) == 28

    def test_bars_3d_at_center_of_thickness(self) -> None:
        document = build_document(make_params())
        z_values = {
            round(bar['vertices'][0][2], 6) for bar in document['bars_3d']
        }
        # シングルは厚中央 (z=-75) に主筋、その上に配力筋
        # (z = -75 + 10/2 + 13/2 = -63.5)
        assert z_values == {-75.0, -63.5}

    def test_cut_lines_front_back(self) -> None:
        document = build_document(make_params())
        lines = [
            line
            for line in document['cut_lines']
            if line['target'] == TARGET_FRONT_BACK
        ]
        # 紙面方向 (X) の主筋は 1 本の直線、紙面直交 (Y) の配力筋は
        # 13 箇所の × (各 2 線) = 26 線
        straight = [
            line for line in lines if line['start'][1] == line['end'][1]
        ]
        assert len(lines) == 27
        assert len(straight) == 1
        assert straight[0]['start'] == [0.0, -75.0]
        assert straight[0]['end'] == [2000.0, -75.0]

    def test_cut_lines_left_right(self) -> None:
        document = build_document(make_params())
        lines = [
            line
            for line in document['cut_lines']
            if line['target'] == TARGET_LEFT_RIGHT
        ]
        # 紙面方向 (Y) の配力筋は 1 本の直線、紙面直交 (X) の主筋は
        # 15 箇所の × (各 2 線) = 30 線
        assert len(lines) == 31
        straight = [
            line for line in lines if line['start'][1] == line['end'][1]
        ]
        assert len(straight) == 1
        assert straight[0]['start'] == [0.0, -63.5]
        assert straight[0]['end'] == [3000.0, -63.5]

    def test_cross_mark_size_follows_diameter_and_scale(self) -> None:
        document = build_document(make_params())
        crosses = [
            line
            for line in document['cut_lines']
            if line['target'] == TARGET_FRONT_BACK
            and line['start'][1] != line['end'][1]
        ]
        # 配力筋 D13 × 倍率 4 = 52 の × (対角線の水平/垂直成分が 52)
        for line in crosses:
            assert math.isclose(abs(line['end'][0] - line['start'][0]), 52.0)
            assert math.isclose(abs(line['end'][1] - line['start'][1]), 52.0)


class TestDoubleLayer:
    def test_plan_lines_doubled(self) -> None:
        document = build_document(
            make_params(
                double_layer=True,
                top_main_bar='D10@200',
                top_dist_bar='D13@150',
            )
        )
        # 平面線はシングルの 2 倍 (上端筋 + 下端筋)
        assert len(document['plan_lines']) == 56

    def test_bar_elevations(self) -> None:
        document = build_document(
            make_params(
                double_layer=True,
                top_main_bar='D10@200',
                top_dist_bar='D13@150',
            )
        )
        z_values = {
            round(bar['vertices'][0][2], 6) for bar in document['bars_3d']
        }
        # 下端筋: 主筋 -150+40+5=-105, 配力筋 -105+5+6.5=-93.5
        # 上端筋: 主筋 -40-5=-45, 配力筋 -45-5-6.5=-56.5
        assert z_values == {-105.0, -93.5, -45.0, -56.5}


class TestMainAngle:
    def test_rotated_main_bars(self) -> None:
        document = build_document(make_params(main_angle=90.0))
        # 主筋が Y 方向 (@200, X 幅 2000 → 9 本)、配力筋が X 方向
        # (@150, Y 幅 3000 → 19 本)
        assert len(document['plan_lines']) == 28
        main_lines = [
            line
            for line in document['plan_lines']
            if math.isclose(line['start'][0], line['end'][0], abs_tol=1e-6)
        ]
        assert len(main_lines) == 9


class TestErrors:
    def test_path_too_short(self) -> None:
        with pytest.raises(SpecError):
            build_document(make_params(path=[[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]]))

    def test_blank_main_bar(self) -> None:
        with pytest.raises(SpecError):
            build_document(make_params(main_bar=''))

    def test_cover_exceeds_thickness_for_double(self) -> None:
        with pytest.raises(SpecError):
            build_document(
                make_params(double_layer=True, slab_thickness=60.0, cover=40.0)
            )

    def test_invalid_mode(self) -> None:
        with pytest.raises(SpecError):
            build_document(make_params(mode='wall'))

    def test_missing_path(self) -> None:
        params = make_params()
        del params['path']
        with pytest.raises(SpecError):
            build_document(params)


class TestPathNormalization:
    def test_closed_ring_with_duplicate_end_vertex(self) -> None:
        path: List[List[float]] = [list(v) for v in RECT_PATH] + [
            list(RECT_PATH[0])
        ]
        document = build_document(make_params(path=path))
        assert len(document['plan_lines']) == 28

    def test_elevated_slab_uses_path_z(self) -> None:
        path = [[v[0], v[1], 500.0] for v in RECT_PATH]
        document = build_document(make_params(path=path))
        z_values = {
            round(bar['vertices'][0][2], 6) for bar in document['bars_3d']
        }
        assert z_values == {425.0, 436.5}
