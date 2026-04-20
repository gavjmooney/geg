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
    def test_all_public_metrics_covered(self, m):
        import geg
        # Every public metric exported from geg.__init__ must appear in the
        # main.py METRICS table; otherwise the batch CSV silently omits it.
        metric_fns = {
            "angular_resolution_min_angle", "angular_resolution_avg_angle",
            "aspect_ratio", "crossing_angle", "edge_crossings",
            "edge_length_deviation", "edge_orthogonality",
            "gabriel_ratio_edges", "gabriel_ratio_nodes",
            "kruskal_stress", "neighbourhood_preservation",
            "node_edge_occlusion", "node_resolution", "node_uniformity",
        }
        for name in metric_fns:
            assert name in m.METRIC_NAMES, f"{name} missing from main.py METRICS"

    def test_compute_metrics_returns_all_keys(self, m):
        G = m.load_drawing(FIXTURES_DIR / "equilateral_triangle.geg")
        result = m.compute_metrics(G)
        assert set(result.keys()) == set(m.METRIC_NAMES)
        # Every value should be finite for a reasonable drawing.
        for name, value in result.items():
            assert value == value, f"{name} is NaN on a clean fixture"


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

    def test_batch_tolerates_missing_dir(self, m, tmp_path):
        with pytest.raises(SystemExit):
            m.main([
                "batch",
                "--input-dir", str(tmp_path / "does-not-exist"),
                "--output-csv", str(tmp_path / "unused.csv"),
            ])
