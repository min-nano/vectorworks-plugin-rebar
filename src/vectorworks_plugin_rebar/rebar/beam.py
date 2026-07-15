"""梁モードの配筋計算。vs に依存しない。

3D パス(梁天端の中心線)に沿って、上下端主筋とせん断補強筋
(あばら筋)を組み立てる。断面はパスの Z を天端として下向きに
「せい」分の矩形とみなす:

- せん断補強筋の外形: 断面からかぶりを除いた矩形。
- 主筋の中心: 面からかぶり + せん断補強筋径 + 主筋径/2 の位置。
  複数本は幅方向に等間隔(1 本なら中央)。
- せん断補強筋のピッチ: 各パス区間の始端から ピッチ/2 の位置を最初とし、
  以降等ピッチ(区間長がピッチ未満なら中央に 1 本)。

平面ビューは主筋を軸方向の線(上下端で平面位置が重なる線は 1 本に
まとめる)、せん断補強筋を軸直交の短線(足の内法幅)で描く。

断面 2D コンポーネントは最長区間の向きで決める: 区間が X 軸寄り
なら横断面(主筋=×・せん断補強筋=矩形)を左右の断面(left_right)に、
縦断面(主筋=水平線・せん断補強筋=等ピッチの縦線)を前後の断面
(front_back)に置く。Y 軸寄りなら逆。斜めの梁は近い側の軸に寄せた
近似になる(2D コンポーネントは物体のローカル軸 6 方向にしか
持てないため)。
"""
from __future__ import annotations

import math
from typing import List, Optional, Sequence, Tuple

from ..document import (
    Bar3DCommand,
    CutLineCommand,
    PlanLineCommand,
    TARGET_FRONT_BACK,
    TARGET_LEFT_RIGHT,
)
from .classes import CLASS_BEAM_MAIN, CLASS_BEAM_STIRRUP
from .slab import cross_cut_lines
from .spec import BarCount, BarPitch, SectionSize, SpecError

# 平面位置(幅方向オフセット)の重複をまとめる丸め (mm)
_OFFSET_ROUND = 2


class _Segment:
    """パスの 1 区間(平面投影)と断面配置の情報。"""

    def __init__(
        self, start: Sequence[float], end: Sequence[float]
    ) -> None:
        self.start = (float(start[0]), float(start[1]))
        self.end = (float(end[0]), float(end[1]))
        self.z_top = float(start[2])
        dx = self.end[0] - self.start[0]
        dy = self.end[1] - self.start[1]
        self.length = math.hypot(dx, dy)
        if self.length > 0:
            self.axis = (dx / self.length, dy / self.length)
        else:
            self.axis = (1.0, 0.0)
        # 幅方向(軸を反時計回りに 90 度回した向き)
        self.lateral = (-self.axis[1], self.axis[0])

    def point_at(self, along: float, offset: float) -> Tuple[float, float]:
        """始端から along、幅方向へ offset の平面座標を返す。"""
        return (
            self.start[0] + self.axis[0] * along + self.lateral[0] * offset,
            self.start[1] + self.axis[1] * along + self.lateral[1] * offset,
        )


def _bar_offsets(count: int, half_extent: float) -> List[float]:
    """主筋の幅方向オフセット列(等間隔、1 本なら中央)を返す。"""
    if count == 1:
        return [0.0]
    step = (2.0 * half_extent) / (count - 1)
    return [-half_extent + i * step for i in range(count)]


def _stirrup_positions(length: float, pitch: float) -> List[float]:
    """区間内のせん断補強筋位置(始端からの距離)を返す。"""
    if length <= 0:
        return []
    if length < pitch:
        return [length / 2.0]
    positions: List[float] = []
    along = pitch / 2.0
    while along <= length - pitch / 2.0 + 1e-6:
        positions.append(along)
        along += pitch
    return positions


