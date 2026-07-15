"""スラブモードの配筋計算。vs に依存しない。

3D パス(閉じた外形)で指定された配筋範囲に、主筋・配力筋の線族を
組み立てる。パス平面はスラブ天端とみなし、Z 方向の鉄筋位置は
スラブ厚・かぶり・鉄筋径から決める:

- シングル配筋: スラブ厚の中央に配筋する(土間スラブの中央配筋の慣例)。
  主筋を下・配力筋をその上に重ねる。
- ダブル配筋: 下端筋は「かぶり + 径/2」だけ底面から上がった位置に主筋、
  その上に配力筋。上端筋は天端から「かぶり + 径/2」下がった位置に主筋、
  その下に配力筋(主筋を外側に置く慣例)。

平面ビューは各鉄筋を外形でクリップした線として描く。断面 2D
コンポーネントは、紙面方向に近い向きの鉄筋を 1 本の直線(層の全幅)、
紙面直交方向に近い向きの鉄筋を等ピッチの × 記号として描く。
向きの判定は紙面軸との成分比較(|軸方向成分| >= |法線成分| なら直線)で、
軸に整合しない斜め配筋は近い側の表現に寄せる近似とする。
× の位置は各鉄筋のクリップ済み線分の中点を紙面軸へ投影した値
(軸整合の配筋では厳密に一致する)。
"""
from __future__ import annotations

import math
from typing import List, Sequence, Tuple

from ..document import (
    Bar3DCommand,
    CutLineCommand,
    PlanLineCommand,
    TARGET_FRONT_BACK,
    TARGET_LEFT_RIGHT,
)
from .geometry import Point2D, Segment2D, clip_line_family, direction_vectors
from .spec import BarPitch, SpecError

# 断面 2D コンポーネントの紙面軸: front_back は紙面 u=ローカル X、
# left_right は紙面 u=ローカル Y (document.py のスキーマ参照)。
_CUT_VIEWS: Tuple[Tuple[str, int], ...] = (
    (TARGET_FRONT_BACK, 0),
    (TARGET_LEFT_RIGHT, 1),
)


class _Family:
    """1 方向の鉄筋群(主筋または配力筋)のクリップ済み配置。"""

    def __init__(
        self,
        spec: BarPitch,
        angle_deg: float,
        z: float,
        segments: List[Segment2D],
    ) -> None:
        self.spec = spec
        self.angle_deg = angle_deg
        self.z = z
        self.segments = segments


def _project_polygon(path: Sequence[Sequence[float]]) -> List[Point2D]:
    """3D パス頂点を平面(XY)の多角形へ投影する。

    連続する重複点と、閉じたパスで先頭に一致する末尾点を除く。
    """
    polygon: List[Point2D] = []
    for vertex in path:
        point = (float(vertex[0]), float(vertex[1]))
        if polygon and _near(polygon[-1], point):
            continue
        polygon.append(point)
    if len(polygon) >= 2 and _near(polygon[0], polygon[-1]):
        polygon.pop()
    return polygon


def _near(a: Point2D, b: Point2D) -> bool:
    return math.hypot(a[0] - b[0], a[1] - b[1]) < 1e-6


def _build_family(
    spec: BarPitch,
    angle_deg: float,
    z: float,
    polygon: Sequence[Point2D],
) -> _Family:
    segments = clip_line_family(polygon, angle_deg, spec.pitch)
    return _Family(spec, angle_deg, z, segments)


def _plan_lines(family: _Family) -> List[PlanLineCommand]:
    return [
        {
            'start': [start[0], start[1]],
            'end': [end[0], end[1]],
        }
        for start, end in family.segments
    ]


def _bars_3d(family: _Family) -> List[Bar3DCommand]:
    return [
        {
            'vertices': [
                [start[0], start[1], family.z],
                [end[0], end[1], family.z],
            ],
            'closed': False,
        }
        for start, end in family.segments
    ]


def cross_cut_lines(
    target: str, u: float, v: float, size: float
) -> List[CutLineCommand]:
    """紙面直交方向の鉄筋を表す × 記号を 2 本の線に分解する。"""
    half = size / 2.0
    return [
        {
            'target': target,
            'start': [u - half, v - half],
            'end': [u + half, v + half],
        },
        {
            'target': target,
            'start': [u - half, v + half],
            'end': [u + half, v - half],
        },
    ]


