"""命令セット組み立て (rebar.build_document) のテスト。vs 非依存。"""
from __future__ import annotations

from typing import Any, Dict

import pytest

from vectorworks_plugin_rebar.document import DOCUMENT_VERSION, validate_document
from vectorworks_plugin_rebar.rebar import SpecError, build_document


def _params(**overrides: Any) -> Dict[str, Any]:
    params: Dict[str, Any] = {
        'line': [[0.0, 0.0], [1000.0, 0.0]],
        'parallel_bar': 'D10',
        'perp_bar': 'D13@200',
        'cover': 40.0,
        'mark_scale': 4.0,
        'flip': False,
    }
    params.update(overrides)
    return params


class TestBuildDocument:
    def test_builds_valid_document(self) -> None:
        doc = build_document(_params())
        assert doc['version'] == DOCUMENT_VERSION
        # 検証を通ること(スキーマ整合)
        assert validate_document(doc) is not None

    def test_has_line_and_marks(self) -> None:
        doc = build_document(_params())
        assert len(doc['lines']) == 1
        assert len(doc['mark_centers']) == 5
        assert doc['symbol_profiles']  # D13 の × 記号

    def test_defaults_used_when_missing(self) -> None:
        # 仕様文字列を省いても既定値 (D10 / D13@200) で組める
        doc = build_document({'line': [[0.0, 0.0], [500.0, 0.0]]})
        assert doc['lines']
        assert doc['mark_centers']

    def test_missing_line_raises(self) -> None:
        with pytest.raises(SpecError):
            build_document({'parallel_bar': 'D10', 'perp_bar': 'D13@200'})

    def test_bad_line_shape_raises(self) -> None:
        with pytest.raises(SpecError):
            build_document(_params(line=[[0.0, 0.0]]))

    def test_bad_perp_spec_raises(self) -> None:
        with pytest.raises(SpecError):
            build_document(_params(perp_bar='D13'))  # ピッチなし

    def test_negative_cover_raises(self) -> None:
        with pytest.raises(SpecError):
            build_document(_params(cover=-5.0))

    def test_nonpositive_mark_scale_falls_back(self) -> None:
        # mark_scale <= 0 は既定 4.0 に丸める(例外にしない)
        doc = build_document(_params(mark_scale=0.0))
        assert doc['symbol_profiles']

    def test_json_serializable(self) -> None:
        import json

        doc = build_document(_params())
        assert json.loads(json.dumps(doc)) == doc
