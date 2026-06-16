"""Node-Edge Occlusion metric (new — not in the GD 2025 paper yet).

For every edge, find the non-endpoint node whose drawn glyph comes closest to
the edge geometry and apply a cubic soft-overlap penalty:

    c = max(0, 1 - gap / ε) ** 3

where
    gap = minimum distance from the node's drawn *shape boundary* to the edge
          geometry (0 when the glyph straddles the edge); polyline segments
          when the edge has a path, the straight chord otherwise
    ε   = `epsilon_fraction` * bounding_box_diagonal of the drawing

The per-edge worst-case penalty is averaged over edges; the final score is
1 minus that mean. Using the per-edge maximum prevents the signal being
diluted by the many (edge, distant-node) pairs that contribute nothing; the
cubic exponent makes mild proximity near-zero while strongly penalising
actual overlap.

Node footprint (how `gap` is measured):

  * **Explicit `radius`** wins whenever present (non-negative): the node is a
    disk of that radius and `gap = max(0, d - radius)` with `d` the
    centre-to-edge distance. This is the default for circular nodes.
  * **Node shape is honoured** when no explicit `radius` is given. A node
    tagged `shape` ∈ {square, rectangle, rect} is modelled as the axis-aligned
    rectangle it is actually drawn as (half-extents from `width`/`height`, or
    `size`), and `gap` is the true segment-to-rectangle distance — so a thin
    rectangle no longer over-reports occlusion the way a circumscribed disk
    would. A node tagged `shape` ∈ {ellipse, circle} (or carrying dimensions
    without a shape tag) is modelled as a disk; for an ellipse with unequal
    axes the circumscribing disk `max(width, height) / 2` is used.
  * **Fallback:** when a node carries no radius, dimensions, or shape, it is
    given a disk of radius `fallback_radius_fraction * bbox_diagonal` so that
    nodes still occupy a realistic visual footprint instead of collapsing to a
    dimensionless point. Pass `fallback_radius_fraction=0.0` to recover the
    pure centre-to-line behaviour.

Polyline / curved edges: the edge path is sampled via `_paths.edge_polyline`
and the gap is the minimum over all of the resulting straight segments. This
catches occlusions along the drawn curve, not just along the node-to-node
chord.
"""

from __future__ import annotations

import math
from typing import Optional, Tuple, Union

import networkx as nx

from ._paths import edge_polyline, flatness_tol_from_fraction
from .geg_parser import get_bounding_box

# A node's drawn footprint for occlusion testing:
#   ("circle", radius)  or  ("box", half_width, half_height)
CircleShape = Tuple[str, float]
BoxShape = Tuple[str, float, float]
NodeShape = Union[CircleShape, BoxShape]

_SQUARE_TAGS = ("square", "rectangle", "rect")
_DISK_TAGS = ("ellipse", "circle")


def _as_positive_float(value) -> Optional[float]:
    """Parse `value` to a strictly-positive float, else None."""
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return f if f > 0 else None


def _node_shape(data: dict, fallback_radius: float) -> NodeShape:
    """Resolve a node's drawn footprint for occlusion testing.

    Preference order:
      1. Explicit non-negative `radius` → disk of that radius.
      2. `shape` ∈ {square, rectangle, rect} → axis-aligned box from
         `width`/`height` (or `size`, or the fallback).
      3. `shape` ∈ {ellipse, circle}, or dimensions present without a shape
         tag → circumscribing disk `max(width, height) / 2` (or `size / 2`).
      4. Nothing usable → disk of radius `fallback_radius`.
    """
    raw_r = data.get("radius")
    if raw_r is not None:
        try:
            r = float(raw_r)
            if r >= 0:
                return ("circle", r)
        except (TypeError, ValueError):
            pass

    shape = str(data.get("shape", "")).strip().lower()
    w = _as_positive_float(data.get("width"))
    h = _as_positive_float(data.get("height"))
    size = _as_positive_float(data.get("size"))

    if shape in _SQUARE_TAGS:
        if w is not None or h is not None:
            half_w = (w if w is not None else h) / 2.0
            half_h = (h if h is not None else w) / 2.0
            return ("box", half_w, half_h)
        if size is not None:
            return ("box", size / 2.0, size / 2.0)
        return ("box", fallback_radius, fallback_radius)

    # Disk-shaped (ellipse/circle), or no usable shape tag: use the
    # circumscribing disk of whatever dimensions exist, else the fallback.
    if w is not None or h is not None:
        return ("circle", max(w or 0.0, h or 0.0) / 2.0)
    if size is not None:
        return ("circle", size / 2.0)
    return ("circle", fallback_radius)