def _family_cut_lines(
    family: _Family, mark_scale: float
) -> List[CutLineCommand]:
    """1 方向の鉄筋群の断面表現を両方の断面コンポーネントへ組み立てる。"""
    commands: List[CutLineCommand] = []
    if not family.segments:
        return commands
    d, _n = direction_vectors(family.angle_deg)
    for target, axis in _CUT_VIEWS:
        coords = [
            coord
            for start, end in family.segments
            for coord in (start[axis], end[axis])
        ]
        u_min = min(coords)
        u_max = max(coords)
        # 紙面軸との成分比較: 紙面方向に近い鉄筋は 1 本の直線、
        # 紙面直交方向に近い鉄筋は × 記号で表す
        other = 1 - axis
        if abs(d[axis]) >= abs(d[other]):
            commands.append(
                {
                    'target': target,
                    'start': [u_min, family.z],
                    'end': [u_max, family.z],
                }
            )
        else:
            size = family.spec.diameter * mark_scale
            for start, end in family.segments:
                u = (start[axis] + end[axis]) / 2.0
                commands.extend(cross_cut_lines(target, u, family.z, size))
    return commands


def build_slab_commands(
    path: Sequence[Sequence[float]],
    *,
    main: BarPitch,
    dist: BarPitch,
    angle_deg: float,
    double_layer: bool,
    top_main: BarPitch,
    top_dist: BarPitch,
    thickness: float,
    cover: float,
    mark_scale: float,
) -> Tuple[List[PlanLineCommand], List[CutLineCommand], List[Bar3DCommand]]:
    """スラブモードの命令(平面線・断面線・3D 鉄筋)を組み立てる。

    main/dist はシングル時またはダブル時の下端筋、top_main/top_dist は
    ダブル時の上端筋。angle_deg は主筋の方向(度、X 軸基準)で、配力筋は
    これに直交する。
    """
    polygon = _project_polygon(path)
    if len(polygon) < 3:
        raise SpecError('スラブモードのパスには 3 点以上の外形が必要です')
    if thickness <= 0:
        raise SpecError(f'スラブ厚は正の値にしてください: {thickness!r}')
    if double_layer and thickness <= 2 * cover:
        raise SpecError(
            f'スラブ厚 {thickness:g} がかぶり {cover:g}×2 以下のため配筋できません'
        )

    z_top_face = sum(float(vertex[2]) for vertex in path) / len(path)
    dist_angle = angle_deg + 90.0

    families: List[_Family] = []
    if double_layer:
        # 下端筋: 主筋が外側(下)、配力筋がその上に重なる
        z_bottom_main = z_top_face - thickness + cover + main.diameter / 2.0
        z_bottom_dist = z_bottom_main + main.diameter / 2.0 + dist.diameter / 2.0
        # 上端筋: 主筋が外側(上)、配力筋がその下に重なる
        z_top_main = z_top_face - cover - top_main.diameter / 2.0
        z_top_dist = z_top_main - top_main.diameter / 2.0 - top_dist.diameter / 2.0
        families.extend(
            [
                _build_family(main, angle_deg, z_bottom_main, polygon),
                _build_family(dist, dist_angle, z_bottom_dist, polygon),
                _build_family(top_main, angle_deg, z_top_main, polygon),
                _build_family(top_dist, dist_angle, z_top_dist, polygon),
            ]
        )
    else:
        # シングル配筋: スラブ厚の中央。主筋が下・配力筋がその上
        z_center = z_top_face - thickness / 2.0
        z_dist = z_center + main.diameter / 2.0 + dist.diameter / 2.0
        families.extend(
            [
                _build_family(main, angle_deg, z_center, polygon),
                _build_family(dist, dist_angle, z_dist, polygon),
            ]
        )

    plan_lines: List[PlanLineCommand] = []
    cut_lines: List[CutLineCommand] = []
    bars_3d: List[Bar3DCommand] = []
    for family in families:
        plan_lines.extend(_plan_lines(family))
        cut_lines.extend(_family_cut_lines(family, mark_scale))
        bars_3d.extend(_bars_3d(family))
    return plan_lines, cut_lines, bars_3d
