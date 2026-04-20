"""Edge orthogonality metric (paper §3.2 eq. 5-6).

Unified definition that handles straight, polyline, and curved edges:
    EO(D) = 1 - (1/|E|) * sum_e δ_e
    δ_e   = sum_j min(θ_{e,j}, |90 - θ_{e,j}|, 180 - θ_{e,j}) / 45
                   * (ℓ_{e,j} / L(e))
where θ_{e,j} is the angle (in degrees) of the j-th polyline segment of edge e
relative to the horizontal. Straight edges are the special case k_e = 1.
"""

import math
import warnings

import networkx as nx

from ._geometry import distance
from ._paths import edge_polyline


def _segment_angle_deg(p0, p1) -> float:
    """Absolute angle (degrees) of segment p0→p1 relative to the horizontal,
    folded into [0, 180)."""
    dx = p1[0] - p0[0]
    dy = p1[1] - p0[1]
    # atan2 returns (-pi, pi]; taking absolute folds to [0, pi]; we want [0, 180).
    theta = math.degrees(math.atan2(abs(dy), abs(dx)))
    # Now theta ∈ [0, 90]; paper's formula is already symmetric under the
    # 90° / 180° folds, so this is sufficient.
    return theta


def _edge_deviation(poly) -> float:
    """Length-weighted δ_e for a single edge polyline (sequence of points)."""
    if len(poly) < 2:
        return 0.0

    segments = [(poly[i], poly[i + 1]) for i in range(len(poly) - 1)]
    seg_lens = [distance(a, b) for a, b in segments]
    total_len = sum(seg_lens)
    if total_len == 0:
        return 0.0

    delta = 0.0
    for (a, b), L in zip(segments, seg_lens):
        if L == 0:
            continue
        theta = _segment_angle_deg(a, b)
        # min(θ, |90 - θ|, 180 - θ), paper §3.2 eq. 6.
        seg_dev = min(theta, abs(90.0 - theta), 180.0 - theta) / 45.0
        delta += seg_dev * (L / total_len)
    return delta


def edge_orthogonality(G: nx.Graph, samples_per_curve: int = 50) -> float:
    """Edge orthogonality metric in [0, 1], per paper §3.2 eq. (5)-(6).

    Each edge is treated as a polyline: straight edges are a single segment,
    polyline/curved edges are sampled. The per-edge deviation is a length-
    weighted average of each segment's deviation from the nearest axis
    (scaled so 0 = axis-aligned, 1 = 45° diagonal). The metric is 1 minus the
    mean per-edge deviation.

    Edgeless graphs return 1.0 (vacuously orthogonal).

    Args:
        G: NetworkX graph with node 'x', 'y' and optional edge 'path' attrs.
        samples_per_curve: Sample density for non-line path segments (Bezier etc).

    Returns:
        Float in [0, 1], 1 = all edges axis-aligned.
    """
    if G.number_of_edges() == 0:
        return 1.0

    deviations = []
    for u, v, attrs in G.edges(data=True):
        source = (G.nodes[u]["x"], G.nodes[u]["y"])
        target = (G.nodes[v]["x"], G.nodes[v]["y"])
        poly = edge_polyline(source, target, attrs.get("path"), samples_per_curve=samples_per_curve)
        deviations.append(_edge_deviation(poly))

    return 1.0 - sum(deviations) / len(deviations)


def curved_edge_orthogonality(G: nx.Graph, global_segments_N: int = 10) -> float:
    """Deprecated. Use `edge_orthogonality`, which now handles curved edges.

    Kept as a thin delegating alias so downstream code keeps working; emits a
    DeprecationWarning. The `global_segments_N` parameter is forwarded as
    `samples_per_curve`.
    """
    warnings.warn(
        "curved_edge_orthogonality is deprecated; call edge_orthogonality "
        "(now handles straight and curved edges uniformly per paper §3.2).",
        DeprecationWarning,
        stacklevel=2,
    )
    return edge_orthogonality(G, samples_per_curve=global_segments_N)
