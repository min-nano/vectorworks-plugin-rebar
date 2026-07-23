"""PIO コンテキストの読み取り。vs だけに依存する。

リセット中の PIO 自身の情報(``vs.GetCustomObjectInfo``)から、パラメータ
(レコードフィールド)と面線の 2 端点を読み取り、配筋計算フェーズ
(``rebar.build_document``)へ渡すプレーンな dict(JSON 直列化可能)を
組み立てる。

この PIO は **2D 線形図形**(Linear plug-in object)で、面線の 2 端点は
``vs.GetSegPt1`` / ``vs.GetSegPt2``(線・壁・線形寸法の始点/終点を返す)で
読む。線形図形のローカル座標系で読むため、描いた図形の配置・回転は
VectorWorks が扱う。**端点が期待どおり返るか・オフセットの左右は
VectorWorks 上で最終確認する**(描画フェーズは VW 上で検証する方針)。

パラメータ(レコードフィールド)名は VectorWorks 側で登録するプラグインの
パラメータ名と一致させる必要がある(README の登録手順参照)。名前はこの
モジュール冒頭の定数に集約している。
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

import vs

# PIO のパラメータ(レコードフィールド)名。VectorWorks 側のプラグイン
# 定義と一致させること。
PARAM_PARALLEL_BAR = 'ParallelBar'
PARAM_PERP_BAR = 'PerpBar'
PARAM_COVER = 'Cover'
PARAM_MARK_SCALE = 'MarkScale'
PARAM_FLIP = 'Flip'

# 数値フィールドの文字列から数値部分を取り出す(単位付き "40.0mm" や
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


def read_line(pio_handle: Any) -> List[List[float]]:
    """2D 線形図形の 2 端点(ローカル座標)を読み取る。

    線形図形は始点・終点の 2 制御点を持ち、``GetSegPt1``/``GetSegPt2`` が
    それぞれの X-Y 座標を返す。
    """
    p1 = vs.GetSegPt1(pio_handle)
    p2 = vs.GetSegPt2(pio_handle)
    return [
        [float(p1[0]), float(p1[1])],
        [float(p2[0]), float(p2[1])],
    ]


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

    params: Dict[str, Any] = {
        'line': read_line(pio_handle),
        'parallel_bar': field(PARAM_PARALLEL_BAR),
        'perp_bar': field(PARAM_PERP_BAR),
        'flip': _boolean(field(PARAM_FLIP)),
    }
    for key, name in (
        ('cover', PARAM_COVER),
        ('mark_scale', PARAM_MARK_SCALE),
    ):
        number = _number(field(name))
        if number is not None:
            params[key] = number
    return pio_handle, params
