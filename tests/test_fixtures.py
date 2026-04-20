"""Parametrized tests that verify each fixture's claimed metric values.

Fixtures are registered in tests/fixtures/_builder.py with a table of
hand-computed expected values for the metrics that have a clean analytical
form on that drawing. This test module iterates every (fixture, metric)
pair in those tables and asserts the metric returns the expected value.
"""

import pytest

import geg

from .fixtures._builder import all_fixtures


_METRIC_FUNCS = {
    "angular_resolution_min_angle": geg.angular_resolution_min_angle,
    "angular_resolution_avg_angle": geg.angular_resolution_avg_angle,
    "aspect_ratio": geg.aspect_ratio,
    "crossing_angle": geg.crossing_angle,
    "edge_crossings": geg.edge_crossings,
    "edge_length_deviation": geg.edge_length_deviation,
    "edge_orthogonality": geg.edge_orthogonality,
    "gabriel_ratio_edges": geg.gabriel_ratio_edges,
    "gabriel_ratio_nodes": geg.gabriel_ratio_nodes,
    "kruskal_stress": geg.kruskal_stress,
    "neighbourhood_preservation": geg.neighbourhood_preservation,
    "node_edge_occlusion": geg.node_edge_occlusion,
    "node_resolution": geg.node_resolution,
    "node_uniformity": geg.node_uniformity,
}


def _cases():
    for fx in all_fixtures().values():
        for metric_name, expected in fx.expected.items():
            if expected is None:
                continue
            yield pytest.param(fx, metric_name, expected, id=f"{fx.name}[{metric_name}]")


@pytest.mark.parametrize("fixture, metric_name, expected", list(_cases()))
def test_fixture_metric(fixture, metric_name, expected):
    fn = _METRIC_FUNCS[metric_name]
    G = fixture.build()
    assert fn(G) == pytest.approx(expected, abs=fixture.tol, rel=fixture.tol)
