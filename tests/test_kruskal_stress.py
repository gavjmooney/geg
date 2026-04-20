"""Tests for geg.kruskal_stress.

Hand-computed expected values for small, fully-specified drawings.
Formula reference: paper §3.2 eq. (7), stress = sqrt(sum((x_ij - h_ij)^2) /
sum(x_ij^2)); KSM = 1 - stress, with h_ij the isotonic regression fit.
"""

import math

import networkx as nx
import pytest

from geg import kruskal_stress


def _layout(coords):
    """Build a graph with x/y node attrs from a dict {node: (x, y)}."""
    G = nx.Graph()
    for n, (x, y) in coords.items():
        G.add_node(n, x=float(x), y=float(y))
    return G


class TestDegenerate:
    def test_single_node(self):
        G = _layout({"a": (0.0, 0.0)})
        assert kruskal_stress(G) == 1.0


class TestPerfectEmbeddings:
    """Layouts where Euclidean distances match graph distances exactly (up
    to a single monotone scaling) — isotonic fit is the identity, sum of
    squared residuals is 0, KSM = 1 - 0 = 1."""

    def test_two_nodes_unit_edge(self):
        # Only pair is (A, B); d = 1, x = 1. Isotonic fit h = 1 trivially,
        # so the numerator sum((x - h)**2) = 0 and KSM = 1.
        G = _layout({"a": (0.0, 0.0), "b": (1.0, 0.0)})
        G.add_edge("a", "b")
        assert kruskal_stress(G) == pytest.approx(1.0)

    def test_equilateral_triangle(self):
        # K3 with unit edges. The three pairs all have d = 1 and x = 1
        # (equilateral side length is 1), so the (d, x) scatter collapses
        # to a single point (1, 1) and the isotonic fit is h = x exactly.
        G = _layout({
            "a": (0.0, 0.0),
            "b": (1.0, 0.0),
            "c": (0.5, math.sqrt(3) / 2),
        })
        G.add_edges_from([("a", "b"), ("b", "c"), ("c", "a")])
        assert kruskal_stress(G) == pytest.approx(1.0)

    def test_collinear_path_proportional_layout(self):
        # Path A-B-C laid out on the x-axis with unit spacing. Pairs give
        # d = [1, 1, 2] and x = [1, 1, 2] — same numbers in the same order,
        # so isotonic regression returns h = x and residuals are all 0.
        G = _layout({"a": (0.0, 0.0), "b": (1.0, 0.0), "c": (2.0, 0.0)})
        G.add_edges_from([("a", "b"), ("b", "c")])
        assert kruskal_stress(G) == pytest.approx(1.0)


class TestStretchedPath:
    def test_path_with_stretched_b_c(self):
        """Three-node path A-B-C with B at (1,0), C at (3,0).

        dij (graph) = [1, 1, 2]   for pairs (A,B), (B,C), (A,C)
        xij (layout) = [1, 2, 3]
        Isotonic fit of x onto d: ties at d=1 pool to mean(1,2)=1.5; d=2 → 3.
        h = [1.5, 1.5, 3]
        raw  = 0.25 + 0.25 + 0    = 0.5
        norm = 1 + 4 + 9          = 14
        stress = sqrt(0.5 / 14)   ≈ 0.18898223650
        KSM    = 1 - stress       ≈ 0.81101776350
        """
        G = _layout({"a": (0.0, 0.0), "b": (1.0, 0.0), "c": (3.0, 0.0)})
        G.add_edges_from([("a", "b"), ("b", "c")])
        expected = 1.0 - math.sqrt(0.5 / 14.0)
        assert kruskal_stress(G) == pytest.approx(expected, rel=1e-9)


class TestInvariants:
    def test_output_in_unit_interval(self):
        # Adversarial layout: random-ish coords on a path graph.
        G = _layout({
            "a": (0.0, 0.0),
            "b": (7.0, -2.0),
            "c": (1.0, 5.0),
            "d": (-3.0, 4.0),
        })
        G.add_edges_from([("a", "b"), ("b", "c"), ("c", "d")])
        k = kruskal_stress(G)
        assert 0.0 <= k <= 1.0

    def test_translation_invariant(self):
        coords = {"a": (0.0, 0.0), "b": (1.0, 0.0), "c": (3.0, 0.0)}
        shifted = {n: (x + 100.0, y - 50.0) for n, (x, y) in coords.items()}
        G1 = _layout(coords)
        G1.add_edges_from([("a", "b"), ("b", "c")])
        G2 = _layout(shifted)
        G2.add_edges_from([("a", "b"), ("b", "c")])
        assert kruskal_stress(G1) == pytest.approx(kruskal_stress(G2))

    def test_uniform_scale_invariant(self):
        """KSM compares the *ordering* of distances; uniform scaling should
        leave the metric unchanged (isotonic regression absorbs the scale)."""
        coords = {"a": (0.0, 0.0), "b": (1.0, 0.0), "c": (3.0, 0.0)}
        scaled = {n: (x * 17.3, y * 17.3) for n, (x, y) in coords.items()}
        G1 = _layout(coords)
        G1.add_edges_from([("a", "b"), ("b", "c")])
        G2 = _layout(scaled)
        G2.add_edges_from([("a", "b"), ("b", "c")])
        assert kruskal_stress(G1) == pytest.approx(kruskal_stress(G2))

    def test_arbitrary_rotation_invariant(self):
        """Pairwise Euclidean distances are rotation-invariant, so KSM is
        too — the (graph-dist, layout-dist) pairs fed to the isotonic
        regression are identical before and after the rotation."""
        theta = math.radians(37.0)
        c, s = math.cos(theta), math.sin(theta)
        coords = {"a": (0.0, 0.0), "b": (1.0, 0.0), "c": (3.0, 0.0)}
        rotated = {n: (x * c - y * s, x * s + y * c) for n, (x, y) in coords.items()}
        G1 = _layout(coords)
        G1.add_edges_from([("a", "b"), ("b", "c")])
        G2 = _layout(rotated)
        G2.add_edges_from([("a", "b"), ("b", "c")])
        assert kruskal_stress(G1) == pytest.approx(kruskal_stress(G2))


