"""Tests for geg.node_uniformity.

Paper §3.2 eq. (10):
  rows  = floor(sqrt(|V|))
  cols  = ceil(|V| / rows)
  T     = rows * cols
  mean  = |V| / T
  D     = sum_i |c_i - mean|
  D_max = 2 |V| (T - 1) / T
  NU    = 1 - D / D_max
Height=0 or width=0 collapses the grid to 1 row or 1 column.
"""

import networkx as nx
import pytest

from geg import node_uniformity


def _layout(coords):
    G = nx.Graph()
    for n, (x, y) in coords.items():
        G.add_node(n, x=float(x), y=float(y))
    return G


class TestDegenerate:
    def test_single_node(self):
        G = _layout({"a": (0.0, 0.0)})
        assert node_uniformity(G) == 1.0

    def test_all_coincident(self):
        G = _layout({"a": (0.0, 0.0), "b": (0.0, 0.0), "c": (0.0, 0.0)})
        assert node_uniformity(G) == 1.0


class TestUniformGrids:
    def test_four_nodes_on_2x2_grid(self):
        # rows=2, cols=2, T=4, mean=1. Each corner in its own cell → D=0.
        G = _layout({
            "a": (0.0, 0.0), "b": (1.0, 0.0),
            "c": (0.0, 1.0), "d": (1.0, 1.0),
        })
        assert node_uniformity(G) == pytest.approx(1.0)

    def test_nine_nodes_on_3x3_grid(self):
        # rows=3, cols=3, T=9, mean=1.
        coords = {f"n{i}_{j}": (float(i), float(j)) for i in range(3) for j in range(3)}
        G = _layout(coords)
        assert node_uniformity(G) == pytest.approx(1.0)


class TestKnownDeviations:
    def test_three_clustered_one_corner_2x2(self):
        """N=4, rows=2, cols=2, T=4, mean=1, D_max=6.

        Three nodes clustered at (0,0) and one at (1,1):
          cell counts = [3, 0, 0, 1]  →  D = 2+1+1+0 = 4
          NU = 1 - 4/6 = 1/3.
        """
        G = _layout({
            "a": (0.0, 0.0),
            "b": (0.0, 0.0),
            "c": (0.0, 0.0),
            "d": (1.0, 1.0),
        })
        assert node_uniformity(G) == pytest.approx(1.0 / 3.0)

    def test_two_nodes_same_cell_is_zero(self):
        """N=2 → rows=1, cols=2, T=2, mean=1, D_max=2.

        Two coincident-on-x nodes at (0, 0) and (0, 1): width=0 forces cols=1,
        rows=N=2 (collapsed to 1D).
          cell counts (rows=2): [1, 1] → D=0 → NU=1.
        """
        G = _layout({"a": (0.0, 0.0), "b": (0.0, 1.0)})
        assert node_uniformity(G) == pytest.approx(1.0)

    def test_two_nodes_with_2d_bbox_perfect(self):
        # Non-degenerate bbox so default rows=1, cols=2 grid kicks in.
        G = _layout({"a": (0.0, 0.0), "b": (1.0, 1.0)})
        # rows = floor(sqrt(2)) = 1, cols = ceil(2/1) = 2.
        # Each node in a distinct cell → NU = 1.
        assert node_uniformity(G) == pytest.approx(1.0)

    def test_horizontal_stack_even_spread(self):
        """Three nodes along the x-axis at 0, 1, 2. height=0 → rows=1, cols=N=3.
        One node per column → D=0 → NU=1.
        """
        G = _layout({"a": (0.0, 0.0), "b": (1.0, 0.0), "c": (2.0, 0.0)})
        assert node_uniformity(G) == pytest.approx(1.0)

    def test_horizontal_stack_clumped(self):
        """Four nodes along the x-axis at 0, 0, 0, 1.
        height=0 → rows=1, cols=4. cell_w = 0.25.
        Columns (x): 0 → c=0, 0 → c=0, 0 → c=0, 1 → c=int(1/0.25)=4→clamped 3.
        counts = [3, 0, 0, 1], mean=1, D = 2+1+1+0 = 4, D_max = 2*4*3/4 = 6.
        NU = 1 - 4/6 = 1/3.
        """
        G = _layout({
            "a": (0.0, 0.0),
            "b": (0.0, 0.0),
            "c": (0.0, 0.0),
            "d": (1.0, 0.0),
        })
        assert node_uniformity(G) == pytest.approx(1.0 / 3.0)


class TestInvariants:
    def test_translation_invariant(self):
        coords = {
            "a": (0.0, 0.0), "b": (1.0, 0.0),
            "c": (0.0, 1.0), "d": (1.0, 1.0),
        }
        G1 = _layout(coords)
        G2 = _layout({n: (x + 500, y - 300) for n, (x, y) in coords.items()})
        assert node_uniformity(G1) == pytest.approx(node_uniformity(G2))

    def test_uniform_scale_invariant(self):
        coords = {
            "a": (0.0, 0.0), "b": (1.0, 0.0),
            "c": (0.0, 1.0), "d": (1.0, 1.0),
        }
        G1 = _layout(coords)
        G2 = _layout({n: (x * 7.7, y * 7.7) for n, (x, y) in coords.items()})
        assert node_uniformity(G1) == pytest.approx(node_uniformity(G2))
