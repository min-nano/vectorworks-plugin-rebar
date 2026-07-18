"""梁モードの配筋計算。vs に依存しない。

3D パス(梁天端の中心線)に沿って、上下端主筋とせん断補強筋
(あばら筋)を組み立てる。断面はパスの Z を天端として下向きに
「せい」分の矩形とみなす:

- せん断補強筋の外形: 断面からかぶりを除いた矩形。
- 主筋の中心: 面からかぶり + せん断補強筋径 + 主筋径/2 の位置。
  複数本は幅方向に等間隔(1 本なら中央)。
- せん断補強筋のピッチ: 各パス区間の始端から ピッチ/2 の位置を最初とし、
  以降等ピッチ(区間長がピッチ未満なら中央に 1 本)。

せん断補強筋は仕様先頭の脚数で配置を切り替える(``spec.parse_stirrup``):

- 1: 断面中央に縦筋 1 本のみ(上下端に 180° フック)。
- 2: 四角状のあばら筋(上端両隅に 135° フック)。
- 3: 四角のあばら筋 + 中央の縦筋(縦筋は 180° フック)。

フックは配筋標準図(材種 SD295A を仮定)に従い、鉄筋径に応じた曲げ内法
半径と余長で描く。曲げ内法直径は D16 以下 3d・D19 以上 4d(=内法半径
1.5d/2d)、鉄筋中心の曲げ半径はこれに径/2 を加えた 2d/2.5d。余長は
180° フックが 4d、135° フックが 6d。円弧は折れ線で近似する。フックは
断面 2D コンポーネント(横断面)と 3D の両方に反映する。

縦筋(180° フック)は一番高い/低い点が上端/下端主筋の中心 Z に一致する
よう位置を合わせる(主筋を巻き込む納まり)。またフックの曲げは最小曲げ
半径の制約で主筋へ密着できないため、現実にはフックを軸方向へ斜めに倒し、
断面へ投影した立ち上がり幅を主筋の見付け幅(``主筋径 + せん断補強筋径``、
例: 主筋 D13・せん断補強筋 D10 なら 10/2+13+10/2=23mm)へ収めて施工する。
これを剛体回転(bend start を通る鉛直軸まわり)で表現し、幅方向を縮めた
分を軸方向へ逃がす。断面 2D コンポーネントは紙面(幅方向・高さ)への投影
なので縮んだ立ち上がり幅で現れ、3D はフックが軸方向へ傾いた姿になる
(収まり検討時のリアリティを持たせる)。回転は剛体なので余長・曲げ半径は
保たれる。

平面ビューは主筋を軸方向の線(上下端で平面位置が重なる線は 1 本に
まとめる)、あばら筋(脚数 2/3)を軸直交の短線(足の内法幅)で描く。
縦筋 1 本のみ(脚数 1)は平面では点になるため平面線は描かない。

断面 2D コンポーネントは区間ごとに実位置へ生成する: 区間が X 軸寄り
なら横断面(梁を横断する切断: 主筋=×・せん断補強筋=矩形)を左右の断面
(left_right)に、縦断面(梁に沿う切断の側面図: 主筋=水平線・せん断補強筋
=等ピッチの縦線)を前後の断面(front_back)に置く。Y 軸寄りなら逆。VW の
断面ビューポートは 3D の切断面と物体の交差から表示コンポーネントを
決めるため、横断/縦断を実位置に用意することで、梁を横断した切断には
横断面、梁に沿った切断(梁幅内)には側面図が表示される。折れ線・矩形
パスでも各区間を切断した位置に断面が出る。斜めの区間は近い側の軸に
寄せた近似になる(2D コンポーネントは物体のローカル軸 6 方向にしか
持てないため)。
"""
from __future__ import annotations

import math
from typing import List, NamedTuple, Optional, Sequence, Tuple

from ..document import (
    Bar3DCommand,
    CutLineCommand,
    PlanLineCommand,
    TARGET_FRONT_BACK,
    TARGET_LEFT_RIGHT,
)
from .slab import cross_cut_lines
from .spec import BarCount, SectionSize, SpecError, StirrupSpec

# 平面位置(幅方向オフセット)の重複をまとめる丸め (mm)
_OFFSET_ROUND = 2

