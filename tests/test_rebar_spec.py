"""配筋仕様文字列パース (rebar.spec) のテスト。vs モック不要。"""
from __future__ import annotations

import pytest

from vectorworks_plugin_rebar.rebar.spec import (
    BarCount,
    BarPitch,
    SectionSize,
    SpecError,
    parse_bar_count,
    parse_bar_pitch,
    parse_section_size,
)


class TestParseBarPitch:
    def test_basic(self) -> None:
        assert parse_bar_pitch('D10@200') == BarPitch(10.0, 200.0)

    def test_lowercase_and_spaces(self) -> None:
        assert parse_bar_pitch(' d13 @ 150 ') == BarPitch(13.0, 150.0)

    def test_full_width(self) -> None:
        # 全角の Ｄ・数字・＠ も NFKC 正規化で受け付ける
        assert parse_bar_pitch('Ｄ１０＠２００') == BarPitch(10.0, 200.0)

    def test_empty_returns_none(self) -> None:
        assert parse_bar_pitch('') is None
        assert parse_bar_pitch('   ') is None

    @pytest.mark.parametrize('text', ['D10', '10@200', 'D10@', 'D-10@200'])
    def test_invalid_raises(self, text: str) -> None:
        with pytest.raises(SpecError):
            parse_bar_pitch(text)

    def test_zero_pitch_raises(self) -> None:
        with pytest.raises(SpecError):
            parse_bar_pitch('D10@0')


class TestParseBarCount:
    def test_basic(self) -> None:
        assert parse_bar_count('2-D16') == BarCount(2, 16.0)

    def test_full_width(self) -> None:
        assert parse_bar_count('２－Ｄ１６') == BarCount(2, 16.0)

    def test_empty_returns_none(self) -> None:
        assert parse_bar_count('') is None

    @pytest.mark.parametrize('text', ['D16', '2D16', '2-16', '0-D16'])
    def test_invalid_raises(self, text: str) -> None:
        with pytest.raises(SpecError):
            parse_bar_count(text)


class TestParseSectionSize:
    def test_multiply_sign(self) -> None:
        assert parse_section_size('150×450') == SectionSize(150.0, 450.0)

    @pytest.mark.parametrize('text', ['150x450', '150X450', '150*450', '150 × 450'])
    def test_separator_variants(self, text: str) -> None:
        assert parse_section_size(text) == SectionSize(150.0, 450.0)

    def test_empty_returns_none(self) -> None:
        assert parse_section_size('') is None

    @pytest.mark.parametrize('text', ['150', '150×', '×450', '150×450×600'])
    def test_invalid_raises(self, text: str) -> None:
        with pytest.raises(SpecError):
            parse_section_size(text)

    def test_zero_raises(self) -> None:
        with pytest.raises(SpecError):
            parse_section_size('0×450')
