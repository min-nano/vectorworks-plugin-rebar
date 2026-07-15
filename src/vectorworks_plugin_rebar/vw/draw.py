"""描画プリミティブ。vs だけに依存する。

命令セットの line / 3D ポリゴンを vs API で描画する。図形の描画属性
(線の太さ・色・線種等)はすべて by-class 属性に従わせ、ユーザーが
クラス側で線種・色を調整できるようにする(homeskz の規約と同じ)。
存在しないクラスは ``SetClass`` 時に VW が自動生成する。
"""
from __future__ import annotations

from typing import Any, Sequence

import vs


def set_class_with_attributes(handle: Any, class_name: str) -> None:
    """クラスを割り当て、描画属性をすべてクラス属性に従わせる。

    ``SetClass`` はクラスを割り当てるだけで各描画属性は by-instance の
    既定値のまま残るため、属性ごとの by-class 設定関数を個別に呼ぶ。
    """
    vs.SetClass(handle, class_name)
    vs.SetPenColorByClass(handle)
    vs.SetFillColorByClass(handle)
    vs.SetLWByClass(handle)
    vs.SetLSByClass(handle)
    vs.SetFPatByClass(handle)
    vs.SetMarkerByClass(handle)
    vs.SetOpacityByClass(handle)


def draw_line_2d(
    start: Sequence[float], end: Sequence[float], class_name: str
) -> Any:
    """2D の線を描き、ハンドルを返す。

    PIO リセット中に作られた 2D 図形は PIO 本体(Top/Plan)の内容になる。
    """
    vs.MoveTo((start[0], start[1]))
    vs.LineTo((end[0], end[1]))
    handle = vs.LNewObj()
    if handle != vs.Handle(0):
        set_class_with_attributes(handle, class_name)
    return handle


def draw_poly_3d(
    vertices: Sequence[Sequence[float]], closed: bool, class_name: str
) -> Any:
    """3D ポリゴン(鉄筋の 3D 表現)を描き、ハンドルを返す。

    ``OpenPoly``/``ClosePoly`` はスクリプトで作るポリゴンの開閉モードを
    切り替えるトグルのため、描画のたびに明示的に設定し、最後に既定の
    閉モードへ戻す。
    """
    if closed:
        vs.ClosePoly()
    else:
        vs.OpenPoly()
    coordinates = [c for vertex in vertices for c in vertex]
    vs.Poly3D(*coordinates)
    handle = vs.LNewObj()
    if handle != vs.Handle(0):
        set_class_with_attributes(handle, class_name)
    if not closed:
        vs.ClosePoly()
    return handle
