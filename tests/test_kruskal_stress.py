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
    def test_two_nodes_unit_edge(self):
        # A-B, unit layout, d = x = 1 → zero stress.
        G = _layout({"a": (0.0, 0.0), "b": (1.0, 0.0)})
        G.add_edge("a", "b")
        assert kruskal_stress(G) == pytest.approx(1.0)

    def test_equilateral_triangle(self):
        # Triangle with unit graph-distances and unit Euclidean distances.
        G = _layout({
            "a": (0.0, 0.0),
            "b": (1.0, 0.0),
            "c": (0.5, math.sqrt(3) / 2),
        })
        G.add_edges_from([("a", "b"), ("b", "c"), ("c", "a")])
        assert kruskal_stress(G) == pytest.approx(1.0)

    def test_collinear_path_proportional_layout(self):
        # A-B-C; layout distances x = [1, 1, 2] match d = [1, 1, 2] exactly.
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
