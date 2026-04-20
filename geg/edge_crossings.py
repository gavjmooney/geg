"""Edge-crossings metric (paper §3.2 eq. (3)).

EC(D) = 1 - c / c_max          if c_max > 0 and c <= c_max
      = 0                       if c > c_max   (curves can exceed c_max)
      = 1                       if c_max == 0  (no crossings possible)

c_max = C(|E|, 2) - sum_v C(deg(v), 2).

Curved / polyline edges are linearised into line segments before intersection
testing. Crossings below `min_angle_tol` (default 2.5°) are discarded to avoid
counting near-parallel overlaps as separate crossings.
"""

import itertools
import math
import xml.etree.ElementTree as ET
from typing import Iterable, List, Tuple, Union

import networkx as nx
from svgpathtools import Path

from ._geometry import bboxes_intersect, segment_intersection
from ._paths import flatten_path_to_segments, parse_path

CrossingHit = Tuple[Tuple[float, float], float]


def annotate_svg(
    input_svg_path: str,
    output_svg_path: str,
    points: Iterable[Tuple[float, float]],
    radius: float = 5,
    color: str = "red",
) -> None:
    """Append circles at `points` to an SVG file and write to a new file.

    Handy for visually annotating computed crossings on a rendered drawing.
    """
    tree = ET.parse(input_svg_path)
    root = tree.getroot()
    if root.tag.startswith("{"):
        ns = root.tag[1: root.tag.index("}")]
    else:
        ns = ""
    ET.register_namespace("", ns)
    for x, y in points:
        ET.SubElement(
            root,
            f"{{{ns}}}circle",
            {"cx": str(x), "cy": str(y), "r": str(radius), "fill": color},
        )
    tree.write(output_svg_path, encoding="utf-8", xml_declaration=True)


def _ec_bounds(G: nx.Graph) -> Tuple[float, float]:
    """Return (c_all, c_deg)."""
    m = G.number_of_edges()
    c_all = m * (m - 1) / 2.0
    # sum_v deg(v) * (deg(v) - 1) / 2
    c_deg = sum(G.degree[u] * (G.degree[u] - 1) for u in G) / 2.0
    return c_all, c_deg


def _score(n_crossings: int, c_max: float) -> float:
    if c_max <= 0:
        return 1.0
    ec = 1.0 - (n_crossings / c_max)
    return max(0.0, ec)


def edge_crossings(
    G: nx.Graph,
    return_crossings: bool = False,
    samples_per_curve: int = 100,
    min_angle_tol: float = 2.5,
) -> Union[float, Tuple[float, List[CrossingHit]]]:
    """Count edge crossings and compute the EC metric (paper §3.2 eq. (3)).

    Each edge path is flattened into straight-line segments; every edge pair's
    segments are tested for interior intersection (bounding-box reject + exact
    segment intersection). Near-parallel crossings (angle < `min_angle_tol`)
    are discarded.

    Args:
        G: NetworkX graph with edge 'path' attributes.
        return_crossings: If True, also return the list of crossings.
        samples_per_curve: Sample density used to linearise curved segments.
        min_angle_tol: Minimum crossing angle (degrees) to keep a crossing.

    Returns:
        Either the EC score in [0, 1], or (score, crossings) where each
        crossing is ((x, y), angle_deg).
    """
    edges = list(G.edges(data=True))
    polys = [flatten_path_to_segments(d["path"], samples_per_curve) for _, _, d in edges]

    crossings: List[CrossingHit] = []
    for (i, _), (j, _) in itertools.combinations(enumerate(edges), 2):
        for p1, p2 in polys[i]:
            for p3, p4 in polys[j]:
                if not bboxes_intersect(p1, p2, p3, p4):
                    continue
                hit = segment_intersection(p1, p2, p3, p4)
                if hit is None:
                    continue
                if hit[1] < min_angle_tol:
                    continue
                crossings.append(hit)

    c_all, c_deg = _ec_bounds(G)
    c_max = c_all - c_deg
    score = _score(len(crossings), c_max)

    if return_crossings:
        return score, crossings
    return score


def edge_crossings_bezier(
    G: nx.Graph,
    tol: float = 1e-6,
    return_crossings: bool = False,
) -> Union[float, Tuple[float, List[CrossingHit]]]:
    """Experimental Bezier-native crossing detector.

    Intersects original SVG path segments (including Bezier curves) without
    polyline linearisation. Slower than `edge_crossings` but avoids sampling
    error. Same score normalisation.
    """
    node_pos = {
        n: complex(data.get("x", 0.0), data.get("y", 0.0))
        for n, data in G.nodes(data=True)
    }
    edges = list(G.edges(data=True))
    paths: List[Path] = [parse_path(d["path"]) for (_, _, d) in edges]

    seen = {(i, j): [] for i, j in itertools.combinations(range(len(edges)), 2)}
    crossings: List[CrossingHit] = []

    for (i, (u1, v1, _)), (j, (u2, v2, _)) in itertools.combinations(enumerate(edges), 2):
        path1, path2 = paths[i], paths[j]
        endpoints = {node_pos[u1], node_pos[v1], node_pos[u2], node_pos[v2]}
        for seg1, seg2 in itertools.product(path1, path2):
            if abs(seg1.start - seg1.end) < tol or abs(seg2.start - seg2.end) < tol:
                continue
            if seg1 == seg2:
                continue
            for t1, t2 in seg1.intersect(seg2):
                pt = seg1.point(t1)
                if any(abs(pt - ep) < tol for ep in endpoints):
                    continue
                x, y = pt.real, pt.imag
                if any(abs(x - xx) < tol and abs(y - yy) < tol for xx, yy in seen[(i, j)]):
                    continue
                seen[(i, j)].append((x, y))
                vec1 = seg1.derivative(t1)
                vec2 = seg2.derivative(t2)
                prod = abs(vec1) * abs(vec2)
                if prod == 0:
                    continue
                cos_theta = (vec1.real * vec2.real + vec1.imag * vec2.imag) / prod
                cos_theta = max(-1.0, min(1.0, cos_theta))
                theta = math.acos(cos_theta)
                if theta > math.pi / 2:
                    theta = math.pi - theta
                crossings.append(((x, y), math.degrees(theta)))

    c_all, c_deg = _ec_bounds(G)
    c_max = c_all - c_deg
    score = _score(len(crossings), c_max)

    if return_crossings:
        return score, crossings
    return score
