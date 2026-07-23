"""フェーズ1: 配筋計算(スラブ・壁の餅網状配筋の断面)。vs に一切依存しない。

PIO のパラメータと面線の 2 端点(プレーンな dict、``vw.pio`` が組み立てる)
から、描くべき図形を JSON 直列化可能な命令セット(``document.py``)として
組み立てる。通常の Python 環境で単体実行・検証できる。

この PIO は 2D 線形図形(直線 1 本)で、スラブ・壁の断面(紙面)に現れる
餅網状の配筋を注釈として描く:

- 線: 紙面平行方向の鉄筋(かぶり分オフセットした直線)。
- 断面記号: 紙面直交方向の鉄筋の端部を表す表示記号(●/× 等、配筋標準図
  KSE 2008)を、オフセット線上にピッチ間隔で並べる。

入力 params のスキーマ:

    {
        "line": [[x1, y1], [x2, y2]],  # 面線の 2 端点 (PIO ローカル座標, mm)
        "parallel_bar": "D10",         # 紙面平行方向の鉄筋(線) 呼び径
        "perp_bar": "D13@200",         # 紙面直交方向の鉄筋(記号) 呼び径@ピッチ
        "cover": 40.0,                 # かぶり (mm)
        "mark_scale": 4.0,             # 記号の大きさ = 呼び径 × 倍率
        "flip": false                 # オフセット方向の反転
    }
"""
from __future__ import annotations

from typing import Any, List, Mapping

from ..document import DOCUMENT_VERSION, Document, LineCommand, Profile
from .mesh import build_mesh_commands
from .spec import SpecError, parse_nominal, parse_nominal_pitch

__all__ = ['build_document', 'SpecError']

DEFAULT_PARALLEL_BAR = 'D10'
DEFAULT_PERP_BAR = 'D13@200'
DEFAULT_COVER = 40.0
DEFAULT_MARK_SCALE = 4.0


def _float(params: Mapping[str, Any], key: str, default: float) -> float:
    value = params.get(key, default)
    try:
        return float(value)
    except (TypeError, ValueError):
        raise SpecError(f'{key} を数値として解釈できません: {value!r}')


def _text(params: Mapping[str, Any], key: str, default: str) -> str:
    value = params.get(key, default)
    return value if isinstance(value, str) else default


def _required(value: Any, message: str) -> Any:
    if value is None:
        raise SpecError(message)
    return value


def build_document(params: Mapping[str, Any]) -> Document:
    """params から命令セット(ドキュメント)を組み立てる。

    仕様文字列の形式不正・幾何的に描けない入力は ``SpecError``
    (ユーザー向けメッセージ)を送出する。
    """
    line = params.get('line')
    if not isinstance(line, list) or len(line) != 2 or not all(
        isinstance(v, (list, tuple)) and len(v) == 2 for v in line
    ):
        raise SpecError('面線の 2 端点を取得できません')

    parallel = _required(
        parse_nominal(_text(params, 'parallel_bar', DEFAULT_PARALLEL_BAR)),
        '紙面平行方向の鉄筋(ParallelBar)を入力してください',
    )
    perp = _required(
        parse_nominal_pitch(_text(params, 'perp_bar', DEFAULT_PERP_BAR)),
        '紙面直交方向の鉄筋(PerpBar)を入力してください',
    )
    cover = _float(params, 'cover', DEFAULT_COVER)
    if cover < 0:
        raise SpecError(f'かぶりは 0 以上にしてください: {cover!r}')
    mark_scale = _float(params, 'mark_scale', DEFAULT_MARK_SCALE)
    if mark_scale <= 0:
        mark_scale = DEFAULT_MARK_SCALE

    lines: List[LineCommand]
    profiles: List[Profile]
    mark_centers: List[List[float]]
    lines, profiles, mark_centers = build_mesh_commands(
        line,
        parallel_nominal=parallel,
        perp=perp,
        cover=cover,
        mark_scale=mark_scale,
        flip=bool(params.get('flip', False)),
    )

    return {
        'version': DOCUMENT_VERSION,
        'lines': lines,
        'symbol_profiles': profiles,
        'mark_centers': mark_centers,
    }
