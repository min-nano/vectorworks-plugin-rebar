"""JSON 命令セット(ドキュメント)のスキーマ定義と検証。

命令セットは配筋計算フェーズ(``rebar`` パッケージ)が生成し、
描画フェーズ(``vw`` パッケージ)が消費する JSON 直列化可能な dict。
このモジュールは vs に依存しない。

図形の作図クラスは命令セットには含まれない。すべての図形は描画フェーズが
PIO 本体の描画クラス(``vs.GetClass(pio)``)に割り当てる(クラス指定は
PIO を扱う側=PIO 本体へのクラス割り当てで管理する)。

スキーマ (version 1):

    {
        "version": 1,
        "plan_lines": [
            {
                # 平面ビューに描く 2D 線。描画フェーズでグループにまとめ、
                # Top/Plan コンポーネント(2D component 定数 10)に設定する
                # (断面コンポーネントが平面ビューに漏れないようにするため)。
                # 座標は PIO のローカル座標 (mm)。
                "start": [x1, y1],
                "end": [x2, y2]
            }
        ],
        "cut_lines": [
            {
                # 断面 2D コンポーネントに描く 2D 線。断面ビューポートの
                # 「2D コンポーネントを表示」で表示される。紙面直交方向の
                # 鉄筋の × 記号は解析フェーズで 2 本の線に分解される。
                # target はどの 2D コンポーネントに置くか:
                #   "front_back" = 前後の断面 (2D component 定数 6,
                #                  紙面 u=ローカル X, v=ローカル Z)
                #   "left_right" = 左右の断面 (2D component 定数 9,
                #                  紙面 u=ローカル Y, v=ローカル Z)
                "target": "front_back",
                "start": [u1, v1],
                "end": [u2, v2]
            }
        ],
        "bars_3d": [
            {
                # 3D 表現(鉄筋の 3D ポリゴン)。閉じた形状(あばら筋等)は
                # closed=true。座標は PIO のローカル座標 (mm)。
                "vertices": [[x1, y1, z1], [x2, y2, z2]],
                "closed": false
            }
        ]
    }

スキーマを変更するときは ``DOCUMENT_VERSION`` の互換性に注意し、
TypedDict 定義・docstring・``validate_document()`` とテストも併せて
更新すること。
"""
from __future__ import annotations

from typing import Any, List, TypedDict

DOCUMENT_VERSION = 1

# cut_lines の target に指定できる値。
TARGET_FRONT_BACK = 'front_back'
TARGET_LEFT_RIGHT = 'left_right'
CUT_TARGETS = (TARGET_FRONT_BACK, TARGET_LEFT_RIGHT)

class PlanLineCommand(TypedDict):
    start: List[float]
    end: List[float]


class CutLineCommand(TypedDict):
    target: str
    start: List[float]
    end: List[float]


class Bar3DCommand(TypedDict):
    vertices: List[List[float]]
    closed: bool


class Document(TypedDict):
    version: int
    plan_lines: List[PlanLineCommand]
    cut_lines: List[CutLineCommand]
    bars_3d: List[Bar3DCommand]


def _validate_point_2d(value: Any, where: str) -> None:
    if (
        not isinstance(value, list)
        or len(value) != 2
        or not all(isinstance(v, (int, float)) for v in value)
    ):
        raise ValueError(f'{where} は [x, y] の数値ペアである必要があります: {value!r}')


def _validate_plan_line(command: Any, index: int) -> None:
    where = f'plan_lines[{index}]'
    if not isinstance(command, dict):
        raise ValueError(f'{where} は dict である必要があります')
    _validate_point_2d(command.get('start'), f'{where}.start')
    _validate_point_2d(command.get('end'), f'{where}.end')


def _validate_cut_line(command: Any, index: int) -> None:
    where = f'cut_lines[{index}]'
    if not isinstance(command, dict):
        raise ValueError(f'{where} は dict である必要があります')
    if command.get('target') not in CUT_TARGETS:
        raise ValueError(
            f'{where}.target は {CUT_TARGETS} のいずれかである必要があります: '
            f'{command.get("target")!r}'
        )
    _validate_point_2d(command.get('start'), f'{where}.start')
    _validate_point_2d(command.get('end'), f'{where}.end')


def _validate_bar_3d(command: Any, index: int) -> None:
    where = f'bars_3d[{index}]'
    if not isinstance(command, dict):
        raise ValueError(f'{where} は dict である必要があります')
    vertices = command.get('vertices')
    if not isinstance(vertices, list) or len(vertices) < 2:
        raise ValueError(f'{where}.vertices は 2 点以上の頂点リストである必要があります')
    for i, vertex in enumerate(vertices):
        if (
            not isinstance(vertex, list)
            or len(vertex) != 3
            or not all(isinstance(v, (int, float)) for v in vertex)
        ):
            raise ValueError(
                f'{where}.vertices[{i}] は [x, y, z] の数値である必要があります: '
                f'{vertex!r}'
            )
    if not isinstance(command.get('closed'), bool):
        raise ValueError(f'{where}.closed は bool である必要があります')


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
    for key, validator in (
        ('plan_lines', _validate_plan_line),
        ('cut_lines', _validate_cut_line),
        ('bars_3d', _validate_bar_3d),
    ):
        commands = document.get(key)
        if not isinstance(commands, list):
            raise ValueError(f'{key} はリストである必要があります')
        for index, command in enumerate(commands):
            validator(command, index)
    return document  # type: ignore[return-value]