# フック(曲げ加工)のパラメータ。材種 SD295A を仮定。
# 内法直径 3d(D16 以下)/4d(D19 以上) → 内法半径 1.5d/2d。
# 鉄筋中心の曲げ半径 = 内法半径 + 径/2。
_INNER_RADIUS_SMALL = 1.5   # ×d, D16 以下
_INNER_RADIUS_LARGE = 2.0   # ×d, D19 以上
_LARGE_BAR_THRESHOLD = 16.0  # mm, これを超える径は大径扱い
# 余長 (標準図): 180° フック = 4d、135° フック = 6d。
_TAIL_180 = 4.0  # ×d
_TAIL_135 = 6.0  # ×d
# 円弧の折れ線近似の分割数。
_ARC_SEGMENTS = 6

# (s, z) 平面の点 (s = 断面幅方向オフセット, z = 天端基準の高さ)。
_PlanarPoint = Tuple[float, float]
# 3D フック点 (a = 軸方向オフセット, s = 幅方向オフセット, z = 天端基準の高さ)。
# フックを鉛直軸まわりに回して幅方向へ縮めた結果、断面(s, z)からはみ出す
# 分を軸方向 a へ逃がす(= 斜めに施工したフックの 3D 表現)。
_HookPoint = Tuple[float, float, float]


class _HookContext(NamedTuple):
    """フックが巻き付く主筋の情報(幅方向の縮小・上下フック位置合わせ用)。

    ``top_dia`` / ``bottom_dia`` は上端/下端主筋の呼び径(``None`` なら主筋
    無し)。``z_main_top`` / ``z_main_bottom`` は上端/下端主筋の中心 Z
    (天端基準、``None`` なら主筋無し)。縦筋の 180° フックは一番高い/低い
    点がこの主筋中心に一致するよう位置を合わせる。
    """

    top_dia: Optional[float]
    bottom_dia: Optional[float]
    z_main_top: Optional[float]
    z_main_bottom: Optional[float]


def _tilt_cos(main_dia: Optional[float], stirrup_dia: float, radius: float) -> float:
    """フックを鉛直軸まわりに傾ける回転角の余弦を返す。

    フックの曲げ(中心曲げ半径 ``radius``)は最小曲げ半径の制約で主筋へ
    密着できるほど小さくできない(例: D10 のフックは leg 間隔 2×20=40mm)。
    現実にはフックを軸方向へ斜めに倒し、断面へ投影した立ち上がり幅を主筋の
    見付け幅 ``主筋径 + せん断補強筋径`` に収めて施工する。断面投影幅が
    この見付け幅に一致する傾き角 θ の cosθ を返す(既に収まっていれば 1.0
    =傾けない)。主筋が無ければ傾けない。
    """
    if main_dia is None:
        return 1.0
    return min(1.0, (main_dia + stirrup_dia) / (2.0 * radius))


def _swing_hook(
    points: List[_PlanarPoint], pivot_s: float, cos_theta: float
) -> List[_HookPoint]:
    """(s, z) フックを bend start(``pivot_s``)を通る鉛直軸まわりに回す。

    幅方向 (s) の投影を ``cos_theta`` 倍に縮め、その分を軸方向 a へ逃がす
    (剛体回転なので鉄筋の長さ・曲げ半径・余長は保たれる)。戻り値は
    (a, s, z) の 3D 点列。``cos_theta`` が 1 以上なら傾けず a=0。
    """
    if cos_theta >= 1.0:
        return [(0.0, s, z) for s, z in points]
    sin_theta = math.sqrt(max(0.0, 1.0 - cos_theta * cos_theta))
    return [
        ((s - pivot_s) * sin_theta, pivot_s + (s - pivot_s) * cos_theta, z)
        for s, z in points
    ]


def _bend_radius(diameter: float) -> float:
    """鉄筋中心の曲げ半径を返す(内法半径 + 径/2)。"""
    factor = (
        _INNER_RADIUS_SMALL
        if diameter <= _LARGE_BAR_THRESHOLD
        else _INNER_RADIUS_LARGE
    )
    return factor * diameter + diameter / 2.0


