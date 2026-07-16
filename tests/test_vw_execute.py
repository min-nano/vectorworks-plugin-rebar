"""描画フェーズ (vw.execute_document) のテスト。vs をモックし手書きの命令で検証する。"""
from __future__ import annotations

import importlib
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

from vectorworks_plugin_rebar.document import DOCUMENT_VERSION

PIO_HANDLE = 'PIO_HANDLE'


def make_document() -> Dict[str, Any]:
    return {
        'version': DOCUMENT_VERSION,
        'plan_lines': [
            {'start': [0.0, 0.0], 'end': [100.0, 0.0]},
            {'start': [0.0, 50.0], 'end': [100.0, 50.0]},
        ],
        'cut_lines': [
            {
                'target': 'front_back',
                'start': [0.0, -75.0],
                'end': [100.0, -75.0],
            },
        ],
        'bars_3d': [
            {
                'vertices': [[0.0, 0.0, -75.0], [100.0, 0.0, -75.0]],
                'closed': False,
            },
            {
                'vertices': [
                    [0.0, -110.0, -40.0],
                    [0.0, 110.0, -40.0],
                    [0.0, 110.0, -560.0],
                    [0.0, -110.0, -560.0],
                ],
                'closed': True,
            },
        ],
    }


def _make_vs_mock() -> MagicMock:
    vs_mock = MagicMock()
    null_handle = object()
    vs_mock.Handle.return_value = null_handle
    handles: List[str] = []

    def new_obj() -> str:
        handles.append(f'OBJ_{len(handles)}')
        return handles[-1]

    vs_mock.LNewObj.side_effect = new_obj
    vs_mock.Set2DComponentGroup.return_value = True
    # PIO 本体の描画クラス (すべての図形をこのクラスに割り当てる)
    vs_mock.GetClass.return_value = 'PIOクラス'
    return vs_mock


def _load(vs_mock: MagicMock) -> Any:
    with patch.dict('sys.modules', {'vs': vs_mock}):
        import vectorworks_plugin_rebar.vw.component as vw_component
        import vectorworks_plugin_rebar.vw.draw as vw_draw
        import vectorworks_plugin_rebar.vw as vw
        importlib.reload(vw_draw)
        importlib.reload(vw_component)
        importlib.reload(vw)
        return vw


