"""描画プリミティブ。vs だけに依存する。

命令セットの 2D 線(紙面平行方向の鉄筋)と 2D 円・線(断面記号)を vs API で
描画する。作図クラスは呼び出し側が渡す(すべて PIO 本体の描画クラス)。
描画属性はすべて by-class 属性に従わせる。

すべて 2D 注釈(ビューポート注釈または設計レイヤの 2D 図形)として描く。
3D・断面 2D コンポーネントは使わない(VectorWorks の作図特性との相性から
2D 注釈方式へ全面刷新した)。
"""
from __future__ import annotations

from typing import Any, Sequence

import vs

# 塗りパターン: 1=実塗り(前景色ベタ)、0=塗りなし。記号の ●/○ は意味が
# 塗り/輪郭で決まるため、クラス塗りに関わらず明示する。
SOLID_FILL_PATTERN = 1
NO_FILL_PATTERN = 0


def _null(handle: Any) -> bool:
    """ハンドルが NULL(生成失敗)かどうか。"""
    try:
        return handle == vs.Handle(0)
    except Exception:
        return handle is None


def set_class_with_attributes(handle: Any, class_name: str) -> None:
    """クラスを割り当て、描画属性をすべてクラス属性に従わせる。

    class_name が空(クラスを取得できない場合)はクラス割り当てを省くが、
    属性は by-class に設定する。``SetClass`` はクラスを割り当てるだけで各
    描画属性は by-instance の既定値のまま残るため、属性ごとの by-class 設定
    関数を個別に呼ぶ。
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
    """2D の線(紙面平行方向の鉄筋・記号の線)を描き、ハンドルを返す。"""
    vs.MoveTo((start[0], start[1]))
    vs.LineTo((end[0], end[1]))
    handle = vs.LNewObj()
    if not _null(handle):
        set_class_with_attributes(handle, class_name)
    return handle


def draw_circle_2d(
    center: Sequence[float], radius: float, filled: bool, class_name: str
) -> Any:
    """2D の円(記号の ○ ・●)を描き、ハンドルを返す。

    記号の意味に合わせ、``filled=True`` は実塗り(●)、``filled=False`` は
    塗りなしの輪郭(○)にする(クラス塗りに関わらず明示)。
    """
    cx, cy = center[0], center[1]
    vs.Oval((cx - radius, cy + radius), (cx + radius, cy - radius))
    handle = vs.LNewObj()
    if not _null(handle):
        set_class_with_attributes(handle, class_name)
        try:
            vs.SetFPat(handle, SOLID_FILL_PATTERN if filled else NO_FILL_PATTERN)
        except Exception:
            # 円オブジェクト自体は生成済み。塗りパターン設定は VectorWorks の
            # 環境差(関数の有無等)で失敗し得るが、記号の描画継続を優先し、
            # 非致命として無視する(塗り/輪郭はクラス属性に従う)。
            pass
    return handle
