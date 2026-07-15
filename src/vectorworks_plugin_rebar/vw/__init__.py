"""フェーズ2: VectorWorks 描画。vs だけに依存する。

命令セットを検証(``validate_document``)してから vs API で描画する。
配筋の知識(ピッチ・かぶり等)は持たず、命令セットの図形をそのまま描く。

描画順:

1. 平面線(plan_lines) — PIO 本体(Top/Plan)の 2D 表現。
2. 3D 鉄筋(bars_3d) — 3D ビュー用の 3D ポリゴン。平面+3D の両方を
   持つことで PIO はハイブリッドオブジェクトになる。
3. 断面線(cut_lines) — target ごとにグループへまとめ、PIO の 2D
   コンポーネント(前後の断面=6・左右の断面=9)に設定する。命令が無い
   target は NULL を設定して前回リセットの残骸を消す。
   ``Set2DComponentGroup`` が使えない環境では作ったグループを削除して
   平面ビューを汚さない。
"""
from __future__ import annotations

from typing import Any, Dict, List

import vs

from ..document import CUT_TARGETS, CutLineCommand, validate_document
from .component import TARGET_COMPONENTS, set_component_group
from .draw import draw_line_2d, draw_poly_3d

__all__ = ['execute_document']


def _execute_cut_lines(
    pio_handle: Any, commands: List[CutLineCommand]
) -> int:
    """cut_lines を target ごとの 2D コンポーネントグループとして設定する。"""
    by_target: Dict[str, List[CutLineCommand]] = {
        target: [] for target in CUT_TARGETS
    }
    for command in commands:
        by_target[command['target']].append(command)

    count = 0
    for target, component in TARGET_COMPONENTS.items():
        lines = by_target[target]
        if not lines:
            # 前回リセットの断面表現が残らないよう空のコンポーネントは削除する
            set_component_group(pio_handle, None, component)
            continue
        vs.BeginGroup()
        for line in lines:
            draw_line_2d(line['start'], line['end'], line['class'])
        vs.EndGroup()
        group = vs.LNewObj()
        if set_component_group(pio_handle, group, component):
            count += len(lines)
        else:
            # 2D コンポーネントが使えない環境(VW 2018 以前)では平面
            # ビューにグループが残るため削除する
            vs.DelObject(group)
    return count


def execute_document(document: Any, pio_handle: Any) -> Dict[str, int]:
    """命令セットを検証してから描画し、実行数を返す。"""
    validated = validate_document(document)

    counts = {'plan_lines': 0, 'cut_lines': 0, 'bars_3d': 0}
    for plan_line in validated['plan_lines']:
        draw_line_2d(plan_line['start'], plan_line['end'], plan_line['class'])
        counts['plan_lines'] += 1
    for bar in validated['bars_3d']:
        draw_poly_3d(bar['vertices'], bar['closed'], bar['class'])
        counts['bars_3d'] += 1
    counts['cut_lines'] = _execute_cut_lines(pio_handle, validated['cut_lines'])
    return counts