def build_beam_commands(
    path: Sequence[Sequence[float]],
    *,
    section: SectionSize,
    top: Optional[BarCount],
    bottom: Optional[BarCount],
    stirrup: Optional[BarPitch],
    cover: float,
    mark_scale: float,
) -> Tuple[List[PlanLineCommand], List[CutLineCommand], List[Bar3DCommand]]:
    """梁モードの命令(平面線・断面線・3D 鉄筋)を組み立てる。"""
    if len(path) < 2:
        raise SpecError('梁モードのパスには 2 点以上が必要です')
    if section.width <= 2 * cover or section.depth <= 2 * cover:
        raise SpecError(
            f'断面サイズ {section.width:g}×{section.depth:g} が'
            f'かぶり {cover:g}×2 以下のため配筋できません'
        )
    segments = [
        _Segment(path[i], path[i + 1]) for i in range(len(path) - 1)
    ]
    segments = [s for s in segments if s.length > 1e-6]
    if not segments:
        raise SpecError('梁モードのパスに長さのある区間がありません')

    stirrup_dia = stirrup.diameter if stirrup else 0.0
    half_width = section.width / 2.0 - cover
    z_stirrup_top = -cover
    z_stirrup_bottom = -section.depth + cover

    # 主筋の配置: (幅方向オフセット, 天端基準 Z, 径)
    main_bars: List[Tuple[float, float, float]] = []
    if top is not None:
        z = -cover - stirrup_dia - top.diameter / 2.0
        half = half_width - stirrup_dia - top.diameter / 2.0
        main_bars.extend(
            (offset, z, top.diameter)
            for offset in _bar_offsets(top.quantity, max(half, 0.0))
        )
    if bottom is not None:
        z = -section.depth + cover + stirrup_dia + bottom.diameter / 2.0
        half = half_width - stirrup_dia - bottom.diameter / 2.0
        main_bars.extend(
            (offset, z, bottom.diameter)
            for offset in _bar_offsets(bottom.quantity, max(half, 0.0))
        )

    plan_lines: List[PlanLineCommand] = []
    cut_lines: List[CutLineCommand] = []
    bars_3d: List[Bar3DCommand] = []

    for segment in segments:
        # 平面: 主筋(平面位置が重なる上下端の線は 1 本にまとめる)
        seen_offsets = set()
        for offset, z, _dia in main_bars:
            key = round(offset, _OFFSET_ROUND)
            if key not in seen_offsets:
                seen_offsets.add(key)
                start = segment.point_at(0.0, offset)
                end = segment.point_at(segment.length, offset)
                plan_lines.append(
                    {
                        'class': CLASS_BEAM_MAIN,
                        'start': [start[0], start[1]],
                        'end': [end[0], end[1]],
                    }
                )
            # 3D: 主筋は上下端それぞれ実位置に描く
            start = segment.point_at(0.0, offset)
            end = segment.point_at(segment.length, offset)
            bars_3d.append(
                {
                    'class': CLASS_BEAM_MAIN,
                    'vertices': [
                        [start[0], start[1], segment.z_top + z],
                        [end[0], end[1], segment.z_top + z],
                    ],
                    'closed': False,
                }
            )
        # 平面 + 3D: せん断補強筋
        if stirrup is not None:
            for along in _stirrup_positions(segment.length, stirrup.pitch):
                left = segment.point_at(along, -half_width)
                right = segment.point_at(along, half_width)
                plan_lines.append(
                    {
                        'class': CLASS_BEAM_STIRRUP,
                        'start': [left[0], left[1]],
                        'end': [right[0], right[1]],
                    }
                )
                bars_3d.append(
                    {
                        'class': CLASS_BEAM_STIRRUP,
                        'vertices': [
                            [left[0], left[1], segment.z_top + z_stirrup_top],
                            [right[0], right[1], segment.z_top + z_stirrup_top],
                            [right[0], right[1], segment.z_top + z_stirrup_bottom],
                            [left[0], left[1], segment.z_top + z_stirrup_bottom],
                        ],
                        'closed': True,
                    }
                )

    # 断面 2D コンポーネント: 最長区間の向きで割り当てる
    longest = max(segments, key=lambda s: s.length)
    x_dominant = abs(longest.axis[0]) >= abs(longest.axis[1])
    cross_target = TARGET_LEFT_RIGHT if x_dominant else TARGET_FRONT_BACK
    length_target = TARGET_FRONT_BACK if x_dominant else TARGET_LEFT_RIGHT
    # 横断面の紙面 u 軸 = 軸と直交する平面軸 / 縦断面の紙面 u 軸 = 軸方向の平面軸
    cross_axis = 1 if x_dominant else 0
    length_axis = 0 if x_dominant else 1
    mid = longest.point_at(longest.length / 2.0, 0.0)
    center_u = mid[cross_axis]
    lateral_sign = longest.lateral[cross_axis]
    z_top_abs = longest.z_top

    # 横断面: せん断補強筋の矩形
    if stirrup is not None:
        u1 = center_u - half_width * abs(lateral_sign)
        u2 = center_u + half_width * abs(lateral_sign)
        v1 = z_top_abs + z_stirrup_bottom
        v2 = z_top_abs + z_stirrup_top
        for start, end in (
            ((u1, v1), (u2, v1)),
            ((u2, v1), (u2, v2)),
            ((u2, v2), (u1, v2)),
            ((u1, v2), (u1, v1)),
        ):
            cut_lines.append(
                {
                    'target': cross_target,
                    'class': CLASS_BEAM_STIRRUP,
                    'start': [start[0], start[1]],
                    'end': [end[0], end[1]],
                }
            )
    # 横断面: 主筋の × 記号
    for offset, z, dia in main_bars:
        u = center_u + offset * lateral_sign
        cut_lines.extend(
            cross_cut_lines(
                cross_target,
                CLASS_BEAM_MAIN,
                u,
                z_top_abs + z,
                dia * mark_scale,
            )
        )

    # 縦断面: 主筋の水平線(上下端それぞれ 1 本)
    a1 = longest.start[length_axis]
    a2 = longest.end[length_axis]
    u_min, u_max = min(a1, a2), max(a1, a2)
    seen_z = set()
    for _offset, z, _dia in main_bars:
        key = round(z, _OFFSET_ROUND)
        if key in seen_z:
            continue
        seen_z.add(key)
        cut_lines.append(
            {
                'target': length_target,
                'class': CLASS_BEAM_MAIN,
                'start': [u_min, z_top_abs + z],
                'end': [u_max, z_top_abs + z],
            }
        )
    # 縦断面: せん断補強筋の縦線(等ピッチ)
    if stirrup is not None:
        axis_sign = longest.axis[length_axis]
        for along in _stirrup_positions(longest.length, stirrup.pitch):
            u = longest.start[length_axis] + along * axis_sign
            cut_lines.append(
                {
                    'target': length_target,
                    'class': CLASS_BEAM_STIRRUP,
                    'start': [u, z_top_abs + z_stirrup_bottom],
                    'end': [u, z_top_abs + z_stirrup_top],
                }
            )

    return plan_lines, cut_lines, bars_3d
