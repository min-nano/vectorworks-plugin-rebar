"""梁モード (rebar.beam / rebar.build_document) のテスト。vs モック不要。

命令セットは作図クラスを持たないため、主筋とせん断補強筋の判別は
幾何(向き・長さ・開閉)で行う。
"""
from __future__ import annotations

import json
import math
from typing import Any, Dict, Mapping

import pytest

from vectorworks_plugin_rebar.document import (
    TARGET_FRONT_BACK,
    TARGET_LEFT_RIGHT,
    validate_document,
)
from vectorworks_plugin_rebar.rebar import build_document
from vectorworks_plugin_rebar.rebar.spec import SpecError


def make_params(**overrides: Any) -> Dict[str, Any]:
    params: Dict[str, Any] = {
        'mode': 'beam',
        # X 方向 4000mm、天端 z=0 の梁
        'path': [[0.0, 0.0, 0.0], [4000.0, 0.0, 0.0]],
        'section_size': '300×600',
        'top_bars': '2-D16',
        'bottom_bars': '3-D16',
        'stirrup': 'D10@200',
        'cover': 40.0,
        'mark_scale': 4.0,
    }
    params.update(overrides)
    return params


def _is_diagonal(line: Mapping[str, Any]) -> bool:
    """× 記号の片割れ(斜め線)かどうか。"""
    return (
        abs(line['end'][0] - line['start'][0]) > 1e-9
        and abs(line['end'][1] - line['start'][1]) > 1e-9
    )


def _length(line: Mapping[str, Any]) -> float:
    return math.hypot(
        line['end'][0] - line['start'][0], line['end'][1] - line['start'][1]
    )


class TestBeamAlongX:
    def test_document_is_valid_and_serializable(self) -> None:
        document = build_document(make_params())
        validate_document(json.loads(json.dumps(document)))

    def test_plan_lines(self) -> None:
        document = build_document(make_params())
        # 主筋 = 軸方向 (X) の線 / せん断補強筋 = 軸直交 (Y) の線
        main = [
            line
            for line in document['plan_lines']
            if line['start'][1] == line['end'][1]
        ]
        stirrups = [
            line
            for line in document['plan_lines']
            if line['start'][0] == line['end'][0]
        ]
        assert len(main) + len(stirrups) == len(document['plan_lines'])
        # 主筋: 上端 ±92 と下端 ±92, 0 のうち平面位置の重複を除いた 3 本
        assert len(main) == 3
        offsets = sorted(line['start'][1] for line in main)
        assert offsets == [-92.0, 0.0, 92.0]
        # せん断補強筋: 100 から 3900 まで @200 の 20 本 (幅は足の外面間)
        assert len(stirrups) == 20
        assert stirrups[0]['start'] == [100.0, -110.0]
        assert stirrups[0]['end'] == [100.0, 110.0]
        assert stirrups[-1]['start'][0] == 3900.0

    def test_bars_3d(self) -> None:
        document = build_document(make_params())
        main = [bar for bar in document['bars_3d'] if not bar['closed']]
        stirrups = [bar for bar in document['bars_3d'] if bar['closed']]
        # 主筋は上端 2 + 下端 3 の実本数、せん断補強筋は閉じた矩形
        assert len(main) == 5
        assert len(stirrups) == 20
        # 上端筋 z = -40-10-8 = -58 / 下端筋 z = -600+40+10+8 = -542
        z_values = {round(bar['vertices'][0][2], 6) for bar in main}
        assert z_values == {-58.0, -542.0}

    def test_cross_section_goes_to_left_right(self) -> None:
        document = build_document(make_params())
        lines = [
            line
            for line in document['cut_lines']
            if line['target'] == TARGET_LEFT_RIGHT
        ]
        # せん断補強筋の矩形 = 軸平行の 4 線 / 主筋の × = 斜め線
        rect = [line for line in lines if not _is_diagonal(line)]
        crosses = [line for line in lines if _is_diagonal(line)]
        assert len(rect) == 4
        assert len(crosses) == 10
        # 矩形はかぶりを除いた外形 (±110, -40〜-560)
        xs = {p[0] for line in rect for p in (line['start'], line['end'])}
        zs = {p[1] for line in rect for p in (line['start'], line['end'])}
        assert xs == {-110.0, 110.0}
        assert zs == {-40.0, -560.0}
        # × の中心 (2 線の中点) は主筋位置
        centers = {
            (
                round((line['start'][0] + line['end'][0]) / 2, 6),
                round((line['start'][1] + line['end'][1]) / 2, 6),
            )
            for line in crosses
        }
        assert centers == {
            (-92.0, -58.0),
            (92.0, -58.0),
            (-92.0, -542.0),
            (0.0, -542.0),
            (92.0, -542.0),
        }

    def test_longitudinal_section_goes_to_front_back(self) -> None:
        document = build_document(make_params())
        lines = [
            line
            for line in document['cut_lines']
            if line['target'] == TARGET_FRONT_BACK
        ]
        # 主筋 = 水平線 / せん断補強筋 = 縦線
        main = [
            line for line in lines if line['start'][1] == line['end'][1]
        ]
        stirrups = [
            line for line in lines if line['start'][0] == line['end'][0]
        ]
        # 主筋: 上端・下端の水平線 2 本 (全長)
        assert len(main) == 2
        for line in main:
            assert line['start'][0] == 0.0
            assert line['end'][0] == 4000.0
        assert {line['start'][1] for line in main} == {-58.0, -542.0}
        # せん断補強筋: @200 の縦線 20 本
        assert len(stirrups) == 20
        for line in stirrups:
            assert {line['start'][1], line['end'][1]} == {-40.0, -560.0}


