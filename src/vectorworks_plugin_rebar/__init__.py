"""基礎コンクリートの配筋を保持・描画する VectorWorks プラグインオブジェクト。

3D パスで指定した範囲(スラブモード=配筋平面の外形・梁モード=梁天端の
中心線)に配筋情報を保持し、平面ビューの 2D 線・3D 表現・断面
ビューポート用の 2D コンポーネント(紙面方向の鉄筋=直線、紙面直交方向の
鉄筋=×)を出力する。

処理は 2 フェーズに完全分離されている:

1. 配筋計算フェーズ (``rebar`` パッケージ, vs 非依存)
   PIO のパラメータとパス頂点から、JSON 直列化可能な命令セットを
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
        result = execute_document(document, pio_handle)

        # 断面 2D コンポーネントが平面ビューに漏れる問題の切り分け用診断を
        # ステータスバーに表示する(2D コンポーネント割り当ての生の戻り値)。
        # 問題解決後に削除する一時的な出力。
        vs.Message(_diagnostic_message(result))
    except SpecError as error:
        vs.Message(f'配筋: {error}')
    except Exception as error:
        vs.Message(f'配筋: エラーが発生しました: {error}')


def _diagnostic_message(result: dict) -> str:
    """描画結果の診断メッセージを組み立てる(2D コンポーネント切り分け用)。

    各 2D コンポーネント割り当て(``Set2DComponentGroup`` /
    ``SetTopPlan2DComp``)の生の戻り値をそのまま表示し、VectorWorks 上で
    どのコンポーネントが成功/失敗しているかを確認できるようにする。
    """
    diag = result.get('diagnostic', {})
    cut = diag.get('cut', {})
    return (
        f"配筋: 平面{result.get('plan_lines', 0)} "
        f"断面{result.get('cut_lines', 0)} 3D{result.get('bars_3d', 0)} | "
        f"profile={diag.get('profile')!r} "
        f"FB={cut.get('front_back')!r} LR={cut.get('left_right')!r} "
        f"topview={diag.get('top_plan_view')!r}"
    )
