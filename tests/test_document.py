"""命令セットの検証 (document.validate_document) のテスト。vs モック不要。"""
from __future__ import annotations

from typing import Any, Dict

import pytest

from vectorworks_plugin_rebar.document import (
    DOCUMENT_VERSION,
    validate_document,
)


def make_document(**overrides: Any) -> Dict[str, Any]:
    document: Dict[str, Any] = {
        'version': DOCUMENT_VERSION,
        'plan_lines': [
            {'class': 'C', 'start': [0.0, 0.0], 'end': [100.0, 0.0]},
        ],
        'cut_lines': [
            {
                'target': 'front_back',
                'class': 'C',
                'start': [0.0, -75.0],
                'end': [100.0, -75.0],
            },
        ],
        'bars_3d': [
            {
                'class': 'C',
                'vertices': [[0.0, 0.0, -75.0], [100.0, 0.0, -75.0]],
                'closed': False,
            },
        ],
    }
    document.update(overrides)
    return document


class TestValidateDocument:
    def test_valid_document_passes(self) -> None:
        assert validate_document(make_document()) is not None

    def test_empty_lists_pass(self) -> None:
        validate_document(
            make_document(plan_lines=[], cut_lines=[], bars_3d=[])
        )

    def test_not_a_dict(self) -> None:
        with pytest.raises(ValueError):
            validate_document([])

    def test_wrong_version(self) -> None:
        with pytest.raises(ValueError):
            validate_document(make_document(version=99))

    def test_missing_key(self) -> None:
        document = make_document()
        del document['cut_lines']
        with pytest.raises(ValueError):
            validate_document(document)

    def test_bad_cut_target(self) -> None:
        document = make_document()
        document['cut_lines'][0]['target'] = 'top'
        with pytest.raises(ValueError):
            validate_document(document)

    def test_bad_point(self) -> None:
        document = make_document()
        document['plan_lines'][0]['start'] = [0.0]
        with pytest.raises(ValueError):
            validate_document(document)

    def test_empty_class(self) -> None:
        document = make_document()
        document['plan_lines'][0]['class'] = ''
        with pytest.raises(ValueError):
            validate_document(document)

    def test_bar_needs_two_vertices(self) -> None:
        document = make_document()
        document['bars_3d'][0]['vertices'] = [[0.0, 0.0, 0.0]]
        with pytest.raises(ValueError):
            validate_document(document)

    def test_bar_vertex_must_be_3d(self) -> None:
        document = make_document()
        document['bars_3d'][0]['vertices'] = [[0.0, 0.0], [1.0, 1.0]]
        with pytest.raises(ValueError):
            validate_document(document)

    def test_bar_closed_must_be_bool(self) -> None:
        document = make_document()
        document['bars_3d'][0]['closed'] = 1
        with pytest.raises(ValueError):
            validate_document(document)
