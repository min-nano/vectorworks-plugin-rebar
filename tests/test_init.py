"""run() (PIO リセット全体のパイプライン) の統合テスト。vs をモックして検証する。"""
from __future__ import annotations

import importlib
from typing import Dict, Tuple
from unittest.mock import MagicMock, patch


def _make_vs_mock(
    fields: Dict[str, str],
    p1: Tuple[float, float] = (0.0, 0.0),
    p2: Tuple[float, float] = (1000.0, 0.0),
) -> MagicMock:
    vs_mock = MagicMock()
    null_handle = object()
    vs_mock.Handle.return_value = null_handle
    vs_mock.GetCustomObjectInfo.return_value = (
        True, '配筋', 'PIO_HANDLE', 'RECORD_HANDLE', 'WALL_HANDLE',
    )
    vs_mock.GetSegPt1.return_value = p1
    vs_mock.GetSegPt2.return_value = p2
    vs_mock.GetRField.side_effect = (
        lambda handle, record, field: fields.get(field, '')
    )
    counter = {'n': 0}

    def unique() -> str:
        counter['n'] += 1
        return f'OBJ_{counter["n"]}'

    vs_mock.LNewObj.side_effect = unique
    vs_mock.GetClass.return_value = 'PIOクラス'
    return vs_mock


def _run(vs_mock: MagicMock) -> None:
    with patch.dict('sys.modules', {'vs': vs_mock}):
        import vectorworks_plugin_rebar as package
        import vectorworks_plugin_rebar.vw.draw as vw_draw
        import vectorworks_plugin_rebar.vw.pio as vw_pio
        import vectorworks_plugin_rebar.vw as vw
        importlib.reload(vw_draw)
        importlib.reload(vw_pio)
        importlib.reload(vw)
        package.run()


FIELDS = {
    'ParallelBar': 'D10',
    'PerpBar': 'D13@200',
    'Cover': '40.0',
    'MarkScale': '4.0',
    'Flip': 'False',
}


class TestRun:
    def test_reset_draws_line_and_marks(self) -> None:
        vs_mock = _make_vs_mock(FIELDS)

        _run(vs_mock)

        # オフセット線 + 記号(D13 の ×)の 2D 図形が描かれる
        assert vs_mock.MoveTo.call_count > 0
        assert vs_mock.LineTo.call_count > 0
        # すべて PIO 本体クラスに割り当てられる
        classes = {c.args[1] for c in vs_mock.SetClass.call_args_list}
        assert classes == {'PIOクラス'}
        # 正常時はエラーメッセージを出さない
        assert not vs_mock.Message.called

    def test_circle_symbol_drawn(self) -> None:
        # D22 は ○(輪郭円)。円記号が Oval で描かれる
        fields = dict(FIELDS, PerpBar='D22@200')
        vs_mock = _make_vs_mock(fields)

        _run(vs_mock)

        assert vs_mock.Oval.called

    def test_spec_error_shows_message_without_crash(self) -> None:
        fields = dict(FIELDS, PerpBar='xxx')
        vs_mock = _make_vs_mock(fields)

        _run(vs_mock)

        assert vs_mock.Message.called
        message = vs_mock.Message.call_args.args[0]
        assert message.startswith('配筋: ')
        assert not vs_mock.MoveTo.called

    def test_zero_length_line_shows_message(self) -> None:
        vs_mock = _make_vs_mock(FIELDS, p1=(5.0, 5.0), p2=(5.0, 5.0))

        _run(vs_mock)

        assert vs_mock.Message.called

    def test_outside_pio_context_does_nothing(self) -> None:
        vs_mock = _make_vs_mock(FIELDS)
        vs_mock.GetCustomObjectInfo.return_value = (False, '', None, None, None)

        _run(vs_mock)

        assert not vs_mock.MoveTo.called
        assert not vs_mock.Message.called
