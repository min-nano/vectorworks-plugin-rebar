"""フェーズ1: 配筋計算。vs に一切依存しない。

PIO のパラメータとパス頂点(プレーンな dict、``vw.pio`` が組み立てる)
から、描くべき図形を JSON 直列化可能な命令セット(``document.py``)
として組み立てる。通常の Python 環境で単体実行・検証できる。

入力 params のスキーマ:

    {
        "mode": "slab" | "beam",     # PIO の Mode パラメータから変換済み
        "path": [[x, y, z], ...],    # 3D パス頂点 (PIO ローカル座標, mm)
        # スラブモード
        "main_bar": "D10@200",       # 主筋(シングル時またはダブルの下端)
        "dist_bar": "D13@150",       # 配力筋(同上)
        "main_angle": 0.0,           # 主筋方向の角度 (度, X 軸基準)
        "double_layer": false,       # ダブル配筋
        "top_main_bar": "D10@200",   # 上端主筋(ダブル時のみ使用)
        "top_dist_bar": "D13@150",   # 上端配力筋(ダブル時のみ使用)
        "slab_thickness": 150.0,     # スラブ厚 (mm)。パス平面=スラブ天端
        # 梁モード
        "section_size": "150×450",   # 断面サイズ 幅×せい (mm)
        "top_bars": "2-D16",         # 上端筋
        "bottom_bars": "2-D16",      # 下端筋
        "stirrup": "D10@200",        # せん断補強筋(先頭の脚数 1/2/3 で配置切替)
        # 共通
        "cover": 40.0,               # かぶり (mm)
        "mark_scale": 4.0            # 断面の × 記号の大きさ = 径 × 倍率
    }
"""
from __future__ import annotations

from typing import Any, Mapping

from ..document import DOCUMENT_VERSION, Document
from .beam import build_beam_commands
from .slab import build_slab_commands
from .spec import (
    SpecError,
    parse_bar_count,
    parse_bar_pitch,
    parse_section_size,
    parse_stirrup,
)

__all__ = ['build_document', 'SpecError']

MODE_SLAB = 'slab'
MODE_BEAM = 'beam'

DEFAULT_MAIN_BAR = 'D10@200'
DEFAULT_DIST_BAR = 'D13@150'
DEFAULT_SLAB_THICKNESS = 150.0
DEFAULT_SECTION_SIZE = '150×450'
DEFAULT_TOP_BARS = '2-D16'
DEFAULT_BOTTOM_BARS = '2-D16'
DEFAULT_STIRRUP = 'D10@200'
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

    仕様文字列の形式不正・幾何的に配筋できない入力は ``SpecError``
    (ユーザー向けメッセージ)を送出する。
    """
    path = params.get('path')
    if not isinstance(path, list) or not all(
        isinstance(v, (list, tuple)) and len(v) == 3 for v in path
    ):
        raise SpecError('パス頂点を取得できません')
    cover = _float(params, 'cover', DEFAULT_COVER)
    mark_scale = _float(params, 'mark_scale', DEFAULT_MARK_SCALE)
    if mark_scale <= 0:
        mark_scale = DEFAULT_MARK_SCALE

    mode = params.get('mode', MODE_SLAB)
    if mode == MODE_SLAB:
        main = _required(
            parse_bar_pitch(_text(params, 'main_bar', DEFAULT_MAIN_BAR)),
            '主筋(MainBar)を入力してください',
        )
        dist = _required(
            parse_bar_pitch(_text(params, 'dist_bar', DEFAULT_DIST_BAR)),
            '配力筋(DistBar)を入力してください',
        )
        double_layer = bool(params.get('double_layer', False))
        top_main = main
        top_dist = dist
        if double_layer:
            top_main = _required(
                parse_bar_pitch(
                    _text(params, 'top_main_bar', DEFAULT_MAIN_BAR)
                ),
                '上端主筋(TopMainBar)を入力してください',
            )
            top_dist = _required(
                parse_bar_pitch(
                    _text(params, 'top_dist_bar', DEFAULT_DIST_BAR)
                ),
                '上端配力筋(TopDistBar)を入力してください',
            )
        plan_lines, cut_lines, bars_3d = build_slab_commands(
            path,
            main=main,
            dist=dist,
            angle_deg=_float(params, 'main_angle', 0.0),
            double_layer=double_layer,
            top_main=top_main,
            top_dist=top_dist,
            thickness=_float(params, 'slab_thickness', DEFAULT_SLAB_THICKNESS),
            cover=cover,
            mark_scale=mark_scale,
        )
    elif mode == MODE_BEAM:
        section = _required(
            parse_section_size(
                _text(params, 'section_size', DEFAULT_SECTION_SIZE)
            ),
            '断面サイズ(SectionSize)を入力してください',
        )
        plan_lines, cut_lines, bars_3d = build_beam_commands(
            path,
            section=section,
            top=parse_bar_count(_text(params, 'top_bars', DEFAULT_TOP_BARS)),
            bottom=parse_bar_count(
                _text(params, 'bottom_bars', DEFAULT_BOTTOM_BARS)
            ),
            stirrup=parse_stirrup(_text(params, 'stirrup', DEFAULT_STIRRUP)),
            cover=cover,
            mark_scale=mark_scale,
        )
    else:
        raise SpecError(f'モードを解釈できません: {mode!r}')

    return {
        'version': DOCUMENT_VERSION,
        'plan_lines': plan_lines,
        'cut_lines': cut_lines,
        'bars_3d': bars_3d,
    }
