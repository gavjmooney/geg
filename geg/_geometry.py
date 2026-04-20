"""Canonical geometry helpers for the metrics package.

All functions operate on plain tuples/lists of (x, y) in screen coordinates
(y increases downwards, matching SVG). Metric modules should import from here
rather than reimplementing distance/angle/bbox logic.
"""

from __future__ import annotations

import math
from typing import Iterable, Optional, Sequence, Tuple

Point = Tuple[float, float]
Vector = Tuple[float, float]
BoundingBox = Tuple[float, float, float, float]
SegmentHit = Tuple[Point, float]  # ((x, y), angle_in_degrees)


def distance(a: Point, b: Point) -> float:
    return math.hypot(b[0] - a[0], b[1] - a[1])


def squared_distance(a: Point, b: Point) -> float:
    dx = b[0] - a[0]
    dy = b[1] - a[1]
    return dx * dx + dy * dy


def angle_between(v1: Vector, v2: Vector) -> float:
    """Unsigned angle between two 2D vectors, in radians, in [0, pi].

    Raises ValueError if either vector has zero magnitude.
    """
    n1 = math.hypot(*v1)
    n2 = math.hypot(*v2)
    if n1 == 0 or n2 == 0:
        raise ValueError("angle_between is undefined for zero-magnitude vectors")
    cos_theta = (v1[0] * v2[0] + v1[1] * v2[1]) / (n1 * n2)
    # Clamp to guard against floating-point drift outside [-1, 1].
    cos_theta = max(-1.0, min(1.0, cos_theta))
    return math.acos(cos_theta)


def acute_angle_between(v1: Vector, v2: Vector) -> float:
    """Angle folded into [0, pi/2]: the acute angle between the two lines
    carrying v1 and v2 (i.e. direction is ignored).
    """
    theta = angle_between(v1, v2)
    if theta > math.pi / 2:
        theta = math.pi - theta
    return theta


def bounding_box(points: Iterable[Point]) -> BoundingBox:
    """Axis-aligned bounding box (min_x, min_y, max_x, max_y) of the points.

    Raises ValueError if `points` is empty.
    """
    it = iter(points)
    try:
        x, y = next(it)
    except StopIteration:
        raise ValueError("bounding_box requires at least one point")
    min_x = max_x = x
    min_y = max_y = y
    for x, y in it:
        if x < min_x:
            min_x = x
        elif x > max_x:
            max_x = x
        if y < min_y:
            min_y = y
        elif y > max_y:
            max_y = y
    return min_x, min_y, max_x, max_y


def bboxes_intersect(p1: Point, p2: Point, p3: Point, p4: Point) -> bool:
    """True iff the AABBs of segment (p1,p2) and (p3,p4) overlap or touch."""
    if max(p1[0], p2[0]) < min(p3[0], p4[0]):
        return False
    if max(p3[0], p4[0]) < min(p1[0], p2[0]):
        return False
    if max(p1[1], p2[1]) < min(p3[1], p4[1]):
        return False
    if max(p3[1], p4[1]) < min(p1[1], p2[1]):
        return False
    return True


def segment_intersection(
    p1: Point,
    p2: Point,
    p3: Point,
    p4: Point,
    tol: float = 1e-9,
) -> Optional[SegmentHit]:
    """Interior intersection of two line segments.

    Returns ((x, y), angle_deg) where angle_deg is the acute angle between the
    segments, or None if they do not intersect in the interior of both. Shared
    endpoints are excluded.
    """
    r = (p2[0] - p1[0], p2[1] - p1[1])
    s = (p4[0] - p3[0], p4[1] - p3[1])
    den = r[0] * s[1] - r[1] * s[0]
    if abs(den) < tol:
        return None  # parallel or collinear
    dx = (p3[0] - p1[0], p3[1] - p1[1])
    t = (dx[0] * s[1] - dx[1] * s[0]) / den
    u = (dx[0] * r[1] - dx[1] * r[0]) / den
    if not (tol < t < 1 - tol and tol < u < 1 - tol):
        return None
    ix = p1[0] + t * r[0]
    iy = p1[1] + t * r[1]
    nr = math.hypot(*r)
    ns = math.hypot(*s)
    if nr < tol or ns < tol:
        return None
    # Acute angle via |cos|.
    cos_theta = abs((r[0] * s[0] + r[1] * s[1]) / (nr * ns))
    cos_theta = max(-1.0, min(1.0, cos_theta))
    angle_deg = math.degrees(math.acos(cos_theta))
    return ((ix, iy), angle_deg)
