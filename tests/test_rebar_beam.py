"""梁モード (rebar.beam / rebar.build_document) のテスト。vs モック不要。"""
from __future__ import annotations

import json
import math
from typing import Any, Dict

import pytest

from vectorworks_plugin_rebar.document import (
    TARGET_FRONT_BACK,
    TARGET_LEFT_RIGHT,
    validate_document,
)
from vectorworks_plugin_rebar.rebar import build_document
from vectorworks_plugin_rebar.rebar.classes import (
    CLASS_BEAM_MAIN,
    CLASS_BEAM_STIRRUP,
)
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


class TestBeamAlongX:
    def test_document_is_valid_and_serializable(self) -> None:
        document = build_document(make_params())
        validate_document(json.loads(json.dumps(document)))

    def test_plan_lines(self) -> None:
        document = build_document(make_params())
        main = [
            line
            for line in document['plan_lines']
            if line['class'] == CLASS_BEAM_MAIN
        ]
        stirrups = [
            line
            for line in document['plan_lines']
            if line['class'] == CLASS_BEAM_STIRRUP
        ]
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
        main = [
            bar
            for bar in document['bars_3d']
            if bar['class'] == CLASS_BEAM_MAIN
        ]
        stirrups = [
            bar
            for bar in document['bars_3d']
            if bar['class'] == CLASS_BEAM_STIRRUP
        ]
        # 主筋は上端 2 + 下端 3 の実本数、せん断補強筋は閉じた矩形
        assert len(main) == 5
        assert all(not bar['closed'] for bar in main)
        assert len(stirrups) == 20
        assert all(bar['closed'] for bar in stirrups)
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
        rect = [line for line in lines if line['class'] == CLASS_BEAM_STIRRUP]
        crosses = [line for line in lines if line['class'] == CLASS_BEAM_MAIN]
        # せん断補強筋の矩形 4 線 + 主筋 5 本の × (各 2 線)
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
        main = [line for line in lines if line['class'] == CLASS_BEAM_MAIN]
        stirrups = [
            line for line in lines if line['class'] == CLASS_BEAM_STIRRUP
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
            assert line['start'][0] == line['end'][0]
            assert {line['start'][1], line['end'][1]} == {-40.0, -560.0}


class TestBeamAlongY:
    def test_targets_are_swapped(self) -> None:
        document = build_document(
            make_params(path=[[0.0, 0.0, 0.0], [0.0, 4000.0, 0.0]])
        )
        cross = [
            line
            for line in document['cut_lines']
            if line['class'] == CLASS_BEAM_STIRRUP
            and line['target'] == TARGET_FRONT_BACK
        ]
        # Y 方向の梁では横断面 (せん断補強筋の矩形) が前後の断面に入る
        assert len(cross) == 4


class TestBeamVariants:
    def test_short_beam_gets_single_stirrup(self) -> None:
        document = build_document(
            make_params(path=[[0.0, 0.0, 0.0], [150.0, 0.0, 0.0]])
        )
        stirrups = [
            line
            for line in document['plan_lines']
            if line['class'] == CLASS_BEAM_STIRRUP
        ]
        assert len(stirrups) == 1
        assert math.isclose(stirrups[0]['start'][0], 75.0)

    def test_without_stirrup(self) -> None:
        document = build_document(make_params(stirrup=''))
        assert not any(
            line['class'] == CLASS_BEAM_STIRRUP
            for line in document['plan_lines']
        )
        # 主筋の × は残る
        assert any(
            line['class'] == CLASS_BEAM_MAIN
            for line in document['cut_lines']
        )

    def test_single_bar_is_centered(self) -> None:
        document = build_document(
            make_params(top_bars='1-D16', bottom_bars='')
        )
        crosses = [
            line
            for line in document['cut_lines']
            if line['target'] == TARGET_LEFT_RIGHT
            and line['class'] == CLASS_BEAM_MAIN
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
        # 各区間に主筋の平面線が引かれる (3 本 × 2 区間)
        main = [
            line
            for line in document['plan_lines']
            if line['class'] == CLASS_BEAM_MAIN
        ]
        assert len(main) == 6


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
