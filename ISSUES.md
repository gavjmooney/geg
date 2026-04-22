# Known Issues and Open Design Questions

Catalogue of bugs, numerical red flags, definitional ambiguities, and open
design questions discovered during the `dev/metrics-refactor-tdd` audit
(Phases 1–4). Issue format:

> **Where:** `path/to/file.py:line`
> **What:** description
> **Fix direction:** one-line proposal (or "Fix:" if already resolved)
> **TVCG-impact:** whether the change alters metric values for the published Mooney et al. (TVCG) dataset (`yes` / `no` / `unknown`)

Empirical deltas for the fixtures in `tests/fixtures/` are in `METRIC_DELTAS.md`.

---

## Confirmed bugs / spec mismatches

### MG-1 — curves_promotion silently collapsed parallel curved edges  [FIXED]
- **Where:** `geg/geg_parser.py::curves_promotion`, old line 442.
- **What:** On a MultiGraph with parallel curved edges between the same `(u, v)` pair, both edges got `eid = attrs.get('id', f"{u}-{v}")`. Without an explicit `id` attribute (the common case), both edges named their intermediate nodes `"{u}-{v}_pt_{i}"`. The second iteration's `H.add_node` calls overwrote the first's coordinates. Observable symptom: the promoted graph for mirror-symmetric arcs (one up, one down) retained only one arc's samples, skewing `aspect_ratio` and anything else that consumes the promoted bbox.
- **Fix:** Iterate with `keys=True` on multigraphs; default `eid` to `f"{u}-{v}-{key}"` for parallel edges so their promoted nodes get unique ids.
- **TVCG-impact:** **none.** Corpus has no multigraphs.

### MG-2 — read_graphml collapsed parallel edges to a simple Graph  [FIXED]
- **Where:** `geg/io/graphml.py::read_graphml`, old line 91.
- **What:** The reader always constructed `nx.Graph()` (or `nx.DiGraph()`), so a round-trip of a `nx.MultiGraph` through `write_graphml` / `read_graphml` silently dropped all but one of each parallel edge — NetworkX's `add_edge` on a simple graph overwrites attrs when called twice with the same endpoints. The writer was correctly emitting two `<edge>` elements; the reader was merging them on parse.
- **Fix:** Pre-scan all `<edge>` elements for duplicate `(source, target)` pairs (normalised for undirected) before constructing the container. If duplicates exist, use `nx.MultiGraph` / `nx.MultiDiGraph`; otherwise stay on `nx.Graph` / `nx.DiGraph` so downstream type expectations don't silently widen.
- **TVCG-impact:** **none.** Corpus is simple.

### AR-1 — Self-loop tangents silently dropped from angular resolution  [FIXED]
- **Where:** `geg/angular_resolution.py::_incident_edge_angles`, old line 88.
- **What:** The guard `if seg0.start == seg0.end: continue` was intended to skip zero-length Line segments, but it also caught every Bezier / Arc self-loop (they have `start == end` at the pivot node by definition, while their control points give them a well-defined tangent). The self-loop's two tangent incidences were both dropped, yet `G.degree[v]` still counted the self-loop as 2 — so the `ideal = 360° / deg(v)` denominator was inflated without the loop's geometry actually being measured. A vertex with a self-loop was silently penalised for having one, regardless of the loop's shape.
- **Fix:** Skip only `Line` segments with coincident endpoints (truly zero-length). For Bezier / Arc segments, trust `unit_tangent(0.0)`; add defensive guards against `NaN` / zero-magnitude tangents to cover any svgpathtools pathology.
- **TVCG-impact:** **none.** The Mooney et al. corpus uses straight-line layouts without self-loops. For any future corpus containing self-loops, AR values on vertices adjacent to a self-loop will change — they were incorrect before this fix.

### ASP-1 — Aspect Ratio returned 0 for degenerate bounding box  [FIXED]
- **Where:** `geg/aspect_ratio.py` (old `width <= 0 or height <= 0` branch).
- **What:** Paper §3.2 defines `Asp(D) = 1` when `h(D) = 0` or `w(D) = 0`. The old code returned `0.0`.
- **Fix:** Return `1.0` in the degenerate branch; also removed the dead `<= 0` guard since bbox dimensions are non-negative by construction.
- **TVCG-impact:** **unknown → near-zero expected.** See `METRIC_DELTAS.md`. Triggered on 3 of 11 fixtures; for the TVCG corpus this requires all nodes collinear along one axis, which is measure-zero for continuous layouts and essentially impossible for the reported algorithms on graphs of n ≥ 3. Worth empirically diffing the Asp column on the real dataset for full confidence.

