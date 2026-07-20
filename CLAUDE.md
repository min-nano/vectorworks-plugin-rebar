# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## このリポジトリについて

スラブ・壁の断面(紙面)に現れる **餅網状の配筋** を、直線を 1 本引くだけで
注釈として描く VectorWorks **プラグインオブジェクト（PIO）** スクリプトです。
姉妹プロジェクト `vectorworks-plugin-rebar-single`（1 本の鉄筋）・
`vectorworks_plugin_import_ifc_homeskz`（IFC インポート）と同じアーキテクチャ・
コーディング規約・実行時自動更新の仕組みを踏襲しています。

PIO は **2D 線形図形**（Linear plug-in object）`配筋` として VectorWorks に
登録され（README の登録手順参照）、次のように動作する:

- ユーザーが引いた **直線 1 本**（スラブ・壁の面）の 2 端点を読み、面線から
  **かぶり分オフセット** した位置に配筋の断面表現を描く。
- **紙面平行方向の鉄筋**（面に沿って紙面内を走る鉄筋）= かぶり分オフセット
  した **2D 直線**。
- **紙面直交方向の鉄筋**（端部が見える鉄筋）= 呼び径に応じた **断面表示記号**
  （●／× 等、配筋標準図 KSE 2008「鉄筋の表示記号」）を、オフセット線上に
  **ピッチ間隔** で並べる。記号定義は `vectorworks-plugin-rebar-single` の
  `rebar/symbol.py` を踏襲する。

出力はすべて **2D 注釈**（ビューポート注釈または設計レイヤの 2D 図形）で、
出力は 2 系統:

1. **線（`lines`）**: 紙面平行方向の鉄筋。かぶり分オフセットした 2D 直線。
2. **断面記号（`symbol_profiles` + `mark_centers`）**: 記号 1 個分の線画
   プロファイル（原点中心）を `mark_centers` の各位置へ平行移動して 2D の
   線・円として描く。

**3D・断面 2D コンポーネントは使わない。** 以前は 3D パス図形として 3D
ポリゴン・断面 2D コンポーネント（`Set2DComponentGroup`）を描いていたが、
VectorWorks の作図特性との相性が悪く、2D 注釈方式へ全面刷新した（3D 描画・
断面 2D コンポーネント・梁モード・スラブ多角形クリップをすべて撤去）。

すべての図形は **PIO 本体の描画クラス**（`vs.GetClass(pio)`）に割り当てる。
クラス指定は PIO を扱う側（PIO 本体へのクラス割り当て）で管理するため、
本パッケージは固有のクラス名を持たない。

## ロードマップ・将来の拡張候補（アイデアメモ・確定した予定ではない）

- **2 段配筋（ダブルメッシュ）**: 上下端の 2 段を 1 オブジェクトで描く（現状は
  面線を 2 本引いてそれぞれに配置する運用）。
- **層の深さ差**: 紙面平行方向の鉄筋と紙面直交方向の鉄筋の層の微小な深さ差を
  反映する（現状は同一オフセット線上に模式化）。
- **梁・柱の断面配筋**: 別のパラメータセット・記号配置で再実装する（旧 3D 版の
  梁モードは撤去済み）。
- **端部の定着・余長・フック**の表現。
- **配筋量の集計**（データタグ / ワークシート連携）。

## アーキテクチャ: 2 フェーズ分離

処理は **配筋計算フェーズ** と **VectorWorks 描画フェーズ** に完全分離されている。
両フェーズは JSON 直列化可能な **命令セット（ドキュメント）** だけで接続され、
`vs` との密結合を避けることで検証や VectorWorks バージョンアップ対応を容易に
している。

1. **配筋計算フェーズ（`rebar` サブパッケージ）** — `vs` に一切依存しない。
   PIO のパラメータと面線の 2 端点（プレーンな dict）から、描くべき図形を
   命令セット（dict）として組み立てる。通常の Python 環境で単体実行・検証できる。
2. **描画フェーズ（`vw` サブパッケージ）** — `vs` だけに依存し、配筋の知識
   （かぶり・記号の意味等）を持たない。命令セットを検証（`validate_document`）
   してから vs API で描画する。

命令セットのスキーマ（version・lines/symbol_profiles/mark_centers の各形式）は
`document.py` の docstring に定義されている。スキーマを変更するときは
`DOCUMENT_VERSION` の互換性に注意し、`TypedDict` 定義・docstring・
`validate_document()` とテストも併せて更新すること。`run()` は両フェーズの間で
`json.dumps`/`json.loads` を通すため、命令セットに直列化不能なオブジェクト
（vs ハンドル等）を入れてはならない。

