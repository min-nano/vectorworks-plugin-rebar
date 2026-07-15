"""平面幾何の共通処理。vs に依存しない。

スラブ配筋の中核となる「等間隔の平行線族を任意多角形でクリップする」
処理を提供する。結果は多角形の頂点順・線の生成順に対して決定的。
"""
from __future__ import annotations

import math
from typing import List, Sequence, Tuple

Point2D = Tuple[float, float]
Segment2D = Tuple[Point2D, Point2D]

# 長さ・座標の比較に使う許容値 (mm)。これより短いクリップ結果は捨てる。
_EPS = 1e-6


def direction_vectors(angle_deg: float) -> Tuple[Point2D, Point2D]:
    """角度(度)から線の方向単位ベクトル d と法線単位ベクトル n を返す。

    n は d を反時計回りに 90 度回した向き。線族は n 方向にピッチ間隔で並ぶ。
    """
    radians = math.radians(angle_deg)
    d = (math.cos(radians), math.sin(radians))
    n = (-d[1], d[0])
    return d, n


def polygon_centroid(polygon: Sequence[Point2D]) -> Point2D:
    """多角形の面積重心を返す。面積が退化している場合は頂点平均。

    線族の基準位置(センタリング)に使うため、頂点の並び順(時計/反時計)や
    重複頂点に依存しない安定した点であればよい。
    """
    area2 = 0.0
    cx = 0.0
    cy = 0.0
    count = len(polygon)
    for i in range(count):
        x1, y1 = polygon[i]
        x2, y2 = polygon[(i + 1) % count]
        cross = x1 * y2 - x2 * y1
        area2 += cross
        cx += (x1 + x2) * cross
        cy += (y1 + y2) * cross
    if abs(area2) < _EPS:
        return (
            sum(p[0] for p in polygon) / count,
            sum(p[1] for p in polygon) / count,
        )
    return (cx / (3.0 * area2), cy / (3.0 * area2))


def clip_line_family(
    polygon: Sequence[Point2D], angle_deg: float, pitch: float
) -> List[Segment2D]:
    """多角形を angle_deg 方向・pitch 間隔の平行線族でクリップする。

    線族は多角形の重心を通る線を基準に法線方向へ ±pitch 刻みで並べる
    (重心基準にすることで両端の余りが対称になり、頂点列の平行移動に
    対して結果が安定する)。各線と多角形の交差区間を偶奇則で求め、
    線分のリストを返す。凹多角形では 1 本の線が複数線分に分かれる。

    多角形の頂点が 3 未満・pitch が非正の場合は空リストを返す。
    """
    if len(polygon) < 3 or pitch <= 0:
        return []
    d, n = direction_vectors(angle_deg)
    centroid = polygon_centroid(polygon)
    t_center = n[0] * centroid[0] + n[1] * centroid[1]
    t_values = [n[0] * p[0] + n[1] * p[1] for p in polygon]
    t_min = min(t_values)
    t_max = max(t_values)
    k_min = math.ceil((t_min - t_center) / pitch - _EPS)
    k_max = math.floor((t_max - t_center) / pitch + _EPS)

    segments: List[Segment2D] = []
    for k in range(k_min, k_max + 1):
        t = t_center + k * pitch
        # 多角形の境界ちょうどに乗る線は除外する(境界上では偶奇則の
        # 交差判定が辺の向きに依存して非対称になるため、両端とも
        # 決定的に描かない)
        if t <= t_min + _EPS or t >= t_max - _EPS:
            continue
        crossings: List[float] = []
        for i in range(len(polygon)):
            ax, ay = polygon[i]
            bx, by = polygon[(i + 1) % len(polygon)]
            ta = n[0] * ax + n[1] * ay - t
            tb = n[0] * bx + n[1] * by - t
            # 半開区間規則: 線上ちょうどの頂点(ta==0)は負側として扱い、
            # 頂点を通る線の交差を二重に数えない
            if (ta > 0.0) == (tb > 0.0):
                continue
            fraction = ta / (ta - tb)
            px = ax + (bx - ax) * fraction
            py = ay + (by - ay) * fraction
            crossings.append(d[0] * px + d[1] * py)
        crossings.sort()
        # 偶奇則: 交点をソートしてペアごとに内部区間とする。数値誤差で
        # 奇数個になった場合は最後の 1 点を捨てる
        for j in range(0, len(crossings) - 1, 2):
            u1 = crossings[j]
            u2 = crossings[j + 1]
            if u2 - u1 < _EPS:
                continue
            start = (u1 * d[0] + t * n[0], u1 * d[1] + t * n[1])
            end = (u2 * d[0] + t * n[0], u2 * d[1] + t * n[1])
            segments.append((start, end))
    return segments
