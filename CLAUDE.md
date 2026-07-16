# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## このリポジトリについて

基礎コンクリートの配筋情報を保持し、平面ビュー・3D ビュー・断面ビューポートに配筋表現を描画する VectorWorks **プラグインオブジェクト（PIO）** スクリプトです。姉妹プロジェクト `vectorworks_plugin_import_ifc_homeskz`（IFC インポート）と同じアーキテクチャ・コーディング規約・実行時自動更新の仕組みを踏襲しています。

PIO は 3D パス図形 `配筋` として VectorWorks に登録され（README の登録手順参照）、モードで動作を切り替える:

- **スラブモード**: 3D パス＝配筋平面の外形（パス平面＝スラブ天端）。主筋（`D10@200`）・配力筋（`D13@150`）・主筋方向角度・ダブル配筋（上端/下端それぞれの仕様）・スラブ厚・かぶりを保持。シングルは厚中央、ダブルはかぶり＋径を考慮した上端/下端に配筋する（主筋を外側に置く慣例）。
- **梁モード**: 3D パス＝梁天端の中心線。断面サイズ（`150×450`）・上下端主筋（`2-D16`）・せん断補強筋（`D10@200`）・かぶりを保持。主筋はせん断補強筋の内側に等間隔で並べる。

出力は 3 系統:

1. **平面（Top/Plan）**: 配筋の 2D 線（PIO 本体のコンテンツ）。
2. **3D**: 鉄筋の 3D ポリゴン（開いた線＝鉄筋、閉じた矩形＝あばら筋）。2D + 3D を持つことで PIO はハイブリッドオブジェクトになる。
3. **断面 2D コンポーネント**: 断面ビューポートの「2D コンポーネントを表示」で表示される断面表現。紙面方向の鉄筋＝直線、紙面直交方向の鉄筋＝×（2 本の線に分解）。

すべての図形は **PIO 本体の描画クラス**（`vs.GetClass(pio)`）に割り当てる。クラス指定は PIO を扱う側（PIO 本体へのクラス割り当て）で管理するため、本パッケージは固有のクラス名を持たない。

## ロードマップ

- **イベント対応スクリプト化**: `SetParameterVisibility` を使い、OIP のパラメータ表示をモード（スラブ/梁）に応じて切り替える（現状は両モードのパラメータが常に表示される）。
- **自動更新の確認頻度**: 開発初期は毎リセットで更新確認する（現状）。安定後は VectorWorks セッション内の初回だけに絞り、編集操作のたびのネットワークアクセスを避ける。

## 将来の拡張候補（アイデアメモ・確定した予定ではない）

- 梁の腹筋・幅止め筋
- スラブ端部の定着・余長の表現
- 配筋量の集計（データタグ / ワークシート連携）
- 上端筋・下端筋など層別に描画属性を分けるオプション（現状は PIO 本体のクラス 1 つに従う）

## アーキテクチャ: 2 フェーズ分離

処理は **配筋計算フェーズ** と **VectorWorks 描画フェーズ** に完全分離されている。両フェーズは JSON 直列化可能な**命令セット（ドキュメント）**だけで接続され、`vs` との密結合を避けることで検証や VectorWorks バージョンアップ対応を容易にしている。

1. **配筋計算フェーズ（`rebar` サブパッケージ）** — `vs` に一切依存しない。PIO のパラメータとパス頂点（プレーンな dict）から、描くべき図形を命令セット（dict）として組み立てる。通常の Python 環境で単体実行・検証できる。
2. **描画フェーズ（`vw` サブパッケージ）** — `vs` だけに依存し、配筋の知識（ピッチ・かぶり等）を持たない。命令セットを検証（`validate_document`）してから vs API で描画する。

命令セットのスキーマ（version・plan_lines/cut_lines/bars_3d 各命令の形式）は `document.py` の docstring に定義されている。スキーマを変更するときは `DOCUMENT_VERSION` の互換性に注意し、`TypedDict` 定義・docstring・`validate_document()` とテストも併せて更新すること。`run()` は両フェーズの間で `json.dumps`/`json.loads` を通すため、命令セットに直列化不能なオブジェクト（vs ハンドル等）を入れてはならない。

