"""2D コンポーネントの設定。vs だけに依存する。

断面ビューポートの「2D コンポーネントを表示」で表示される断面表現を、
PIO の 2D コンポーネントグループとして設定する。VectorWorks 2019 以降の
``Set2DComponentGroup`` を使う(定数は公式リファレンスの
Table - 2D components に基づく):

    0=未設定, 1=上面, 2=下面, 3=上下の断面, 4=前面, 5=背面,
    6=前後の断面, 7=左面, 8=右面, 9=左右の断面, 10=2D/平面

命令セットの target との対応:

- ``front_back`` → 前後の断面 (6)。紙面 u=ローカル X・v=ローカル Z。
- ``left_right`` → 左右の断面 (9)。紙面 u=ローカル Y・v=ローカル Z。

平面線は Top/Plan コンポーネント (10) として明示的に設定する。断面
コンポーネント (6/9) のグループも PIO の 2D プロファイルの一部として
残るため、Top/Plan を明示定義しないと断面表現が平面ビューにも漏れて
表示されてしまう。Top/Plan を平面線グループに固定することで、平面
ビューには平面線だけ、断面ビューポートには断面線だけが表示される。

紙面座標の符号(左右ビューの鏡像の扱い)は VectorWorks 上で最終確認する
(描画フェーズは VW 上で検証する方針)。
"""
from __future__ import annotations

from typing import Any, Optional

import vs

from ..document import TARGET_FRONT_BACK, TARGET_LEFT_RIGHT

# Set2DComponentGroup の component 定数 (VW 2019+)
COMPONENT_TOP_PLAN = 10
COMPONENT_FRONT_BACK_CUT = 6
COMPONENT_LEFT_RIGHT_CUT = 9

# SetTopPlan2DComp の component 定数: Top/Plan ビューにどのコンポーネントを
# 表示するか (0=Top, 1=Top and Bottom Cut)。断面コンポーネントが平面ビューに
# 出ないよう Top(0)に固定する。
TOP_PLAN_VIEW_TOP = 0

# ``Set2DComponentGroup`` が関数として存在しない/例外だったことを表す番兵。
# 戻り値が数値(SDK の ESetSpecialGroupErrors)や BOOLEAN の場合と区別する。
COMPONENT_SET_UNAVAILABLE = 'unavailable'

TARGET_COMPONENTS = {
    TARGET_FRONT_BACK: COMPONENT_FRONT_BACK_CUT,
    TARGET_LEFT_RIGHT: COMPONENT_LEFT_RIGHT_CUT,
}


def set_component_group(
    pio_handle: Any, group_handle: Optional[Any], component: int
) -> Any:
    """PIO の 2D コンポーネントグループを設定(置換)し、生の戻り値を返す。

    group_handle が None の場合は NULL ハンドルを渡して既存グループを
    削除する(前回リセットの断面表現が残らないようにする)。

    戻り値は ``vs.Set2DComponentGroup`` の生の値をそのまま返す。公式 VS
    ラッパーは BOOLEAN(成功=True)を返すとされるが、内部 SDK は
    ``ESetSpecialGroupErrors``(NoError=0, CannotSet_BadData,
    CannotSet_UserSpecified)を返すため、環境によっては整数が返る可能性が
    ある。成否判定は ``component_set_succeeded`` で行う。関数が無い環境
    (VW 2018 以前)や例外時は ``COMPONENT_SET_UNAVAILABLE`` を返す。
    """
    try:
        setter = vs.Set2DComponentGroup
    except AttributeError:
        return COMPONENT_SET_UNAVAILABLE
    handle = group_handle if group_handle is not None else vs.Handle(0)
    try:
        return setter(pio_handle, handle, component)
    except Exception:
        return COMPONENT_SET_UNAVAILABLE


def component_set_succeeded(result: Any) -> bool:
    """``set_component_group`` の戻り値から成否を判定する。

    ``bool`` は True を成功とみなす(公式 VS ラッパーの規約)。整数は SDK の
    ``ESetSpecialGroupErrors`` とみなし 0(NoError)だけを成功とする。
    ``COMPONENT_SET_UNAVAILABLE`` やその他は失敗とみなす。
    """
    if isinstance(result, bool):
        return result
    if isinstance(result, int):
        return result == 0
    return False


def set_custom_object_profile_group(
    pio_handle: Any, group_handle: Optional[Any]
) -> Any:
    """パス custom object の 2D プロファイル(Top/Plan に出る 2D)を固定する。

    リセットで描いた全図形が既定で PIO のプロファイル(= デザインレイヤの
    平面ビューに表示される 2D)になるため、断面線もそのまま平面ビューに
    漏れる(``Set2DComponentGroup`` が成功=True を返してもプロファイルから
    取り除かれない)。プロファイルを平面線グループに固定することで、平面
    ビューには平面線だけを表示する。

    ``SetCustomObjectProfileGroup`` が無い環境や例外時は
    ``COMPONENT_SET_UNAVAILABLE`` を返す。
    """
    try:
        setter = vs.SetCustomObjectProfileGroup
    except AttributeError:
        return COMPONENT_SET_UNAVAILABLE
    handle = group_handle if group_handle is not None else vs.Handle(0)
    try:
        return setter(pio_handle, handle)
    except Exception:
        return COMPONENT_SET_UNAVAILABLE


def set_top_plan_view_component(pio_handle: Any) -> Any:
    """Top/Plan ビューに表示するコンポーネントを Top(非断面)に固定する。

    ``vs.SetTopPlan2DComp(pio, 0)`` で Top/Plan ビューが断面コンポーネント
    (前後/左右の断面)を表示しないようにする。断面コンポーネントが平面
    ビューに漏れる問題への直接的な対策。関数が無い環境(VW 2018 以前)や
    例外時は ``COMPONENT_SET_UNAVAILABLE`` を返す。
    """
    try:
        setter = vs.SetTopPlan2DComp
    except AttributeError:
        return COMPONENT_SET_UNAVAILABLE
    try:
        return setter(pio_handle, TOP_PLAN_VIEW_TOP)
    except Exception:
        return COMPONENT_SET_UNAVAILABLE
