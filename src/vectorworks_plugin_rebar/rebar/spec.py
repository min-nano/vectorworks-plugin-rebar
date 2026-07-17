"""配筋仕様文字列のパース。vs に依存しない。

VectorWorks の OIP でユーザーが入力する仕様文字列を解釈する:

- 径とピッチ: ``D10@200`` → (径 10, ピッチ 200)
- 本数と径:   ``2-D16``   → (本数 2, 径 16)
- 断面サイズ: ``150×450`` → (幅 150, せい 450)
- せん断補強筋: ``D10@200`` / ``2-D10@250`` → (径, ピッチ, 脚数)。
  先頭の脚数(1/2/3)でせん断補強筋の配置を切り替える(省略時は 2)。

全角文字(Ｄ・＠・×・全角数字)での入力にも耐えるよう、パース前に
NFKC 正規化で半角へ揃える。区切りの ``×`` は ``x``/``X``/``*`` も受け付ける。
空文字・空白のみの入力は「指定なし」として ``None`` を返し、形式不正は
``SpecError``(ValueError) を送出する(呼び出し側がメッセージ表示に使う)。
"""
from __future__ import annotations

import re
import unicodedata
from typing import NamedTuple, Optional


class SpecError(ValueError):
    """配筋仕様文字列の形式不正。メッセージはユーザー向け(日本語)。"""


class BarPitch(NamedTuple):
    """径とピッチの仕様 (例 D10@200)。"""

    diameter: float  # 呼び径 (mm)
    pitch: float     # ピッチ (mm)


class BarCount(NamedTuple):
    """本数と径の仕様 (例 2-D16)。

    本数のフィールド名は ``tuple.count`` メソッドと衝突しないよう
    ``quantity`` とする。
    """

    quantity: int    # 本数
    diameter: float  # 呼び径 (mm)


class SectionSize(NamedTuple):
    """矩形断面サイズの仕様 (例 150×450)。"""

    width: float   # 幅 (mm)
    depth: float   # せい (mm)


class StirrupSpec(NamedTuple):
    """せん断補強筋の仕様 (例 D10@200 / 2-D10@250)。

    先頭の脚数でせん断補強筋の配置を切り替える:
    1=縦筋 1 本のみ(180° フック)、2=四角状のあばら筋(135° フック)、
    3=四角のあばら筋の内部に縦筋(180° フック)。省略時は 2。
    本数のフィールド名は ``tuple.count`` メソッドと衝突しないよう ``legs``。
    """

    diameter: float  # 呼び径 (mm)
    pitch: float     # ピッチ (mm)
    legs: int        # 脚数 (1 / 2 / 3)


_NUMBER = r'\d+(?:\.\d+)?'
_BAR_PITCH_RE = re.compile(rf'^D\s*({_NUMBER})\s*@\s*({_NUMBER})$', re.IGNORECASE)
_BAR_COUNT_RE = re.compile(rf'^(\d+)\s*-\s*D\s*({_NUMBER})$', re.IGNORECASE)
_SECTION_RE = re.compile(rf'^({_NUMBER})\s*[x*]\s*({_NUMBER})$', re.IGNORECASE)
_STIRRUP_RE = re.compile(
    rf'^(?:(\d+)\s*-\s*)?D\s*({_NUMBER})\s*@\s*({_NUMBER})$', re.IGNORECASE
)

# せん断補強筋の脚数として受け付ける値 (配置モード)。
STIRRUP_LEGS = (1, 2, 3)
DEFAULT_STIRRUP_LEGS = 2


def _normalize(text: str) -> str:
    """全角英数字・記号を半角へ正規化し、前後の空白を除く。

    NFKC は ``Ｄ１０＠２００`` を ``D10@200`` に揃えるが、乗算記号
    ``×``(U+00D7) は変換されないため個別に ``x`` へ置き換える。
    """
    return unicodedata.normalize('NFKC', text).replace('×', 'x').strip()


def parse_bar_pitch(text: str) -> Optional[BarPitch]:
    """``D10@200`` 形式(径@ピッチ)をパースする。空入力は None。"""
    normalized = _normalize(text)
    if not normalized:
        return None
    match = _BAR_PITCH_RE.match(normalized)
    if match is None:
        raise SpecError(f'鉄筋仕様を解釈できません(D10@200 の形式): {text!r}')
    diameter = float(match.group(1))
    pitch = float(match.group(2))
    if diameter <= 0 or pitch <= 0:
        raise SpecError(f'鉄筋仕様の径・ピッチは正の値にしてください: {text!r}')
    return BarPitch(diameter, pitch)


def parse_bar_count(text: str) -> Optional[BarCount]:
    """``2-D16`` 形式(本数-径)をパースする。空入力は None。"""
    normalized = _normalize(text)
    if not normalized:
        return None
    match = _BAR_COUNT_RE.match(normalized)
    if match is None:
        raise SpecError(f'主筋仕様を解釈できません(2-D16 の形式): {text!r}')
    count = int(match.group(1))
    diameter = float(match.group(2))
    if count <= 0 or diameter <= 0:
        raise SpecError(f'主筋仕様の本数・径は正の値にしてください: {text!r}')
    return BarCount(count, diameter)


def parse_stirrup(text: str) -> Optional[StirrupSpec]:
    """``D10@200`` / ``2-D10@250`` 形式(任意の脚数-径@ピッチ)をパースする。

    先頭の脚数(1/2/3)でせん断補強筋の配置を切り替える。脚数を省略した
    ``D10@200`` は 2(四角状のあばら筋)として扱う。空入力は None。
    """
    normalized = _normalize(text)
    if not normalized:
        return None
    match = _STIRRUP_RE.match(normalized)
    if match is None:
        raise SpecError(
            f'せん断補強筋仕様を解釈できません(D10@200 / 2-D10@250 の形式): {text!r}'
        )
    legs = int(match.group(1)) if match.group(1) is not None else DEFAULT_STIRRUP_LEGS
    diameter = float(match.group(2))
    pitch = float(match.group(3))
    if diameter <= 0 or pitch <= 0:
        raise SpecError(f'せん断補強筋の径・ピッチは正の値にしてください: {text!r}')
    if legs not in STIRRUP_LEGS:
        raise SpecError(
            f'せん断補強筋の脚数(先頭の本数)は 1・2・3 のいずれかにしてください: {text!r}'
        )
    return StirrupSpec(diameter, pitch, legs)


def parse_section_size(text: str) -> Optional[SectionSize]:
    """``150×450`` 形式(幅×せい)をパースする。空入力は None。"""
    normalized = _normalize(text)
    if not normalized:
        return None
    match = _SECTION_RE.match(normalized)
    if match is None:
        raise SpecError(f'断面サイズを解釈できません(150×450 の形式): {text!r}')
    width = float(match.group(1))
    depth = float(match.group(2))
    if width <= 0 or depth <= 0:
        raise SpecError(f'断面サイズは正の値にしてください: {text!r}')
    return SectionSize(width, depth)
