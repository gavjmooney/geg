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
maximum occlusion (c = 1). When nodes don't carry a `radius` attribute the
metric collapses to the centre-to-line form.

Polyline / curved edges: the edge path is sampled via `_paths.edge_polyline`
and `d` is the minimum distance from the node centre to any of the resulting
straight segments. This catches occlusions along the drawn curve, not just
along the node-to-node chord.
"""

from __future__ import annotations

import math

import networkx as nx

from ._paths import edge_polyline
from .geg_parser import get_bounding_box


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
    samples_per_curve: int = 50,
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
        samples_per_curve: Curve-sampling density used to flatten Bezier
            segments into straight pieces before the distance test.

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
        try:
            r = float(data.get("radius", 0.0))
        except (TypeError, ValueError):
            r = 0.0
        nodes.append((n, x, y, max(0.0, r)))

    if len(nodes) < 2:
        return 1.0

    min_x, min_y, max_x, max_y = get_bounding_box(G)
    diag = math.hypot(max_x - min_x, max_y - min_y)
    if diag < 1e-9:
        return 1.0

    epsilon = epsilon_fraction * diag
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
            source, target, data.get("path"), samples_per_curve=samples_per_curve
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
