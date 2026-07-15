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

        counts = vw.execute_document(make_document(), PIO_HANDLE)

        assert counts == {'plan_lines': 2, 'cut_lines': 1, 'bars_3d': 2}

    def test_plan_lines_drawn_with_class(self) -> None:
        vs_mock = _make_vs_mock()
        vw = _load(vs_mock)

        vw.execute_document(make_document(), PIO_HANDLE)

        # 平面線 2 + 断面線 1 = 3 本の MoveTo/LineTo
        assert vs_mock.MoveTo.call_count == 3
        assert vs_mock.LineTo.call_count == 3
        assert vs_mock.MoveTo.call_args_list[0].args[0] == (0.0, 0.0)
        assert vs_mock.LineTo.call_args_list[0].args[0] == (100.0, 0.0)
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

    def test_plan_lines_assigned_to_top_plan_component(self) -> None:
        vs_mock = _make_vs_mock()
        vw = _load(vs_mock)

        vw.execute_document(make_document(), PIO_HANDLE)

        calls = vs_mock.Set2DComponentGroup.call_args_list
        by_component = {c.args[2]: c.args for c in calls}
        # 平面線は Top/Plan コンポーネント (10) にグループとして設定する。
        # これにより断面コンポーネント (6/9) が平面ビューに漏れない。
        assert 10 in by_component
        top_plan = by_component[10]
        assert top_plan[0] == PIO_HANDLE
        assert top_plan[1].startswith('OBJ_')

    def test_cut_lines_assigned_to_component(self) -> None:
        vs_mock = _make_vs_mock()
        vw = _load(vs_mock)

        vw.execute_document(make_document(), PIO_HANDLE)

        calls = vs_mock.Set2DComponentGroup.call_args_list
        # front_back には作ったグループを、空の left_right には NULL を設定する
        by_component = {c.args[2]: c.args for c in calls}
        assert set(by_component) == {6, 9, 10}
        front_back = by_component[6]
        assert front_back[0] == PIO_HANDLE
        assert front_back[1].startswith('OBJ_')
        left_right = by_component[9]
        assert left_right[1] is vs_mock.Handle.return_value
        # 平面線グループ + 断面線グループの 2 グループを作る
        assert vs_mock.BeginGroup.call_count == 2
        assert vs_mock.EndGroup.call_count == 2

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
