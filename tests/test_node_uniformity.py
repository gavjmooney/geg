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


class TestIncludeCurvesKwarg:
    """`include_curves=True` switches the grid from the node-only bbox to
    the curve-promoted drawing bbox. The default remains False (node-only),
    so existing scores are unchanged unless the caller opts in.
    """

    def _two_nodes_with_ballooning_curve(self):
        """Two nodes at (0, 0) and (1, 0). The edge path is a cubic that
        bulges up, so the curve-promoted bbox is much taller than the
        node-only one. (`polyline=True` is required: `curves_promotion`
        only explodes edges flagged as polylines, matching what the GEG
        reader sets for non-straight paths.)"""
        G = nx.Graph()
        G.add_node("a", x=0.0, y=0.0)
        G.add_node("b", x=1.0, y=0.0)
        G.add_edge("a", "b", path="M 0,0 C 0,4 1,4 1,0", polyline=True)
        return G

    def test_default_uses_node_only_bbox(self):
        G = self._two_nodes_with_ballooning_curve()
        # Node bbox has height=0 → collapses to 1×N grid, one node per cell → NU=1.
        assert node_uniformity(G) == pytest.approx(1.0)

    def test_include_curves_uses_promoted_bbox(self):
        G = self._two_nodes_with_ballooning_curve()
        # Curve bbox is 1×~3 → rows=floor(sqrt(2))=1, cols=2. cell_w=0.5.
        # Both nodes lie at y=0 (top row), x ∈ {0, 1} → cells [0,0] and [0,1].
        # Each node in its own cell → NU = 1.0 as well — so this case alone
        # doesn't distinguish the kwarg.  Verify only that the two modes
        # don't crash and return valid scores; a discriminating case is in
        # `test_include_curves_changes_score`.
        s = node_uniformity(G, include_curves=True)
        assert 0.0 <= s <= 1.0

    def test_include_curves_changes_score(self):
        """Four nodes arranged as a tight cluster in the top-left, with one
        edge whose curve sweeps far to the bottom-right. Node-only bbox is
        tight around the cluster (NU high); curve-promoted bbox is large,
        putting all four nodes in one cell (NU low)."""
        G = nx.Graph()
        for n, (x, y) in {
            "a": (0.0, 0.0), "b": (0.0, 1.0),
            "c": (1.0, 0.0), "d": (1.0, 1.0),
        }.items():
            G.add_node(n, x=x, y=y)
        # Edge with a cubic that balloons out to (20, 20), way past the nodes.
        G.add_edge("a", "b", path="M 0,0 C 20,20 20,20 0,1", polyline=True)

        node_only = node_uniformity(G)                       # default False
        drawing   = node_uniformity(G, include_curves=True)
        # Default behaviour unchanged — 2×2 grid, one node per cell.
        assert node_only == pytest.approx(1.0)
        # With the promoted bbox the grid is much larger; all four nodes
        # fall into the top-left cell → NU < 1.
        assert drawing < node_only

    def test_caller_supplied_bbox_overrides_include_curves(self):
        G = self._two_nodes_with_ballooning_curve()
        # Explicit bbox — `include_curves` is ignored.
        explicit = (-10.0, -10.0, 10.0, 10.0)
        a = node_uniformity(G, bbox=explicit, include_curves=False)
        b = node_uniformity(G, bbox=explicit, include_curves=True)
        assert a == b


class TestInvariants:
    """Node uniformity is translation- and uniform-scale-invariant: the
    axis-aligned grid scales and shifts with the bounding box, so each
    node stays in the same cell. It is *not* rotation-invariant in
    general — the grid is axis-aligned to the bbox, not to the drawing,
    so rotating the layout redraws the cell boundaries relative to the
    nodes and node↔cell membership can change. No arbitrary-rotation
    test is included for this reason."""

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
