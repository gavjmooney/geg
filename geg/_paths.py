"""Canonical SVG-path sampling helpers for the metrics package.

Metric modules that need to walk an edge's geometry should use these helpers
rather than calling `svgpathtools.parse_path` and reimplementing sampling.

Conventions:
- `flatten_path_to_polyline` returns N (x, y) points (endpoint at both ends).
- `flatten_path_to_segments` returns N-1 consecutive ((x0, y0), (x1, y1)) segment
  pairs — matches the contract of the previous `flatten_path_to_lines`.
- Straight-line `Line` segments are kept as their exact two endpoints; only
  curved segments are sampled.
- Two flattening modes coexist:
    1. **Fixed-N** (`flatten_path_to_polyline`, `samples_per_curve=100`) — every
       non-Line segment gets the same number of samples, regardless of shape
       or length. Paper §3.2 prescribed. Use when reproducing published TVCG
       numbers.
    2. **Adaptive / curvature-aware** (`flatten_path_adaptive`, `flatness_tol`)
       — midpoint-to-chord subdivision. Highly curved segments get denser
       samples; nearly-straight segments terminate after one or two splits.
       Use when curve fidelity matters more than paper conformance (e.g.
       post-TVCG updates, drawings with very tight curves).
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
    *,
    flatness_tol: Optional[float] = None,
    max_depth: int = 16,
) -> List[Point]:
    """Convenience: an edge's path flattened to a polyline with endpoints
    snapped exactly to `source` and `target`.

    If `path_str` is falsy, returns the straight-line polyline
    `[source, target]`.

    Flattening mode:
      - `flatness_tol` unset (default): fixed-N mode — every non-Line segment
        gets `samples_per_curve` samples (paper §3.2 prescribed).
      - `flatness_tol` set: adaptive curvature-aware mode — segments are
        recursively split until the midpoint-to-chord distance drops below
        `flatness_tol`. `samples_per_curve` is ignored. Typically set to a
        fraction of the drawing's bbox diagonal for scale invariance.
    """
    if not path_str:
        return [source, target]
    if flatness_tol is not None:
        poly = flatten_path_adaptive(path_str, flatness_tol, max_depth=max_depth)
    else:
        poly = flatten_path_to_polyline(path_str, samples_per_curve=samples_per_curve)
    if poly:
        # Orient poly so its first point matches source. An undirected
        # graph's `G.edges(data=True)` can yield (u, v) in either order,
        # so if the caller passed `source = G.nodes[u]` the path may
        # actually start at `target`'s position. Reversing here keeps
        # the snapped polyline consistent with (source, target) rather
        # than end-swapping it.
        d_start_src = math.hypot(poly[0][0] - source[0], poly[0][1] - source[1])
        d_start_tgt = math.hypot(poly[0][0] - target[0], poly[0][1] - target[1])
        if d_start_tgt < d_start_src:
            poly.reverse()
        poly[0] = source
        poly[-1] = target
    return poly


# ---------- adaptive / curvature-aware flattening ----------

def _point_to_segment_distance(
    px: float, py: float,
    ax: float, ay: float,
    bx: float, by: float,
) -> float:
    """Perpendicular distance from point (px, py) to the line through
    (ax, ay) and (bx, by). Degenerate (zero-length) "segments" collapse to
    point-to-point distance from (px, py) to (ax, ay).

    Note: this is distance to the infinite line when the segment has non-zero
    length, which is what the flatness test wants — we're measuring how far
    the curve's midpoint deviates from the chord connecting its endpoints.
    The midpoint of a convex arc always has its nearest point on the interior
    of the chord, so perpendicular-to-line and perpendicular-to-segment agree.
    """
    dx = bx - ax
    dy = by - ay
    seg_sq = dx * dx + dy * dy
    if seg_sq < 1e-18:
        return math.hypot(px - ax, py - ay)
    # Perpendicular distance = |cross product| / chord length.
    cross = (px - ax) * dy - (py - ay) * dx
    return abs(cross) / math.sqrt(seg_sq)


_FLATNESS_PROBE_TS = (0.25, 0.5, 0.75)


def _adaptive_flatten_segment(
    seg,
    flatness_tol: float,
    max_depth: int,
) -> List[Point]:
    """Recursively subdivide `seg` (a non-Line svgpathtools segment) using
    max-point-to-chord distance at multiple interior sample points as the
    flatness proxy. Returns a list of (x, y) points starting at
    `seg.point(0)` and ending at `seg.point(1)`.

    The recursion sticks with the original `seg`'s parametrisation — each
    call works on a [t0, t1] sub-range of [0, 1] rather than cropped
    sub-segments. Avoids depending on segment-specific `.cropped()` support
    and keeps all sampled points on the true curve.

    Why multiple probes: midpoint-only testing misses S-shaped curves whose
    inflection point lies exactly at t=0.5 — the curve midpoint coincides
    with the chord midpoint by symmetry, so the flatness test returns 0
    and recursion terminates even though the curve swings wildly off the
    chord at t=0.25 and t=0.75. Probing (0.25, 0.5, 0.75) catches this
    case; the overhead is three extra point evaluations per recursion
    level (cheap compared to svgpathtools' `seg.point` evaluation cost).
    """
    def recurse(t0: float, t1: float, depth: int) -> List[Point]:
        p0 = seg.point(t0)
        p1 = seg.point(t1)
        max_d = 0.0
        for u in _FLATNESS_PROBE_TS:
            t = t0 + u * (t1 - t0)
            p = seg.point(t)
            d = _point_to_segment_distance(
                p.real, p.imag, p0.real, p0.imag, p1.real, p1.imag,
            )
            if d > max_d:
                max_d = d
                if max_d > flatness_tol:
                    break  # already failed; no need to probe further
        if max_d <= flatness_tol or depth >= max_depth:
            return [(p0.real, p0.imag), (p1.real, p1.imag)]
        tm = 0.5 * (t0 + t1)
        left = recurse(t0, tm, depth + 1)
        right = recurse(tm, t1, depth + 1)
        # Dedup the shared midpoint — last of `left` equals first of `right`.
        return left + right[1:]

    return recurse(0.0, 1.0, 0)


def flatten_path_adaptive(
    path: "str | Path",
    flatness_tol: float,
    max_depth: int = 16,
) -> List[Point]:
    """Curvature-aware flattening: adaptively subdivide each non-Line segment
    until the midpoint-to-chord deviation drops below `flatness_tol`.

    Lines are kept as their exact two endpoints (as in `flatten_path_to_polyline`).
    Consecutive segments share their join point (emitted once).

    High-curvature regions naturally recurse deeper; nearly-straight regions
    terminate after one midpoint check. The output is a polyline whose
    maximum pointwise deviation from the true curve is ≤ `flatness_tol`
    (modulo the `max_depth` guard).

    Args:
        path: SVG path string or svgpathtools.Path.
        flatness_tol: Maximum allowed midpoint-to-chord distance, in the
            same units as the path coordinates. For scale invariance, set
            to `fraction · bbox_diagonal` in the caller — the helper does
            not know about the graph.
        max_depth: Recursion cap. 2^max_depth subsegments per curve segment
            is the worst case; default 16 is generous for well-behaved
            curves and prevents pathological recursion on zero-area loops.

    Returns:
        List of (x, y) points; first = path start, last = path end.
    """
    if flatness_tol <= 0:
        raise ValueError("flatness_tol must be positive")
    if isinstance(path, str):
        path = parse_path(path)
    poly: List[Point] = []
    for seg in path:
        if isinstance(seg, Line):
            pts = [
                (seg.start.real, seg.start.imag),
                (seg.end.real, seg.end.imag),
            ]
        else:
            pts = _adaptive_flatten_segment(seg, flatness_tol, max_depth)
        if not poly:
            poly.extend(pts)
        else:
            poly.extend(pts[1:])
    return poly