## パッケージ構造

```
src/
    vectorworks_plugin_rebar/    # pip インストール可能なパッケージ本体
        __init__.py       # run() を公開 (PIO 読取 → 配筋計算 → JSON 命令セット → 描画)
        document.py       # 命令セットのスキーマ定義・検証 (vs 非依存)
        rebar/            # フェーズ1: 配筋計算 (vs 非依存)
            __init__.py   # build_document(params) -> dict / 既定値定数
            spec.py       # 仕様文字列パース (D10@200 / 2-D16 / 150×450, NFKC 正規化)
            geometry.py   # 平面幾何 (平行線族の多角形クリップ, 偶奇則)
            slab.py       # スラブモード → plan_lines/cut_lines/bars_3d
            beam.py       # 梁モード → plan_lines/cut_lines/bars_3d
        vw/               # フェーズ2: VectorWorks 描画 (vs 依存)
            __init__.py   # execute_document(document, pio_handle) -> 実行数 dict
            pio.py        # PIO コンテキスト読取 (パラメータ・パス頂点 → params dict)
            draw.py       # 2D 線・3D ポリゴンの描画 (by-class 属性)
            component.py  # 断面 2D コンポーネントの設定 (Set2DComponentGroup)
main.py                  # VectorWorks に登録する PIO スクリプト (実行時に自動インストール・更新)
tests/                   # pytest 用テスト (CI は vs.py スタブを GitHub からダウンロード)
pyproject.toml           # パッケージメタデータ
```

`vs` を import してよいのは `vw` サブパッケージ内・`run()` 関数内・`main.py` の設定フォルダ検出（いずれも関数内の遅延 import）だけ。`rebar` サブパッケージや `document.py` に `vs` への依存を持ち込まないこと。テストもこの分離に従う: `tests/test_rebar_*.py`・`tests/test_document.py` は vs モック不要、`tests/test_vw_*.py`・`tests/test_init.py` は手書きの命令・パラメータを vs モックで実行して検証する。

## コーディング規約: 型注釈

すべての関数・メソッド（テストコード・モック用クロージャ含む）に引数と戻り値の型注釈を付ける。型検査は mypy で行い、CI で `mypy` を実行する（設定は `pyproject.toml` の `[tool.mypy]`、`disallow_untyped_defs` 有効）。

- 各モジュール先頭に `from __future__ import annotations` を置く。Python 3.9 互換を保ちつつ `list[str]` / `X | None` 構文を使うため。
- 命令セットの型は `document.py` の `TypedDict`（`Document` / `PlanLineCommand` / `CutLineCommand` / `Bar3DCommand`）を使う。`class` キー（作図クラス名）が予約語のため functional 構文で定義している。
- `vs` モジュールは型スタブが存在しないため `ignore_missing_imports` で許容し、vs ハンドルは `Any` で扱う。VectorWorks 公式 `vs.py` スタブ（`tests/vs.py`）は型検査対象から除外している。
- 検証前の命令セット（JSON 由来の信頼できない入力）を受ける関数（`validate_document()` / `execute_document()`）の引数は `Any` とし、検証済みの値だけを `Document` 型として扱う。
- `NamedTuple` のフィールド名は `tuple` のメソッド名（`count` / `index`）と衝突させない（`BarCount.quantity`）。

## スクリプトの実行方法

このスクリプトは単独の Python プログラムとして動作しません。**VectorWorks 内で PIO のリセットスクリプトとして実行する必要があります**。`vs` モジュールは VectorWorks 独自の Python スクリプト API であり、pip でインストールすることはできません。

テストは VectorWorks の公式 `vs.py` スタブをモック対象として `pytest` で実行します（`.github/workflows/test.yml` 参照）。

## 実行時自動更新（main.py）

