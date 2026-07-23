"""配筋仕様文字列のパース (rebar.spec) のテスト。vs 非依存。"""
from __future__ import annotations

import pytest

from vectorworks_plugin_rebar.rebar.spec import (
    NominalPitch,
    SpecError,
    parse_nominal,
    parse_nominal_pitch,
)


class TestParseNominal:
    def test_with_d_prefix(self) -> None:
        assert parse_nominal('D10') == 10

    def test_without_prefix(self) -> None:
        assert parse_nominal('13') == 13

    def test_lowercase_and_spaces(self) -> None:
        assert parse_nominal(' d 16 ') == 16

    def test_fullwidth(self) -> None:
        assert parse_nominal('Ｄ１９') == 19

    def test_blank_returns_none(self) -> None:
        assert parse_nominal('') is None
        assert parse_nominal('   ') is None

    def test_rounds_to_int(self) -> None:
        assert parse_nominal('D9.6') == 10

    def test_invalid_raises(self) -> None:
        with pytest.raises(SpecError):
            parse_nominal('abc')

    def test_zero_raises(self) -> None:
        with pytest.raises(SpecError):
            parse_nominal('D0')


class TestParseNominalPitch:
    def test_basic(self) -> None:
        assert parse_nominal_pitch('D13@200') == NominalPitch(13, 200.0)

    def test_without_prefix(self) -> None:
        assert parse_nominal_pitch('13@150') == NominalPitch(13, 150.0)

    def test_fullwidth_at(self) -> None:
        assert parse_nominal_pitch('Ｄ１０＠２００') == NominalPitch(10, 200.0)

    def test_spaces(self) -> None:
        assert parse_nominal_pitch('D 13 @ 250') == NominalPitch(13, 250.0)

    def test_blank_returns_none(self) -> None:
        assert parse_nominal_pitch('') is None

    def test_missing_pitch_raises(self) -> None:
        with pytest.raises(SpecError):
            parse_nominal_pitch('D13')

    def test_invalid_raises(self) -> None:
        with pytest.raises(SpecError):
            parse_nominal_pitch('D13x200')

    def test_nonpositive_raises(self) -> None:
        with pytest.raises(SpecError):
            parse_nominal_pitch('D13@0')
