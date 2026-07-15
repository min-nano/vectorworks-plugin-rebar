"""PIO コンテキストの読み取り。vs だけに依存する。

リセット中の PIO 自身の情報(``vs.GetCustomObjectInfo``)から、
パラメータ(レコードフィールド)と 3D パス頂点を読み取り、
配筋計算フェーズ(``rebar.build_document``)へ渡すプレーンな
dict(JSON 直列化可能)を組み立てる。

パラメータ(レコードフィールド)名は VectorWorks 側で登録する
プラグインのパラメータ名と一致させる必要がある(README の登録手順
参照)。名前はこのモジュール冒頭の定数に集約している。
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

import vs

from ..rebar import MODE_BEAM, MODE_SLAB

# PIO のパラメータ(レコードフィールド)名。VectorWorks 側のプラグイン
# 定義と一致させること。
PARAM_MODE = 'Mode'
PARAM_MAIN_BAR = 'MainBar'
PARAM_DIST_BAR = 'DistBar'
PARAM_MAIN_ANGLE = 'MainBarAngle'
PARAM_DOUBLE_LAYER = 'DoubleLayer'
PARAM_TOP_MAIN_BAR = 'TopMainBar'
PARAM_TOP_DIST_BAR = 'TopDistBar'
PARAM_SLAB_THICKNESS = 'SlabThickness'
PARAM_SECTION_SIZE = 'SectionSize'
PARAM_TOP_BARS = 'TopBars'
PARAM_BOTTOM_BARS = 'BottomBars'
PARAM_STIRRUP = 'Stirrup'
PARAM_COVER = 'Cover'
PARAM_MARK_SCALE = 'MarkScale'

# Mode ポップアップの表示値。梁を含む値なら梁モード、それ以外はスラブ。
MODE_LABEL_BEAM = '梁'

# 数値フィールドの文字列から数値部分を取り出す(単位付き "150.0mm" や
# 桁区切りを許容する)
_NUMBER_RE = re.compile(r'-?\d+(?:\.\d+)?')


def _field(record_name: str, handle: Any, field: str) -> str:
    """レコードフィールドを文字列で読む。失敗時は空文字。"""
    try:
        value = vs.GetRField(handle, record_name, field)
    except Exception:
        return ''
    return value if isinstance(value, str) else ''


def _number(text: str) -> Optional[float]:
    """数値フィールドの文字列を float にする(単位表記を無視)。"""
    match = _NUMBER_RE.search(text.replace(',', ''))
    return float(match.group(0)) if match else None


def _boolean(text: str) -> bool:
    """ブールフィールドの文字列('True'/'1' 等)を bool にする。"""
    return text.strip().lower() in ('true', 'yes', '1')


def read_path(pio_handle: Any) -> List[List[float]]:
    """PIO のパス頂点(ローカル座標)を読み取る。

    3D パス図形のパスは 3D 基準の多角形(または NURBS 曲線)で、
    ``GetPolyPt3D`` は 0 始まりのインデックスで頂点を返す。
    """
    path_handle = vs.GetCustomObjectPath(pio_handle)
    if path_handle == vs.Handle(0):
        return []
    count = vs.GetVertNum(path_handle)
    path: List[List[float]] = []
    for index in range(count):
        x, y, z = vs.GetPolyPt3D(path_handle, index)
        path.append([float(x), float(y), float(z)])
    return path


def read_pio_input() -> Optional[Tuple[Any, Dict[str, Any]]]:
    """リセット中の PIO のハンドルと params dict を返す。

    PIO コンテキスト外(``GetCustomObjectInfo`` が False)の場合は None。
    数値フィールドが解釈できない場合はキーを省き、配筋計算フェーズの
    既定値に委ねる。
    """
    ok, record_name, pio_handle, _record, _wall = vs.GetCustomObjectInfo()
    if not ok:
        return None

    def field(name: str) -> str:
        return _field(record_name, pio_handle, name)

    mode_label = field(PARAM_MODE)
    params: Dict[str, Any] = {
        'mode': MODE_BEAM if MODE_LABEL_BEAM in mode_label else MODE_SLAB,
        'path': read_path(pio_handle),
        'main_bar': field(PARAM_MAIN_BAR),
        'dist_bar': field(PARAM_DIST_BAR),
        'double_layer': _boolean(field(PARAM_DOUBLE_LAYER)),
        'top_main_bar': field(PARAM_TOP_MAIN_BAR),
        'top_dist_bar': field(PARAM_TOP_DIST_BAR),
        'section_size': field(PARAM_SECTION_SIZE),
        'top_bars': field(PARAM_TOP_BARS),
        'bottom_bars': field(PARAM_BOTTOM_BARS),
        'stirrup': field(PARAM_STIRRUP),
    }
    for key, name in (
        ('main_angle', PARAM_MAIN_ANGLE),
        ('slab_thickness', PARAM_SLAB_THICKNESS),
        ('cover', PARAM_COVER),
        ('mark_scale', PARAM_MARK_SCALE),
    ):
        number = _number(field(name))
        if number is not None:
            params[key] = number
    return pio_handle, params
