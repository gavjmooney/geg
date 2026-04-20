# Known Issues and Open Design Questions

This file catalogues bugs, numerical red flags, definitional ambiguities, and open design questions discovered during the `dev/metrics-refactor-tdd` audit. Each metric-bug entry follows the format:

> **Where:** `path/to/file.py:line`  
> **What:** description of the bug or mismatch  
> **Fix direction:** one-line proposal  
> **TVCG-impact:** whether the fix would change metric values for drawings in the published Mooney et al. (TVCG) dataset (`yes` / `no` / `unknown`)

---

## Confirmed bugs / spec mismatches

### ASP-1 — Aspect Ratio returns 0 for degenerate bounding box
- **Where:** `geg/aspect_ratio.py:24` (approximately; `width <= 0 or height <= 0` branch returns `0.0`).
- **What:** Paper §3.2 defines `Asp(D) = 1` when `h(D) = 0` or `w(D) = 0`. Current code returns `0.0` (worst) in that case.
- **Fix direction:** Return `1.0` in the degenerate branch, matching the spec.
- **TVCG-impact:** unknown — would only affect drawings with a fully-collinear bounding box. Likely rare in the TVCG dataset; to be measured against fixtures.

### ELD-1 — Division by zero if average edge length is 0
- **Where:** `geg/edge_length_deviation.py:75` (approximately).
- **What:** When all edges have length 0 (coincident endpoints), `get_average_edge_length` returns 0 and the metric divides by it.
- **Fix direction:** Guard the degenerate case; return `1.0` (no deviation possible) or document as undefined.
- **TVCG-impact:** no — TVCG drawings do not contain zero-length edges.

### EC-1 — Debug `print()` calls in production path
- **Where:** `geg/edge_crossings.py:82,87` (approximately).
- **What:** Stray debug prints left in library code.
- **Fix direction:** Remove or gate behind a `verbose=False` kwarg / `logging`.
- **TVCG-impact:** no (output only).

### PG-1 — Dead inline test code in `parse_graph.py`
- **Where:** `geg/parse_graph.py:226–327` (approximately).
- **What:** `test_graph_read_write()` and related inline test routines that are never called.
- **Fix direction:** Move to `tests/` as real pytest tests or delete.
- **TVCG-impact:** no.

---

## Open design questions

### DQ-1 — Disconnected-graph handling per metric
- **Context:** Paper §3.3 specifies weighted-sum-by-convex-hull-area across components for KSM and NP, notes AR is locally defined so unaffected, and warns that a weighted-sum for Edge Crossings would be misleading (ignores inter-component crossings).
- **Open question:** What should each of the remaining metrics do for disconnected drawings? Some are naturally unaffected (AR, NR min/max over all pairs), some likely want area-weighting, some may want a different aggregation. Decide per metric and document in the metric module.
- **Action:** Address during Phase 2 TDD. Each metric gets an explicit design note in its module docstring stating its disconnected-graph behaviour.
- **Progress:**
  - [x] KSM — weighted sum by component convex-hull area (paper §3.3). Fixed.
  - [x] NP — weighted sum by component convex-hull area (paper §3.3). Fixed.
  - [ ] AR, Asp, CA, EC, ELD, EO, GR, NR, NU — per-metric decision required.

### DQ-2 — Curved / Bézier edge handling per metric
- **Context:** `curves_promotion` explodes curves into polyline segments. Which metrics should run on the promoted graph vs. the original varies (e.g. ELD uses segment lengths; EC is defined pre-crosses-promotion).
- **Open question:** For each metric, is the authoritative behaviour documented unambiguously in the paper, or is there an under-specification (especially for Bézier curves, which the paper's Figure 1 covers but formulas rarely mention explicitly)?
- **Action:** Address per metric in Phase 2. Flag each under-specification here.

### DQ-3 — Gabriel Ratio status
- **Context:** Paper §3.2 excludes Gabriel Ratio ("not applicable for drawings with curves"). Gavin has decided to keep it in the library as a non-canonical metric since it still applies to straight-line drawings.
- **Action:** Document as non-canonical in the module docstring; ensure it is callable but not in the default "paper metrics" set. Consider a `geg.canonical_metrics` convenience helper that excludes it.

---

## Numerical red flags to verify

_(entries added during Phase 2 as each metric is audited)_

---

## Helper duplication clusters

Canonical helpers now live in `geg/_geometry.py` and `geg/_paths.py` (added in Phase 1). The clusters below are still present in the existing metric / parser modules — each will be removed as Phase 2 refactors that module onto the canonical helpers.

- [ ] Angle computation reimplemented in `angular_resolution.py`, `edge_orthogonality.py`, `edge_crossings.py` — replace with `_geometry.angle_between` / `_geometry.acute_angle_between`.
- [ ] Path linearisation in `geg_parser.approximate_edge_polyline` and `edge_crossings.flatten_path_to_lines` — replace with `_paths.flatten_path_to_polyline` / `_paths.flatten_path_to_segments` / `_paths.edge_polyline`.
- [ ] `_squared_distance` in `gabriel_ratio.py` duplicates `_geometry.squared_distance`.
- [ ] Segment-intersection / bbox-overlap helpers in `edge_crossings.py` (`bboxes_intersect`, `check_intersection`) — replace with `_geometry.bboxes_intersect` / `_geometry.segment_intersection`.
- [ ] Multiple direct `svgpathtools.parse_path` call-sites (5 modules) — route through `_paths.parse_path` (or one of the flatten helpers).