## パッケージ構造

```
src/
    vectorworks_plugin_rebar/    # pip インストール可能なパッケージ本体
        __init__.py       # run() を公開 (PIO 読取 → 配筋計算 → JSON 命令セット → 描画)
        document.py       # 命令セットのスキーマ定義・検証 (vs 非依存)
        rebar/            # フェーズ1: 配筋計算 (vs 非依存)
            __init__.py   # build_document(params) -> dict / 既定値定数
            spec.py       # 仕様文字列パース (D10 / D13@200, NFKC 正規化)
            symbol.py     # 表示記号(KSE 2008) → 線・円プロファイル
            mesh.py       # 面線 → オフセット線 + 記号位置 (幾何)
        vw/               # フェーズ2: VectorWorks 描画 (vs 依存)
            __init__.py   # execute_document(document, pio_handle) -> 実行数 dict
            pio.py        # PIO コンテキスト読取 (パラメータ・面線 2 端点 → params dict)
            draw.py       # 2D 線・2D 円の描画 (by-class 属性)
main.py                  # VectorWorks に登録する PIO スクリプト (実行時に自動インストール・更新)
tests/                   # pytest 用テスト (CI は vs.py スタブを GitHub からダウンロード)
pyproject.toml           # パッケージメタデータ
```

`vs` を import してよいのは `vw` サブパッケージ内・`run()` 関数内・`main.py` の
設定フォルダ検出（いずれも関数内の遅延 import）だけ。`rebar` サブパッケージや
`document.py` に `vs` への依存を持ち込まないこと。テストもこの分離に従う:
`tests/test_rebar_*.py`・`tests/test_document.py` は vs モック不要、
`tests/test_vw_*.py`・`tests/test_init.py` は手書きの命令・パラメータを vs
モックで実行して検証する。

## コーディング規約: 型注釈

すべての関数・メソッド（テストコード・モック用クロージャ含む）に引数と戻り値の
型注釈を付ける。型検査は mypy で行い、CI で `mypy` を実行する（設定は
`pyproject.toml` の `[tool.mypy]`、`disallow_untyped_defs` 有効）。

- 各モジュール先頭に `from __future__ import annotations` を置く。Python 3.9
  互換を保ちつつ `list[str]` / `X | None` 構文を使うため。
- 命令セットの線の型は `document.py` の `TypedDict`（`Document` / `LineCommand`）
  を使う。断面記号プロファイル（line/circle で持つキーが異なる不均質な dict）は
  `Profile = Dict[str, Any]` とし、実行時検証（`validate_document`）で形を保証する。
- `vs` モジュールは型スタブが存在しないため `ignore_missing_imports` で許容し、
  vs ハンドルは `Any` で扱う。VectorWorks 公式 `vs.py` スタブ（`tests/vs.py`）は
  型検査対象から除外している。
- 検証前の命令セット（JSON 由来の信頼できない入力）を受ける関数
  （`validate_document()` / `execute_document()`）の引数は `Any` とし、検証済みの
  値だけを `Document` 型として扱う。

## スクリプトの実行方法

このスクリプトは単独の Python プログラムとして動作しません。**VectorWorks 内で
PIO のリセットスクリプトとして実行する必要があります**。`vs` モジュールは
VectorWorks 独自の Python スクリプト API であり、pip でインストールすることは
できません。

テストは VectorWorks の公式 `vs.py` スタブをモック対象として `pytest` で実行
します（`.github/workflows/test.yml` 参照）。

## 実行時自動更新（main.py）

姉妹プロジェクトの main.py と同じ仕組み（GitHub `main` ブランチのコミット SHA
比較 → アーカイブ直接展開 → 依存は pip）。**開発初期は頻繁に変更して試すため、
リセットのたびに毎回更新を確認する**。更新した場合はキャッシュ済みモジュールを
破棄するため、VectorWorks を再起動しなくても次のリセットから新しいコードが
使われる。

## PIO スクリプトの処理フロー

`vectorworks_plugin_rebar.run()` は PIO のリセットのたびに以下を行う:

1. **PIO コンテキスト読取（`vw/pio.py`）** — `vs.GetCustomObjectInfo()` で PIO
   ハンドルを取得し、`vs.GetRField` でパラメータを、`vs.GetSegPt1` /
   `vs.GetSegPt2`（線形図形の始点/終点の X-Y 座標）で面線の 2 端点を読む。
   数値フィールドは単位付き文字列（`40.0mm`）を許容し、解釈できないフィールドは
   キーを省いて既定値に委ねる。
