"""Tests for geg.neighbourhood_preservation.

Paper §3.2 eq. (8): NP = |A ∧ M^k| / |A ∨ M^k|,
with k = floor(2|E|/|V|) = floor(average degree).
"""

import networkx as nx
import pytest

from geg import neighbourhood_preservation as NP


def _layout(coords):
    G = nx.Graph()
    for n, (x, y) in coords.items():
        G.add_node(n, x=float(x), y=float(y))
    return G


class TestDegenerate:
    def test_single_node(self):
        G = _layout({"a": (0.0, 0.0)})
        assert NP(G) == 1.0


class TestPerfectPreservation:
    def test_two_nodes_one_edge(self):
        # n=2, avg deg = 1, k = 1. Each node's nearest is the other.
        G = _layout({"a": (0.0, 0.0), "b": (1.0, 0.0)})
        G.add_edge("a", "b")
        assert NP(G) == pytest.approx(1.0)

    def test_triangle(self):
        # n=3, avg deg = 2, k = 2. Each node's 2 nearest are the other two.
        G = _layout({"a": (0.0, 0.0), "b": (1.0, 0.0), "c": (0.5, 0.87)})
        G.add_edges_from([("a", "b"), ("b", "c"), ("c", "a")])
        assert NP(G) == pytest.approx(1.0)

    def test_complete_k4_any_layout(self):
        # K4: every node is adjacent to every other. k = 3 means every node's
        # 3 nearest are exactly the other three → K matches A perfectly.
        G = _layout({
            "a": (0.0, 0.0), "b": (5.0, 1.0),
            "c": (7.0, -3.0), "d": (2.0, -2.0),
        })
        for u in G.nodes():
            for v in G.nodes():
                if u < v:
                    G.add_edge(u, v)
        assert NP(G) == pytest.approx(1.0)


class TestPartialPreservation:
    def test_star_with_distinct_leaf_distances(self):
        """Star K_{1,3}: centre C at origin, leaves at (1,0), (-2,0), (0,3).

        n=4, m=3, avg deg = 1.5, k = 1.
        Nearest neighbours (geometric):
          C  → L1 (dist 1)
          L1 → C  (dist 1)
          L2 → C  (dist 2)
          L3 → C  (dist 3)
        A entries = 6 (3 undirected edges).
        K entries = 4 (one per row, no self).
        A ∧ K = 4; A ∨ K = 6.  NP = 4/6 = 2/3.
        """
        G = _layout({
            "c": (0.0, 0.0),
            "l1": (1.0, 0.0),
            "l2": (-2.0, 0.0),
            "l3": (0.0, 3.0),
        })
        G.add_edges_from([("c", "l1"), ("c", "l2"), ("c", "l3")])
        assert NP(G) == pytest.approx(4.0 / 6.0)

    def test_path_of_four_asymmetric_spacing(self):
        """Path a-b-c-d at x = 0, 1, 3, 6 (no ties in nearest-neighbour).

        k = floor((2·3)/4) = 1.
        A has 6 directed entries (3 undirected edges).
        K entries (per node):
          a → b  (nearest)
          b → a  (1 < 2)
          c → b  (2 < 3)
          d → c  (only one direction to consider)
        A ∧ K = 4 matches; A ∨ K = 6. NP = 4/6.
        """
        G = _layout({
            "a": (0.0, 0.0),
            "b": (1.0, 0.0),
            "c": (3.0, 0.0),
            "d": (6.0, 0.0),
        })
        G.add_edges_from([("a", "b"), ("b", "c"), ("c", "d")])
        assert NP(G) == pytest.approx(4.0 / 6.0)


class TestInvariants:
    def test_translation_invariant(self):
        coords = {"a": (0.0, 0.0), "b": (1.0, 0.0), "c": (3.0, 0.0)}
        G1 = _layout(coords)
        G1.add_edges_from([("a", "b"), ("b", "c")])
        G2 = _layout({n: (x + 100, y - 50) for n, (x, y) in coords.items()})
        G2.add_edges_from([("a", "b"), ("b", "c")])
        assert NP(G1) == pytest.approx(NP(G2))

    def test_uniform_scale_invariant(self):
        coords = {"a": (0.0, 0.0), "b": (1.0, 0.0), "c": (3.0, 0.0)}
        G1 = _layout(coords)
        G1.add_edges_from([("a", "b"), ("b", "c")])
        G2 = _layout({n: (x * 17.3, y * 17.3) for n, (x, y) in coords.items()})
        G2.add_edges_from([("a", "b"), ("b", "c")])
        assert NP(G1) == pytest.approx(NP(G2))


class TestDisconnected:
    """Paper §3.3: NP on disconnected drawings is a weighted sum over
    connected components, weights proportional to each component's convex-hull
    area."""

    def test_two_well_separated_perfect_triangles(self):
        # Two equilateral triangles far enough apart that within-component
        # k-NN never crosses component boundaries.
        G = _layout({
            "a": (0.0, 0.0), "b": (1.0, 0.0), "c": (0.5, 0.87),
            "d": (100.0, 100.0), "e": (101.0, 100.0), "f": (100.5, 100.87),
        })
        G.add_edges_from([
            ("a", "b"), ("b", "c"), ("c", "a"),
            ("d", "e"), ("e", "f"), ("f", "d"),
        ])
        assert NP(G) == pytest.approx(1.0)

    def test_close_components_with_cross_component_knn(self):
        """Component 1 = long edge (A,B) at x=0 and x=10; component 2 =
        isolated node C at (1, 0.1) — closer to A than B is.

        Connected-case NP blindly runs k-NN on the full layout:
          A's nearest = C (wrong component), B's nearest = C, C's nearest = A.
          → A ∧ K = 0, A ∨ K = 5, NP = 0.

        Paper §3.3 result:
          Component 1 is a K2 → NP = 1. Component 2 is a singleton (skipped).
          Weighted by hull area → NP = 1.
        """
        G = _layout({
            "a": (0.0, 0.0),
            "b": (10.0, 0.0),
            "c": (1.0, 0.1),
        })
        G.add_edge("a", "b")
        # c is isolated
        assert NP(G) == pytest.approx(1.0)

    def test_does_not_raise_on_all_isolated(self):
        G = _layout({"a": (0.0, 0.0), "b": (1.0, 0.0), "c": (2.0, 0.0)})
        # No edges; every node is isolated.
        result = NP(G)
        assert 0.0 <= result <= 1.0
