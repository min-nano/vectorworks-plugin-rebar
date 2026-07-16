"""描画プリミティブ。vs だけに依存する。

命令セットの line / 3D ポリゴンを vs API で描画する。図形の作図クラスは
**PIO 本体の描画クラス**(呼び出し側が ``vs.GetClass(pio)`` で取得して
渡す)に揃え、描画属性(線の太さ・色・線種等)はすべて by-class 属性に
従わせる。クラス指定は PIO を扱う側(= PIO 本体へのクラス割り当て)で
管理するため、このパッケージは固有のクラス名を持たない。
"""
from __future__ import annotations

from typing import Any, Sequence

import vs

# 画面平面(screen plane)の planar ref ID(vs のリファレンス: screen
# plane = 0)。2D コンポーネントのグループは画面平面のオブジェクトである
# 必要がある。層平面(layer plane)のままだと ``Set2DComponentGroup`` が
# 断面コンポーネントのコンテナへオブジェクトを移動できず、断面表現が
# デザインレイヤの平面ビュー(Top/Plan)に残って表示されてしまう。
SCREEN_PLANE_REF = 0


def set_screen_plane(handle: Any) -> None:
    """2D 図形を画面平面(screen plane)に置く。

    2D コンポーネント(Top/Plan・断面)のグループは画面平面のオブジェクト
    でないと ``Set2DComponentGroup`` が各コンポーネントのコンテナへ正しく
    移動できず、断面表現が平面ビューに漏れて表示される。``SetPlanarRef``
    が無い環境(VW 2018 以前)では 2D コンポーネントの仕組み自体が無いので
    何もしない(層平面の 2D 線がそのまま平面ビューの表現になる)。
    """
    try:
        setter = vs.SetPlanarRef
    except AttributeError:
        return
    setter(handle, SCREEN_PLANE_REF)


def set_class_with_attributes(handle: Any, class_name: str) -> None:
    """クラスを割り当て、描画属性をすべてクラス属性に従わせる。

    class_name が空(PIO のクラスを取得できない場合)はクラス割り当てを
    省くが、属性は by-class に設定する。``SetClass`` はクラスを割り当てる
    だけで各描画属性は by-instance の既定値のまま残るため、属性ごとの
    by-class 設定関数を個別に呼ぶ。
    """
    if class_name:
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

    PIO リセット中に作られた 2D 図形は PIO 本体の内容になる。2D
    コンポーネント(Top/Plan・断面)に振り分けられるよう画面平面
    (screen plane)に置く(``set_screen_plane`` 参照)。
    """
    vs.MoveTo((start[0], start[1]))
    vs.LineTo((end[0], end[1]))
    handle = vs.LNewObj()
    if handle != vs.Handle(0):
        set_screen_plane(handle)
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
