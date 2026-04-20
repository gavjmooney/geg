# Changelog

All notable changes to the `geg` package are recorded here. Format loosely follows [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased] — `dev/metrics-refactor-tdd`

TDD refactor of the metrics library against the GD 2025 paper definitions (paper §3.2, §3.3), plus a parser/I/O cleanup. Per-fixture value deltas against `main` are in `METRIC_DELTAS.md`; known-issue catalogue is in `ISSUES.md`.

### Added

- **Test suite.** Pytest runnable from the package root (`pytest`), including 328 tests covering every public metric, every canonical helper, every fixture × expected-value claim, and the three I/O formats (GEG / GraphML / GML). Full suite runs in ~1.8s.
- **`geg/io/` subpackage** holding the file-format readers, writers, and converters:
  - `geg.io.geg` — GEG JSON reader/writer + file-level introspection (`has_self_loops_file`, `is_multigraph_file`).
  - `geg.io.graphml` — yEd-flavoured GraphML reader/writer + `graphml_to_geg`; merges the former `geg/parse_graph.py` module.
  - `geg.io.gml` — GML → GEG converter.
  Public import surface (`from geg import read_geg, write_geg, graphml_to_geg, gml_to_geg, read_graphml, write_graphml`) is unchanged. `geg/parse_graph.py` and the old I/O entry points on `geg/geg_parser.py` are backcompat shims that re-export from `geg.io`.
- **`dev` optional-dependency group.** `pip install -e .[dev]`.
- **Canonical internal helpers** (`geg._geometry`, `geg._paths`, underscore-prefixed — not re-exported). Metric modules import from these instead of reimplementing:
  - `_geometry`: `distance`, `squared_distance`, `angle_between`, `acute_angle_between`, `bounding_box`, `bboxes_intersect`, `segment_intersection`.
  - `_paths`: `parse_path`, `flatten_path_to_polyline`, `flatten_path_to_segments`, `polyline_length`, `edge_polyline`.
- **`tests/fixtures/`.** 11 unit-coord fixtures (`.geg` + grid `.svg` + `.md` with hand-computed expected metric values). Driven by `tests/fixtures/_builder.py`; regenerate artefacts with `python -m tests.fixtures._builder`.

### Changed

- **`edge_orthogonality(G, samples_per_curve=50)`** is now the unified paper §3.2 eq. (5)-(6) definition for all edges (straight, polyline, or curved). Previously the public function ignored edge `path` attrs and used node-to-node straight-line orientation; curved handling lived in the separate `curved_edge_orthogonality`. Behaviour is unchanged on drawings with straight edges only.
- **`edge_orthogonality`** returns `1.0` on edgeless graphs (was `0.0`) — matches the "1 = best" convention.
- **`to_svg(G, out, ...)`** rewritten. Keyword-only parameters: `scale` (pixels per GEG unit, default 50), `grid` (integer-coordinate background grid, default False), `node_radius`, `stroke_width`, `grid_stroke`, `grid_stroke_width`. `margin` is now in pixels (previously GEG units). Output SVG coordinates are pre-scaled to pixels; callers that need raw GEG coords in the output should pass `scale=1.0`.
- **`read_geg`**: no longer stores `source` / `target` as edge *attributes* (they are the edge tuple, not attrs). Every other attribute on the edge is preserved; the `id` attribute continues to round-trip.
- **`graphml_to_geg`** now preserves node dimensions (`width`, `height`), node labels, edge colour, edge stroke width, and edge labels, in addition to position / colour / shape. Node `colour` is canonicalised (was `color`).
- **`gml_to_geg`** now preserves node dimensions, node labels, edge colour, edge stroke width, edge labels, and edge weight, in addition to position / colour / shape.
- **`read_graphml`** (yEd flavour): no longer crashes on nodes missing a Fill / Shape / NodeLabel child. Optional attributes default to absent rather than raising `UnboundLocalError`. New: extracts `label`, `width`, `height`, edge `colour` / `stroke_width` / `label`.
- **`write_graphml`**: now reads `colour` (the GEG-canonical spelling) with `color` fallback; respects `shape`, `label`, `width`, `height`, `stroke_width` on input; emits directed/undirected correctly per graph type.

### Deprecated

- **`curved_edge_orthogonality(G, global_segments_N=10)`**. Emits `DeprecationWarning` and delegates to `edge_orthogonality`. `global_segments_N` is forwarded as `samples_per_curve`. Remove in a future major release.

### Removed

- **`parse_graph.test_graph_read_write()`** and the commented-out scratch block (old lines 226–328). Neither was reachable; kept the two real converter utilities (`convert_gml_to_graphml`, `convert_graphml_to_gml`).
- **`edge_crossings.py`** internal helpers `bboxes_intersect`, `check_intersection`, `flatten_path_to_lines` — now use the canonical `_geometry` / `_paths` versions instead.

### Fixed

- **`kruskal_stress`**: handles disconnected drawings per paper §3.3 (weighted sum by per-component convex-hull area; singleton components contribute nothing). Previously raised `KeyError` on any drawing with more than one connected component.
- **`neighbourhood_preservation`**: handles disconnected drawings per paper §3.3 (weighted sum by per-component convex-hull area). Previously the k-NN matrix was computed over the full layout, which could draw neighbours across component boundaries and artificially depress the score.
- **`aspect_ratio`**: degenerate bounding boxes (h = 0 or w = 0) now return `1.0` per paper §3.2. Previously returned `0.0` (worst), which contradicted the spec.
- **`edge_length_deviation`**: no longer raises `ZeroDivisionError` when the average edge length is 0; graphs with all-zero-length edges (or an explicit `ideal=0`) now return `1.0` (vacuously uniform). Edgeless graphs now return `1.0` (was `0.0`).
- **`edge_crossings_bezier`**: removed stray `print()` and progress-counter calls left over from development.

### Internal / non-user-visible

- **Parser reorganisation (Phase 5).** `geg/geg_parser.py` no longer owns file I/O — it keeps rendering (`to_svg`), geometry helpers (`get_bounding_box`, `get_convex_hull_area`), curves-promotion (`curves_promotion`, `approximate_edge_polyline`, `compute_global_scale`, `determine_N_for_segment`), and graph introspection (`contains_curves` / `contains_polylines` / `contains_straight_bends` / `has_self_loops_graph` / `is_multigraph_graph`). Everything else is re-exported from `geg.io` so existing imports keep working.
- `gabriel_ratio._squared_distance` → imports from `geg._geometry.squared_distance`.
- `node_resolution` uses `_geometry.distance` instead of `math.hypot` directly.
- `angular_resolution_min_angle` and `..._avg_angle` share `_incident_edge_angles` + `_gaps_around_vertex` helpers (was ~90 lines of copy-paste).
- `edge_crossings` uses `_geometry.bboxes_intersect`, `_geometry.segment_intersection`, and `_paths.flatten_path_to_segments` in place of local re-implementations.
- `edge_length_deviation` factors out `_edge_length` helper shared between the public metric and `get_average_edge_length`.
