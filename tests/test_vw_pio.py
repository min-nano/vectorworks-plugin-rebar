"""PIO コンテキスト読み取り (vw.pio) のテスト。vs をモックして検証する。"""
from __future__ import annotations

import importlib
from typing import Any, Dict, List, Tuple
from unittest.mock import MagicMock, patch


def _make_vs_mock(fields: Dict[str, str], path: List[Tuple[float, float, float]]) -> MagicMock:
    vs_mock = MagicMock()
    null_handle = object()
    vs_mock.Handle.return_value = null_handle
    vs_mock.GetCustomObjectInfo.return_value = (
        True, '配筋', 'PIO_HANDLE', 'RECORD_HANDLE', 'WALL_HANDLE',
    )
    vs_mock.GetCustomObjectPath.return_value = 'PATH_HANDLE'
    vs_mock.GetVertNum.return_value = len(path)
    vs_mock.GetPolyPt3D.side_effect = lambda handle, index: path[index]

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


SLAB_FIELDS = {
    'Mode': 'スラブ',
    'MainBar': 'D10@200',
    'DistBar': 'D13@150',
    'MainBarAngle': '0.0',
    'DoubleLayer': 'False',
    'TopMainBar': 'D10@200',
    'TopDistBar': 'D13@150',
    'SlabThickness': '150.0',
    'SectionSize': '150×450',
    'TopBars': '2-D16',
    'BottomBars': '2-D16',
    'Stirrup': 'D10@200',
    'Cover': '40.0',
    'MarkScale': '4.0',
}

PATH = [(0.0, 0.0, 0.0), (2000.0, 0.0, 0.0), (2000.0, 3000.0, 0.0)]


class TestReadPioInput:
    def test_reads_params_and_path(self) -> None:
        vs_mock = _make_vs_mock(SLAB_FIELDS, PATH)
        vw_pio = _load(vs_mock)

        result = vw_pio.read_pio_input()

        assert result is not None
        handle, params = result
        assert handle == 'PIO_HANDLE'
        assert params['mode'] == 'slab'
        assert params['main_bar'] == 'D10@200'
        assert params['dist_bar'] == 'D13@150'
        assert params['double_layer'] is False
        assert params['slab_thickness'] == 150.0
        assert params['cover'] == 40.0
        assert params['mark_scale'] == 4.0
        assert params['path'] == [
            [0.0, 0.0, 0.0],
            [2000.0, 0.0, 0.0],
            [2000.0, 3000.0, 0.0],
        ]

    def test_beam_mode_label(self) -> None:
        fields = dict(SLAB_FIELDS, Mode='梁')
        vw_pio = _load(_make_vs_mock(fields, PATH))

        result = vw_pio.read_pio_input()
        assert result is not None
        assert result[1]['mode'] == 'beam'

    def test_boolean_field_variants(self) -> None:
        for text, expected in (('True', True), ('1', True), ('False', False), ('0', False)):
            fields = dict(SLAB_FIELDS, DoubleLayer=text)
            vw_pio = _load(_make_vs_mock(fields, PATH))
            result = vw_pio.read_pio_input()
            assert result is not None
            assert result[1]['double_layer'] is expected

    def test_number_with_unit_suffix(self) -> None:
        # 数値フィールドは単位付き表記 ("150.0mm") でも読める
        fields = dict(SLAB_FIELDS, SlabThickness='150.0mm', Cover='40mm')
        vw_pio = _load(_make_vs_mock(fields, PATH))
        result = vw_pio.read_pio_input()
        assert result is not None
        assert result[1]['slab_thickness'] == 150.0
        assert result[1]['cover'] == 40.0

    def test_unparsable_number_omitted(self) -> None:
        # 解釈できない数値フィールドはキーを省き、既定値に委ねる
        fields = dict(SLAB_FIELDS, MarkScale='abc')
        vw_pio = _load(_make_vs_mock(fields, PATH))
        result = vw_pio.read_pio_input()
        assert result is not None
        assert 'mark_scale' not in result[1]

    def test_outside_pio_context_returns_none(self) -> None:
        vs_mock = _make_vs_mock(SLAB_FIELDS, PATH)
        vs_mock.GetCustomObjectInfo.return_value = (False, '', None, None, None)
        vw_pio = _load(vs_mock)

        assert vw_pio.read_pio_input() is None

    def test_missing_path_returns_empty(self) -> None:
        vs_mock = _make_vs_mock(SLAB_FIELDS, PATH)
        vs_mock.GetCustomObjectPath.return_value = vs_mock.Handle.return_value
        vw_pio = _load(vs_mock)

        result = vw_pio.read_pio_input()
        assert result is not None
        assert result[1]['path'] == []