def _segment_point_distance(
    px: float, py: float,
    ax: float, ay: float,
    bx: float, by: float,
) -> float:
    """Minimum distance from point (px, py) to segment (ax, ay) — (bx, by)."""
    dx, dy = bx - ax, by - ay
    seg_sq = dx * dx + dy * dy
    if seg_sq < 1e-12:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / seg_sq))
    return math.hypot(px - ax - t * dx, py - ay - t * dy)


def _point_box_distance(
    px: float, py: float,
    cx: float, cy: float,
    half_w: float, half_h: float,
) -> float:
    """Distance from point (px, py) to an axis-aligned box centred at
    (cx, cy) with the given half-extents (0 if the point is inside)."""
    dx = max(abs(px - cx) - half_w, 0.0)
    dy = max(abs(py - cy) - half_h, 0.0)
    return math.hypot(dx, dy)


def _segment_intersects_box(
    ax: float, ay: float,
    bx: float, by: float,
    cx: float, cy: float,
    half_w: float, half_h: float,
) -> bool:
    """True iff segment (ax, ay)—(bx, by) touches/enters the axis-aligned box.

    Liang–Barsky slab clipping; also handles the degenerate zero-length
    segment (treated as a point-in-box test).
    """
    min_x, max_x = cx - half_w, cx + half_w
    min_y, max_y = cy - half_h, cy + half_h
    dx, dy = bx - ax, by - ay
    p = (-dx, dx, -dy, dy)
    q = (ax - min_x, max_x - ax, ay - min_y, max_y - ay)
    t0, t1 = 0.0, 1.0
    for pi, qi in zip(p, q):
        if pi == 0:
            if qi < 0:  # parallel to this slab and outside it
                return False
        else:
            t = qi / pi
            if pi < 0:  # entering this slab
                if t > t1:
                    return False
                if t > t0:
                    t0 = t
            else:  # leaving this slab
                if t < t0:
                    return False
                if t < t1:
                    t1 = t
    return t0 <= t1


def _segment_box_distance(
    ax: float, ay: float,
    bx: float, by: float,
    cx: float, cy: float,
    half_w: float, half_h: float,
) -> float:
    """Minimum distance from segment (ax, ay)—(bx, by) to an axis-aligned box.

    0 when the segment touches or enters the box. Otherwise the closest pair
    is realised at a segment endpoint or a box corner, so the minimum over
    {endpoints → box, corners → segment} is exact for these two convex shapes.
    """
    if _segment_intersects_box(ax, ay, bx, by, cx, cy, half_w, half_h):
        return 0.0
    best = min(
        _point_box_distance(ax, ay, cx, cy, half_w, half_h),
        _point_box_distance(bx, by, cx, cy, half_w, half_h),
    )
    min_x, max_x = cx - half_w, cx + half_w
    min_y, max_y = cy - half_h, cy + half_h
    for qx, qy in (
        (min_x, min_y), (min_x, max_y), (max_x, min_y), (max_x, max_y),
    ):
        d = _segment_point_distance(qx, qy, ax, ay, bx, by)
        if d < best:
            best = d
    return best


def _gap_to_shape(shape: NodeShape, px: float, py: float, segments) -> float:
    """Minimum gap between a node's drawn footprint and the edge `segments`.

    `px`/`py` are the node centre. For a disk the gap is `max(0, d - r)`; for
    a box it is the true segment-to-rectangle distance.
    """
    if shape[0] == "box":
        _, half_w, half_h = shape
        return min(
            _segment_box_distance(p0[0], p0[1], p1[0], p1[1], px, py, half_w, half_h)
            for p0, p1 in segments
        )
    _, r = shape
    d = min(
        _segment_point_distance(px, py, p0[0], p0[1], p1[0], p1[1])
        for p0, p1 in segments
    )
    return max(0.0, d - r)


