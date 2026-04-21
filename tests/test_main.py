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