homeskz の main.py と同じ仕組み（GitHub `main` ブランチのコミット SHA 比較 → アーカイブ直接展開 → 依存は pip）。**開発初期は頻繁に変更して試すため、リセットのたびに毎回更新を確認する**。更新した場合はキャッシュ済みモジュールを破棄するため、VectorWorks を再起動しなくても次のリセットから新しいコードが使われる。リセットは図形の移動・編集のたびに実行されるため、安定後は更新確認をセッション内の初回だけに絞る予定（ロードマップ参照）。

## PIO スクリプトの処理フロー

`vectorworks_plugin_rebar.run()` は PIO のリセットのたびに以下を行う:

1. **PIO コンテキスト読取（`vw/pio.py`）** — `vs.GetCustomObjectInfo()` で PIO ハンドルを取得し、`vs.GetRField` でパラメータを、`vs.GetCustomObjectPath` + `vs.GetPolyPt3D`（**0 始まり**インデックス）でパス頂点を読む。数値フィールドは単位付き文字列（`150.0mm`）を許容し、解釈できないフィールドはキーを省いて既定値に委ねる。`Mode` の表示値に `梁` を含めば梁モード、それ以外はスラブモード。
2. **配筋計算（フェーズ1）** — `rebar.build_document(params)` で JSON 命令セットを組み立てる。仕様文字列の形式不正・幾何的に配筋できない入力は `SpecError`（ユーザー向け日本語メッセージ）。
3. **JSON 経由の受け渡し** — `json.dumps` → `json.loads` を通し直列化可能性を保証。
4. **描画（フェーズ2）** — `vw.execute_document(document, pio_handle)` が検証後、3D 鉄筋 → 平面線（regen）→ 断面 2D コンポーネントの順で描画する。
5. **エラー表示** — リセットは頻繁に実行されるためモーダルダイアログは使わず、`vs.Message` でステータスバーに表示する（`SpecError` は入力の直し方が分かるメッセージ）。

### 断面 2D コンポーネント（vw/component.py）

- **`vs.Set2DComponentGroup(pio, group, component)`（VW 2019+）** で PIO の 2D コンポーネントグループを設定する。component 定数は公式リファレンス（Table - 2D components）に基づく: `0`=未設定, `1`=Top, `2`=Bottom, `3`=Top/Bottom Cut, `4`=Front, `5`=Back, **`6`=Front and Back Cut**, `7`=Left, `8`=Right, **`9`=Left and Right Cut**, `10`=Top/Plan。
- 命令セットの `target` との対応: `front_back` → 6（紙面 u=ローカル X・v=ローカル Z）、`left_right` → 9（紙面 u=ローカル Y・v=ローカル Z）。**紙面座標の符号（左右ビューの鏡像の扱い）と 2D コンポーネントの原点は VectorWorks 上で最終確認する**（描画フェーズは VW 上で検証する方針）。
- **デザインレイヤの平面ビューはリセットで描いた regen（全 2D 図形）をそのまま表示する**（VW 上で確認済み）。`Set2DComponentGroup` は成功（戻り値 True）を返しても断面線を regen から取り除かないため、平面ビューに漏れる。`SetCustomObjectProfileGroup` はパス図形の**スイープ用プロファイル**を設定する関数で、これに渡すと平面線が 2D 表示から消えてしまう（＝断面線を消す用途には使えない）。
- **平面線は通常の 2D 図形（regen）として描く**（グループ化・プロファイル固定しない）。regen をそのまま平面ビューに出す。
- **断面線は `Set2DComponentGroup` で 6/9 に割り当てた後、元グループを `vs.DelObject` で regen から削除する**。`Set2DComponentGroup` はコンポーネント側へジオメトリを**コピー**するため、regen の元グループを消しても断面ビューポートには断面が残る（VW 上で確認済み）。割り当て成否に関わらず削除する（平面ビューに漏らさない）。
- 断面線は `vs.BeginGroup`/`vs.EndGroup` でグループにまとめてから設定する。命令が無い target は NULL ハンドル（`vs.Handle(0)`）を設定して前回リセットのコンポーネントを消す。
- **2D 線は画面平面（screen plane, planar ref 0）に置く**（`vw/draw.py` の `set_screen_plane` = `vs.SetPlanarRef(handle, 0)`）。`Set2DComponentGroup` は画面平面のオブジェクトのグループを要求するため。`SetPlanarRef` が無い環境（VW 2018 以前）は何もしない。
- **`Set2DComponentGroup` の戻り値は成否判定（本数カウント）に使う**（`component_set_succeeded`）。公式 VS ラッパーは BOOLEAN（成功=True）だが、内部 SDK は `ESetSpecialGroupErrors`（NoError=0, CannotSet_BadData, CannotSet_UserSpecified）を返すため、`bool` は True を、`int` は 0（NoError）を成功として扱う。
- **`vs.SetTopPlan2DComp(pio, 0)` で Top/Plan ビューを Top（非断面）に固定する**（0=Top, 1=Top and Bottom Cut）。Top/Plan ビューポート等で断面コンポーネントが出ないための補助的な安全策（設計レイヤの平面漏れは上記の regen 削除で解消済み）。関数が無い環境（VW 2018 以前）は何もしない。
- 断面ビューポート側は「2D コンポーネントを表示」を有効にする必要がある（README 参照）。2D コンポーネントはオブジェクトのローカル軸 6 方向にしか持てないため、斜め方向の配筋・梁は近い軸の表現で近似される。