def node_edge_occlusion(
    G: nx.Graph,
    epsilon_fraction: float = 0.02,
    samples_per_curve: Optional[int] = None,
    *,
    bbox: Optional[Tuple[float, float, float, float]] = None,
    flatness_fraction: float = 0.003,
    fallback_radius_fraction: float = 0.01,
) -> float:
    """Node-Edge Occlusion score in [0, 1] (1 = no occlusion).

    Flattening mode (v0.3.0 onwards defaults to adaptive):
      - **Default (adaptive):** segments are recursively split until
        midpoint-to-chord deviation < `flatness_fraction * diag`.
      - **Fixed-N (opt-in):** pass `samples_per_curve=N` for uniform
        sampling; use for TVCG reproduction (N = 100).

    Args:
        G: NetworkX graph with node `x` and `y` attributes. A node's drawn
            footprint is resolved by `_node_shape`: an explicit `radius`
            attribute wins; otherwise the `shape` attribute selects a box
            (square/rectangle/rect) or a disk (ellipse/circle), sized from
            `width`/`height`/`size`; a node with none of these is given the
            `fallback_radius_fraction` disk (see below).
        epsilon_fraction: Penalty-zone width as a fraction of the bounding-box
            diagonal. Default 0.02 (nodes with radii typically render ~5-15%
            of the diagonal, so a 2% buffer around the glyph captures visible
            overlap).
        samples_per_curve: If set, forces fixed-N mode at this density.
            When `None` (default) the metric uses adaptive flattening.
        flatness_fraction: Adaptive-mode tolerance as a fraction of the
            node-bbox diagonal. Ignored when `samples_per_curve` is set.
            Default 0.003.
        bbox: Optional pre-computed (min_x, min_y, max_x, max_y) over node
            positions. If None, computed via
            `get_bounding_box(G, promote=False)`. NEO uses the node-only
            bbox so the penalty zone `epsilon_fraction * diag` (and the
            `fallback_radius_fraction * diag` fallback) scale with how far
            apart the nodes sit, not with how far a curved edge strays from
            its endpoints.
        fallback_radius_fraction: Disk radius — as a fraction of the
            bounding-box diagonal — given to nodes that carry no `radius`,
            no `width`/`height`/`size`, and no `shape`. Default 0.01 (≈ the
            footprint a default-rendered node glyph occupies). Pass 0.0 to
            recover the pure centre-to-line behaviour for such nodes.

    Returns:
        Float in [0, 1]. Returns 1.0 for degenerate graphs (fewer than two
        positioned nodes, no edges, or zero-size bounding box).
    """
    positioned = []
    for n, data in G.nodes(data=True):
        if "x" not in data or "y" not in data:
            continue
        try:
            x = float(data["x"])
            y = float(data["y"])
        except (TypeError, ValueError):
            continue
        positioned.append((n, x, y, data))

    if len(positioned) < 2:
        return 1.0

    if bbox is None:
        bbox = get_bounding_box(G, promote=False)
    min_x, min_y, max_x, max_y = bbox
    diag = math.hypot(max_x - min_x, max_y - min_y)
    if diag < 1e-9:
        return 1.0

    epsilon = epsilon_fraction * diag
    fallback_radius = fallback_radius_fraction * diag
    if samples_per_curve is None:
        # Use the node-only bbox we already computed for epsilon.
        flatness_tol = flatness_tol_from_fraction(G, flatness_fraction, bbox=bbox)
        fixed_N = 100  # ignored by edge_polyline when flatness_tol set
    else:
        flatness_tol = None
        fixed_N = samples_per_curve

    nodes = [
        (n, x, y, _node_shape(data, fallback_radius))
        for n, x, y, data in positioned
    ]
    pos = {n: (x, y) for n, x, y, _ in nodes}

    edges = [
        (u, v, data)
        for u, v, data in G.edges(data=True)
        if u != v and u in pos and v in pos
    ]
    if not edges:
        return 1.0

    per_edge_worst = []
    for u, v, data in edges:
        source = pos[u]
        target = pos[v]
        poly = edge_polyline(
            source, target, data.get("path"),
            samples_per_curve=fixed_N,
            flatness_tol=flatness_tol,
        )
        segments = list(zip(poly, poly[1:]))
        if not segments:
            per_edge_worst.append(0.0)
            continue

        worst = 0.0
        for n, px, py, shape in nodes:
            if n == u or n == v:
                continue
            gap = _gap_to_shape(shape, px, py, segments)
            c = max(0.0, 1.0 - gap / epsilon) ** 3
            if c > worst:
                worst = c
        per_edge_worst.append(worst)

    return max(0.0, 1.0 - sum(per_edge_worst) / len(per_edge_worst))
