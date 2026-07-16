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
    TARGET_COMPONENTS,
    component_set_succeeded,
    set_component_group,
    set_custom_object_profile_group,
    set_top_plan_view_component,
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
) -> tuple[int, Any]:
    """plan_lines をパスオブジェクトの 2D プロファイルに固定する。

    リセットで描いた全図形が既定で PIO のプロファイル(= 平面ビューに出る
    2D)になるため、断面線もそのまま平面ビューに漏れる。プロファイルを
    平面線グループに ``SetCustomObjectProfileGroup`` で固定することで、
    平面ビューには平面線だけを表示する。命令が無い場合は NULL を渡す。

    戻り値は (本数, SetCustomObjectProfileGroup の生の戻り値)。
    """
    if not commands:
        result = set_custom_object_profile_group(pio_handle, None)
        return 0, result
    vs.BeginGroup()
    for command in commands:
        draw_line_2d(command['start'], command['end'], class_name)
    vs.EndGroup()
    group = vs.LNewObj()
    result = set_custom_object_profile_group(pio_handle, group)
    return len(commands), result


def _execute_cut_lines(
    pio_handle: Any, commands: List[CutLineCommand], class_name: str
) -> tuple[int, Dict[str, Any]]:
    """cut_lines を target ごとの 2D コンポーネントグループとして設定する。

    戻り値は (本数, {target: Set2DComponentGroup の生の戻り値})。
    """
    by_target: Dict[str, List[CutLineCommand]] = {
        target: [] for target in CUT_TARGETS
    }
    for command in commands:
        by_target[command['target']].append(command)

    count = 0
    results: Dict[str, Any] = {}
    for target, component in TARGET_COMPONENTS.items():
        lines = by_target[target]
        if not lines:
            # 前回リセットの断面表現が残らないよう空のコンポーネントは削除する
            results[target] = set_component_group(pio_handle, None, component)
            continue
        vs.BeginGroup()
        for line in lines:
            draw_line_2d(line['start'], line['end'], class_name)
        vs.EndGroup()
        group = vs.LNewObj()
        result = set_component_group(pio_handle, group, component)
        results[target] = result
        if component_set_succeeded(result):
            count += len(lines)
        else:
            # 断面コンポーネントへ移動できなかった場合は、そのグループが
            # 平面ビュー(PIO 本体の 2D プロファイル)に残って断面表現が
            # 漏れるため削除する(VW 2018 以前や割り当て失敗時)。
            vs.DelObject(group)
    return count, results


def execute_document(document: Any, pio_handle: Any) -> Dict[str, Any]:
    """命令セットを検証してから描画し、実行数と診断情報を返す。

    診断情報 ``diagnostic`` には各 2D コンポーネント割り当ての生の戻り値を
    含める(平面ビューへの漏れを VW 上で切り分けるため、``run()`` が
    ステータスバーに表示する)。
    """
    validated = validate_document(document)
    class_name = _pio_class(pio_handle)

    bars = 0
    for bar in validated['bars_3d']:
        draw_poly_3d(bar['vertices'], bar['closed'], class_name)
        bars += 1
    # 断面コンポーネントを先に割り当ててから、プロファイルを平面線グループに
    # 固定する(プロファイル固定を最後にして平面ビューに平面線だけが残るよう
    # にする)。
    cut_count, cut_results = _execute_cut_lines(
        pio_handle, validated['cut_lines'], class_name
    )
    plan_count, profile_result = _execute_plan_lines(
        pio_handle, validated['plan_lines'], class_name
    )
    # Top/Plan ビューが断面コンポーネントを表示しないよう Top に固定する
    top_view_result = set_top_plan_view_component(pio_handle)
    return {
        'plan_lines': plan_count,
        'cut_lines': cut_count,
        'bars_3d': bars,
        'diagnostic': {
            'profile': profile_result,
            'top_plan_view': top_view_result,
            'cut': cut_results,
        },
    }
