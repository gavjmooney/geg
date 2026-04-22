"""Angular resolution metric (paper §3.2 eq. (1)).

AR(D) = 1 - (1/|V_{>1}|) * sum_v |θ_v - θ_v^min| / θ_v
with θ_v = 360° / deg(v) and θ_v^min the smallest angular gap between any two
edges incident to v. The paper's definition uses min-angle; this module also
provides a mean-absolute-deviation variant as a library extension.

Both variants:
  - Skip nodes with degree <= 1 (no angular gap defined).
  - Skip promoted bend points (is_segment=True).
  - Use the tangent vector at the vertex end of each incident edge's path.
"""

import math
from typing import Hashable, List

import networkx as nx
from svgpathtools import Line

from ._paths import parse_path, reverse_svg_path


def orient_svg_path_for_node(path_str: str, node_x: float, node_y: float, tol: float = 1e-6) -> str:
    """Return `path_str` oriented so the first-segment `start` is the endpoint
    closest to `(node_x, node_y)`.

    Uses a distance comparison rather than an exact-match check so extraction
    noise (endpoints off by a few units) does not silently give the wrong
    tangent, and "flipped" paths from GEG files where source/target were
    swapped during extraction are corrected transparently.

    `tol` is retained for the fast-path exact match but is no longer a
    pass/fail gate: if neither endpoint matches exactly, orientation is
    decided by whichever endpoint is numerically closer to the target node.
    """
    path = parse_path(path_str)
    if not path:
        return path_str
    start = path[0].start
    if abs(start.real - node_x) < tol and abs(start.imag - node_y) < tol:
        return path_str
    end = path[-1].end
    d_start = math.hypot(start.real - node_x, start.imag - node_y)
    d_end   = math.hypot(end.real   - node_x, end.imag   - node_y)
    if d_end < d_start:
        return reverse_svg_path(path_str)
    return path_str


def get_outbound_edges(G: nx.Graph, node: Hashable) -> List:
    """Incident edges as (u, v, data) or (u, v, key, data) for multigraphs."""
    if G.is_multigraph():
        kw = dict(keys=True, data=True)
    else:
        kw = dict(data=True)
    if G.is_directed():
        return list(G.out_edges(node, **kw))
    return list(G.edges(node, **kw))


def _incident_edge_angles(G: nx.Graph, node: Hashable) -> List[float]:
    """Clockwise-from-+y angles (degrees) of each edge incident to `node`.

    Handles self-loops (counted twice, with path reversed for the second
    incidence) and uses the unit tangent at the vertex-side endpoint of each
    oriented path.
    """
    x, y = G.nodes[node]["x"], G.nodes[node]["y"]
    raw_paths = []
    for u, v, *rest in get_outbound_edges(G, node):
        data = rest[-1]
        raw = data["path"]
        raw_paths.append(raw)
        if u == v:
            raw_paths.append(reverse_svg_path(raw))

    angles = []
    for raw in raw_paths:
        path = parse_path(orient_svg_path_for_node(raw, x, y))
        seg0 = path[0]
        # Degeneracy: a Line with coincident endpoints is a zero-length
        # segment and has no tangent. Beziers/Arcs can legally have
        # start == end (self-loops!) while still defining a well-formed
        # tangent through their control points — don't skip those.
        if isinstance(seg0, Line) and seg0.start == seg0.end:
            continue
        try:
            tangent = seg0.unit_tangent(0.0)
        except (ValueError, ZeroDivisionError):
            continue
        if not math.isfinite(tangent.real) or not math.isfinite(tangent.imag):
            continue
        if abs(tangent) < 1e-12:
            continue
        vx, vy = tangent.real, -tangent.imag  # flip y to Cartesian
        theta_from_y = math.degrees(math.atan2(vy, vx) - math.pi / 2) % 360
        angles.append((360 - theta_from_y) % 360)
    return angles


def _gaps_around_vertex(angles: List[float]) -> List[float]:
    """Sorted angular gaps (including wrap-around) from a list of incident angles."""
    angles = sorted(angles)
    gaps = [angles[i + 1] - angles[i] for i in range(len(angles) - 1)]
    gaps.append((angles[0] + 360.0) - angles[-1])
    return gaps


def _iter_eligible_vertices(G: nx.Graph):
    """Yield vertices with degree >= 2 that are not promoted bend points."""
    for node in G:
        if G.degree[node] <= 1:
            continue
        if G.nodes[node].get("is_segment", False):
            continue
        yield node


def angular_resolution_min_angle(G: nx.Graph) -> float:
    """Angular resolution using the minimum gap at each vertex (paper §3.2 eq. (1))."""
    total = 0.0
    count = 0
    for node in _iter_eligible_vertices(G):
        angles = _incident_edge_angles(G, node)
        if len(angles) < 2:
            continue
        ideal = 360.0 / G.degree[node]
        min_gap = min(_gaps_around_vertex(angles))
        total += (ideal - min_gap) / ideal
        count += 1
    if count == 0:
        return 1.0
    return 1.0 - total / count


def angular_resolution_avg_angle(G: nx.Graph) -> float:
    """Angular resolution using mean absolute gap deviation from ideal (library extension).

    For each eligible vertex the gaps sum to 360° and their mean is ideal, so
    we score uniformity by the mean absolute deviation of gaps from `ideal`,
    normalised by `ideal`.
    """
    total = 0.0
    count = 0
    for node in _iter_eligible_vertices(G):
        angles = _incident_edge_angles(G, node)
        if len(angles) < 2:
            continue
        ideal = 360.0 / G.degree[node]
        gaps = _gaps_around_vertex(angles)
        mean_abs_dev = sum(abs(g - ideal) for g in gaps) / len(gaps)
        total += mean_abs_dev / ideal
        count += 1
    if count == 0:
        return 1.0
    return 1.0 - total / count