class TestDisconnected:
    """Paper §3.3: KSM on disconnected drawings is a weighted sum over
    connected components, weights proportional to each component's convex-hull
    area."""

    def test_two_perfectly_embedded_components_return_one(self):
        # Component 1: unit equilateral triangle.
        # Component 2: equilateral triangle scaled ×2, translated away.
        G = _layout({
            "a": (0.0, 0.0),
            "b": (1.0, 0.0),
            "c": (0.5, math.sqrt(3) / 2),
            "d": (100.0, 100.0),
            "e": (102.0, 100.0),
            "f": (101.0, 100.0 + math.sqrt(3)),
        })
        G.add_edges_from([
            ("a", "b"), ("b", "c"), ("c", "a"),
            ("d", "e"), ("e", "f"), ("f", "d"),
        ])
        # Both components are perfectly embedded (KSM per-component = 1), so
        # the weighted sum is 1 regardless of the individual hull weights.
        assert kruskal_stress(G) == pytest.approx(1.0)

    def test_single_component_matches_plain_kruskal(self):
        # A disconnected "drawing" whose only non-trivial component is the
        # stretched path should give the same number as the connected version,
        # because isolated singleton nodes have no pairs and zero weight.
        path_coords = {"a": (0.0, 0.0), "b": (1.0, 0.0), "c": (3.0, 0.0)}
        G_connected = _layout(path_coords)
        G_connected.add_edges_from([("a", "b"), ("b", "c")])

        G_disconnected = _layout({
            **path_coords,
            "d": (50.0, 50.0),  # isolated singleton
        })
        G_disconnected.add_edges_from([("a", "b"), ("b", "c")])

        assert kruskal_stress(G_disconnected) == pytest.approx(
            kruskal_stress(G_connected)
        )

    def test_does_not_raise_on_disconnected(self):
        # Two disjoint edges — connected-case code path KeyErrors here.
        G = _layout({
            "a": (0.0, 0.0), "b": (1.0, 0.0),
            "c": (5.0, 5.0), "d": (6.0, 5.0),
        })
        G.add_edges_from([("a", "b"), ("c", "d")])
        result = kruskal_stress(G)
        assert 0.0 <= result <= 1.0


class TestDirectedGraph:
    def test_directed_path_no_key_error(self):
        """Regression: on a DiGraph, all_pairs_shortest_path_length is
        asymmetric, so naive pairwise lookups hit KeyError. Stress should
        treat the graph as undirected for this computation.

        Undirected view: n1 - n2 - n0 (length-2 path).
            graph-distance  d = [1, 1, 2]    for (n1,n2), (n2,n0), (n1,n0)
            Euclidean       x = [400, 400, 400·√2]
        Pairs at d=1 tie (both x=400, pool mean = 400); pair at d=2 has
        x=400·√2. h is monotone in d and equals x everywhere, so residuals
        are 0 and KSM = 1.
        """
        G = nx.DiGraph()
        G.add_node("n0", x=0.0, y=0.0)
        G.add_node("n1", x=400.0, y=400.0)
        G.add_node("n2", x=400.0, y=0.0)
        G.add_edge("n1", "n2")  # n0 is a sink under directed semantics
        G.add_edge("n2", "n0")
        assert kruskal_stress(G) == pytest.approx(1.0)

    def test_matches_undirected_equivalent(self):
        """Kruskal stress must be identical on a DiGraph and its undirected
        twin: stress compares Euclidean distance (symmetric) to graph
        distance."""
        coords = {"a": (0.0, 0.0), "b": (1.0, 0.0), "c": (2.0, 0.0)}
        DG = nx.DiGraph()
        for n, (x, y) in coords.items():
            DG.add_node(n, x=x, y=y)
        DG.add_edges_from([("a", "b"), ("b", "c")])

        UG = DG.to_undirected()
        assert kruskal_stress(DG) == pytest.approx(kruskal_stress(UG))
