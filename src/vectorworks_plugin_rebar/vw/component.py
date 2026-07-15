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

紙面座標の符号(左右ビューの鏡像の扱い)は VectorWorks 上で最終確認する
(描画フェーズは VW 上で検証する方針)。
"""
from __future__ import annotations

from typing import Any, Optional

import vs

from ..document import TARGET_FRONT_BACK, TARGET_LEFT_RIGHT

# Set2DComponentGroup の component 定数 (VW 2019+)
COMPONENT_FRONT_BACK_CUT = 6
COMPONENT_LEFT_RIGHT_CUT = 9

TARGET_COMPONENTS = {
    TARGET_FRONT_BACK: COMPONENT_FRONT_BACK_CUT,
    TARGET_LEFT_RIGHT: COMPONENT_LEFT_RIGHT_CUT,
}


def set_component_group(
    pio_handle: Any, group_handle: Optional[Any], component: int
) -> bool:
    """PIO の 2D コンポーネントグループを設定(置換)する。

    group_handle が None の場合は NULL ハンドルを渡して既存グループを
    削除する(前回リセットの断面表現が残らないようにする)。
    ``Set2DComponentGroup`` が使えない環境(VW 2018 以前)では False を
    返す(呼び出し側がグループを削除して平面ビューの汚染を防ぐ)。
    """
    try:
        setter = vs.Set2DComponentGroup
    except AttributeError:
        return False
    handle = group_handle if group_handle is not None else vs.Handle(0)
    try:
        return bool(setter(pio_handle, handle, component))
    except Exception:
        return False
