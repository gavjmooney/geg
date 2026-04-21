"""Smoke tests for main.py — the library tutorial / CLI entry point.

Covers the three load dispatch paths (.geg / .graphml / .gml), the metric
table coverage, and an end-to-end batch run against the fixtures directory.
"""

import csv
import importlib.util
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
MAIN_PATH = REPO_ROOT / "main.py"
FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures"


def _import_main():
    spec = importlib.util.spec_from_file_location("_geg_main", MAIN_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["_geg_main"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def m():
    return _import_main()


class TestFindDrawings:
    def test_walks_subdirs(self, m):
        drawings = list(m.find_drawings(FIXTURES_DIR))
        suffixes = {p.suffix.lower() for p in drawings}
        assert ".geg" in suffixes
        assert ".graphml" in suffixes
        assert ".gml" in suffixes

    def test_single_file_yielded_directly(self, m):
        path = FIXTURES_DIR / "equilateral_triangle.geg"
        assert list(m.find_drawings(path)) == [path]

    def test_unsupported_extension_skipped(self, m, tmp_path):
        (tmp_path / "notes.txt").write_text("hello")
        assert list(m.find_drawings(tmp_path)) == []


class TestLoadDrawing:
    def test_geg(self, m):
        G = m.load_drawing(FIXTURES_DIR / "equilateral_triangle.geg")
        assert G.number_of_nodes() == 3

    def test_graphml(self, m):
        G = m.load_drawing(FIXTURES_DIR / "io" / "sample.graphml")
        assert G.number_of_nodes() == 2

    def test_gml(self, m):
        G = m.load_drawing(FIXTURES_DIR / "io" / "sample.gml")
        assert G.number_of_nodes() == 2

    def test_unknown_extension_raises(self, m, tmp_path):
        p = tmp_path / "x.unknown"
        p.write_text("")
        with pytest.raises(ValueError, match="Unsupported input extension"):
            m.load_drawing(p)


class TestMetricTable:
    def test_canonical_metrics_present(self, m):
        """The canonical metric set — as curated for the batch CSV — must
        cover every paper-§3.2 metric plus node_edge_occlusion. Gabriel Ratio
        is intentionally excluded (non-canonical per paper §3.2), and only the
        min-angle variant of Angular Resolution is included (the avg-angle
        variant is a library extension).
        """
        expected = {
            "angular_resolution",
            "aspect_ratio",
            "crossing_angle",
            "edge_crossings",
            "edge_length_deviation",
            "edge_orthogonality",
            "kruskal_stress",
            "neighbourhood_preservation",
            "node_edge_occlusion",
            "node_resolution",
            "node_uniformity",
        }
        assert set(m.METRIC_NAMES) == expected

    def test_non_canonical_metrics_still_callable_from_library(self, m):
        """Deselected metrics must still be reachable from `geg` directly —
        only the batch / CLI surface is curated."""
        import geg as geg_pkg
        assert callable(geg_pkg.angular_resolution_avg_angle)
        assert callable(geg_pkg.gabriel_ratio_edges)
        assert callable(geg_pkg.gabriel_ratio_nodes)

    def test_compute_metrics_returns_all_keys(self, m):
        G = m.load_drawing(FIXTURES_DIR / "equilateral_triangle.geg")
        result = m.compute_metrics(G)
        assert set(result.keys()) == set(m.METRIC_NAMES)
        for name, value in result.items():
            assert value == value, f"{name} is NaN on a clean fixture"


class TestComputeMetricsEdgeCases:
    """compute_metrics must degrade gracefully on pathological inputs — it
    sits on the batch-CSV hot path, and a crash on one file would kill the
    whole batch. All metrics guard against empty / degenerate / self-loop
    / directed / multi graphs by returning a finite [0, 1] value rather
    than raising; compute_metrics' per-metric try-except catches anything
    that slips through as NaN. Pin this behaviour explicitly rather than
    relying on fixture-level happy paths."""

    def test_empty_graph(self, m):
        import networkx as nx
        G = nx.Graph()
        result = m.compute_metrics(G)
        assert set(result.keys()) == set(m.METRIC_NAMES)
        # Vacuous graphs: every metric should return 1.0 (best / no issues)
        # or NaN (if the metric's derivation is genuinely undefined).
        import math
        for name, value in result.items():
            assert value == 1.0 or math.isnan(value), f"{name} = {value}"

    def test_single_node_graph(self, m):
        import networkx as nx
        G = nx.Graph(); G.add_node("a", x=0.0, y=0.0)
        result = m.compute_metrics(G)
        assert set(result.keys()) == set(m.METRIC_NAMES)
        import math
        for name, value in result.items():
            assert math.isfinite(value) or math.isnan(value), f"{name} = {value}"

    def test_self_loop_with_curve(self, m):
        """Self-loops are legal in GEG; `a → a` with a curved path should
        not crash any metric."""
        import networkx as nx
        G = nx.Graph()
        G.add_node("a", x=0.0, y=0.0)
        G.add_node("b", x=10.0, y=0.0)
        G.add_edge("a", "a", polyline=True, path="M0,0 Q2,2 0,0")
        G.add_edge("a", "b", path="M0,0 L10,0")
        result = m.compute_metrics(G)
        import math
        for name, value in result.items():
            assert math.isfinite(value) or math.isnan(value), f"{name} = {value}"


class TestSelfLoopMetricValues:
    """Pin metric values on canonical self-loop drawings. Existing
    self-loop coverage checks that nothing crashes but pins no values —
    this makes silent drift visible if a future refactor subtly changes
    how any metric sees the u == v case.

    Not exhaustive: metrics that a self-loop should leave undisturbed
    (EC, CA, NEO, GR, NR) are pinned at 1.0; metrics that self-loops
    materially change (EO, AR, ELD, Asp) are pinned at currently-
    observed values against a known fixture.
    """

    def test_pure_self_loop_with_isolated_node(self):
        """Single self-loop on `a` plus an isolated `b`. The self-loop's
        Q curve extends the bbox above the chord so Asp ≠ 1."""
        import pytest
        import networkx as nx
        from geg import (
            angular_resolution_min_angle, aspect_ratio, crossing_angle,
            edge_crossings, edge_length_deviation, edge_orthogonality,
            gabriel_ratio_edges, node_edge_occlusion, node_resolution,
            node_uniformity,
        )
        G = nx.Graph()
        G.add_node("a", x=0.0, y=0.0)
        G.add_node("b", x=10.0, y=0.0)
        G.add_edge("a", "a", polyline=True, path="M0,0 Q3,3 0,0")

        # Metrics that ignore / are immune to the self-loop.
        assert angular_resolution_min_angle(G) == pytest.approx(1.0)
        assert crossing_angle(G) == pytest.approx(1.0)
        assert edge_crossings(G) == pytest.approx(1.0)
        assert gabriel_ratio_edges(G) == pytest.approx(1.0)
        assert node_edge_occlusion(G) == pytest.approx(1.0)
        assert node_resolution(G) == pytest.approx(1.0)
        assert node_uniformity(G) == pytest.approx(1.0)
        assert edge_length_deviation(G) == pytest.approx(1.0)

        # Aspect ratio uses the curve-promoted bbox: width = 10, height
        # = 1.5 (Q curve peak at (1.5, 1.5), t=0.5) → h/w = 0.15.
        assert aspect_ratio(G) == pytest.approx(0.15)

        # EO on the self-loop only: the Q curve samples at ~45° angles,
        # giving a mean segment-deviation ≈ 1 → EO ≈ 0.
        assert edge_orthogonality(G) == pytest.approx(0.0, abs=1e-6)

    def test_triangle_plus_self_loop(self):
        """Equilateral triangle with an extra self-loop on vertex `a`.
        The self-loop *does* perturb the metrics that weight edges —
        pin current behaviour so we catch silent drift."""
        import math
        import pytest
        import networkx as nx
        from geg import (
            angular_resolution_min_angle, edge_crossings, edge_length_deviation,
            edge_orthogonality, gabriel_ratio_edges, node_edge_occlusion,
        )
        G = nx.Graph()
        G.add_node("a", x=0.0, y=0.0)
        G.add_node("b", x=1.0, y=0.0)
        G.add_node("c", x=0.5, y=math.sqrt(3) / 2)
        G.add_edge("a", "b", path="M0,0 L1,0")
        G.add_edge("b", "c", path=f"M1,0 L0.5,{math.sqrt(3) / 2}")
        G.add_edge("c", "a", path=f"M0.5,{math.sqrt(3) / 2} L0,0")
        G.add_edge("a", "a", polyline=True, path="M0,0 Q-0.3,-0.3 0,0")

        # AR changes at vertex a (now degree 4 with self-loop's two
        # tangents, vs degree 2 on plain triangle).
        assert angular_resolution_min_angle(G) == pytest.approx(4.0 / 9.0)
        # EC / NEO / GR still see no crossings / occlusions on a legal
        # planar triangle + localised self-loop.
        assert edge_crossings(G) == pytest.approx(1.0)
        assert gabriel_ratio_edges(G) == pytest.approx(1.0)
        assert node_edge_occlusion(G) == pytest.approx(1.0)
        # EO / ELD drift vs. the plain triangle (EO=5/9, ELD=1):
        assert edge_orthogonality(G) == pytest.approx(0.416667, abs=1e-5)
        assert edge_length_deviation(G) == pytest.approx(0.798594, abs=1e-5)

    def test_directed_graph_with_curve(self, m):
        import networkx as nx
        G = nx.DiGraph()
        G.add_node("a", x=0.0, y=0.0)
        G.add_node("b", x=10.0, y=0.0)
        G.add_edge("a", "b", polyline=True, path="M0,0 Q5,5 10,0")
        result = m.compute_metrics(G)
        # All metrics at least return SOMETHING (no crashes); specifically
        # EO, EC, NEO, Asp all return finite numbers on a single curved edge.
        import math
        for name in ("edge_orthogonality", "edge_crossings",
                     "node_edge_occlusion", "aspect_ratio"):
            assert math.isfinite(result[name]), f"{name} not finite"

    def test_multigraph_with_parallel_curves(self, m):
        """Two parallel curved edges between the same pair of nodes."""
        import networkx as nx
        G = nx.MultiGraph()
        G.add_node("a", x=0.0, y=0.0)
        G.add_node("b", x=10.0, y=0.0)
        G.add_edge("a", "b", polyline=True, path="M0,0 Q5,3 10,0")
        G.add_edge("a", "b", polyline=True, path="M0,0 Q5,-3 10,0")
        result = m.compute_metrics(G)
        import math
        for name in ("edge_orthogonality", "edge_crossings",
                     "node_edge_occlusion"):
            assert math.isfinite(result[name]), f"{name} not finite"


class TestComputeMetricsSharing:
    """The batch processor must not re-run expensive intermediates that
    several metrics share. Hot spots:
      - `get_bounding_box(G)` (curve-promoted) feeds aspect_ratio.
      - `get_bounding_box(G, promote=False)` (node-only) feeds
        node_uniformity and node_edge_occlusion. Only the promoted call
        runs `curves_promotion`; the node-only path is a cheap scan of
        node positions.
      - `edge_crossings(return_crossings=True)` returns both the score
        and the crossings list that `crossing_angle` needs.
    """

    def test_get_bounding_box_called_at_most_twice_per_graph(self, m, monkeypatch):
        """Once curve-promoted (Asp), once node-only (NU + NEO). The
        node-only call is O(n) and shared between NU and NEO; the
        expensive promoted call happens exactly once."""
        import geg as geg_pkg
        calls = {"promoted": 0, "node_only": 0}
        original = geg_pkg.get_bounding_box

        def counting(G, *args, **kwargs):
            promote = kwargs.get("promote", True)
            if len(args) >= 1:
                promote = args[0]
            if promote:
                calls["promoted"] += 1
            else:
                calls["node_only"] += 1
            return original(G, *args, **kwargs)

        monkeypatch.setattr(m.geg, "get_bounding_box", counting)

        G = m.load_drawing(FIXTURES_DIR / "equilateral_triangle.geg")
        m.compute_metrics(G)
        assert calls["promoted"] == 1, (
            f"curve-promoted get_bounding_box was called {calls['promoted']}× "
            f"(expected 1 — runs curves_promotion, must be shared)"
        )
        assert calls["node_only"] == 1, (
            f"node-only get_bounding_box was called {calls['node_only']}× "
            f"(expected 1 — shared between NU and NEO)"
        )

    def test_edge_crossings_called_once_per_graph(self, m, monkeypatch):
        import geg as geg_pkg
        calls = {"n": 0}
        original = geg_pkg.edge_crossings

        def counting(G, *args, **kwargs):
            calls["n"] += 1
            return original(G, *args, **kwargs)

        monkeypatch.setattr(m.geg, "edge_crossings", counting)

        G = m.load_drawing(FIXTURES_DIR / "equilateral_triangle.geg")
        m.compute_metrics(G)
        assert calls["n"] == 1, (
            f"edge_crossings was called {calls['n']}× in one compute_metrics; "
            f"expected 1 (shared with crossing_angle via return_crossings=True)"
        )

    def test_results_unchanged_from_shared_path(self, m):
        """Precomputing shared data must not change any metric value."""
        G = m.load_drawing(FIXTURES_DIR / "equilateral_triangle.geg")

        shared = m.compute_metrics(G)
        # Reference: call each metric directly with no sharing.
        reference = {name: float(fn(G)) for name, fn in m.METRICS}

        for name in m.METRIC_NAMES:
            assert shared[name] == pytest.approx(reference[name], rel=1e-9), name


class TestBatchCSV:
    def test_batch_writes_rows_per_fixture(self, m, tmp_path):
        out_csv = tmp_path / "out.csv"
        m.main([
            "batch",
            "--input-dir", str(FIXTURES_DIR),
            "--output-csv", str(out_csv),
        ])
        assert out_csv.exists()
        with open(out_csv, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))

        # At least one row per supported extension.
        assert {r["format"] for r in rows} >= {"geg", "graphml", "gml"}
        # Every row has a format, n_nodes, n_edges.
        for r in rows:
            assert r["file"]
            assert r["format"] in {"geg", "graphml", "gml"}
            assert r["n_nodes"]
            # Every metric column is non-empty for clean fixtures.
            for name in m.METRIC_NAMES:
                assert r[name] != "", f"{r['file']}: {name} missing"

    def test_batch_includes_graph_property_columns(self, m, tmp_path):
        """Every property in PROPERTY_NAMES is emitted as its own column and
        populated for clean fixtures."""
        out_csv = tmp_path / "out.csv"
        m.main([
            "batch",
            "--input-dir", str(FIXTURES_DIR),
            "--output-csv", str(out_csv),
        ])
        with open(out_csv, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        assert rows
        for r in rows:
            for name in m.PROPERTY_NAMES:
                assert name in r, f"property column {name} missing in row"
                assert r[name] != "", f"{r['file']}: {name} empty"

    def test_batch_computes_apsp_once_per_file(self, m, monkeypatch):
        """The batch subcommand must precompute APSP once per file and share
        it between kruskal_stress (metric) and the three distance
        properties."""
        import geg as geg_pkg
        calls = {"n": 0}

        original = geg_pkg.graph_properties.compute_apsp

        def counting(G, *a, **kw):
            calls["n"] += 1
            return original(G, *a, **kw)

        monkeypatch.setattr(m.geg.graph_properties, "compute_apsp", counting)

        # Pick one fixture and run the compute pipeline it exposes.
        G = m.load_drawing(FIXTURES_DIR / "equilateral_triangle.geg")
        apsp = m._safe_apsp(G)
        m.geg.compute_properties(G, apsp=apsp)
        m.compute_metrics(G, apsp=apsp)

        assert calls["n"] == 1, (
            f"compute_apsp ran {calls['n']}× per file; expected 1"
        )

    def test_batch_tolerates_missing_dir(self, m, tmp_path):
        with pytest.raises(SystemExit):
            m.main([
                "batch",
                "--input-dir", str(tmp_path / "does-not-exist"),
                "--output-csv", str(tmp_path / "unused.csv"),
            ])
