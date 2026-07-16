"""run() (PIO リセット全体のパイプライン) の統合テスト。vs をモックして検証する。"""
from __future__ import annotations

import importlib
from typing import Any, Dict, List, Tuple
from unittest.mock import MagicMock, patch


def _make_vs_mock(
    fields: Dict[str, str], path: List[Tuple[float, float, float]]
) -> MagicMock:
    vs_mock = MagicMock()
    null_handle = object()
    vs_mock.Handle.return_value = null_handle
    vs_mock.GetCustomObjectInfo.return_value = (
        True, '配筋', 'PIO_HANDLE', 'RECORD_HANDLE', 'WALL_HANDLE',
    )
    vs_mock.GetCustomObjectPath.return_value = 'PATH_HANDLE'
    vs_mock.GetVertNum.return_value = len(path)
    vs_mock.GetPolyPt3D.side_effect = lambda handle, index: path[index]
    vs_mock.GetRField.side_effect = (
        lambda handle, record, field: fields.get(field, '')
    )
    vs_mock.LNewObj.return_value = 'OBJ'
    vs_mock.Set2DComponentGroup.return_value = True
    vs_mock.GetClass.return_value = 'PIOクラス'
    return vs_mock


def _run(vs_mock: MagicMock) -> None:
    with patch.dict('sys.modules', {'vs': vs_mock}):
        import vectorworks_plugin_rebar as package
        import vectorworks_plugin_rebar.vw.component as vw_component
        import vectorworks_plugin_rebar.vw.draw as vw_draw
        import vectorworks_plugin_rebar.vw.pio as vw_pio
        import vectorworks_plugin_rebar.vw as vw
        importlib.reload(vw_draw)
        importlib.reload(vw_component)
        importlib.reload(vw_pio)
        importlib.reload(vw)
        package.run()


SLAB_FIELDS = {
    'Mode': 'スラブ',
    'MainBar': 'D10@200',
    'DistBar': 'D13@150',
    'MainBarAngle': '0.0',
    'DoubleLayer': 'False',
    'SlabThickness': '150.0',
    'Cover': '40.0',
    'MarkScale': '4.0',
}

RECT_PATH = [
    (0.0, 0.0, 0.0),
    (2000.0, 0.0, 0.0),
    (2000.0, 3000.0, 0.0),
    (0.0, 3000.0, 0.0),
]


class TestRun:
    def test_slab_reset_draws_all_representations(self) -> None:
        vs_mock = _make_vs_mock(SLAB_FIELDS, RECT_PATH)

        _run(vs_mock)

        # 平面 2D 線 + 断面線が描かれる
        assert vs_mock.MoveTo.call_count > 0
        # 3D 鉄筋が描かれる
        assert vs_mock.Poly3D.call_count > 0
        # Top/Plan (10) と両方の断面 2D コンポーネント (6/9) が設定される
        components = {
            c.args[2] for c in vs_mock.Set2DComponentGroup.call_args_list
        }
        assert components == {6, 9, 10}
        # Top/Plan ビューを Top(0)に固定する
        vs_mock.SetTopPlan2DComp.assert_called_once_with('PIO_HANDLE', 0)
        # 診断メッセージは出るがエラーではない
        assert vs_mock.Message.called
        message = vs_mock.Message.call_args_list[-1].args[0]
        assert message.startswith('配筋:')
        assert 'エラー' not in message

    def test_beam_reset(self) -> None:
        fields = {
            'Mode': '梁',
            'SectionSize': '300×600',
            'TopBars': '2-D16',
            'BottomBars': '3-D16',
            'Stirrup': 'D10@200',
            'Cover': '40.0',
            'MarkScale': '4.0',
        }
        vs_mock = _make_vs_mock(
            fields, [(0.0, 0.0, 0.0), (4000.0, 0.0, 0.0)]
        )

        _run(vs_mock)

        assert vs_mock.Poly3D.call_count > 0
        # 診断メッセージは出るがエラーではない
        message = vs_mock.Message.call_args_list[-1].args[0]
        assert message.startswith('配筋:')
        assert 'エラー' not in message

    def test_spec_error_shows_message_without_crash(self) -> None:
        fields = dict(SLAB_FIELDS, MainBar='xxx')
        vs_mock = _make_vs_mock(fields, RECT_PATH)

        _run(vs_mock)

        # 仕様の形式不正はステータスバーへ表示し、例外は外へ出さない
        assert vs_mock.Message.called
        message = vs_mock.Message.call_args.args[0]
        assert message.startswith('配筋: ')
        # 図形は描かれない
        assert not vs_mock.MoveTo.called

    def test_outside_pio_context_does_nothing(self) -> None:
        vs_mock = _make_vs_mock(SLAB_FIELDS, RECT_PATH)
        vs_mock.GetCustomObjectInfo.return_value = (False, '', None, None, None)

        _run(vs_mock)

        assert not vs_mock.MoveTo.called
        assert not vs_mock.Message.called
