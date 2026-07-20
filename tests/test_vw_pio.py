"""PIO コンテキスト読み取り (vw.pio) のテスト。vs をモックして検証する。"""
from __future__ import annotations

import importlib
from typing import Any, Dict, Tuple
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

    def get_r_field(handle: str, record: str, field: str) -> str:
        assert handle == 'PIO_HANDLE'
        assert record == '配筋'
        return fields.get(field, '')

    vs_mock.GetRField.side_effect = get_r_field
    return vs_mock


def _load(vs_mock: MagicMock) -> Any:
    with patch.dict('sys.modules', {'vs': vs_mock}):
        import vectorworks_plugin_rebar.vw.pio as vw_pio
        importlib.reload(vw_pio)
        return vw_pio


FIELDS = {
    'ParallelBar': 'D10',
    'PerpBar': 'D13@200',
    'Cover': '40.0',
    'MarkScale': '4.0',
    'Flip': 'False',
}


class TestReadPioInput:
    def test_reads_params_and_line(self) -> None:
        vw_pio = _load(_make_vs_mock(FIELDS))

        result = vw_pio.read_pio_input()

        assert result is not None
        handle, params = result
        assert handle == 'PIO_HANDLE'
        assert params['line'] == [[0.0, 0.0], [1000.0, 0.0]]
        assert params['parallel_bar'] == 'D10'
        assert params['perp_bar'] == 'D13@200'
        assert params['cover'] == 40.0
        assert params['mark_scale'] == 4.0
        assert params['flip'] is False

    def test_reads_line_endpoints(self) -> None:
        vw_pio = _load(_make_vs_mock(FIELDS, p1=(100.0, 200.0), p2=(100.0, 900.0)))
        result = vw_pio.read_pio_input()
        assert result is not None
        assert result[1]['line'] == [[100.0, 200.0], [100.0, 900.0]]

    def test_flip_true(self) -> None:
        fields = dict(FIELDS, Flip='True')
        vw_pio = _load(_make_vs_mock(fields))
        result = vw_pio.read_pio_input()
        assert result is not None
        assert result[1]['flip'] is True

    def test_number_with_unit_suffix(self) -> None:
        fields = dict(FIELDS, Cover='40.0mm')
        vw_pio = _load(_make_vs_mock(fields))
        result = vw_pio.read_pio_input()
        assert result is not None
        assert result[1]['cover'] == 40.0

    def test_unparsable_number_omitted(self) -> None:
        fields = dict(FIELDS, Cover='auto')
        vw_pio = _load(_make_vs_mock(fields))
        result = vw_pio.read_pio_input()
        assert result is not None
        assert 'cover' not in result[1]

    def test_outside_pio_context_returns_none(self) -> None:
        vs_mock = _make_vs_mock(FIELDS)
        vs_mock.GetCustomObjectInfo.return_value = (False, '', None, None, None)
        vw_pio = _load(vs_mock)

        assert vw_pio.read_pio_input() is None
