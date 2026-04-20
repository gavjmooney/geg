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
- _(none yet)_

### Deprecated
- _(none yet)_

### Removed
- _(none yet)_

### Fixed
- _(none yet)_