def _hook_points(
    start: _PlanarPoint,
    approach: _PlanarPoint,
    turn_sign: float,
    turn_angle: float,
    radius: float,
    tail_len: float,
) -> List[_PlanarPoint]:
    """(s, z) 平面でフック中心線を折れ線点列として返す。

    ``start``(曲げ開始点)へ ``approach`` 方向で入り、``turn_sign``
    (+1=反時計回り / -1=時計回り)に ``turn_angle`` だけ曲げ、余長
    ``tail_len`` の直線で終わる。円弧は ``_ARC_SEGMENTS`` 分割で近似する。
    """
    ax, ay = approach
    # 曲げ中心は進行方向に直交する向き(turn_sign 側)へ半径分ずれる。
    center = (start[0] - ay * turn_sign * radius, start[1] + ax * turn_sign * radius)
    vx = start[0] - center[0]
    vy = start[1] - center[1]
    points: List[_PlanarPoint] = [start]
    for i in range(1, _ARC_SEGMENTS + 1):
        angle = turn_sign * turn_angle * i / _ARC_SEGMENTS
        cos_a = math.cos(angle)
        sin_a = math.sin(angle)
        points.append(
            (
                center[0] + vx * cos_a - vy * sin_a,
                center[1] + vx * sin_a + vy * cos_a,
            )
        )
    # 余長: 進行方向を turn_sign*turn_angle だけ回した向きへ直進する。
    end_angle = turn_sign * turn_angle
    cos_e = math.cos(end_angle)
    sin_e = math.sin(end_angle)
    tail_dir = (ax * cos_e - ay * sin_e, ax * sin_e + ay * cos_e)
    end = points[-1]
    points.append((end[0] + tail_dir[0] * tail_len, end[1] + tail_dir[1] * tail_len))
    return points


def _vertical_leg(
    s: float,
    z_top: float,
    z_bottom: float,
    diameter: float,
    hooks: _HookContext,
) -> List[_HookPoint]:
    """中央縦筋(上下端 180° フック付き)の 1 本の開いた折れ線を返す。

    フックの一番高い/低い点が上端/下端主筋の中心 Z に一致するよう bend
    start を移動し(主筋が無ければ ``z_top`` / ``z_bottom`` のまま)、各
    フックを主筋の見付け幅へ傾けて幅方向へ縮める。戻り値は (a, s, z)。
    """
    radius = _bend_radius(diameter)
    tail = _TAIL_180 * diameter
    pi = math.pi
    # フック頂点 = bend start ± radius。頂点を主筋中心に合わせて bend start
    # を求める(主筋が無ければ従来どおりせん断補強筋の上下端に置く)。
    z_top_bend = (
        hooks.z_main_top - radius if hooks.z_main_top is not None else z_top
    )
    z_bottom_bend = (
        hooks.z_main_bottom + radius
        if hooks.z_main_bottom is not None
        else z_bottom
    )
    top = _hook_points((s, z_top_bend), (0.0, 1.0), 1.0, pi, radius, tail)
    bottom = _hook_points((s, z_bottom_bend), (0.0, -1.0), 1.0, pi, radius, tail)
    top_swung = _swing_hook(top, s, _tilt_cos(hooks.top_dia, diameter, radius))
    bottom_swung = _swing_hook(
        bottom, s, _tilt_cos(hooks.bottom_dia, diameter, radius)
    )
    # 上端フックを逆順にして脚を下り、そのまま下端フックへ続ける。
    return list(reversed(top_swung)) + bottom_swung


def _hoop_hooks(
    half_width: float, z_top: float, diameter: float, hooks: _HookContext
) -> List[List[_HookPoint]]:
    """四角あばら筋の上端両隅に付す 135° フック(余長は断面内側へ)。

    両隅のフックは上端主筋を巻くため、上端主筋の見付け幅へ傾けて幅方向へ
    縮める。戻り値は (a, s, z) の点列 2 本。
    """
    radius = _bend_radius(diameter)
    tail = _TAIL_135 * diameter
    angle = math.radians(135.0)
    cos_theta = _tilt_cos(hooks.top_dia, diameter, radius)
    left = _hook_points((-half_width, z_top), (0.0, 1.0), -1.0, angle, radius, tail)
    right = _hook_points((half_width, z_top), (0.0, 1.0), 1.0, angle, radius, tail)
    return [
        _swing_hook(left, -half_width, cos_theta),
        _swing_hook(right, half_width, cos_theta),
    ]


