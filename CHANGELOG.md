# Changelog

All notable changes to the `geg` package are recorded here. Format loosely follows [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased] — dev/metrics-refactor-tdd

Ongoing TDD refactor of the metrics library. Entries below track public-API–affecting changes; downstream scripts should review before upgrading.

### Added
- Test suite under `tests/` (pytest). Runnable via `pytest` from the package root.
- `dev` optional-dependency group: `pip install -e .[dev]`.
- Internal canonical helpers (`geg._geometry`, `geg._paths`) — not re-exported from the public API. Metric modules will be refactored onto these in Phase 2. Public signatures are unchanged in Phase 1.
  - `_geometry`: `distance`, `squared_distance`, `angle_between`, `acute_angle_between`, `bounding_box`, `bboxes_intersect`, `segment_intersection`.
  - `_paths`: `parse_path`, `flatten_path_to_polyline`, `flatten_path_to_segments`, `polyline_length`, `edge_polyline`.

### Changed
- `edge_orthogonality(G)` is now the unified paper §3.2 eq. (5)-(6) definition: handles straight, polyline, and curved edges via length-weighted segment deviation. Behaviour is unchanged for drawings with only straight edges; for drawings with curved/polyline edges, it now incorporates them (previously it ignored the `path` attribute).
- `edge_orthogonality(G)` returns 1.0 on edgeless graphs (was 0.0).
- `to_svg(G, out, ...)`: rewritten. New keyword-only parameters `scale` (pixels per GEG unit; default 50), `grid` (draw faint integer-coordinate grid; default False), `node_radius`, `stroke_width`, `grid_stroke`, `grid_stroke_width`. `margin` is now in pixels. Drawing coordinates are pre-scaled so edge path 'd' attrs in the output use pixel values, not raw GEG coords. Calls to `to_svg(G, out, margin=...)` still work positionally; any call site relying on GEG-unit coords in the output will need to set `scale=1.0` to preserve old behaviour.

### Deprecated
- `curved_edge_orthogonality(G, global_segments_N=...)`: emits DeprecationWarning and delegates to `edge_orthogonality`. `global_segments_N` is forwarded as `samples_per_curve`.

### Removed
- _(none yet)_

### Fixed
- `kruskal_stress`: now handles disconnected drawings per paper §3.3 (weighted sum by per-component convex-hull area). The previous implementation raised `KeyError` on any graph with more than one connected component.
- `neighbourhood_preservation`: now handles disconnected drawings per paper §3.3 (weighted sum by per-component convex-hull area). Previously, the k-NN matrix was computed over the full layout, which could include cross-component neighbours and artificially depress the score.
- `aspect_ratio`: degenerate bounding boxes (h=0 or w=0) now return 1.0 per paper §3.2. Previously returned 0.0 (worst), which contradicted the spec.
- `edge_length_deviation`: no longer raises `ZeroDivisionError` when the average edge length is 0; graphs with all-zero-length edges (or an explicit `ideal=0`) now return 1.0 (vacuously uniform). Edgeless graphs now return 1.0 as well (previously returned 0.0).
- `edge_crossings_bezier`: removed stray `print()` / progress-counter calls left over from development.
