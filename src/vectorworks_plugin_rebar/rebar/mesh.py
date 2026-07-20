"""スラブ・壁の餅網状配筋(断面)の計算。vs に依存しない。

ユーザーが引いた 1 本の直線(スラブ・壁の面)から、かぶり分オフセットした
位置に、紙面平行方向の鉄筋を **線**、紙面直交方向の鉄筋を **断面記号** で
並べる。座標はすべて PIO のローカル座標(2D 線形図形のローカル系)。

- オフセット: 面線の法線方向へ ``cover + 平行筋の径/2`` だけずらした線を
  紙面平行方向の鉄筋(線)とする(面から平行筋の芯までの距離)。オフセット
  する側は面線の進行方向 (start→end) の左側を既定とし、``flip`` で反転する。
- 断面記号: オフセット線上に、ピッチ間隔で紙面直交方向の鉄筋の端部記号を
  並べる。最初の記号は始端から ``ピッチ/2``、以降は等ピッチ。線長がピッチ
  未満なら中央に 1 本。記号(断面プロファイル)はオフセット線上に中心を置く
  (餅網の 2 方向を同一オフセット線上に模式化する。平行筋と直交筋の層の
  微小な深さ差は将来の拡張とする)。

**オフセットの向き(左右)・記号の見え方は VectorWorks 上で最終確認する**
(描画フェーズは VW 上で検証する方針)。反転は ``flip`` パラメータで対応する。
"""
from __future__ import annotations

import math
from typing import List, Sequence, Tuple

from ..document import LineCommand, Profile
from .spec import NominalPitch, SpecError
from .symbol import build_symbol_profiles

# 線長・座標の比較に使う許容値 (mm)。
_EPS = 1e-6

Point2D = Tuple[float, float]


def _unit(dx: float, dy: float) -> Tuple[Point2D, float]:
    """(dx, dy) の単位ベクトルと長さを返す。長さ 0 は (0, 0), 0。"""
    length = math.hypot(dx, dy)
    if length < _EPS:
        return (0.0, 0.0), 0.0
    return (dx / length, dy / length), length


def _mark_offsets(length: float, pitch: float) -> List[float]:
    """線長 ``length`` に沿って記号を置く位置(始端からの距離)を返す。

    最初は始端から ``ピッチ/2``、以降は等ピッチ。線長がピッチ未満なら中央に
    1 本(始端・終端に寄りすぎないよう対称に置く)。
    """
    if length < _EPS or pitch <= 0:
        return []
    if length < pitch:
        return [length / 2.0]
    offsets: List[float] = []
    s = pitch / 2.0
    while s < length - _EPS:
        offsets.append(s)
        s += pitch
    return offsets


def build_mesh_commands(
    line: Sequence[Sequence[float]],
    *,
    parallel_nominal: int,
    perp: NominalPitch,
    cover: float,
    mark_scale: float,
    flip: bool,
) -> Tuple[List[LineCommand], List[Profile], List[List[float]]]:
    """餅網配筋(断面)の命令(線・記号プロファイル・記号位置)を組み立てる。

    line は面線の 2 端点 [[x1, y1], [x2, y2]]。parallel_nominal は紙面平行
    方向の鉄筋(線)の呼び径、perp は紙面直交方向の鉄筋(断面記号)の呼び径@
    ピッチ。cover はかぶり、mark_scale は記号の大きさ倍率、flip はオフセット
    方向の反転。
    """
    if len(line) < 2:
        raise SpecError('面線には 2 点が必要です')
    p0 = (float(line[0][0]), float(line[0][1]))
    p1 = (float(line[1][0]), float(line[1][1]))
    (dx, dy), length = _unit(p1[0] - p0[0], p1[1] - p0[1])
    if length < _EPS:
        raise SpecError('面線の長さが 0 です。始点と終点を離してください')

    # 法線(進行方向の左側 = 反時計回りに 90°)。flip で反対側へ。
    nx, ny = -dy, dx
    if flip:
        nx, ny = -nx, -ny

    offset = cover + parallel_nominal / 2.0
    a0 = [p0[0] + nx * offset, p0[1] + ny * offset]
    a1 = [p1[0] + nx * offset, p1[1] + ny * offset]
    lines: List[LineCommand] = [{'start': a0, 'end': a1}]

    profiles = build_symbol_profiles(perp.nominal, perp.nominal * mark_scale)

    mark_centers: List[List[float]] = []
    for s in _mark_offsets(length, perp.pitch):
        mark_centers.append([a0[0] + dx * s, a0[1] + dy * s])

    return lines, profiles, mark_centers
