"""フェーズ2: VectorWorks 描画。vs だけに依存する。

命令セットを検証(``validate_document``)してから vs API で描画する。
配筋の知識(ピッチ・かぶり等)は持たず、命令セットの図形をそのまま描く。

すべての図形は **PIO 本体の描画クラス**(``vs.GetClass(pio)``)に割り当て、
描画属性を by-class にする(クラス指定は PIO を扱う側=PIO 本体への
クラス割り当てで管理する)。

描画順:

1. 3D 鉄筋(bars_3d) — 3D ビュー用の 3D ポリゴン。平面+3D の両方を
   持つことで PIO はハイブリッドオブジェクトになる。
2. 平面線(plan_lines) — グループへまとめ、Top/Plan コンポーネント
   (10)に設定する。断面コンポーネントのグループも PIO の 2D
   プロファイルに残るため、Top/Plan を明示定義しないと断面線が平面
   ビューにも漏れて表示される。Top/Plan を平面線グループに固定する
   ことで平面ビューには平面線だけが表示される。
3. 断面線(cut_lines) — target ごとにグループへまとめ、PIO の 2D
   コンポーネント(前後の断面=6・左右の断面=9)に設定する。命令が無い
   target は NULL を設定して前回リセットの残骸を消す。
   ``Set2DComponentGroup`` が使えない環境では作ったグループを削除して
   平面ビューを汚さない。
"""
from __future__ import annotations

from typing import Any, Dict, List

import vs

from ..document import (
    CUT_TARGETS,
    CutLineCommand,
    PlanLineCommand,
    validate_document,
)
from .component import (
    COMPONENT_TOP_PLAN,
    TARGET_COMPONENTS,
    set_component_group,
)
from .draw import draw_line_2d, draw_poly_3d

__all__ = ['execute_document']


def _pio_class(pio_handle: Any) -> str:
    """PIO 本体の描画クラス名を返す。取得できない場合は空文字。"""
    try:
        name = vs.GetClass(pio_handle)
    except Exception:
        return ''
    return name if isinstance(name, str) else ''


def _execute_plan_lines(
    pio_handle: Any, commands: List[PlanLineCommand], class_name: str
) -> int:
    """plan_lines を Top/Plan コンポーネント(10)のグループとして設定する。

    Top/Plan を平面線グループに明示定義することで、断面コンポーネント
    (6/9)のグループが平面ビューに漏れて表示されるのを防ぐ。命令が無い
    場合は NULL を設定して前回リセットの残骸を消す。

    ``Set2DComponentGroup`` が使えない環境(VW 2018 以前)では 2D
    コンポーネントの仕組みが無く、作ったグループがそのまま平面ビューの
    2D 表現になるためグループは削除しない(断面線側はこの環境では削除
    されるため、平面ビューには平面線だけが残る)。
    """
    if not commands:
        set_component_group(pio_handle, None, COMPONENT_TOP_PLAN)
        return 0
    vs.BeginGroup()
    for command in commands:
        draw_line_2d(command['start'], command['end'], class_name)
    vs.EndGroup()
    group = vs.LNewObj()
    set_component_group(pio_handle, group, COMPONENT_TOP_PLAN)
    return len(commands)


def _execute_cut_lines(
    pio_handle: Any, commands: List[CutLineCommand], class_name: str
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
            draw_line_2d(line['start'], line['end'], class_name)
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
    class_name = _pio_class(pio_handle)

    counts = {'plan_lines': 0, 'cut_lines': 0, 'bars_3d': 0}
    for bar in validated['bars_3d']:
        draw_poly_3d(bar['vertices'], bar['closed'], class_name)
        counts['bars_3d'] += 1
    counts['plan_lines'] = _execute_plan_lines(
        pio_handle, validated['plan_lines'], class_name
    )
    counts['cut_lines'] = _execute_cut_lines(
        pio_handle, validated['cut_lines'], class_name
    )
    return counts
