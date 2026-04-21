# Changelog

All notable changes to the `geg` package are recorded here. Format loosely follows [Keep a Changelog](https://keepachangelog.com/).

## [0.2.0] — 2026-04-21 (`dev/metrics-refactor-tdd`)

TDD refactor of the metrics library against the GD 2025 paper definitions (paper §3.2, §3.3), plus a parser/I/O cleanup. Per-fixture value deltas against the previous release are in `METRIC_DELTAS.md`; known-issue catalogue is in `ISSUES.md`.

### Added

- **Opt-in weighted variants** for every metric and property that has a
  meaningful weighted interpretation. New `weight: Optional[str] = None`
  kwarg on:
  - `kruskal_stress(G, apsp=None, weight=None)` — forwarded to networkx's
    Dijkstra APSP when set; hop-count BFS when left at `None`.
  - `graph_properties.diameter / radius / avg_shortest_path_length(G, …,
    weight=None)` — same semantics.
  - `graph_properties.compute_apsp(G, weight=None)` — produces weighted or
    unweighted APSP; consumers that accept a precomputed `apsp` use whatever
    semantics are baked in.
  - `graph_properties.compute_properties(G, apsp=None, weight=None)` threads
    `weight` through to the distance properties.
  - `main.compute_metrics(G, apsp=None, weight=None)` threads to
    `kruskal_stress` and `edge_length_deviation`.
  - `main.py batch --weight NAME` — CLI flag.
- **`edge_length_deviation(G, ideal=None, *, weight=None)`** weighted variant:
  each edge aims for `L*(e) = |w_e| · s`, with scale `s = sum(L) / sum(|w|)`
  so total ideal length matches total drawn length. Reduces to the
  unweighted case exactly when all weights are equal. Negative weights are
  taken as magnitude (the spring-rest-length interpretation has no sign);
  zero weight raises `ValueError`; passing both `ideal` and `weight` raises
  `ValueError`. `neighbourhood_preservation` intentionally has no weighted
  variant (paper Jaccard is topological; documented).
- **`geg.angular_resolution`** is now also callable as the canonical paper §3.2 eq. (1) min-angle variant (alias for `angular_resolution_min_angle`). The submodule path `from geg.angular_resolution import …` continues to work (resolved through `sys.modules`); only the package attribute is rebound to the function so `geg.angular_resolution(G)` is the ergonomic one-liner users probably expect.
- **`geg.graph_properties` module** — topological descriptors of the graph, independent of the layout. 30 properties:
  - **Basic counts & flags:** `n_nodes`, `n_edges`, `density`, `is_directed`, `is_multigraph`, `n_self_loops`, `n_connected_components`, `is_connected`.
  - **Degree statistics:** `min_degree`, `max_degree`, `mean_degree`, `degree_std`.
  - **Structural classes:** `is_tree`, `is_forest`, `is_bipartite`, `is_planar`, `is_dag`, `is_regular`, `is_eulerian`, `degeneracy` (k-core degeneracy: largest k for which a non-empty k-core exists; self-loops stripped, multi/directed reduced to simple undirected), `n_biconnected_components` (maximal 2-node-connected subgraphs; bridges are 2-node bicomps; isolated nodes ignored).
  - **Distances (per-component weighted sum, KSM/NP-style):** `diameter`, `radius`, `avg_shortest_path_length`. Singleton components are skipped; all-singleton graphs return NaN. Directed inputs are reduced to their undirected view for this computation, same as KSM / NP.
  - **Clustering:** `n_triangles`, `average_clustering`, `transitivity`.
  - **Assortativity:** `degree_assortativity` (NaN when undefined, e.g. regular graphs).
  - **Analytic crossing-number lower bounds** (appended to the end of `PROPERTY_NAMES` to keep CSV column order stable for consumers joined against older rows): `crossing_number_lb_euler` (Euler's bound `max(0, m - (3n - 6))` for any simple graph; 0 when `n < 3`) and `crossing_number_lb_bipartite` (tightened to `max(0, m - (2n - 4))` for bipartite graphs with `n ≥ 3`; returns NaN on non-bipartite inputs so downstream cohort filters can distinguish "bound is 0" from "bound not applicable"). Both are O(1) in `n`, `m` (O(n + m) for the bipartite test). Matches the known crossing numbers for K₅ (=1) and K₃,₃ (=1) as a sanity check.
  - **Batch entry point:** `compute_properties(G)` returns every property as a dict, catching per-property exceptions into NaN; `PROPERTY_NAMES` pins the ordering.
  - Re-exported from the top-level package as `geg.graph_properties` and `geg.compute_properties`.
- **`geg.io.convert` module** centralising every cross-format entry point:
  - **`convert(src, dst, **kwargs)`** — one-liner format swap; both ends detected from the file extension. Forwards kwargs to the destination writer, so e.g. `convert("a.graphml", "a.svg", grid=True)` works. Returns the loaded graph for inspection.
  - **`read_drawing(path)`** — load any supported input format (`.geg` / `.graphml` / `.gml`) as a GEG-canonical NetworkX graph.
  - **`write_drawing(G, path, **kwargs)`** — write any supported output format (`.geg` / `.graphml` / `.gml` / `.svg`) by extension. SVG kwargs (`grid`, `scale`, `margin`, …) are forwarded to `to_svg`.
  - The pair-wise converters (`gml_to_geg`, `graphml_to_geg`, `convert_gml_to_graphml`, `convert_graphml_to_gml`) moved into this module; their behaviour is unchanged and every existing import path (`from geg import ...`, `from geg.io import ...`, `from geg.parse_graph import ...`) continues to resolve. `gml.py` and `graphml.py` now hold only format-native readers and writers.
- **`read_gml(input_file)` / `write_gml(G, output_file)`.** Explicit GML reader and writer, mirroring the `read_graphml` / `write_graphml` pattern. `read_gml` returns a NetworkX graph with GEG-canonical node attributes (`x`, `y`, `width`, `height`, `colour`, `shape`, `label`) and format-native edge geometry (`bends` list + `polyline` flag, consistent with `read_graphml`). `write_gml` emits a yEd-flavoured GML file honouring `x`/`y`/`width`/`height`/`shape`/`colour`/`label` per node and `bends`/`colour`/`stroke_width`/`label`/`weight` per edge. `gml_to_geg` is unchanged in behaviour and now composes on top of `read_gml`. Both new names are re-exported from `geg` and from `geg.geg_parser` for symmetry with the GraphML pair.
- **`node_edge_occlusion(G, epsilon_fraction=0.02, samples_per_curve=50)`** — new metric (not in the GD 2025 paper yet). For every edge, finds the non-endpoint node whose bounding disk comes closest to the drawn edge and records a cubic soft-overlap penalty `max(0, 1 - max(0, d - r) / ε) ** 3`, where `d` is the minimum distance from the node centre to the edge geometry, `r` is the node's `radius` attribute (defaults to 0 if missing), and `ε` is a fraction of the bounding-box diagonal. The score is 1 minus the mean per-edge worst-case penalty. Curved / polyline edges are handled by sampling the path via `_paths.edge_polyline`; the bbox uses curve-promoted geometry via `get_bounding_box` for consistency with Asp / NU. **Definition confirmed and finalised** (the "1–2 additions" flagged in `library_update_brief.md`).
- **Test suite.** Pytest runnable from the package root (`pytest`), including 355 tests covering every public metric, every canonical helper, every fixture × expected-value claim, and the three I/O formats (GEG / GraphML / GML). Full suite runs in ~1.8s.
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

- **`main.py batch`** now emits graph properties alongside layout metrics in a single CSV row. New columns come from `geg.graph_properties.PROPERTY_NAMES` and appear before the metric columns. CSV header is now `file, format, <property columns>, <metric columns>` (previously `file, format, n_nodes, n_edges, <metric columns>`); `n_nodes` / `n_edges` are now sourced from the property set rather than emitted separately.
- **APSP shared across `kruskal_stress`, `diameter`, `radius`, `avg_shortest_path_length`**. `kruskal_stress(G, apsp=None)` and `graph_properties.diameter / radius / avg_shortest_path_length(G, apsp=None)` now accept a precomputed all-pairs-shortest-path-length dict. `geg.graph_properties.compute_apsp(G)` is the canonical producer (runs once on the undirected view). `compute_properties(G, apsp=...)` and `main.compute_metrics(G, apsp=...)` thread it through, and the batch subcommand precomputes it once per file. On a 200-node random geometric graph this yields a ~1.2× speedup per batch entry; ratio scales with graph size.
- **`main.compute_metrics(G)`** now shares expensive intermediates across metrics:
  - Calls `get_bounding_box(G)` once per graph (previously 3× — once each for `aspect_ratio`, `node_uniformity`, `node_edge_occlusion`). Each call internally runs `curves_promotion`, which is the costly part.
  - Calls `edge_crossings(G, return_crossings=True)` once per graph (previously 2× — once for the `edge_crossings` score, once again inside `crossing_angle`'s fallback). The crossings list is now computed once and passed into `crossing_angle(crossings=...)`.
  - Supporting kwargs: `aspect_ratio`, `node_uniformity`, and `node_edge_occlusion` each gained a keyword-only `bbox` argument. Passing a pre-computed `(min_x, min_y, max_x, max_y)` skips the internal `get_bounding_box`/`curves_promotion` call. Default behaviour is unchanged (the metrics compute their own bbox when called directly).
- **Curved-edge handling unified (closes DQ-2).** Four coupled changes land together:
  - **Sampling density:** `samples_per_curve = 100` is now the single default for every metric that flattens an edge's path. Previously `edge_crossings` used 100 (paper §3.2 prescribed) while `edge_orthogonality`, `node_edge_occlusion`, `_paths.flatten_path_to_polyline`, and `_paths.edge_polyline` defaulted to 50, and `curves_promotion` used a completely different scheme (`target_segments = 10`, diagonal-relative). Motivation: metrics measuring the same curve now measure the same polyline; the paper's value wins. Callers may still override per-call.
  - **Single sampler:** `curves_promotion` delegates to `_paths.edge_polyline`. The old `approximate_edge_polyline`, `compute_global_scale`, and `determine_N_for_segment` helpers are **removed** from the public API (previously re-exported from the top-level `geg` package). No internal caller remained after the `_paths` migration in Phase 2.
  - **Bbox per metric:**
    - **`aspect_ratio(G)`** continues to use the **curve-promoted** bbox — a curve that reaches outside the node hull is part of the drawing's visual footprint.
    - **`node_uniformity(G)`** now uses the **node-only** bbox (`get_bounding_box(G, promote=False)`). Motivation: NU is a statement about node placement; a drawing with one long curved edge reaching outside the node cluster would previously stretch the grid and spuriously dilute cell counts for the *nodes*, which is not what NU is about.
    - **`node_edge_occlusion(G)`** now uses the **node-only** bbox for `ε = epsilon_fraction · diag`. Motivation: the penalty-zone width should scale with how far apart nodes sit, not with how far a curve strays from its endpoints. Per-edge distance computations still run against the flattened polyline; the curve still counts for occlusion testing, just not for ε's scale.
    - Downstream: `main.compute_metrics` now computes both bboxes once each (promoted for Asp; node-only shared between NU and NEO) rather than reusing one promoted bbox across all three.
  - **SVG path-command fixture coverage:** new `cubic_bezier` and `orthogonal_hv` fixtures pin handling of the `C` (cubic Bezier) and `H` / `V` (orthogonal lineto) commands alongside the existing `polyline_bend` (L) and `bezier_curve` (Q) cases. `S`, `T`, `A`, `Z` are not pinned but flow through the `svgpathtools` parser.

  **TVCG-impact:** the unified sampling and the NU/NEO bbox change both affect curved drawings only. The TVCG corpus is straight-line throughout, so every per-drawing metric value remains byte-identical. Any downstream study that consumes curved drawings should re-run NU and NEO (now node-only) and may see values shift on drawings where a curve reached outside the node hull.

- **`read_graphml(filename, yed_corner_anchor=None)`** now accounts for yEd's top-left node-anchor convention. yEd stores `x`/`y` as the top-left corner of each node's bounding box while edge bends are in absolute drawing coordinates, so an orthogonal L-shaped path looks diagonal when the coordinates are taken as node centres. The reader auto-detects yEd-authored files (via the `<!--Created by yEd-->` comment or the `xmlns:yed` namespace) and shifts `x += width/2, y += height/2` so centres line up with bends. Pass `yed_corner_anchor=True` or `False` to override auto-detection; the same kwarg is threaded through `graphml_to_geg`. Same manual-test file now produces identical metric values from the `.graphml` and `.gml` side (e.g. `edge_orthogonality = 1.0` for an orthogonal layout, `kruskal_stress` values match across both formats).
- **`write_graphml(..., yed_corner_anchor=False)`** gains a kwarg to emit yEd-convention output: shifts `x`/`y` to the top-left and declares `xmlns:yed`. The default keeps centre-anchored coordinates and omits the unused yed namespace, which keeps library round-trips (write → read) an identity.
- **`node_edge_occlusion`**: when a node has no `radius` attribute but carries `width` / `height` (as produced by `read_graphml` and `read_gml`), the metric now uses the circumscribed-disk radius `max(width, height) / 2` instead of silently collapsing to `r = 0`. Only when all three attributes are absent does it fall back to the centre-to-line form. Explicit `radius` still wins when both are present. Previously NEO reported "no occlusion" for drawings whose node disks visibly straddled edges simply because the radius attribute wasn't named correctly after format conversion.
- **`convert_graphml_to_gml`** now preserves node geometry and edge bends by default (routes through `read_graphml` + `write_gml`). Previously it called `nx.write_gml` which crashed on tuple-valued `bends` attributes. Pass `with_nx=True` for the original raw-networkx behaviour.
- **`edge_orthogonality(G, samples_per_curve=100)`** is now the unified paper §3.2 eq. (5)-(6) definition for all edges (straight, polyline, or curved). Previously the public function ignored edge `path` attrs and used node-to-node straight-line orientation; curved handling lived in the separate `curved_edge_orthogonality`. Behaviour is unchanged on drawings with straight edges only. (Default bumped from 50 to 100 in 0.2.0 to match `edge_crossings`; see DQ-2 resolution.)
- **`edge_orthogonality`** returns `1.0` on edgeless graphs (was `0.0`) — matches the "1 = best" convention.
- **`to_svg(G, out, ...)`** now auto-fits to a sensible pixel canvas. New keyword-only parameters:
  - `width` (default `None` → 800 in auto-fit mode) — target canvas width in pixels.
  - `height` (default `None` → derived from curve-promoted bounding-box aspect ratio) — target canvas height in pixels. When both `width` and `height` are given, the drawing is aspect-preserved to fit both and centred (letter-boxed if the aspect ratios differ).
  - `scale` is now `Optional[float]` (default `None` = auto-fit). Passing `scale` reverts to the previous `bbox × scale + 2 × margin` sizing (width/height then auto-derive unless overridden).
  - Previously `to_svg` used a fixed `scale=50` pixel-per-GEG-unit default, which rendered real-world drawings (e.g. yEd coordinates in the 100s–1000s) at tens of thousands of pixels wide. Auto-fit produces an 800px-wide SVG regardless of input coordinate scale.
  - `main.py render --scale 50 --margin 50` replaced by `--width 800 --height N --margin 50 --scale X`; all flags are optional and the old `--scale` still works.
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
- **`approximate_edge_polyline(G, edge, global_segments_N=10)`**, **`compute_global_scale(G, target_segments=10)`**, **`determine_N_for_segment(G, segment, ...)`** — the legacy curve-sampling trio used by the old `curves_promotion`. `curves_promotion(G)` now delegates to `_paths.edge_polyline`, so these helpers had no remaining caller. They were previously re-exported from the top-level `geg` package; callers who imported them should switch to `geg._paths.flatten_path_to_polyline(path_str, samples_per_curve=100)` (closes DQ-2 sampler duplication).

### Fixed

- **`crossing_angle`**: clamps the per-crossing shortfall to `[0, ∞)` and the final score to `[0, 1]`. Previously a caller who passed a pre-computed `crossings` list with an angle above `ideal_angle` (e.g. an obtuse crossing) could get a score above 1. The canonical call path via `edge_crossings(return_crossings=True)` always yields acute angles so was unaffected; the clamp is defensive for external callers.
- **`write_graphml(G, …)`**: no longer crashes on `MultiGraph` inputs. The old loop did `for u, v in G.edges()` then `G.edges[u, v]`, which raises on multigraphs (they require an edge key). Now uses `for u, v, attrs in G.edges(data=True)`, which works for both simple and multi graphs and emits each parallel edge as its own `<edge>` element.
- **`read_geg`**: parses the GEG JSON file once per call. The old multigraph detection step re-opened and re-parsed the file, doubling I/O on every read. Internal helper `_data_is_multigraph(data)` operates on the already-parsed dict; the public `is_multigraph_file(path)` still works and is kept as a standalone file-level check.
- **`kruskal_stress`**: no longer raises `KeyError` on directed graphs with a sink (or any DiGraph where forward reachability is asymmetric). Stress compares Euclidean distance (symmetric) to graph-theoretic distance, so the metric now operates on an undirected view of the input. Scores on directed inputs match those of their undirected twin.
- **`neighbourhood_preservation`**: same fix — now operates on an undirected view of directed inputs. Previously built an asymmetric adjacency matrix against a symmetric k-NN matrix, artificially depressing Jaccard scores on DiGraphs.
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
