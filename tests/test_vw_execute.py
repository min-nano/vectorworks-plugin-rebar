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
        'lines': [{'start': [0.0, 45.0], 'end': [1000.0, 45.0]}],
        'symbol_profiles': [
            {'kind': 'circle', 'center': [0.0, 0.0], 'radius': 26.0, 'filled': False},
            {'kind': 'circle', 'center': [0.0, 0.0], 'radius': 6.0, 'filled': True},
            {'kind': 'line', 'start': [-18.0, -18.0], 'end': [18.0, 18.0]},
        ],
        'mark_centers': [[100.0, 45.0], [300.0, 45.0]],
    }


def _make_vs_mock() -> MagicMock:
    vs_mock = MagicMock()
    null_handle = object()
    vs_mock.Handle.return_value = null_handle

    counter = {'n': 0}

    def unique() -> str:
        counter['n'] += 1
        return f'OBJ_{counter["n"]}'

    vs_mock.LNewObj.side_effect = unique
    vs_mock.GetClass.return_value = 'PIOクラス'
    return vs_mock


def _load(vs_mock: MagicMock) -> Any:
    with patch.dict('sys.modules', {'vs': vs_mock}):
        import vectorworks_plugin_rebar.vw.draw as vw_draw
        import vectorworks_plugin_rebar.vw as vw
        importlib.reload(vw_draw)
        importlib.reload(vw)
        return vw


class TestExecuteDocument:
    def test_counts(self) -> None:
        vs_mock = _make_vs_mock()
        vw = _load(vs_mock)

        result = vw.execute_document(make_document(), PIO_HANDLE)

        assert result['lines'] == 1
        assert result['marks'] == 2

    def test_line_drawn(self) -> None:
        vs_mock = _make_vs_mock()
        vw = _load(vs_mock)

        vw.execute_document(make_document(), PIO_HANDLE)

        starts = {c.args[0] for c in vs_mock.MoveTo.call_args_list}
        assert (0.0, 45.0) in starts

    def test_marks_translated_to_each_center(self) -> None:
        vs_mock = _make_vs_mock()
        vw = _load(vs_mock)

        vw.execute_document(make_document(), PIO_HANDLE)

        # 記号の線(-18,-18)〜(18,18)が各記号位置へ平行移動して描かれる
        starts = {c.args[0] for c in vs_mock.MoveTo.call_args_list}
        assert (82.0, 27.0) in starts    # 中心 (100,45) + (-18,-18)
        assert (282.0, 27.0) in starts   # 中心 (300,45) + (-18,-18)

    def test_circle_marks_use_oval_and_fpat(self) -> None:
        vs_mock = _make_vs_mock()
        vw = _load(vs_mock)

        vw.execute_document(make_document(), PIO_HANDLE)

        assert vs_mock.Oval.called
        # 輪郭(filled=false)=0・塗り(filled=true)=1 の両方が設定される
        fpats = {c.args[1] for c in vs_mock.SetFPat.call_args_list}
        assert fpats == {0, 1}

    def test_circle_center_translated(self) -> None:
        vs_mock = _make_vs_mock()
        vw = _load(vs_mock)

        vw.execute_document(make_document(), PIO_HANDLE)

        # 中心 (100,45)・半径 26 の輪郭円 → Oval の左上 = (100-26, 45+26) = (74, 71)
        top_lefts = {c.args[0] for c in vs_mock.Oval.call_args_list}
        assert (74.0, 71.0) in top_lefts

    def test_all_on_pio_class(self) -> None:
        vs_mock = _make_vs_mock()
        vw = _load(vs_mock)

        vw.execute_document(make_document(), PIO_HANDLE)

        classes = {c.args[1] for c in vs_mock.SetClass.call_args_list}
        assert classes == {'PIOクラス'}

    def test_no_marks_when_empty_centers(self) -> None:
        vs_mock = _make_vs_mock()
        vw = _load(vs_mock)

        document = make_document()
        document['mark_centers'] = []
        result = vw.execute_document(document, PIO_HANDLE)

        assert result['marks'] == 0
        assert not vs_mock.Oval.called

    def test_invalid_document_raises(self) -> None:
        vs_mock = _make_vs_mock()
        vw = _load(vs_mock)

        try:
            vw.execute_document({'version': 99}, PIO_HANDLE)
        except ValueError:
            pass
        else:
            raise AssertionError('ValueError が送出されるべき')
        assert not vs_mock.MoveTo.called