2. **配筋計算（フェーズ1）** — `rebar.build_document(params)` で JSON 命令セットを
   組み立てる。仕様文字列の形式不正・面線の長さ 0 等は `SpecError`（ユーザー
   向け日本語メッセージ）。
3. **JSON 経由の受け渡し** — `json.dumps` → `json.loads` を通し直列化可能性を保証。
4. **描画（フェーズ2）** — `vw.execute_document(document, pio_handle)` が検証後、
   線（紙面平行方向の鉄筋）→ 断面記号（各記号位置へ平行移動）の順で描画する。
5. **エラー表示** — リセットは頻繁に実行されるためモーダルダイアログは使わず、
   `vs.Message` でステータスバーに表示する（`SpecError` は入力の直し方が分かる
   メッセージ）。

### 面線の読み取り（vw/pio.py）

- 2D 線形図形（Linear plug-in object）は始点・終点の 2 制御点を持つ。
  `vs.GetSegPt1(pio)` / `vs.GetSegPt2(pio)` がそれぞれの X-Y 座標を返す（線・
  壁・線形寸法の始点/終点を返す関数）。線形図形のローカル座標系で読むため、
  描いた図形の配置・回転は VectorWorks が扱う。
- **端点が期待どおり返るか・オフセットの左右（面のどちら側に描くか）は
  VectorWorks 上で最終確認する**（描画フェーズは VW 上で検証する方針）。左右が
  逆であれば `Flip` パラメータで反転できる。

### 幾何の規約（rebar/mesh.py）

- オフセット: 面線の法線方向（進行方向 start→end の左側 = 反時計回りに 90°）へ
  `かぶり + 平行筋径/2` だけずらした線を紙面平行方向の鉄筋（線）とする。`flip`
  で反対側へ。
- 断面記号: オフセット線上に、始端から `ピッチ/2` を最初として等ピッチで並べる
  （線長がピッチ未満なら中央に 1 本）。記号（原点中心のプロファイル）はオフ
  セット線上に中心を置く（餅網の 2 方向を同一オフセット線上に模式化）。

### 表示記号（rebar/symbol.py）

- 配筋標準図（KSE 2008）「鉄筋の表示記号」に従い、呼び径ごとに断面の表示記号を
  線画のプロファイル（line / circle）へ分解する（D10=●, D13=×, D16=⊘, D19=●,
  D22=○, D25=⊙, D29=⊗, D32=◎, D35=⊕, D38=●⊕, D41=⊗）。姉妹プロジェクト
  `vectorworks-plugin-rebar-single` の同名モジュールと同じ記号定義を踏襲する。
- 記号の大きさは `呼び径 × MarkScale` を外径とした模式表現。○ 等の輪郭は
  `filled=false` の円、● は `filled=true` の円で表す。表にない呼び径は最も近い
  標準呼び径の記号で近似する。

### 描画の規約（vw/draw.py）

- 2D 線は `vs.MoveTo` → `vs.LineTo` → `vs.LNewObj`。2D 円は `vs.Oval` →
  `vs.LNewObj`、記号の意味に合わせ `vs.SetFPat`（塗り=1・輪郭=0）で塗り/輪郭を
  明示する（`SetFPat` が無い/失敗する環境では非致命として無視し、クラス塗りに
  従う）。
- すべての図形を **PIO 本体の描画クラス**（`execute_document` が `vs.GetClass(pio)`
  で 1 回取得）に `vs.SetClass` で割り当て、描画属性（線色・塗色・太さ・線種・
  パターン・マーカー・透明度）を属性ごとの by-class 設定関数で **すべてクラス
  属性に従わせる**。クラス指定・線種や色の調整は PIO を扱う側が PIO 本体の
  クラスで管理する。命令セットは作図クラスを持たない（`document.py` 参照）。

## 開発プロセス: PR 作成と監視

コード修正を実施する際は以下のプロセスに従う:

1. **PR作成の判断基準**:
   - コード編集後、ユーザーに確認すべき疑義が特にない場合は**自動的に PR を作成する**。
   - 迷いや未確定事項がある場合（変更方針をユーザーに確認中など）は、PR 作成を保留し先にユーザーに確認する。

2. **PR 作成後の対応**:
   - PR を作成したら `subscribe_pr_activity` で CI 結果とレビューコメントを監視する。
   - CI 失敗は原因を診断して修正コミットを自動的に push する。
   - レビューコメントは内容を確認し、軽微な修正は自動で追加コミットする。大きな変更・設計判断が必要な指摘はユーザーに確認してから対応する。
   - CI が全て green でレビュー上の問題もなければ**自動的にマージする**。

3. **コミットメッセージ**:
   - Claude セッション URL を追加する形式: `https://claude.ai/code/session_<SESSION_ID>`
