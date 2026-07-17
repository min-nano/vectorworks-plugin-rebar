"""梁モード (rebar.beam / rebar.build_document) のテスト。vs モック不要。

命令セットは作図クラスを持たないため、主筋とせん断補強筋の判別は
幾何(向き・長さ・開閉)で行う。
"""
from __future__ import annotations

import json
import math
from collections import Counter
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
        open_bars = [bar for bar in document['bars_3d'] if not bar['closed']]
        stirrups = [bar for bar in document['bars_3d'] if bar['closed']]
        # 主筋 = 軸方向に全長を通る開いた線 (X 方向に 1000mm 超)
        main = [
            bar
            for bar in open_bars
            if abs(bar['vertices'][-1][0] - bar['vertices'][0][0]) > 1000.0
        ]
        # 主筋は上端 2 + 下端 3 の実本数、あばら筋の矩形は閉じた 20 本
        assert len(main) == 5
        assert len(stirrups) == 20
        # 上端筋 z = -40-10-8 = -58 / 下端筋 z = -600+40+10+8 = -542
        z_values = {round(bar['vertices'][0][2], 6) for bar in main}
        assert z_values == {-58.0, -542.0}
        # フック = 短い開いた線 (あばら筋 1 本につき 135° フック 2 本)
        hooks = [bar for bar in open_bars if bar not in main]
        assert len(hooks) == 2 * 20

    def test_stirrup_rectangle_in_cross_section(self) -> None:
        document = build_document(make_params())
        lines = [
            line
            for line in document['cut_lines']
            if line['target'] == TARGET_LEFT_RIGHT
        ]
        # 四角あばら筋の矩形 = 軸平行の 4 線 (フックと主筋 × は斜め線)
        rect = [line for line in lines if not _is_diagonal(line)]
        assert len(rect) == 4
        # 矩形はかぶりを除いた外形 (±110, -40〜-560)
        xs = {p[0] for line in rect for p in (line['start'], line['end'])}
        zs = {p[1] for line in rect for p in (line['start'], line['end'])}
        assert xs == {-110.0, 110.0}
        assert zs == {-40.0, -560.0}

    def test_main_bar_crosses_in_cross_section(self) -> None:
        # 主筋の × 記号の中心が主筋位置に一致する。フックも斜め線を持つため、
        # 各主筋位置に × の 2 線が中心を共有して現れることで確認する
        # (せん断補強筋を外すと主筋位置自体がずれるので既定のまま検証する)。
        document = build_document(make_params())
        crosses = [
            line
            for line in document['cut_lines']
            if line['target'] == TARGET_LEFT_RIGHT and _is_diagonal(line)
        ]
        centers = Counter(
            (
                round((line['start'][0] + line['end'][0]) / 2, 6),
                round((line['start'][1] + line['end'][1]) / 2, 6),
            )
            for line in crosses
        )
        # 上端 2 + 下端 3 = 5 本の主筋、× は 1 本につき中心を共有する 2 線
        for center in (
            (-92.0, -58.0),
            (92.0, -58.0),
            (-92.0, -542.0),
            (0.0, -542.0),
            (92.0, -542.0),
        ):
            assert centers[center] == 2

    def test_longitudinal_section_goes_to_front_back(self) -> None:
        # 縦断面(梁に沿う切断の側面図)は front_back に入る。梁に沿って切断
        # したとき、上下主筋の水平線とせん断補強筋の縦線を表示する。
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
        # せん断補強筋を外し、主筋 1 本の × だけを見る (フックの斜め線を除く)
        document = build_document(
            make_params(top_bars='1-D16', bottom_bars='', stirrup='')
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


class TestStirrupModes:
    """先頭の脚数によるせん断補強筋の配置切り替え。"""

    def _plan_stirrup_lines(self, document: Any) -> list:
        return [
            line
            for line in document['plan_lines']
            if line['start'][0] == line['end'][0]
        ]

    def _closed_3d(self, document: Any) -> list:
        return [bar for bar in document['bars_3d'] if bar['closed']]

    def test_single_leg_has_no_hoop_or_plan_line(self) -> None:
        # 1-D10@250: 縦筋 1 本のみ。閉じた矩形は無く、平面線も出ない
        # (縦筋は上面から見ると点になるため)。
        document = build_document(make_params(stirrup='1-D10@250'))
        validate_document(json.loads(json.dumps(document)))
        assert self._closed_3d(document) == []
        assert self._plan_stirrup_lines(document) == []

    def test_hoop_has_closed_rect_and_plan_line(self) -> None:
        # 2-D10@250: 四角状のあばら筋。閉じた矩形と幅方向の平面線が出る。
        document = build_document(make_params(stirrup='2-D10@250'))
        # 4000mm を @250、始端 125 から 16 本
        assert len(self._closed_3d(document)) == 16
        assert len(self._plan_stirrup_lines(document)) == 16

    def test_hoop_with_inner_bar_adds_open_leg(self) -> None:
        # 3-D10@250: 四角あばら筋 + 中央縦筋。閉じた矩形の本数は 2 本脚と
        # 同じだが、開いた線 (フック + 中央縦筋) が増える。
        hoop = build_document(make_params(stirrup='2-D10@250'))
        inner = build_document(make_params(stirrup='3-D10@250'))
        assert len(self._closed_3d(inner)) == len(self._closed_3d(hoop))
        open_hoop = [b for b in hoop['bars_3d'] if not b['closed']]
        open_inner = [b for b in inner['bars_3d'] if not b['closed']]
        # 内部縦筋 (1 本/位置) の分だけ開いた線が増える (16 位置)
        assert len(open_inner) - len(open_hoop) == 16

    def test_default_stirrup_is_two_leg_hoop(self) -> None:
        # 脚数を省いた D10@200 は 2 本脚 (四角あばら筋) と同じ配置。
        default = build_document(make_params(stirrup='D10@200'))
        two_leg = build_document(make_params(stirrup='2-D10@200'))
        assert default['bars_3d'] == two_leg['bars_3d']
        assert default['cut_lines'] == two_leg['cut_lines']

    def test_hook_tail_lengths_follow_standard(self) -> None:
        # 135° フックの余長 = 6d、180° フックの余長 = 4d (SD295A 標準図)。
        # 端部の直線区間 (最後のセグメント) の長さで確認する。
        d = 10.0
        # 3 本脚: 135° (あばら筋) と 180° (中央縦筋) の両方を含む
        document = build_document(make_params(stirrup='3-D10@250'))
        open_bars = [b for b in document['bars_3d'] if not b['closed']]
        # 中央縦筋以外 = 主筋 (長い) と 135° フック (短い)
        tails = set()
        for bar in open_bars:
            verts = bar['vertices']
            if abs(verts[-1][0] - verts[0][0]) > 1000.0:
                continue  # 主筋
            seg = math.hypot(
                verts[-1][0] - verts[-2][0], verts[-1][1] - verts[-2][1]
            )
            # z 方向の余長も拾う
            seg = math.hypot(seg, verts[-1][2] - verts[-2][2])
            tails.add(round(seg, 3))
        assert round(6 * d, 3) in tails  # 135° 余長 60mm
        assert round(4 * d, 3) in tails  # 180° 余長 40mm

    def test_large_bar_uses_larger_bend_radius(self) -> None:
        from vectorworks_plugin_rebar.rebar.beam import _bend_radius

        # 内法直径 D16 以下 3d / D19 以上 4d → 中心曲げ半径 2d / 2.5d
        assert _bend_radius(10.0) == 20.0
        assert _bend_radius(16.0) == 32.0
        assert _bend_radius(22.0) == 55.0

    def test_invalid_leg_count_raises(self) -> None:
        with pytest.raises(SpecError):
            build_document(make_params(stirrup='4-D10@250'))


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
