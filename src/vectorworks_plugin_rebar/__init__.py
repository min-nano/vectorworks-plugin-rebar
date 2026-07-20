"""スラブ・壁の餅網状配筋を断面注釈として描く VectorWorks プラグインオブジェクト。

**2D 線形図形**(直線 1 本)として登録し、ユーザーが引いた直線(スラブ・壁の
面)から、かぶり分オフセットした位置に配筋の断面表現を注釈として描く:

- 紙面平行方向の鉄筋 = かぶり分オフセットした 2D 直線。
- 紙面直交方向の鉄筋 = 端部の表示記号(●/× 等、配筋標準図 KSE 2008)を
  オフセット線上にピッチ間隔で並べる。

線をいちいち描かなくても、直線を 1 本引くだけで配筋記号が並ぶ。3D・断面
2D コンポーネントは使わず、すべて 2D 注釈として描く(VectorWorks の作図
特性との相性から 2D 注釈方式へ全面刷新した)。

処理は 2 フェーズに完全分離されている:

1. 配筋計算フェーズ (``rebar`` パッケージ, vs 非依存)
   PIO のパラメータと面線の 2 端点から、JSON 直列化可能な命令セットを
   組み立てる。
2. 描画フェーズ (``vw`` パッケージ, vs 依存)
   命令セットに従って vs モジュールで実際の描画を行う。

命令セットのスキーマは ``document.py`` を参照。
"""
from __future__ import annotations

import json

from .document import validate_document
from .rebar import SpecError, build_document

__all__ = ['build_document', 'run', 'validate_document']


def run() -> None:
    """PIO のリセットスクリプト本体。

    リセットは頻繁に実行される(移動・編集のたび)ため、エラーは
    モーダルダイアログではなくステータスバー(``vs.Message``)に表示する。
    """
    # vs に依存するモジュールは VectorWorks 上での実行時のみ読み込む。
    # これにより rebar パッケージ(配筋計算フェーズ)は通常の Python 環境でも
    # 利用できる。
    import vs

    from .vw import execute_document
    from .vw.pio import read_pio_input

    try:
        context = read_pio_input()
        if context is None:
            return
        pio_handle, params = context

        # フェーズ1: 配筋計算 → JSON 命令セット。JSON 文字列を経由して
        # 受け渡すことで、命令セットが常に直列化可能(= vs のハンドル等を
        # 含まない)ことを保証する
        document = json.loads(json.dumps(build_document(params)))

        # フェーズ2: 命令セットに従って描画
        execute_document(document, pio_handle)
    except SpecError as error:
        vs.Message(f'配筋: {error}')
    except Exception as error:
        vs.Message(f'配筋: エラーが発生しました: {error}')