### 描画の規約（vw/draw.py）

- 2D 線は `vs.MoveTo` → `vs.LineTo` → `vs.LNewObj`、3D 鉄筋は `vs.OpenPoly`/`vs.ClosePoly`（開閉モードのトグル）を明示設定してから `vs.Poly3D(*座標)` → `vs.LNewObj`。
- すべての図形を **PIO 本体の描画クラス**（`execute_document` が `vs.GetClass(pio)` で 1 回取得）に `vs.SetClass` で割り当て、描画属性（線色・塗色・太さ・線種・パターン・マーカー・透明度）を属性ごとの by-class 設定関数で**すべてクラス属性に従わせる**（homeskz の `_set_all_attributes_by_class` と同じ規約）。クラス指定・線種や色の調整は PIO を扱う側が PIO 本体のクラスで管理する。命令セットは作図クラスを持たない（`document.py` 参照）。

### 幾何の規約（rebar/geometry.py・slab.py・beam.py）

- スラブの線族は**多角形の面積重心を通る線を基準**に法線方向へ ±ピッチ刻みで並べる（頂点列の平行移動・並び順に対して決定的）。クリップは偶奇則（半開区間規則で頂点通過の二重カウントを防ぐ）。**多角形の境界ちょうどに乗る線は除外する**（境界上では交差判定が辺の向きに依存して非対称になるため）。
- 断面の × 記号は「クリップ済み線分の中点を紙面軸へ投影した位置」に置く（軸整合の配筋では厳密なピッチ位置と一致する）。大きさは `呼び径 × MarkScale`。
- 梁のせん断補強筋は各区間の始端から `ピッチ/2` を最初とし等ピッチ（区間長がピッチ未満なら中央に 1 本）。断面 2D コンポーネントは**区間ごと**に実位置へ生成し、各区間の向き（X 軸寄り/Y 軸寄り）で横断面（梁を横断する切断＝×・矩形）と縦断面（梁に沿う切断の側面図＝主筋の水平線・あばら筋の縦線）の target（left_right/front_back）を決める。VW の断面ビューポートは 3D の切断面と物体の交差から表示コンポーネントを決めるため、横断/縦断を実位置に用意することで、梁を横断した切断には横断面、梁に沿った切断（梁幅内）には側面図が表示される。折れ線・矩形パスでも各区間を切断した位置に断面が出る（2D コンポーネントはローカル軸 6 方向にしか持てないため、斜め区間は近い軸へ寄せた近似）。

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
