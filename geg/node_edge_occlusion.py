"""Node-Edge Occlusion metric (new — not in the GD 2025 paper yet).

For every edge, find the non-endpoint node whose bounding disk comes closest
to the drawn edge geometry and apply a cubic soft-overlap penalty:

    c = max(0, 1 - max(0, d - r) / ε) ** 3

where
    d  = minimum distance from the node centre to the edge geometry
         (polyline segments when the edge has a path; straight line otherwise)
    r  = node's `radius` attribute (defaults to 0 if missing)
    ε  = `epsilon_fraction` * bounding_box_diagonal of the drawing

The per-edge worst-case penalty is averaged over edges; the final score is
1 minus that mean. Using the per-edge maximum prevents the signal being
diluted by the many (edge, distant-node) pairs that contribute nothing; the
cubic exponent makes mild proximity near-zero while strongly penalising
actual overlap.

Radius awareness: a node's disk straddling the edge (r >= d) is treated as
maximum occlusion (c = 1). If a node has no `radius` attribute but carries
`width` / `height` (as produced by `read_graphml` and `read_gml`), the
circumscribed-disk radius `max(width, height) / 2` is used. Only when all
three attributes are absent does the metric fall back to the centre-to-line
form.

Polyline / curved edges: the edge path is sampled via `_paths.edge_polyline`
and `d` is the minimum distance from the node centre to any of the resulting
straight segments. This catches occlusions along the drawn curve, not just
along the node-to-node chord.
"""

from __future__ import annotations

import math
from typing import Optional, Tuple

import networkx as nx

from ._paths import edge_polyline
from .geg_parser import get_bounding_box


def _node_radius(data: dict) -> float:
    """Resolve a node's effective disk radius for occlusion testing.

    Preference order:
      1. Explicit `radius` attribute (non-negative).
      2. Circumscribed disk of the bounding box — `max(width, height) / 2`.
      3. 0.0 — centre-to-line fallback.
    """
    raw_r = data.get("radius")
    if raw_r is not None:
        try:
            r = float(raw_r)
            if r >= 0:
                return r
        except (TypeError, ValueError):
            pass

    try:
        w = float(data.get("width", 0.0))
    except (TypeError, ValueError):
        w = 0.0
    try:
        h = float(data.get("height", 0.0))
    except (TypeError, ValueError):
        h = 0.0
    if w > 0 or h > 0:
        return max(w, h) / 2.0
    return 0.0


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


def node_edge_occlusion(
    G: nx.Graph,
    epsilon_fraction: float = 0.02,
    samples_per_curve: int = 100,
    *,
    bbox: Optional[Tuple[float, float, float, float]] = None,
    flatness_fraction: Optional[float] = None,
) -> float:
    """Node-Edge Occlusion score in [0, 1] (1 = no occlusion).

    Args:
        G: NetworkX graph with node `x` and `y` attributes. Optional per-node
            `radius` attribute tightens the proximity test (the node's disk
            edge, rather than its centre, is compared to the edge).
        epsilon_fraction: Penalty-zone width as a fraction of the bounding-box
            diagonal. Default 0.02 (nodes with radii typically render ~5-15%
            of the diagonal, so a 2% buffer around the disk captures visible
            overlap).
        samples_per_curve: Fixed-N curve-sampling density used to flatten
            Bezier segments into straight pieces. Ignored when
            `flatness_fraction` is set.
        flatness_fraction: Adaptive curvature-aware flattening tolerance as
            a fraction of the node-bbox diagonal. When set, segments are
            recursively split until the midpoint-to-chord distance drops
            below `flatness_fraction · diag` instead of using a fixed N.
        bbox: Optional pre-computed (min_x, min_y, max_x, max_y) over node
            positions. If None, computed via
            `get_bounding_box(G, promote=False)`. NEO uses the node-only
            bbox so the penalty zone `epsilon_fraction * diag` scales with
            how far apart the nodes sit, not with how far a curved edge
            strays from its endpoints.

    Returns:
        Float in [0, 1]. Returns 1.0 for degenerate graphs (fewer than two
        positioned nodes, no edges, or zero-size bounding box).
    """
    nodes = []
    for n, data in G.nodes(data=True):
        if "x" not in data or "y" not in data:
            continue
        try:
            x = float(data["x"])
            y = float(data["y"])
        except (TypeError, ValueError):
            continue
        nodes.append((n, x, y, _node_radius(data)))

    if len(nodes) < 2:
        return 1.0

    if bbox is None:
        bbox = get_bounding_box(G, promote=False)
    min_x, min_y, max_x, max_y = bbox
    diag = math.hypot(max_x - min_x, max_y - min_y)
    if diag < 1e-9:
        return 1.0

    epsilon = epsilon_fraction * diag
    flatness_tol = flatness_fraction * diag if flatness_fraction is not None else None
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
            samples_per_curve=samples_per_curve,
            flatness_tol=flatness_tol,
        )
        segments = list(zip(poly, poly[1:]))
        if not segments:
            per_edge_worst.append(0.0)
            continue

        worst = 0.0
        for n, px, py, r in nodes:
            if n == u or n == v:
                continue
            d = min(
                _segment_point_distance(px, py, p0[0], p0[1], p1[0], p1[1])
                for p0, p1 in segments
            )
            gap = max(0.0, d - r)
            c = max(0.0, 1.0 - gap / epsilon) ** 3
            if c > worst:
                worst = c
        per_edge_worst.append(worst)

    return max(0.0, 1.0 - sum(per_edge_worst) / len(per_edge_worst))
