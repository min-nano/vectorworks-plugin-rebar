"""フェーズ2: VectorWorks 描画(スラブ・壁の餅網状配筋の断面)。vs だけに依存する。

命令セットを検証(``validate_document``)してから vs API で描画する。
配筋の知識(呼び径・記号の意味・かぶり等)は持たず、命令セットの図形を
そのまま描く。すべての図形は PIO 本体の描画クラス(``vs.GetClass(pio)``)に
割り当てる。

描画:

1. 線(lines) — 紙面平行方向の鉄筋。かぶり分オフセットした 2D 直線。
2. 断面記号 — 記号 1 個分の断面プロファイル(原点中心)を、各記号位置
   (``mark_centers``)へ平行移動して 2D の線・円として描く。

すべて 2D 注釈として描く。3D・断面 2D コンポーネントは使わない。
"""
from __future__ import annotations

from typing import Any, Dict, List

import vs

from ..document import (
    KIND_CIRCLE,
    KIND_LINE,
    LineCommand,
    Profile,
    validate_document,
)
from .draw import draw_circle_2d, draw_line_2d

__all__ = ['execute_document']


def _pio_class(pio_handle: Any) -> str:
    """PIO 本体の描画クラス名を返す。取得できない場合は空文字。"""
    try:
        name = vs.GetClass(pio_handle)
    except Exception:
        return ''
    return name if isinstance(name, str) else ''


def _execute_lines(commands: List[LineCommand], class_name: str) -> int:
    """lines(紙面平行方向の鉄筋)を 2D の直線として描く。"""
    for command in commands:
        draw_line_2d(command['start'], command['end'], class_name)
    return len(commands)


def _execute_mark_at(
    profiles: List[Profile], center: List[float], class_name: str
) -> None:
    """記号の断面プロファイル(原点中心)を ``center`` へ平行移動して描く。"""
    cx, cy = center[0], center[1]
    for profile in profiles:
        if profile['kind'] == KIND_LINE:
            start, end = profile['start'], profile['end']
            draw_line_2d(
                [start[0] + cx, start[1] + cy],
                [end[0] + cx, end[1] + cy],
                class_name,
            )
        elif profile['kind'] == KIND_CIRCLE:
            c = profile['center']
            draw_circle_2d(
                [c[0] + cx, c[1] + cy],
                profile['radius'],
                profile['filled'],
                class_name,
            )


def _execute_marks(
    profiles: List[Profile], centers: List[List[float]], class_name: str
) -> int:
    """断面記号を各記号位置(``mark_centers``)へ描く。描いた記号の数を返す。"""
    for center in centers:
        _execute_mark_at(profiles, center, class_name)
    return len(centers)


def execute_document(document: Any, pio_handle: Any) -> Dict[str, int]:
    """命令セットを検証してから描画し、実行数を返す。"""
    validated = validate_document(document)
    class_name = _pio_class(pio_handle)

    line_count = _execute_lines(validated['lines'], class_name)
    mark_count = _execute_marks(
        validated['symbol_profiles'], validated['mark_centers'], class_name
    )
    return {'lines': line_count, 'marks': mark_count}