class TestExecuteDocument:
    def test_counts(self) -> None:
        vs_mock = _make_vs_mock()
        vw = _load(vs_mock)

        result = vw.execute_document(make_document(), PIO_HANDLE)

        assert result['plan_lines'] == 2
        assert result['cut_lines'] == 1
        assert result['bars_3d'] == 2

    def test_top_plan_view_fixed_to_top(self) -> None:
        vs_mock = _make_vs_mock()
        vw = _load(vs_mock)

        vw.execute_document(make_document(), PIO_HANDLE)

        # Top/Plan ビューを Top(0)に固定し、断面コンポーネントが平面
        # ビューに表示されないようにする
        vs_mock.SetTopPlan2DComp.assert_called_once_with(PIO_HANDLE, 0)

    def test_diagnostic_reports_raw_component_results(self) -> None:
        vs_mock = _make_vs_mock()
        vs_mock.Set2DComponentGroup.return_value = 0  # SDK: NoError=0 を成功扱い
        vw = _load(vs_mock)

        result = vw.execute_document(make_document(), PIO_HANDLE)

        # 生の戻り値(int 0 = 成功)を診断情報に含める
        diag = result['diagnostic']
        assert diag['cut']['front_back']['set'] == 0
        # int 0 (NoError) は成功として数える
        assert result['cut_lines'] == 1

    def test_plan_lines_drawn_with_class(self) -> None:
        vs_mock = _make_vs_mock()
        vw = _load(vs_mock)

        vw.execute_document(make_document(), PIO_HANDLE)

        # 平面線 2 + 断面線 1 = 3 本の MoveTo/LineTo
        assert vs_mock.MoveTo.call_count == 3
        assert vs_mock.LineTo.call_count == 3
        # 平面線 (0,0)->(100,0) が描かれていることを確認する
        starts = {c.args[0] for c in vs_mock.MoveTo.call_args_list}
        ends = {c.args[0] for c in vs_mock.LineTo.call_args_list}
        assert (0.0, 0.0) in starts
        assert (100.0, 0.0) in ends
        # すべての図形を PIO 本体の描画クラスに割り当て、属性を by-class にする
        vs_mock.GetClass.assert_called_once_with(PIO_HANDLE)
        class_names = {c.args[1] for c in vs_mock.SetClass.call_args_list}
        assert class_names == {'PIOクラス'}
        assert vs_mock.SetLWByClass.call_count == vs_mock.SetClass.call_count

    def test_bars_3d_drawn_as_polys(self) -> None:
        vs_mock = _make_vs_mock()
        vw = _load(vs_mock)

        vw.execute_document(make_document(), PIO_HANDLE)

        assert vs_mock.Poly3D.call_count == 2
        # 開いた鉄筋は OpenPoly、閉じたあばら筋は ClosePoly を先に呼ぶ
        first_bar = vs_mock.Poly3D.call_args_list[0].args
        assert first_bar == (0.0, 0.0, -75.0, 100.0, 0.0, -75.0)
        assert vs_mock.OpenPoly.called
        assert vs_mock.ClosePoly.called

    def test_2d_lines_placed_on_screen_plane(self) -> None:
        vs_mock = _make_vs_mock()
        vw = _load(vs_mock)

        vw.execute_document(make_document(), PIO_HANDLE)

        # 平面線 2 + 断面線 1 = 3 本すべてを画面平面 (planar ref 0) に置く
        # (Set2DComponentGroup は画面平面のグループを要求するため)。
        assert vs_mock.SetPlanarRef.call_count == 3
        for call in vs_mock.SetPlanarRef.call_args_list:
            assert call.args[1] == 0

    def test_plan_lines_drawn_plainly_not_grouped(self) -> None:
        vs_mock = _make_vs_mock()
        vw = _load(vs_mock)

        vw.execute_document(make_document(), PIO_HANDLE)

        # 平面線は通常の regen 2D として描く(グループ化・プロファイル固定
        # しない)。デザインレイヤ平面ビューは regen をそのまま表示するため。
        assert not vs_mock.SetCustomObjectProfileGroup.called
        # グループは断面線(front_back)の 1 つだけ
        assert vs_mock.BeginGroup.call_count == 1
        assert vs_mock.EndGroup.call_count == 1

    def test_cut_lines_assigned_to_component(self) -> None:
        vs_mock = _make_vs_mock()
        vw = _load(vs_mock)

        vw.execute_document(make_document(), PIO_HANDLE)

        calls = vs_mock.Set2DComponentGroup.call_args_list
        # front_back には作ったグループを、空の left_right には NULL を設定する
        by_component = {c.args[2]: c.args for c in calls}
        assert set(by_component) == {6, 9}
        front_back = by_component[6]
        assert front_back[0] == PIO_HANDLE
        assert front_back[1].startswith('OBJ_')
        left_right = by_component[9]
        assert left_right[1] is vs_mock.Handle.return_value

    def test_cut_group_deleted_from_regen(self) -> None:
        vs_mock = _make_vs_mock()
        vw = _load(vs_mock)

        result = vw.execute_document(make_document(), PIO_HANDLE)

        # 割り当て成功後、断面線グループを regen(平面ビュー)から削除する
        assert vs_mock.DelObject.call_count == 1
        # 削除後にコンポーネントが残っているか(コピーか参照か)を診断する
        assert vs_mock.Get2DComponentGroup.called
        assert result['diagnostic']['cut']['front_back']['kept'] is True

    def test_component_failure_deletes_group(self) -> None:
        vs_mock = _make_vs_mock()
        vs_mock.Set2DComponentGroup.return_value = False
        vw = _load(vs_mock)

        counts = vw.execute_document(make_document(), PIO_HANDLE)

        # 2D コンポーネントを設定できない環境では平面ビューを汚さない
        # ようグループを削除し、実行数にも数えない
        assert counts['cut_lines'] == 0
        assert vs_mock.DelObject.call_count == 1

    def test_component_function_missing_deletes_group(self) -> None:
        vs_mock = _make_vs_mock()
        del vs_mock.Set2DComponentGroup
        vw = _load(vs_mock)

        counts = vw.execute_document(make_document(), PIO_HANDLE)

        assert counts['cut_lines'] == 0
        assert vs_mock.DelObject.call_count == 1

    def test_invalid_document_raises(self) -> None:
        vs_mock = _make_vs_mock()
        vw = _load(vs_mock)

        try:
            vw.execute_document({'version': 99}, PIO_HANDLE)
        except ValueError:
            pass
        else:
            raise AssertionError('ValueError が送出されるべき')
        # 検証前に描画しない
        assert not vs_mock.MoveTo.called