### ELD-1 — Division by zero when average edge length is 0  [FIXED]
- **Where:** `geg/edge_length_deviation.py` (old line 75).
- **What:** When all edges had length 0 (coincident endpoints), `get_average_edge_length` returned 0 and the metric divided by it.
- **Fix:** Guarded `ideal == 0` (return 1.0 — paper's "same length" condition holds vacuously). Also changed the m=0 (edgeless) return from 0.0 → 1.0 for consistency with the "1 = best" convention. Migrated to canonical helpers (`_geometry.distance`, `_paths.parse_path`).
- **TVCG-impact:** **no.** TVCG drawings have no zero-length edges and m > 0.

### EC-1 — Debug `print()` calls in production path  [FIXED]
- **Where:** `geg/edge_crossings.py` (old lines 82, 87 in `edge_crossings_bezier`).
- **What:** Stray debug prints and progress counter left in library code.
- **Fix:** Removed.
- **TVCG-impact:** **no** — output only; `edge_crossings_bezier` was experimental.

### CA-1 — `crossing_angle` could return >1 on user-supplied crossings  [FIXED]
- **Where:** `geg/crossing_angle.py:36-39`.
- **What:** The formula `1 - shortfall/len(crossings)` with `shortfall = sum((ideal - angle) / ideal)` goes above 1 if any per-crossing `angle > ideal`. The canonical path via `edge_crossings(return_crossings=True)` only emits acute angles (≤ 90°) so was safe, but a caller passing a precomputed list with obtuse angles would exit [0, 1].
- **Fix:** Clamp the per-crossing shortfall at 0 and the final score at [0, 1]. Added regression tests.
- **TVCG-impact:** **no** — the paper corpus was computed via the canonical path.

### GML-2 — `write_graphml` crashes on MultiGraph inputs  [FIXED]
- **Where:** `geg/io/graphml.py:269-270`.
- **What:** The writer iterated `for u, v in G.edges()` then subscripted `G.edges[u, v]`, which raises on MultiGraph (needs an edge key).
- **Fix:** Iterate `for u, v, attrs in G.edges(data=True)`. Parallel edges now round-trip as separate `<edge>` elements.
- **TVCG-impact:** **no** — TVCG corpus is simple graphs.

### GEG-1 — `read_geg` re-parsed the file for multigraph detection  [FIXED]
- **Where:** `geg/io/geg.py:105-107`.
- **What:** The reader parsed JSON, then called `is_multigraph_file(path)` which opened and parsed the file again to decide the graph class.
- **Fix:** Extracted `_data_is_multigraph(data)` helper operating on the already-parsed dict; `read_geg` calls that. Public `is_multigraph_file(path)` preserved as a standalone file-level check.
- **TVCG-impact:** **no** — doubles I/O cost but produces identical output.

### GML-1 — yEd GraphML stores node x/y as top-left, not centre  [FIXED]
- **Where:** `geg/io/graphml.py:read_graphml`.
- **What:** yEd's GraphML export puts `x`/`y` at the top-left corner of each node's bounding box, while edge bends are in absolute drawing coordinates. Treating x/y as the node centre (as every other source and our own writer do) misaligns the drawing by (width/2, height/2) and makes orthogonal L-shaped routings look diagonal.
- **Fix:** Reader auto-detects yEd-authored files via the `<!--Created by yEd-->` comment or `xmlns:yed` namespace and shifts `x += width/2, y += height/2`. New `yed_corner_anchor` kwarg on `read_graphml` / `graphml_to_geg` forces or suppresses the shift. `write_graphml` gains a matching kwarg to emit yEd-convention output; default is unchanged (centre-anchored, yed namespace omitted), so library round-trips are an identity.
- **TVCG-impact:** **unknown.** If any paper fixtures were produced by yEd and consumed without the shift, their metrics (especially EO, EC, CA, NEO) were computed against off-centre node positions. An empirical diff on the dataset would confirm.

### KSM-2 / NP-2 — DiGraph inputs crash / mis-score  [FIXED]
- **Where:** `geg/kruskal_stress.py:_connected_kruskal` and `geg/neighbourhood_preservation.py:_connected_np`.
- **What:** On a directed graph, `nx.all_pairs_shortest_path_length(G)` only records forward reachability, so sinks had no outbound entries and the pairwise distance matrix raised `KeyError`. NP built an asymmetric adjacency against a symmetric k-NN matrix, producing artificially low Jaccard scores.
- **Fix:** Both metrics now call `G.to_undirected(as_view=True)` at the top before component decomposition; the metric definitions are symmetric (Euclidean distance / neighbourhood), so direction is irrelevant.
- **TVCG-impact:** **unknown.** The published corpus may include directed drawings; if so, NP scores for those will increase. KSM would have previously errored on any DiGraph with a sink, so any published KSM value on a directed drawing was already using some workaround.

### PG-1 — Dead inline test / commented-out scratch in `parse_graph.py`  [FIXED]
- **Where:** `geg/parse_graph.py` lines 226–328 (old).
- **What:** `test_graph_read_write()` referencing non-existent files, plus a block of commented-out scratch code.
- **Fix:** Deleted. Kept the two useful converter utilities (`convert_gml_to_graphml`, `convert_graphml_to_gml`).
- **TVCG-impact:** **no.**

---

## Open design questions

### DQ-1 — Disconnected-graph handling per metric  [RESOLVED]
Paper §3.3 specifies weighted-sum-by-convex-hull-area for KSM and NP, and warns against per-component aggregation for EC.

| Metric | Behaviour | Source |
|---|---|---|
| KSM | Weighted sum by per-component convex-hull area | Paper §3.3 (explicit) |
| NP  | Weighted sum by per-component convex-hull area | Paper §3.3 (explicit) |
| AR  | Full-graph (locally defined per vertex) | Paper §3.3 (explicit) |
| Asp | Full-graph (bbox of entire drawing) | Gavin's call: components share the canvas |
| CA  | Full-graph (all crossings in `X(D)`) | Paper §3.3: per-component would miss inter-component crossings |
| EC  | Full-graph | Same reasoning as CA |
| ELD | Full-graph | Edge-length uniformity is about the set of edges; partitioning would conflate per-component scales |
| EO  | Full-graph (per-edge local) | Component-agnostic by construction |
| GR  | Full-graph | Another component's node inside your edge's disk is a real visual-clutter violation |
| NR  | Full-graph | min/max over all pair distances is layout geometry, not topology |
| NU  | Full-graph | Grid uniformity is over the full bbox |

### DQ-2 — Curved / Bézier edge handling per metric  [RESOLVED]
- **Context:** curved edges are flattened into polylines before per-metric measurement. The decisions are (a) which sampler / density, (b) which bbox convention per metric, (c) which SVG path commands are covered.
- **Resolution (v0.2.0):**
  - **Unified sampling density:** `samples_per_curve = 100` for every metric that flattens paths (EC, EO, NEO, and `curves_promotion` itself). Previously EC used 100 while EO, NEO, and `_paths.flatten_path_to_polyline` defaulted to 50, and `curves_promotion` used a different diagonal-relative strategy (`target_segments=10`). Unification means the polyline a curve is measured against is the same across metrics, and the paper §3.2 prescribed value wins. Callers can still override per-call.
  - **Unified sampler:** `_paths.flatten_path_to_polyline` is the only polyline sampler. `curves_promotion` now delegates to it; the legacy `approximate_edge_polyline` / `compute_global_scale` / `determine_N_for_segment` helpers and their re-exports are removed.
  - **Bbox convention per metric:**
    - **Asp** — curve-promoted bbox (keeps paper §3.2 "bounding box of the drawing" with curves included; their interior can reach outside the node hull).
    - **NU** — node-only bbox (grid occupancy is a statement about node placement; a large curve shouldn't stretch the grid and dilute cell counts).
    - **NEO** — node-only bbox for the `ε = epsilon_fraction · diag` scaling (ε should reflect node spread, not curve excursion). Per-edge distances still run against the promoted polyline — that hasn't changed.
  - **SVG path-command coverage:** M, L, H, V, Q, C all covered and fixtured (`polyline_bend`, `orthogonal_hv`, `bezier_curve`, `cubic_bezier`). S (smooth cubic), T (smooth quadratic), A (arc), Z (closepath) are supported by `svgpathtools` so they flow through `_paths.flatten_path_to_polyline` transparently, but no fixture pins expected values — Z in particular is unusual for edges (they're open polylines).
  - **Per-metric dispatch** unchanged from Phase 2: AR uses vertex-side tangents, ELD uses `svgpathtools` arc length, the rest flatten via the unified sampler.
- **Remaining ambiguity:** none of blocking weight. Sampling-sensitive metric values drift slightly with `samples_per_curve`; see `bezier_curve.md` and `cubic_bezier.md` which deliberately leave Asp / EO unpinned on curves for that reason.

### DQ-3 — Gabriel Ratio status  [RESOLVED]
- **Decision:** Kept in the library as non-canonical (Gavin). Paper §3.2 excludes GR because it is not applicable to drawings with curves, but the metric is still defined and useful for straight-line drawings.
- **Implementation:** `gabriel_ratio.py` module docstring states this. Both `gabriel_ratio_edges` and `gabriel_ratio_nodes` ignore edge `path` attrs and operate on node positions only.

---

## Remaining follow-ups (low priority)

- [ ] `edge_crossings_bezier` still reimplements acute-angle-between-vectors inline via svgpathtools complex-number tangents. It's the experimental / slow variant, so not urgent. Replacing with `_geometry.angle_between` would require adapting to complex-number inputs or converting first.
- [ ] `geg_parser.approximate_edge_polyline` still lives alongside `_paths.flatten_path_to_polyline`. Both are used (AR calls `approximate_edge_polyline` indirectly via its own SVG-path traversal; the new helpers are fine). Could consolidate further but no metric impact.
- [x] New metrics (the "1–2 additions" flagged in `library_update_brief.md`) — **Node-Edge Occlusion** is now in (`geg.node_edge_occlusion`). Definition is a cubic soft-overlap penalty, radius-aware (`max(0, d - r) / ε`). Default `epsilon_fraction = 0.02` (lowered from the initial 0.03 to account for the radius buffer). **Formula confirmed and finalised.**

---

## Manual-verification viewer — drawing-quality issues

Surfaced during the first end-to-end review pass over `manual_verification/review.json`. The *tests* are correct; these are SVG-rendering issues in `tests/_manual_verification.py` that make visual verification harder than it should be. Low priority, non-blocking for metric correctness.

### MV-1 — Nodes-only tests render as faceted component stacks
- **Where:** `tests/_manual_verification.py::_split_far_components` (and surrounding layout code).
- **What:** Tests that only populate node `x`/`y` (no edges) — common in `test_aspect_ratio`, `test_node_uniformity`, `test_node_resolution` — get split into one mini-panel per isolated node, so the actual *geometry under test* (a horizontal line, a unit square, a collinear triple) is not visible. The reviewer cannot tell from the SVG whether nodes are on a line, clustered, or squared off.
- **Flagged by reviewer on:**
  `test_aspect_ratio` (9): `TestBasic_test_unit_square`, `TestDegenerate_test_horizontal_line_of_nodes`, `TestDegenerate_test_vertical_line_of_nodes`, `TestInvariants_test_swapping_width_and_height_gives_same_value`, `TestInvariants_test_translation_invariant`, `TestInvariants_test_uniform_scale_invariant`, `TestRatios_test_tall_rectangle_1_to_3`, `TestRatios_test_unit_square`, `TestRatios_test_wide_rectangle_2_to_1`.
  `test_node_uniformity` (5): `TestKnownDeviations_test_two_nodes_with_2d_bbox_perfect`, `test_two_nodes_same_cell_is_zero`, `test_three_clustered_one_corner_2x2`, `test_horizontal_stack_even_spread`, `test_horizontal_stack_clumped`.
  `test_node_resolution` (2): `TestPerfectResolution_test_equilateral_triangle`, `TestKnownRatios_test_collinear_0_1_3`.
- **Fix direction:** Detect edgeless inputs and skip `_split_far_components`; draw all nodes in a single coordinate frame with a visible bbox outline. Optionally draft connecting segments just for rendering (with styling that makes clear they are not graph edges).

### MV-2 — Invariance tests have no before/after comparison
- **Where:** `tests/_manual_verification.py` graph-extraction stage.
- **What:** Translation / rotation / scale invariance tests declare two graphs `G1` and `G2` that differ only by the transformation under test, but the viewer only renders one. A reviewer can't see that the transformation actually ran or what the "after" looked like.
- **Flagged by reviewer on:** `test_edge_crossings/TestInvariants_test_arbitrary_rotation_invariant`, `test_translation_invariant`, `test_uniform_scale_invariant`.
- **Fix direction:** Extract all nx.Graph locals from the test body, not just the first; render paired SVGs when multiple graphs are present with a suffix (`_before` / `_after` or `_G1` / `_G2`).

### MV-3 — node_edge_occlusion drawings don't reflect asserted radii
- **Where:** `tests/_manual_verification.py` node rendering.
- **What:** Tests for radius-fallback logic pin expected overlap values based on test-supplied `width`/`height` attributes, but the viewer renders default-sized node glyphs ignoring those attributes. The reviewer can't visually verify that the edge actually passes within the node's claimed radius or that a "rectangular" node is rectangular.
- **Flagged by reviewer on:** `test_node_edge_occlusion/TestRadiusFallback_test_width_height_drive_occlusion`, `TestRadiusFallback_test_rectangular_node_uses_max_dimension`; also "could use an image" on `TestNoOcclusion_test_star_k1_4_legs_dont_pass_over_other_leaves`, `TestNoOcclusion_test_equilateral_triangle`.
- **Fix direction:** Honour per-node `width`/`height` node attrs when rendering. Emit distinct glyphs for circular vs rectangular nodes (pick max dimension for radius, or draw the literal rectangle).
