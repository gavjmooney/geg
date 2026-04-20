# Changelog

All notable changes to the `geg` package are recorded here. Format loosely follows [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased] — `dev/metrics-refactor-tdd`

TDD refactor of the metrics library against the GD 2025 paper definitions (paper §3.2, §3.3). Per-fixture value deltas against `main` are in `METRIC_DELTAS.md`; known-issue catalogue is in `ISSUES.md`.

### Added

- **Test suite.** Pytest runnable from the package root (`pytest`), including 261 tests covering every public metric, every canonical helper, and every fixture × expected-value claim. Full suite runs in ~1.5s.
- **`dev` optional-dependency group.** `pip install -e .[dev]`.
- **Canonical internal helpers** (`geg._geometry`, `geg._paths`, underscore-prefixed — not re-exported). Metric modules import from these instead of reimplementing:
  - `_geometry`: `distance`, `squared_distance`, `angle_between`, `acute_angle_between`, `bounding_box`, `bboxes_intersect`, `segment_intersection`.
  - `_paths`: `parse_path`, `flatten_path_to_polyline`, `flatten_path_to_segments`, `polyline_length`, `edge_polyline`.
- **`tests/fixtures/`.** 11 unit-coord fixtures (`.geg` + grid `.svg` + `.md` with hand-computed expected metric values). Driven by `tests/fixtures/_builder.py`; regenerate artefacts with `python -m tests.fixtures._builder`.

### Changed

- **`edge_orthogonality(G, samples_per_curve=50)`** is now the unified paper §3.2 eq. (5)-(6) definition for all edges (straight, polyline, or curved). Previously the public function ignored edge `path` attrs and used node-to-node straight-line orientation; curved handling lived in the separate `curved_edge_orthogonality`. Behaviour is unchanged on drawings with straight edges only.
- **`edge_orthogonality`** returns `1.0` on edgeless graphs (was `0.0`) — matches the "1 = best" convention.
- **`to_svg(G, out, ...)`** rewritten. Keyword-only parameters: `scale` (pixels per GEG unit, default 50), `grid` (integer-coordinate background grid, default False), `node_radius`, `stroke_width`, `grid_stroke`, `grid_stroke_width`. `margin` is now in pixels (previously GEG units). Output SVG coordinates are pre-scaled to pixels; callers that need raw GEG coords in the output should pass `scale=1.0`.

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

- `gabriel_ratio._squared_distance` → imports from `geg._geometry.squared_distance`.
- `node_resolution` uses `_geometry.distance` instead of `math.hypot` directly.
- `angular_resolution_min_angle` and `..._avg_angle` share `_incident_edge_angles` + `_gaps_around_vertex` helpers (was ~90 lines of copy-paste).
- `edge_crossings` uses `_geometry.bboxes_intersect`, `_geometry.segment_intersection`, and `_paths.flatten_path_to_segments` in place of local re-implementations.
- `edge_length_deviation` factors out `_edge_length` helper shared between the public metric and `get_average_edge_length`.