def _stirrup_planar_shapes(
    stirrup: StirrupSpec,
    half_width: float,
    z_top: float,
    z_bottom: float,
    hooks: _HookContext,
) -> Tuple[List[List[_HookPoint]], List[List[_HookPoint]]]:
    """せん断補強筋形状を (閉ループ, 開いた線) で返す。点は (a, s, z)。

    脚数に応じて縦筋(180° フック)・四角あばら筋(135° フック)・その
    組み合わせを組み立てる。閉ループは 3D で閉じたポリゴン、断面では矩形
    として描く。開いた線はフックや縦筋。矩形本体は断面内(a=0)、フックは
    主筋の見付け幅へ傾けた分だけ軸方向 a を持つ。
    """
    closed: List[List[_HookPoint]] = []
    open_polys: List[List[_HookPoint]] = []
    diameter = stirrup.diameter
    if stirrup.legs == 1:
        open_polys.append(_vertical_leg(0.0, z_top, z_bottom, diameter, hooks))
    else:
        closed.append(
            [
                (0.0, -half_width, z_top),
                (0.0, half_width, z_top),
                (0.0, half_width, z_bottom),
                (0.0, -half_width, z_bottom),
            ]
        )
        open_polys.extend(_hoop_hooks(half_width, z_top, diameter, hooks))
        if stirrup.legs == 3:
            open_polys.append(
                _vertical_leg(0.0, z_top, z_bottom, diameter, hooks)
            )
    return closed, open_polys


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


def _segment_cut_lines(
    segment: _Segment,
    main_bars: List[Tuple[float, float, float]],
    stirrup: Optional[StirrupSpec],
    half_width: float,
    z_stirrup_top: float,
    z_stirrup_bottom: float,
    mark_scale: float,
    hooks: _HookContext,
) -> List[CutLineCommand]:
    """1 区間の断面 2D コンポーネント(横断面・縦断面)を組み立てる。

    区間ごとに実位置へ生成する。区間が X 軸寄りなら横断面(梁を横断する
    切断: 主筋=×・せん断補強筋=矩形)を左右の断面(left_right)に、縦断面
    (梁に沿う切断の側面図: 主筋=水平線・せん断補強筋=等ピッチの縦線)を
    前後の断面(front_back)に置く。Y 軸寄りなら逆。VW の断面ビューポートは
    3D の切断面と物体の交差から表示コンポーネントを決めるため、横断/縦断を
    実位置に用意することで、梁を横断した切断には横断面、梁に沿った切断
    (梁幅内)には側面図が表示される。斜めの区間は近い側の軸に寄せた近似。
    """
    commands: List[CutLineCommand] = []
    x_dominant = abs(segment.axis[0]) >= abs(segment.axis[1])
    cross_target = TARGET_LEFT_RIGHT if x_dominant else TARGET_FRONT_BACK
    length_target = TARGET_FRONT_BACK if x_dominant else TARGET_LEFT_RIGHT
    # 横断面の紙面 u 軸 = 軸と直交する平面軸 / 縦断面の紙面 u 軸 = 軸方向の平面軸
    cross_axis = 1 if x_dominant else 0
    length_axis = 0 if x_dominant else 1
    mid = segment.point_at(segment.length / 2.0, 0.0)
    center_u = mid[cross_axis]
    lateral_sign = segment.lateral[cross_axis]
    z_top_abs = segment.z_top

    def to_cut(points: List[_HookPoint], closed: bool) -> None:
        """(a, s, z) 折れ線を横断面の cut_line 群として commands へ足す。

        断面 2D コンポーネントは紙面(s, z)への投影なので軸方向 a は捨てる
        (フックの傾きは断面では幅方向の縮小として現れる)。
        """
        mapped = [
            (center_u + s * lateral_sign, z_top_abs + z) for _a, s, z in points
        ]
        if closed:
            mapped.append(mapped[0])
        for start, end in zip(mapped, mapped[1:]):
            commands.append(
                {
                    'target': cross_target,
                    'start': [start[0], start[1]],
                    'end': [end[0], end[1]],
                }
            )

    # 横断面: せん断補強筋(四角あばら筋 = 矩形、縦筋、フック)
    if stirrup is not None:
        closed_shapes, open_shapes = _stirrup_planar_shapes(
            stirrup, half_width, z_stirrup_top, z_stirrup_bottom, hooks
        )
        for shape in closed_shapes:
            to_cut(shape, closed=True)
        for shape in open_shapes:
            to_cut(shape, closed=False)
    # 横断面: 主筋の × 記号
    for offset, z, dia in main_bars:
        u = center_u + offset * lateral_sign
        commands.extend(
            cross_cut_lines(cross_target, u, z_top_abs + z, dia * mark_scale)
        )

    # 縦断面(側面図): 主筋の水平線(上下端それぞれ 1 本、区間の全長)
    a1 = segment.start[length_axis]
    a2 = segment.end[length_axis]
    u_min, u_max = min(a1, a2), max(a1, a2)
    seen_z = set()
    for _offset, z, _dia in main_bars:
        key = round(z, _OFFSET_ROUND)
        if key in seen_z:
            continue
        seen_z.add(key)
        commands.append(
            {
                'target': length_target,
                'start': [u_min, z_top_abs + z],
                'end': [u_max, z_top_abs + z],
            }
        )
    # 縦断面(側面図): せん断補強筋の縦線(等ピッチ)
    if stirrup is not None:
        axis_sign = segment.axis[length_axis]
        for along in _stirrup_positions(segment.length, stirrup.pitch):
            u = segment.start[length_axis] + along * axis_sign
            commands.append(
                {
                    'target': length_target,
                    'start': [u, z_top_abs + z_stirrup_bottom],
                    'end': [u, z_top_abs + z_stirrup_top],
                }
            )
    return commands


