"""断面の表示記号(●/× 等)を線画のプロファイルへ分解する。vs に依存しない。

配筋標準図(KSE 2008)「鉄筋の表示記号」に従い、呼び径ごとに断面の表示
記号を **線画のプロファイル**(線=line、円=circle)へ分解する。プロファイルは
原点(0, 0)中心に組み立て、描画フェーズが各記号位置(``mark_centers``)へ
平行移動して 2D の線・円として描く。姉妹プロジェクト「鉄筋」
(vectorworks-plugin-rebar-single)の同名モジュールと同じ記号定義を踏襲する:

    呼び径  記号
    D10     ●   小さい塗り丸
    D13     ×   斜め十字(線 2 本)
    D16     ⊘   円 + 斜線(線 1 本)
    D19     ●   大きい塗り丸(呼び径で自然に大きくなる)
    D22     ○   円(輪郭)
    D25     ⊙   円 + 中心の塗り丸
    D29     ⊗   円 + 内側の ×(線 2 本)
    D32     ◎   二重円
    D35     ⊕   円 + 十字(線 2 本)
    D38     ●⊕ 塗り丸 + 十字(線 2 本)
    D41     ⊗   円 + 内側の ×

記号の大きさは ``呼び径 × MarkScale``(= ``size``)を外径とする。輪郭の円
(○ 等)は ``filled=false``、塗り丸(●)は ``filled=true``。表にない呼び径は
最も近い標準呼び径の記号で近似する。
"""
from __future__ import annotations

import math
from typing import Callable, Dict, List

from ..document import KIND_CIRCLE, KIND_LINE, Profile

# 45° 方向の単位長(円周上の斜め点の座標係数)。
_DIAG = math.sqrt(0.5)


def _line(x1: float, y1: float, x2: float, y2: float) -> Profile:
    return {'kind': KIND_LINE, 'start': [x1, y1], 'end': [x2, y2]}


def _circle(radius: float, filled: bool) -> Profile:
    return {
        'kind': KIND_CIRCLE,
        'center': [0.0, 0.0],
        'radius': radius,
        'filled': filled,
    }


def _dot(r: float) -> List[Profile]:
    """● 塗り丸。"""
    return [_circle(r, True)]


def _open_circle(r: float) -> List[Profile]:
    """○ 円(輪郭)。"""
    return [_circle(r, False)]


def _cross(r: float) -> List[Profile]:
    """× 斜め十字(記号の外形いっぱいに広がる)。"""
    return [
        _line(-r, -r, r, r),
        _line(-r, r, r, -r),
    ]


def _inner_cross(r: float) -> List[Profile]:
    """円の内側に収まる斜め十字(円周上まで)。"""
    d = r * _DIAG
    return [
        _line(-d, -d, d, d),
        _line(-d, d, d, -d),
    ]


def _plus(r: float) -> List[Profile]:
    """十字線(縦横)。円周をわずかに越えて伸びる。"""
    e = r * 1.2
    return [
        _line(-e, 0.0, e, 0.0),
        _line(0.0, -e, 0.0, e),
    ]


def _circle_slash(r: float) -> List[Profile]:
    """⊘ 円 + 斜線 1 本。"""
    d = r * _DIAG
    return [_circle(r, False), _line(-d, -d, d, d)]


def _circle_dot(r: float) -> List[Profile]:
    """⊙ 円 + 中心の塗り丸。"""
    return [_circle(r, False), _circle(r * 0.22, True)]


def _circle_cross(r: float) -> List[Profile]:
    """⊗ 円 + 内側の ×。"""
    return [_circle(r, False), *_inner_cross(r)]


def _double_circle(r: float) -> List[Profile]:
    """◎ 二重円。"""
    return [_circle(r, False), _circle(r * 0.5, False)]


def _circle_plus(r: float) -> List[Profile]:
    """⊕ 円 + 十字。"""
    return [_circle(r, False), *_plus(r)]


def _dot_plus(r: float) -> List[Profile]:
    """●⊕ 塗り丸 + 十字。"""
    return [_circle(r * 0.6, True), *_plus(r)]


# 呼び径 -> 記号の組み立て関数(引数は記号の半径 r = size/2)。
_SYMBOL_BUILDERS: Dict[int, Callable[[float], List[Profile]]] = {
    10: _dot,
    13: _cross,
    16: _circle_slash,
    19: _dot,
    22: _open_circle,
    25: _circle_dot,
    29: _circle_cross,
    32: _double_circle,
    35: _circle_plus,
    38: _dot_plus,
    41: _circle_cross,
}


def _builder_for(nominal: int) -> Callable[[float], List[Profile]]:
    """呼び径に対応する記号組み立て関数を返す(表外は最も近い標準径)。"""
    if nominal in _SYMBOL_BUILDERS:
        return _SYMBOL_BUILDERS[nominal]
    nearest = min(_SYMBOL_BUILDERS, key=lambda d: (abs(d - nominal), d))
    return _SYMBOL_BUILDERS[nearest]


def build_symbol_profiles(nominal: int, size: float) -> List[Profile]:
    """呼び径 ``nominal`` の断面表示記号を外径 ``size`` の線画プロファイルにする。

    プロファイルは原点(0, 0)を基準にした線・円のリスト。``size`` は記号の
    外径(``呼び径 × MarkScale``)で、半径 ``r = size/2``。
    """
    return _builder_for(nominal)(size / 2.0)
