"""Fixture registry for the metrics test suite.

Each fixture is registered via `@register` with its NetworkX builder and a
table of hand-computed expected metric values. Running this module as a
script regenerates the `.geg` and grid `.svg` artefacts for all fixtures.

The `.md` derivation files are hand-written (not emitted here).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, Optional

import networkx as nx

from geg import to_svg, write_geg


FIXTURES_DIR = Path(__file__).parent


@dataclass
class Fixture:
    name: str
    description: str
    build: Callable[[], nx.Graph]
    # Map metric-name → expected value. Only include metrics with a
    # uniquely defined (hand-computable) expected value for this fixture.
    # Supported metric names are keys of `_METRIC_FUNCS` in test_fixtures.py.
    expected: Dict[str, float] = field(default_factory=dict)
    tol: float = 1e-9


_REGISTRY: Dict[str, Fixture] = {}


def register(fixture: Fixture) -> Fixture:
    if fixture.name in _REGISTRY:
        raise ValueError(f"duplicate fixture name: {fixture.name}")
    _REGISTRY[fixture.name] = fixture
    return fixture


def all_fixtures() -> Dict[str, Fixture]:
    return dict(_REGISTRY)


def _straight(u: str, v: str, G: nx.Graph) -> str:
    x0, y0 = G.nodes[u]["x"], G.nodes[u]["y"]
    x1, y1 = G.nodes[v]["x"], G.nodes[v]["y"]
    return f"M{x0},{y0} L{x1},{y1}"


def _add_node(G: nx.Graph, n: str, x: float, y: float) -> None:
    G.add_node(n, x=float(x), y=float(y))


def _add_edge_straight(G: nx.Graph, u: str, v: str) -> None:
    # We always emit the 'path' attribute so edge_crossings and SVG output
    # work uniformly; metrics that care about path (EO, EC) need it.
    G.add_edge(u, v, path=_straight(u, v, G))


# ---------- Fixture definitions ----------

def _build_single_edge() -> nx.Graph:
    G = nx.Graph()
    _add_node(G, "a", 0, 0)
    _add_node(G, "b", 1, 0)
    _add_edge_straight(G, "a", "b")
    return G


register(Fixture(
    name="single_edge",
    description="One horizontal edge between a=(0,0) and b=(1,0). Every metric is vacuously or trivially 1.",
    build=_build_single_edge,
    expected={
        "angular_resolution_min_angle": 1.0,
        "angular_resolution_avg_angle": 1.0,
        "aspect_ratio": 1.0,
        "crossing_angle": 1.0,
        "edge_crossings": 1.0,
        "edge_length_deviation": 1.0,
        "edge_orthogonality": 1.0,
        "gabriel_ratio_edges": 1.0,
        "gabriel_ratio_nodes": 1.0,
        "kruskal_stress": 1.0,
        "neighbourhood_preservation": 1.0,
        "node_resolution": 1.0,
        "node_uniformity": 1.0,
    },
))


def _build_path_stretched() -> nx.Graph:
    # Non-uniform spacing to avoid k-NN ties in NP.
    G = nx.Graph()
    for n, x in [("a", 0), ("b", 1), ("c", 3), ("d", 6)]:
        _add_node(G, n, x, 0)
    for u, v in [("a", "b"), ("b", "c"), ("c", "d")]:
        _add_edge_straight(G, u, v)
    return G


register(Fixture(
    name="path_stretched",
    description="Four collinear nodes at x=0,1,3,6; edges a-b, b-c, c-d. Edge lengths 1, 2, 3.",
    build=_build_path_stretched,
    expected={
        # Middle nodes have degree 2, legs at 0° and 180° → gaps 180/180 → AR = 1.
        "angular_resolution_min_angle": 1.0,
        "angular_resolution_avg_angle": 1.0,
        "aspect_ratio": 1.0,  # h = 0 → degenerate case → 1 per spec.
        "crossing_angle": 1.0,
        "edge_crossings": 1.0,  # collinear, no crossings.
        "edge_orthogonality": 1.0,  # all horizontal.
        # ELD derivation (see path_stretched.md):
        # ideal = 2; rel devs = 0.5, 0, 0.5; avg = 1/3; ELD = 1/(1+1/3) = 3/4.
        "edge_length_deviation": 0.75,
        "gabriel_ratio_edges": 1.0,  # every edge's disk is empty of other nodes.
        "node_resolution": 1.0 / 6.0,  # min pair = 1, max pair = 6.
    },
))


def _build_equilateral_triangle() -> nx.Graph:
    G = nx.Graph()
    _add_node(G, "a", 0, 0)
    _add_node(G, "b", 1, 0)
    _add_node(G, "c", 0.5, math.sqrt(3) / 2)
    for u, v in [("a", "b"), ("b", "c"), ("c", "a")]:
        _add_edge_straight(G, u, v)
    return G


register(Fixture(
    name="equilateral_triangle",
    description="Unit-side equilateral triangle. Vertices have degree 2; the two incident edges meet at 60° (interior) or 300° (exterior).",
    build=_build_equilateral_triangle,
    expected={
        # Degree-2 vertex: gaps [60, 300]; min = 60; ideal = 180; dev = 2/3 → AR = 1/3.
        "angular_resolution_min_angle": 1.0 / 3.0,
        "angular_resolution_avg_angle": 1.0 / 3.0,
        # Bbox h = sqrt(3)/2, w = 1; h/w = sqrt(3)/2 (since h < w).
        "aspect_ratio": math.sqrt(3) / 2,
        "crossing_angle": 1.0,
        "edge_crossings": 1.0,  # c_max = 0; K3 exhausts degree discount.
        "edge_length_deviation": 1.0,  # all edges unit length.
        # 3 edges: horizontal (δ=0), +60° (δ=30/45=2/3), +120° (δ=60/45→folded: min(120,30,60)/45=30/45=2/3).
        # Actually let's hand-check: angles measured to horizontal: 0°, 60°, 120° (or the complementary).
        # Segment (b,c) goes from (1,0) to (0.5, 0.866) → Δ=(-0.5, 0.866) → angle = atan2(0.866, 0.5) = 60°.
        # min(60, |90-60|=30, 180-60=120) / 45 = 30/45 = 2/3.
        # Segment (c,a) goes from (0.5, 0.866) to (0, 0) → Δ=(-0.5, -0.866) → atan2 on abs = atan2(0.866, 0.5) = 60°.
        # Same δ = 2/3.
        # Mean δ over 3 edges = (0 + 2/3 + 2/3) / 3 = 4/9. EO = 1 - 4/9 = 5/9.
        "edge_orthogonality": 5.0 / 9.0,
        "gabriel_ratio_edges": 1.0,
        "kruskal_stress": 1.0,  # equilateral: d_ij = x_ij = 1 for all pairs.
        "neighbourhood_preservation": 1.0,  # K3: every node's 2 nearest are the other two.
        "node_resolution": 1.0,  # all pair distances = 1.
    },
))


def _build_unit_square_k4() -> nx.Graph:
    # Unit square with all edges (cycle + 2 diagonals) = K4.
    G = nx.Graph()
    for n, (x, y) in [("a", (0, 0)), ("b", (1, 0)), ("c", (1, 1)), ("d", (0, 1))]:
        _add_node(G, n, x, y)
    for u, v in [("a", "b"), ("b", "c"), ("c", "d"), ("d", "a"),
                  ("a", "c"), ("b", "d")]:
        _add_edge_straight(G, u, v)
    return G


register(Fixture(
    name="unit_square_k4",
    description="K4 on the unit square. Four axis-aligned sides + two 45° diagonals; diagonals cross at (0.5, 0.5) at 90°.",
    build=_build_unit_square_k4,
    expected={
        "aspect_ratio": 1.0,
        # 1 crossing at 90° → perfect.
        "crossing_angle": 1.0,
        # m=6, c_all=15, c_deg = 4·C(3,2) = 12, c_max = 3. 1 crossing → EC = 1 - 1/3 = 2/3.
        "edge_crossings": 2.0 / 3.0,
        # Side lengths: 1, 1, 1, 1, sqrt(2), sqrt(2). L_ideal = (4 + 2sqrt(2))/6 = (2 + sqrt(2))/3.
        # avg rel dev = ((4·|1 - ideal| + 2·|sqrt(2) - ideal|) / ideal) / 6.
        "edge_length_deviation": None,  # non-trivial, see .md derivation.
        # EO: 4 axis-aligned (δ=0) + 2 diagonals at 45° (δ=1). mean = 2/6 = 1/3. EO = 2/3.
        "edge_orthogonality": 2.0 / 3.0,
        "node_resolution": 1.0 / math.sqrt(2),
        # NU: 4 nodes, 2×2 grid, each in its own cell → NU = 1.
        "node_uniformity": 1.0,
    },
))
# Compute the ELD expected value once, so the .md can echo the symbolic form.
_sides = [1.0] * 4 + [math.sqrt(2)] * 2
_ideal = sum(_sides) / 6
_eld_avg = sum(abs(L - _ideal) for L in _sides) / (6 * _ideal)
_REGISTRY["unit_square_k4"].expected["edge_length_deviation"] = 1.0 / (1.0 + _eld_avg)


def _build_pentagon() -> nx.Graph:
    # Regular pentagon with unit-circumradius.
    G = nx.Graph()
    names = ["v0", "v1", "v2", "v3", "v4"]
    for i, n in enumerate(names):
        theta = math.radians(-90 + i * 72)  # start pointing up
        _add_node(G, n, math.cos(theta), math.sin(theta))
    # Only the 5 sides (no diagonals).
    for i in range(5):
        _add_edge_straight(G, names[i], names[(i + 1) % 5])
    return G


register(Fixture(
    name="pentagon",
    description="Regular pentagon (5-cycle), unit-circumradius, apex at (0, -1). No diagonals drawn.",
    build=_build_pentagon,
    expected={
        # Each vertex has degree 2; interior angle of a regular pentagon is 108°.
        # Gaps around each vertex: [108, 252]. min=108. ideal=180. dev=(180-108)/180=0.4.
        # AR = 1 - 0.4 = 0.6.
        "angular_resolution_min_angle": 0.6,
        "angular_resolution_avg_angle": 0.6,  # symmetric: |108-180|=|252-180|=72.
        "crossing_angle": 1.0,
        "edge_crossings": 1.0,
        "edge_length_deviation": 1.0,
        "gabriel_ratio_edges": 1.0,  # convex regular polygon: sides are Gabriel.
    },
))


def _build_45_diagonal() -> nx.Graph:
    G = nx.Graph()
    _add_node(G, "a", 0, 0)
    _add_node(G, "b", 1, 1)
    _add_edge_straight(G, "a", "b")
    return G


register(Fixture(
    name="diagonal_45",
    description="Single edge at exactly 45° — the EO worst case.",
    build=_build_45_diagonal,
    expected={
        "edge_orthogonality": 0.0,  # θ=45° → δ=1 → EO = 0.
        "aspect_ratio": 1.0,  # bbox 1×1.
        "edge_crossings": 1.0,
        "edge_length_deviation": 1.0,
    },
))


def _build_star_k1_4() -> nx.Graph:
    G = nx.Graph()
    _add_node(G, "c", 0, 0)
    for n, (x, y) in [("e", (1, 0)), ("s", (0, 1)), ("w", (-1, 0)), ("n", (0, -1))]:
        _add_node(G, n, x, y)
    for leaf in ("e", "s", "w", "n"):
        _add_edge_straight(G, "c", leaf)
    return G


register(Fixture(
    name="star_k1_4",
    description="Four-pointed axis-aligned star: centre c=(0,0) with legs east/south/west/north.",
    build=_build_star_k1_4,
    expected={
        # Centre has 4 legs at 90° intervals → perfect. Leaves are degree 1.
        "angular_resolution_min_angle": 1.0,
        "angular_resolution_avg_angle": 1.0,
        "aspect_ratio": 1.0,  # bbox 2x2.
        "crossing_angle": 1.0,
        # m=4, all degree ≤ 4 centre + 1 per leaf. c_all=6, c_deg=C(4,2)=6, c_max=0.
        "edge_crossings": 1.0,
        "edge_length_deviation": 1.0,  # all legs unit length.
        "edge_orthogonality": 1.0,  # all axis-aligned.
        "gabriel_ratio_edges": 1.0,
        "node_resolution": 0.5,  # min=1 (centre-leaf), max=2 (opposite leaves).
    },
))


def _build_unit_square_cycle() -> nx.Graph:
    G = nx.Graph()
    for n, (x, y) in [("a", (0, 0)), ("b", (1, 0)), ("c", (1, 1)), ("d", (0, 1))]:
        _add_node(G, n, x, y)
    for u, v in [("a", "b"), ("b", "c"), ("c", "d"), ("d", "a")]:
        _add_edge_straight(G, u, v)
    return G


register(Fixture(
    name="unit_square_cycle",
    description="4-cycle on the unit square (sides only, no diagonals). Planar, perfectly orthogonal.",
    build=_build_unit_square_cycle,
    expected={
        # Each vertex degree 2 with perpendicular legs → gaps [90, 270].
        # min = 90, ideal = 180 → shortfall 0.5 per vertex → AR = 0.5.
        "angular_resolution_min_angle": 0.5,
        "angular_resolution_avg_angle": 0.5,
        "aspect_ratio": 1.0,
        "crossing_angle": 1.0,
        # m=4, all degree 2. c_all=6, c_deg=4·1=4, c_max=2. No crossings → 1.
        "edge_crossings": 1.0,
        "edge_length_deviation": 1.0,
        "edge_orthogonality": 1.0,
        "gabriel_ratio_edges": 1.0,
        "node_resolution": 1.0 / math.sqrt(2),
        "node_uniformity": 1.0,  # 2x2 grid, 1 per cell.
    },
))


def _build_grid_3x3() -> nx.Graph:
    G = nx.Graph()
    names = {}
    for i in range(3):
        for j in range(3):
            n = f"n{i}_{j}"
            names[(i, j)] = n
            _add_node(G, n, i, j)
    for i in range(3):
        for j in range(3):
            if i + 1 < 3:
                _add_edge_straight(G, names[(i, j)], names[(i + 1, j)])
            if j + 1 < 3:
                _add_edge_straight(G, names[(i, j)], names[(i, j + 1)])
    return G


def _grid3x3_ar() -> float:
    # Corners (4): degree 2 perpendicular → shortfall 0.5 each.
    # Edge mid-sides (4): degree 3, gaps [90, 90, 180], min=90, ideal=120 → shortfall 1/4.
    # Centre (1): degree 4 perfect → shortfall 0.
    total = 4 * 0.5 + 4 * 0.25 + 1 * 0.0
    return 1.0 - total / 9.0


register(Fixture(
    name="grid_3x3",
    description="3×3 node grid with orthogonal grid edges (12 edges). Planar, perfectly orthogonal.",
    build=_build_grid_3x3,
    expected={
        "angular_resolution_min_angle": _grid3x3_ar(),
        # Avg variant: corners same |deviation| = 0.5. Edge vertices: gaps
        # [90, 90, 180], dev |30, 30, 60|, mean=40, norm=40/120=1/3. Centre 0.
        # Mean shortfall = (4·0.5 + 4·(1/3) + 0) / 9 = (2 + 4/3) / 9 = 10/27.
        "angular_resolution_avg_angle": 1.0 - 10.0 / 27.0,
        "aspect_ratio": 1.0,
        "crossing_angle": 1.0,
        "edge_crossings": 1.0,  # planar, no crossings.
        "edge_length_deviation": 1.0,
        "edge_orthogonality": 1.0,
        "gabriel_ratio_edges": 1.0,
        "node_uniformity": 1.0,  # 3x3 grid, 1 per cell.
        "node_resolution": 1.0 / (2 * math.sqrt(2)),  # min=1, max=diag 2√2.
    },
))


def _build_long_edge_path() -> nx.Graph:
    # a-b-c-d with lengths 1, 1, 10 (one stretched edge).
    G = nx.Graph()
    for n, x in [("a", 0), ("b", 1), ("c", 2), ("d", 12)]:
        _add_node(G, n, x, 0)
    for u, v in [("a", "b"), ("b", "c"), ("c", "d")]:
        _add_edge_straight(G, u, v)
    return G


register(Fixture(
    name="long_edge_path",
    description="Four collinear nodes a=0, b=1, c=2, d=12; edges form a path a-b-c-d with lengths 1, 1, 10. Exercises ELD.",
    build=_build_long_edge_path,
    expected={
        "angular_resolution_min_angle": 1.0,
        "angular_resolution_avg_angle": 1.0,
        "aspect_ratio": 1.0,  # h=0.
        "crossing_angle": 1.0,
        "edge_crossings": 1.0,
        "edge_orthogonality": 1.0,
        # L_ideal = (1+1+10)/3 = 4. rel devs = 3/4, 3/4, 6/4. sum = 3. avg = 1.
        # ELD = 1/(1+1) = 0.5.
        "edge_length_deviation": 0.5,
        "gabriel_ratio_edges": 1.0,
        "node_resolution": 1.0 / 12.0,
    },
))


def _build_polyline_bend() -> nx.Graph:
    # Two nodes connected by an L-shaped polyline (purely orthogonal bends).
    G = nx.Graph()
    _add_node(G, "a", 0, 0)
    _add_node(G, "b", 2, 2)
    G.add_edge("a", "b", polyline=True, path="M0,0 L2,0 L2,2")
    return G


register(Fixture(
    name="polyline_bend",
    description="Single L-shaped polyline edge from (0,0) via (2,0) to (2,2). Two orthogonal segments.",
    build=_build_polyline_bend,
    expected={
        # Both segments axis-aligned → δ_e = 0 → EO = 1.
        "edge_orthogonality": 1.0,
        # Bbox promoted to 2×2 → square.
        "aspect_ratio": 1.0,
        "edge_crossings": 1.0,
        "edge_length_deviation": 1.0,  # only one edge.
    },
))


def _build_disconnected_two_paths() -> nx.Graph:
    # Two disjoint components: P3 (a-b-c) at x=0,1,2 and P2 (d-e) at x=4,5.
    G = nx.Graph()
    for n, x in [("a", 0), ("b", 1), ("c", 2), ("d", 4), ("e", 5)]:
        _add_node(G, n, x, 0)
    for u, v in [("a", "b"), ("b", "c"), ("d", "e")]:
        _add_edge_straight(G, u, v)
    return G


register(Fixture(
    name="disconnected_two_paths",
    description="Two collinear path components: P3 a-b-c at x=0,1,2 and P2 d-e at x=4,5. Exercises per-component weighted aggregation in KSM / NP (DQ-1).",
    build=_build_disconnected_two_paths,
    expected={
        # h=0 → degenerate → 1 per spec.
        "aspect_ratio": 1.0,
        # Only eligible node for min-angle AR is 'b' (degree 2, 180° gap) → 1.
        # All others are degree 1 and excluded.
        "angular_resolution_min_angle": 1.0,
        "angular_resolution_avg_angle": 1.0,
        "crossing_angle": 1.0,
        "edge_crossings": 1.0,  # no crossings.
        "edge_orthogonality": 1.0,  # all horizontal.
        "edge_length_deviation": 1.0,  # all unit length.
        "gabriel_ratio_edges": 1.0,
        # Component-weighted KSM: each component is a straight path with
        # d_ij = x_ij, so KSM = 1 per component; weighted sum by node count
        # is also 1 (paper §3.3 disconnected rule, mirrored by DQ-1).
        "kruskal_stress": 1.0,
        # NR is global: min pair = 1, max pair = |a − e| = 5 → 1/5.
        "node_resolution": 1.0 / 5.0,
    },
))


def _build_bezier_curve() -> nx.Graph:
    # Single quadratic Bézier arc from a=(0,0) to b=(4,0), control (2,2);
    # curve peaks at (2,1) at t=0.5 (parabolic arch). Exercises DQ-2 —
    # the metric set's behaviour on a curved edge.
    G = nx.Graph()
    _add_node(G, "a", 0, 0)
    _add_node(G, "b", 4, 0)
    G.add_edge("a", "b", polyline=True, path="M0,0 Q2,2 4,0")
    return G


register(Fixture(
    name="bezier_curve",
    description="Single quadratic Bézier edge from (0,0) to (4,0) with control (2,2); parabolic arch peaking at (2,1). Forces DQ-2 into concrete expected values for curve sampling.",
    build=_build_bezier_curve,
    expected={
        # Only one edge → ELD vacuously 1.
        "edge_length_deviation": 1.0,
        # No crossings possible with a single edge.
        "edge_crossings": 1.0,
        "crossing_angle": 1.0,
        # Both nodes degree 1 → AR is vacuous → 1.
        "angular_resolution_min_angle": 1.0,
        "angular_resolution_avg_angle": 1.0,
    },
))


def _build_k5_crossed() -> nx.Graph:
    # Regular pentagon (unit circumradius) with all 10 edges = K5. The 5
    # chords (pentagram) produce exactly 5 crossings at the interior star
    # points; no side crosses any chord. The crossing count 5 matches the
    # drawing's convex-position crossing count (not cr(K5) = 1).
    G = nx.Graph()
    names = ["v0", "v1", "v2", "v3", "v4"]
    for i, n in enumerate(names):
        theta = math.radians(-90 + i * 72)
        _add_node(G, n, math.cos(theta), math.sin(theta))
    # All C(5,2) = 10 pairs → complete graph on 5 vertices.
    for i in range(5):
        for j in range(i + 1, 5):
            _add_edge_straight(G, names[i], names[j])
    return G


register(Fixture(
    name="k5_crossed",
    description="K5 drawn on a regular unit-circumradius pentagon; the 5 chords form a pentagram with exactly 5 interior crossings. Exercises EC with a non-trivial crossing count.",
    build=_build_k5_crossed,
    expected={
        # m=10, c_all = C(10,2) = 45, c_deg = 5 * C(4,2) = 30, c_max = 15.
        # c = 5 crossings (pentagram). EC = 1 - 5/15 = 2/3.
        "edge_crossings": 2.0 / 3.0,
        # NR: min pair = pentagon side = 2 sin(π/5); max pair = diagonal
        # = 2 sin(2π/5). Ratio = sin(π/5) / sin(2π/5) = 1/φ (golden ratio).
        "node_resolution": math.sin(math.pi / 5) / math.sin(2 * math.pi / 5),
        # All 10 edges drawn; ELD depends on side vs. chord lengths.
        # Sides (5): length 2 sin(π/5). Chords (5): length 2 sin(2π/5).
        # ideal = (5·s + 5·c) / 10 = (s + c) / 2. dev per edge = |L - ideal|
        # = (c - s)/2. rel dev = (c - s) / (s + c) for every edge.
        # avg rel dev = (c - s) / (s + c). ELD = 1 / (1 + (c-s)/(s+c))
        # = (s + c) / (2c) = (sin(π/5) + sin(2π/5)) / (2 sin(2π/5)).
        "edge_length_deviation": (
            (math.sin(math.pi / 5) + math.sin(2 * math.pi / 5))
            / (2 * math.sin(2 * math.pi / 5))
        ),
    },
))


# ---------- Post-registration: metrics that hold 1.0 across every fixture ----------
# Every Phase-3 fixture is constructed so that no non-endpoint node is close
# enough to any edge to trigger a node-edge-occlusion penalty at the default
# epsilon_fraction=0.02. Pin that expectation uniformly.
for _fx in _REGISTRY.values():
    _fx.expected.setdefault("node_edge_occlusion", 1.0)


# ---------- Artefact generation ----------

def generate(name: Optional[str] = None) -> None:
    """Regenerate .geg + .svg for one fixture (by name) or all fixtures."""
    targets = [_REGISTRY[name]] if name else list(_REGISTRY.values())
    for fx in targets:
        G = fx.build()
        write_geg(G, str(FIXTURES_DIR / f"{fx.name}.geg"))
        to_svg(G, str(FIXTURES_DIR / f"{fx.name}.svg"), grid=True)


if __name__ == "__main__":
    generate()
    print(f"Generated {len(_REGISTRY)} fixtures in {FIXTURES_DIR}")