def build_beam_commands(
    path: Sequence[Sequence[float]],
    *,
    section: SectionSize,
    top: Optional[BarCount],
    bottom: Optional[BarCount],
    stirrup: Optional[StirrupSpec],
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

    # フックが巻き付く主筋の情報(幅方向の縮小・上下フック位置合わせ用)。
    hooks = _HookContext(
        top_dia=top.diameter if top is not None else None,
        bottom_dia=bottom.diameter if bottom is not None else None,
        z_main_top=(
            -cover - stirrup_dia - top.diameter / 2.0
            if top is not None
            else None
        ),
        z_main_bottom=(
            -section.depth + cover + stirrup_dia + bottom.diameter / 2.0
            if bottom is not None
            else None
        ),
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
                        'start': [start[0], start[1]],
                        'end': [end[0], end[1]],
                    }
                )
            # 3D: 主筋は上下端それぞれ実位置に描く
            start = segment.point_at(0.0, offset)
            end = segment.point_at(segment.length, offset)
            bars_3d.append(
                {
                    'vertices': [
                        [start[0], start[1], segment.z_top + z],
                        [end[0], end[1], segment.z_top + z],
                    ],
                    'closed': False,
                }
            )
        # 平面 + 3D: せん断補強筋(脚数に応じた形状・フック)
        if stirrup is not None:
            closed_shapes, open_shapes = _stirrup_planar_shapes(
                stirrup, half_width, z_stirrup_top, z_stirrup_bottom, hooks
            )
            for along in _stirrup_positions(segment.length, stirrup.pitch):
                # 平面: 四角あばら筋(脚数 2/3)は幅方向の線。縦筋 1 本のみ
                # (脚数 1)は平面では点になるため線を描かない。
                if stirrup.legs != 1:
                    left = segment.point_at(along, -half_width)
                    right = segment.point_at(along, half_width)
                    plan_lines.append(
                        {
                            'start': [left[0], left[1]],
                            'end': [right[0], right[1]],
                        }
                    )
                # 3D: (a, s, z) 形状を区間の実位置(断面平面)へ写像する。
                # a は軸方向オフセット(フックの傾き)なので along に足す。
                for poly, is_closed in (
                    [(shape, True) for shape in closed_shapes]
                    + [(shape, False) for shape in open_shapes]
                ):
                    bars_3d.append(
                        {
                            'vertices': [
                                [
                                    *segment.point_at(along + a, s),
                                    segment.z_top + z,
                                ]
                                for a, s, z in poly
                            ],
                            'closed': is_closed,
                        }
                    )
        # 断面 2D コンポーネント: 区間ごとに生成する。折れ線・矩形パスでも
        # 各区間を切断した位置に断面が出るよう、区間の向きに応じた target へ
        # 割り当てる(2D コンポーネントはローカル軸 6 方向にしか持てないため、
        # 各区間は近い軸の表現に寄せた近似)。
        cut_lines.extend(
            _segment_cut_lines(
                segment,
                main_bars,
                stirrup,
                half_width,
                z_stirrup_top,
                z_stirrup_bottom,
                mark_scale,
                hooks,
            )
        )

    return plan_lines, cut_lines, bars_3d
