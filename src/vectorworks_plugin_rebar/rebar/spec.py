"""配筋仕様文字列のパース。vs に依存しない。

VectorWorks の OIP でユーザーが入力する仕様文字列を解釈する:

- 呼び径:        ``D10`` / ``10``    → 呼び径 10(紙面平行方向の鉄筋=線)
- 呼び径とピッチ: ``D13@200``         → (呼び径 13, ピッチ 200)
                                        (紙面直交方向の鉄筋=断面記号)

呼び径は表示記号の選択と記号の大きさ(``呼び径 × MarkScale``)に使う。
最外径(3D ソリッドの断面円)は 2D 注釈では使わないため保持しない。

全角文字(Ｄ・＠・全角数字)での入力にも耐えるよう、パース前に NFKC
正規化で半角へ揃える。空文字・空白のみの入力は「指定なし」として ``None``
を返し、形式不正は ``SpecError``(ValueError) を送出する(呼び出し側が
メッセージ表示に使う)。
"""
from __future__ import annotations

import re
import unicodedata
from typing import NamedTuple, Optional


class SpecError(ValueError):
    """配筋仕様文字列の形式不正。メッセージはユーザー向け(日本語)。"""


class NominalPitch(NamedTuple):
    """呼び径とピッチの仕様 (例 D13@200)。"""

    nominal: int   # 呼び径 (mm)
    pitch: float   # ピッチ (mm)


_NUMBER = r'\d+(?:\.\d+)?'
_BAR_RE = re.compile(rf'^D?\s*({_NUMBER})$', re.IGNORECASE)
_BAR_PITCH_RE = re.compile(rf'^D?\s*({_NUMBER})\s*@\s*({_NUMBER})$', re.IGNORECASE)


def _normalize(text: str) -> str:
    """全角英数字・記号を半角へ正規化し、前後の空白を除く。"""
    return unicodedata.normalize('NFKC', text).strip()


def parse_nominal(text: str) -> Optional[int]:
    """``D10`` / ``10`` 形式(呼び径)をパースする。空入力は None。"""
    normalized = _normalize(text)
    if not normalized:
        return None
    match = _BAR_RE.match(normalized)
    if match is None:
        raise SpecError(f'鉄筋径を解釈できません(D10 の形式): {text!r}')
    value = float(match.group(1))
    if value <= 0:
        raise SpecError(f'鉄筋径は正の値にしてください: {text!r}')
    return int(round(value))


def parse_nominal_pitch(text: str) -> Optional[NominalPitch]:
    """``D13@200`` 形式(呼び径@ピッチ)をパースする。空入力は None。"""
    normalized = _normalize(text)
    if not normalized:
        return None
    match = _BAR_PITCH_RE.match(normalized)
    if match is None:
        raise SpecError(f'鉄筋仕様を解釈できません(D13@200 の形式): {text!r}')
    nominal = float(match.group(1))
    pitch = float(match.group(2))
    if nominal <= 0 or pitch <= 0:
        raise SpecError(f'鉄筋仕様の径・ピッチは正の値にしてください: {text!r}')
    return NominalPitch(int(round(nominal)), pitch)
