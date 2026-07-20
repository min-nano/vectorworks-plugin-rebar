"""命令セットの検証 (document.validate_document) のテスト。vs 非依存。"""
from __future__ import annotations

from typing import Any, Dict

import pytest

from vectorworks_plugin_rebar.document import DOCUMENT_VERSION, validate_document


def _valid() -> Dict[str, Any]:
    return {
        'version': DOCUMENT_VERSION,
        'lines': [{'start': [0.0, 45.0], 'end': [1000.0, 45.0]}],
        'symbol_profiles': [
            {'kind': 'line', 'start': [-26.0, -26.0], 'end': [26.0, 26.0]},
            {'kind': 'line', 'start': [-26.0, 26.0], 'end': [26.0, -26.0]},
        ],
        'mark_centers': [[100.0, 45.0], [300.0, 45.0]],
    }


class TestValidateDocument:
    def test_valid_passes(self) -> None:
        assert validate_document(_valid()) is not None

    def test_not_dict(self) -> None:
        with pytest.raises(ValueError):
            validate_document([])

    def test_wrong_version(self) -> None:
        doc = _valid()
        doc['version'] = 1
        with pytest.raises(ValueError):
            validate_document(doc)

    def test_lines_not_list(self) -> None:
        doc = _valid()
        doc['lines'] = 'nope'
        with pytest.raises(ValueError):
            validate_document(doc)

    def test_line_bad_point(self) -> None:
        doc = _valid()
        doc['lines'][0]['start'] = [0.0]
        with pytest.raises(ValueError):
            validate_document(doc)

    def test_lines_empty_ok(self) -> None:
        doc = _valid()
        doc['lines'] = []
        assert validate_document(doc) is not None

    def test_profiles_not_list(self) -> None:
        doc = _valid()
        doc['symbol_profiles'] = {}
        with pytest.raises(ValueError):
            validate_document(doc)

    def test_circle_profile_ok(self) -> None:
        doc = _valid()
        doc['symbol_profiles'] = [
            {'kind': 'circle', 'center': [0.0, 0.0], 'radius': 26.0, 'filled': True}
        ]
        assert validate_document(doc) is not None

    def test_circle_bad_radius(self) -> None:
        doc = _valid()
        doc['symbol_profiles'] = [
            {'kind': 'circle', 'center': [0.0, 0.0], 'radius': 0, 'filled': True}
        ]
        with pytest.raises(ValueError):
            validate_document(doc)

    def test_circle_missing_filled(self) -> None:
        doc = _valid()
        doc['symbol_profiles'] = [
            {'kind': 'circle', 'center': [0.0, 0.0], 'radius': 26.0}
        ]
        with pytest.raises(ValueError):
            validate_document(doc)

    def test_profile_bad_kind(self) -> None:
        doc = _valid()
        doc['symbol_profiles'][0]['kind'] = 'star'
        with pytest.raises(ValueError):
            validate_document(doc)

    def test_empty_profiles_ok(self) -> None:
        doc = _valid()
        doc['symbol_profiles'] = []
        assert validate_document(doc) is not None

    def test_mark_centers_required(self) -> None:
        doc = _valid()
        del doc['mark_centers']
        with pytest.raises(ValueError):
            validate_document(doc)

    def test_mark_centers_not_list(self) -> None:
        doc = _valid()
        doc['mark_centers'] = [100.0, 45.0]
        with pytest.raises(ValueError):
            validate_document(doc)

    def test_mark_centers_bad_point(self) -> None:
        doc = _valid()
        doc['mark_centers'] = [[1.0, 2.0, 3.0]]
        with pytest.raises(ValueError):
            validate_document(doc)

    def test_mark_centers_empty_ok(self) -> None:
        doc = _valid()
        doc['mark_centers'] = []
        assert validate_document(doc) is not None
