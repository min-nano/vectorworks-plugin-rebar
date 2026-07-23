"""JSON 命令セット(ドキュメント)のスキーマ定義と検証。

命令セットは配筋計算フェーズ(``rebar`` パッケージ)が生成し、
描画フェーズ(``vw`` パッケージ)が消費する JSON 直列化可能な dict。
このモジュールは vs に依存しない。

この PIO は **2D 線形図形**(直線 1 本)として登録され、スラブ・壁の断面
(紙面)に現れる餅網状の配筋を、線を引くだけで注釈として描く。ユーザーが
引いた直線(スラブ・壁の面)からかぶり分オフセットした位置に、紙面平行
方向の鉄筋を **線**、紙面直交方向の鉄筋を **断面記号**(●/× 等、配筋標準図
KSE 2008)で並べる。3D・断面 2D コンポーネントは使わず、すべてビュー
ポート(または設計レイヤ)上の 2D 注釈として描く。

出力は 2 系統:

1. 線(``lines``): 紙面平行方向の鉄筋。かぶり分オフセットした 2D 直線。
2. 断面記号(``symbol_profiles`` + ``mark_centers``): 紙面直交方向の鉄筋の
   端部を表す表示記号。記号 1 個分の線画プロファイル(原点中心)を
   ``symbol_profiles`` に 1 度だけ持ち、``mark_centers`` の各位置へ平行移動
   して 2D の線・円として描く(ピッチ間隔で並ぶ)。

すべての図形は描画フェーズが PIO 本体の描画クラス(``vs.GetClass(pio)``)に
割り当てる。作図クラスは命令セットには含めない(クラス管理は描画フェーズ
=PIO を扱う側)。

断面記号プロファイル(``symbol_profiles``)は紙面上の線画で、原点(0, 0)を
中心に組み立てる(``mark_centers`` の各位置へ平行移動して描く):

    {"kind": "line",   "start": [u, v], "end": [u, v]}   # 線(× ・+ ・斜線)
    {"kind": "circle", "center": [u, v], "radius": r, "filled": bool}
        # filled=false: 輪郭の円(○ 等)
        # filled=true:  塗り円(● 等)

スキーマ (version 2):

    {
        "version": 2,
        "lines": [
            {"start": [x, y], "end": [x, y]}   # 紙面平行方向の鉄筋(2D 線)
        ],
        "symbol_profiles": [ <profile>, ... ],  # 記号 1 個分の線画(原点中心)
        "mark_centers": [ [cx, cy], ... ]       # 記号を描く位置(ピッチ間隔)
    }

version 1 は 3D パス図形時代の別スキーマ(plan_lines/cut_lines/bars_3d)で、
2D 注釈方式への全面刷新に伴い version 2 へ更新した(互換性なし)。命令セットは
リセットのたびに再生成され永続化されないため、旧バージョンの読取りは不要。

スキーマを変更するときは ``DOCUMENT_VERSION`` の互換性に注意し、
TypedDict 定義・docstring・``validate_document()`` とテストも併せて
更新すること。
"""
from __future__ import annotations

from typing import Any, Dict, List, TypedDict

DOCUMENT_VERSION = 2

# symbol_profiles の kind。
KIND_LINE = 'line'
KIND_CIRCLE = 'circle'
PROFILE_KINDS = (KIND_LINE, KIND_CIRCLE)

# 断面記号プロファイル(線・円で持つキーが異なる不均質な dict)。実行時検証
# (``validate_document``)で形を保証する ``Dict[str, Any]`` として扱う。
Profile = Dict[str, Any]


class LineCommand(TypedDict):
    start: List[float]
    end: List[float]


class Document(TypedDict):
    version: int
    lines: List[LineCommand]
    symbol_profiles: List[Profile]
    mark_centers: List[List[float]]


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _validate_point_2d(value: Any, where: str) -> None:
    if (
        not isinstance(value, list)
        or len(value) != 2
        or not all(_is_number(v) for v in value)
    ):
        raise ValueError(f'{where} は [x, y] の数値ペアである必要があります: {value!r}')


def _validate_line(command: Any, index: int) -> None:
    where = f'lines[{index}]'
    if not isinstance(command, dict):
        raise ValueError(f'{where} は dict である必要があります')
    _validate_point_2d(command.get('start'), f'{where}.start')
    _validate_point_2d(command.get('end'), f'{where}.end')


def _validate_positive(value: Any, where: str) -> None:
    if not _is_number(value):
        raise ValueError(f'{where} は数値である必要があります: {value!r}')
    if value <= 0:
        raise ValueError(f'{where} は正の値である必要があります: {value!r}')


def _validate_profile(profile: Any, index: int) -> None:
    where = f'symbol_profiles[{index}]'
    if not isinstance(profile, dict):
        raise ValueError(f'{where} は dict である必要があります')
    kind = profile.get('kind')
    if kind == KIND_LINE:
        _validate_point_2d(profile.get('start'), f'{where}.start')
        _validate_point_2d(profile.get('end'), f'{where}.end')
    elif kind == KIND_CIRCLE:
        _validate_point_2d(profile.get('center'), f'{where}.center')
        _validate_positive(profile.get('radius'), f'{where}.radius')
        if not isinstance(profile.get('filled'), bool):
            raise ValueError(f'{where}.filled は bool である必要があります')
    else:
        raise ValueError(
            f'{where}.kind は {PROFILE_KINDS} のいずれかである必要があります: {kind!r}'
        )


def validate_document(document: Any) -> Document:
    """命令セットを検証し、型付きの ``Document`` として返す。

    JSON 由来の信頼できない入力を受けるため引数は ``Any`` とし、
    検証に通った値だけを ``Document`` 型として扱う。
    不正な場合は ``ValueError`` を送出する。
    """
    if not isinstance(document, dict):
        raise ValueError('命令セットは dict である必要があります')
    if document.get('version') != DOCUMENT_VERSION:
        raise ValueError(
            f'命令セットの version が {DOCUMENT_VERSION} ではありません: '
            f'{document.get("version")!r}'
        )

    lines = document.get('lines')
    if not isinstance(lines, list):
        raise ValueError('lines はリストである必要があります')
    for index, command in enumerate(lines):
        _validate_line(command, index)

    profiles = document.get('symbol_profiles')
    if not isinstance(profiles, list):
        raise ValueError('symbol_profiles はリストである必要があります')
    for index, profile in enumerate(profiles):
        _validate_profile(profile, index)

    centers = document.get('mark_centers')
    if not isinstance(centers, list):
        raise ValueError('mark_centers はリストである必要があります')
    for index, center in enumerate(centers):
        _validate_point_2d(center, f'mark_centers[{index}]')
    return document  # type: ignore[return-value]
