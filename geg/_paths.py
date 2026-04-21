"""Canonical SVG-path sampling helpers for the metrics package.

Metric modules that need to walk an edge's geometry should use these helpers
rather than calling `svgpathtools.parse_path` and reimplementing sampling.

Conventions:
- `flatten_path_to_polyline` returns N (x, y) points (endpoint at both ends).
- `flatten_path_to_segments` returns N-1 consecutive ((x0, y0), (x1, y1)) segment
  pairs — matches the contract of the previous `flatten_path_to_lines`.
- Straight-line `Line` segments are kept as their exact two endpoints; only
  curved segments are sampled.
"""

from __future__ import annotations

import math
from typing import Iterable, List, Optional, Sequence, Tuple

import svgpathtools
from svgpathtools import Line, Path

from ._geometry import distance

Point = Tuple[float, float]
Segment2D = Tuple[Point, Point]


def parse_path(path_str: str) -> Path:
    """Parse an SVG path string into an svgpathtools Path."""
    return svgpathtools.parse_path(path_str)


def _sample_segment(seg, n_samples: int) -> List[Point]:
    if isinstance(seg, Line):
        return [
            (seg.start.real, seg.start.imag),
            (seg.end.real, seg.end.imag),
        ]
    ts = [k / (n_samples - 1) for k in range(n_samples)]
    return [(seg.point(t).real, seg.point(t).imag) for t in ts]


def flatten_path_to_polyline(
    path: "str | Path",
    samples_per_curve: int = 100,
) -> List[Point]:
    """Flatten a path into a list of (x, y) points tracing the whole path.

    Consecutive segments share their join point (emitted once).
    """
    if isinstance(path, str):
        path = parse_path(path)
    poly: List[Point] = []
    for seg in path:
        pts = _sample_segment(seg, samples_per_curve)
        if not poly:
            poly.extend(pts)
        else:
            poly.extend(pts[1:])
    return poly


def flatten_path_to_segments(
    path: "str | Path",
    samples_per_curve: int = 100,
) -> List[Segment2D]:
    """Flatten a path into a list of consecutive line segments.

    Real Line segments are kept as-is. Curved segments are sampled into
    `samples_per_curve` points and emitted as consecutive line segments.
    """
    if isinstance(path, str):
        path = parse_path(path)
    segs: List[Segment2D] = []
    for seg in path:
        pts = _sample_segment(seg, samples_per_curve)
        for p0, p1 in zip(pts, pts[1:]):
            segs.append((p0, p1))
    return segs


def polyline_length(points: Sequence[Point]) -> float:
    """Cumulative length of a polyline traced through `points`."""
    total = 0.0
    for a, b in zip(points, points[1:]):
        total += distance(a, b)
    return total


def edge_polyline(
    source: Point,
    target: Point,
    path_str: Optional[str],
    samples_per_curve: int = 100,
) -> List[Point]:
    """Convenience: an edge's path flattened to a polyline with endpoints
    snapped exactly to `source` and `target`.

    If `path_str` is falsy, returns the straight-line polyline [source, target].
    """
    if not path_str:
        return [source, target]
    poly = flatten_path_to_polyline(path_str, samples_per_curve=samples_per_curve)
    if poly:
        poly[0] = source
        poly[-1] = target
    return poly