class TestBeamAlongY:
    def test_targets_are_swapped(self) -> None:
        document = build_document(
            make_params(path=[[0.0, 0.0, 0.0], [0.0, 4000.0, 0.0]])
        )
        # Y 方向の梁では横断面 (せん断補強筋の矩形 = 軸平行 4 線) が
        # 前後の断面に入る
        front_back = [
            line
            for line in document['cut_lines']
            if line['target'] == TARGET_FRONT_BACK
        ]
        rect = [line for line in front_back if not _is_diagonal(line)]
        assert len(rect) == 4


class TestBeamVariants:
    def test_short_beam_gets_single_stirrup(self) -> None:
        document = build_document(
            make_params(path=[[0.0, 0.0, 0.0], [150.0, 0.0, 0.0]])
        )
        stirrups = [
            line
            for line in document['plan_lines']
            if line['start'][0] == line['end'][0]
        ]
        assert len(stirrups) == 1
        assert math.isclose(stirrups[0]['start'][0], 75.0)

    def test_without_stirrup(self) -> None:
        document = build_document(make_params(stirrup=''))
        # 軸直交のせん断補強筋線が無い
        assert not any(
            line['start'][0] == line['end'][0]
            for line in document['plan_lines']
        )
        # 主筋の × は残る
        assert any(_is_diagonal(line) for line in document['cut_lines'])

    def test_single_bar_is_centered(self) -> None:
        document = build_document(
            make_params(top_bars='1-D16', bottom_bars='')
        )
        crosses = [
            line
            for line in document['cut_lines']
            if line['target'] == TARGET_LEFT_RIGHT and _is_diagonal(line)
        ]
        assert len(crosses) == 2
        center_u = round((crosses[0]['start'][0] + crosses[0]['end'][0]) / 2, 6)
        assert center_u == 0.0

    def test_multi_segment_path(self) -> None:
        document = build_document(
            make_params(
                path=[
                    [0.0, 0.0, 0.0],
                    [4000.0, 0.0, 0.0],
                    [4000.0, 2000.0, 0.0],
                ]
            )
        )
        # 各区間に主筋の平面線が引かれる (3 本 × 2 区間)。主筋は区間の
        # 全長 (2000mm 以上)、せん断補強筋は幅方向 (220mm) の短線
        main = [
            line for line in document['plan_lines'] if _length(line) > 1000.0
        ]
        assert len(main) == 6

    def test_cut_section_generated_per_segment(self) -> None:
        # L 字パス: 区間1 = X 方向 (0-4000)、区間2 = Y 方向 (X=4000, 0-2000)。
        # 区間ごとに断面を生成するため、区間1 の横断面は left_right、区間2 の
        # 横断面は front_back に × 記号として現れる(最長区間だけだと区間2 の
        # 断面が出なかった)。
        document = build_document(
            make_params(
                path=[
                    [0.0, 0.0, 0.0],
                    [4000.0, 0.0, 0.0],
                    [4000.0, 2000.0, 0.0],
                ]
            )
        )
        fb_marks = [
            line
            for line in document['cut_lines']
            if line['target'] == TARGET_FRONT_BACK and _is_diagonal(line)
        ]
        lr_marks = [
            line
            for line in document['cut_lines']
            if line['target'] == TARGET_LEFT_RIGHT and _is_diagonal(line)
        ]
        # 区間1 (X 方向) の横断面 × 記号
        assert lr_marks
        # 区間2 (Y 方向) の横断面 × 記号。区間2 の中点 X≈4000 付近に位置する。
        assert fb_marks
        assert any(abs(line['start'][0] - 4000.0) < 200.0 for line in fb_marks)


class TestBeamErrors:
    def test_path_too_short(self) -> None:
        with pytest.raises(SpecError):
            build_document(make_params(path=[[0.0, 0.0, 0.0]]))

    def test_blank_section_size(self) -> None:
        with pytest.raises(SpecError):
            build_document(make_params(section_size=''))

    def test_cover_exceeds_section(self) -> None:
        with pytest.raises(SpecError):
            build_document(make_params(section_size='60×600', cover=40.0))

    def test_zero_length_path(self) -> None:
        with pytest.raises(SpecError):
            build_document(
                make_params(path=[[0.0, 0.0, 0.0], [0.0, 0.0, 0.0]])
            )
