# GEG — Graph drawing metrics and I/O

**GEG Encodes Graphs.** GEG is a JSON-based file format for storing graph
*drawings* — not just the topology, but the coordinates of every node and the
full SVG-path geometry of every edge. The GEG package is useful for graph
drawing researchers who wish to evaluate the aesthetic/readability quality of
their drawings, particularly for comparing large sets of drawings across
different graph sizes/structures and layout regimes/scales.

GEG is developed and maintained by Gavin J. Mooney. (https://www.gavjmooney.com).

This package contains:

- a reader/writer for the GEG format,
- converters to/from GML and GraphML,
- an SVG renderer,
- and implementations of every readability metric in the GD 2025 canonical set.

Distribution name on PyPI is `geg-metrics`; the import name is `geg`.

```python
>>> import geg
>>> G = geg.read_geg("example.geg")
>>> geg.aspect_ratio(G)
0.84
>>> geg.edge_crossings(G)
1.0
```

The metric set follows:

Gavin J. Mooney, Tim Hegemann, Alexander Wolff, Michael Wybrow, and Helen C. Purchase. Universal Quality Metrics for Graph Drawings: Which Graphs Excite Us Most?. In 33rd International Symposium on Graph Drawing and Network Visualization (GD 2025). Leibniz International Proceedings in Informatics (LIPIcs), Volume 357, pp. 30:1-30:20, Schloss Dagstuhl – Leibniz-Zentrum für Informatik (2025) https://doi.org/10.4230/LIPIcs.GD.2025.30

Every metric returns a float in **[0, 1]**, with **1 = best**. Every metric
accepts any input drawing — straight, polyline, or curved edges — and dispatches
on the geometry internally; there is one function per metric.

## Installation

Requires Python ≥ 3.9.

```bash
pip install geg-metrics
```

Runtime dependencies: `networkx`, `numpy`, `scipy`, `scikit-learn`, `svgpathtools`.

## Quickstart

```python
import geg

G = geg.read_geg("example.geg")
print("Aspect ratio      :", geg.aspect_ratio(G))
print("Angular resolution:", geg.angular_resolution(G))
print("Edge crossings    :", geg.edge_crossings(G))
```

GEG files load into a `networkx.Graph` with per-node `x` / `y` attributes and
per-edge `path` / `polyline` attributes; any NetworkX operation that ignores
unknown node/edge data works as expected.

### Convert GraphML or GML to GEG

```python
G = geg.graphml_to_geg("example.graphml")   # or gml_to_geg
geg.write_geg(G, "example.geg")
```

### Render to SVG

```python
geg.to_svg(G, "example.svg", margin=50)
```

### Compute every metric in a dict

```python
from geg import (
    aspect_ratio, angular_resolution, crossing_angle, edge_crossings,
    edge_length_deviation, edge_orthogonality, kruskal_stress,
    neighbourhood_preservation, node_edge_occlusion, node_resolution,
    node_uniformity,
)

G = geg.read_geg("example.geg")
metrics = {
    "AR":  angular_resolution(G),
    "Asp": aspect_ratio(G),
    "CA":  crossing_angle(G),
    "EC":  edge_crossings(G),
    "EL":  edge_length_deviation(G),
    "EO":  edge_orthogonality(G),
    "KSM": kruskal_stress(G),
    "NP":  neighbourhood_preservation(G),
    "NEO": node_edge_occlusion(G),
    "NR":  node_resolution(G),
    "NU":  node_uniformity(G),
}
```

### Topological graph properties

`geg.compute_properties(G)` returns a dict of topology-only descriptors
(node/edge counts, degree stats, connectivity, planarity, diameter, radius,
clustering, assortativity, crossing-number lower bounds, …). Individual
functions are available from `geg.graph_properties`.

```python
from geg import compute_properties
props = compute_properties(G)
props["density"], props["is_planar"], props["diameter"]
```

## API reference

### Readability metrics

All metrics take a `networkx.Graph` with `x` / `y` node
attributes and return a float in `[0, 1]`. Metrics that depend on edge
geometry additionally read the edge `path` attribute.

| Function                            | Paper §/eq. | What it measures                                                         |
| ----------------------------------- | ----------- | ------------------------------------------------------------------------ |
| `angular_resolution(G)`             | §3.2 eq. 1  | Uniformity of angles between incident edges at each vertex.              |
| `aspect_ratio(G)`                   | §3.2        | Closeness of the drawing's bounding box to a square.                     |
| `crossing_angle(G)`                 | §3.2 eq. 2  | Closeness of edge-crossing angles to 90° (or `ideal_angle=`).            |
| `edge_crossings(G)`                 | §3.2 eq. 3  | Ratio of observed crossings to the Euler lower bound.                    |
| `edge_length_deviation(G)`          | §3.2 eq. 4  | Uniformity of drawn edge lengths.                                        |
| `edge_orthogonality(G)`             | §3.2 eq. 5–6| Alignment of edge segments to horizontal/vertical (length-weighted).     |
| `kruskal_stress(G)`                 | §3.2 eq. 7  | Isotonic-regression stress between graph-theoretic and layout distances. |
| `neighbourhood_preservation(G)`     | §3.2 eq. 8  | Jaccard overlap of topological k-neighbourhoods vs. k-nearest in layout. |
| `node_resolution(G)`                | §3.2 eq. 9  | Ratio of the minimum to the maximum pairwise node distance.              |
| `node_uniformity(G)`                | §3.2 eq. 10 | Evenness of node placement under grid occupancy.                         |
| `node_edge_occlusion(G)`            | ext.        | Cubic-soft penalty for edges passing too close to non-incident nodes.    |

`node_edge_occlusion` is a library extension not in the GD 2025 paper;
it is introduced in a forthcoming publication.

#### Selected signatures

```python
aspect_ratio(G, *, bbox=None) -> float
angular_resolution(G) -> float
crossing_angle(G, ideal_angle=90.0) -> float
edge_crossings(G, *, min_angle_tol=2.5) -> float
edge_length_deviation(G, ideal=None, *, weight=None) -> float
edge_orthogonality(G) -> float
kruskal_stress(G, *, apsp=None, weight=None) -> float
neighbourhood_preservation(G, k=None) -> float
node_edge_occlusion(G, *, epsilon_fraction=0.05) -> float
node_resolution(G) -> float
node_uniformity(G, *, bbox=None, include_curves=False) -> float
```

#### Invariances and disconnected-graph handling

| Metric | Scale-invariant | Rotation-invariant | Disconnected handling |
| ------------------------------ | --- | --- | --- |
| `angular_resolution(G)`        | ✓   | ✓   | none needed — per-vertex, skips degree ≤ 1 |
| `aspect_ratio(G)`              | ✓   | ✗ ¹ | none — single bbox over the whole drawing |
| `crossing_angle(G)`            | ✓   | ✓   | none — per-crossing |
| `edge_crossings(G)`            | ✓   | ✓ ² | none — counts crossings globally |
| `edge_length_deviation(G)`     | ✓   | ✓   | none — uses the edge-length distribution |
| `edge_orthogonality(G)`        | ✓   | ✗ ¹ | none — per-edge, independent |
| `kruskal_stress(G)`            | ✓   | ✓   | **per-component** weighted by convex-hull area (paper §3.3); singleton components contribute nothing |
| `neighbourhood_preservation(G)`| ✓   | ✓   | **per-component** weighted by convex-hull area (paper §3.3) |
| `node_edge_occlusion(G)`       | ✓ ³ | ≈ ⁴ | none — per edge, independent |
| `node_resolution(G)`           | ✓   | ✓   | none — global min/max over all pairs |
| `node_uniformity(G)`           | ✓   | ✗ ¹ | none — single grid over all nodes |

¹ *Uses the axis-aligned bounding box (AR, NU) or the horizontal/vertical
  axes (EO). Rotating the drawing rotates the bbox / axes away from the
  drawing, so the value changes. The 90° special case is an identity for
  EO and NU, and a reciprocal for AR (`h/w ↔ w/h`, same score).*

² *Generic rotations preserve the crossing set. Measure-zero rotations
  that make two edges collinear change the count; pick any non-degenerate
  angle and EC is invariant.*

³ *NEO is scale-invariant when node radii scale with the coordinates. Raw
  scaling of `x`/`y` without also scaling `radius` / `width` / `height`
  changes the penalty zone and the result.*

⁴ *NEO's penalty zone is `epsilon_fraction × bbox_diagonal`, so the bbox
  diagonal of a rotated drawing (which is generally larger than the
  unrotated one for the axis-aligned box) changes ε slightly. In
  practice the shift is small; the metric is not strictly
  rotation-invariant.*

### I/O

```python
read_geg(path)     -> nx.Graph
write_geg(G, path) -> None

read_gml(path)     -> nx.Graph
write_gml(G, path) -> None

read_graphml(path)     -> nx.Graph
write_graphml(G, path) -> None

# auto-dispatch by file extension
read_drawing(path)     -> nx.Graph
write_drawing(G, path) -> None
convert(src_path, dst_path) -> None
```

### Rendering and geometry helpers

```python
to_svg(G, output_path, margin=50) -> None
get_bounding_box(G, promote=True) -> (min_x, min_y, max_x, max_y)
get_convex_hull_area(G) -> float
curves_promotion(G) -> nx.Graph   # see below
```

### Graph properties (topology only)

`compute_properties(G)` runs every property and returns a dict; failures
become `NaN` so a single exception never kills a batch. Individual functions
are importable from `geg.graph_properties`: `n_nodes`, `n_edges`, `density`,
`is_directed`, `is_multigraph`, `n_self_loops`, `n_connected_components`,
`is_connected`, `min_degree`, `max_degree`, `mean_degree`, `degree_std`,
`is_tree`, `is_forest`, `is_bipartite`, `is_planar`, `is_dag`, `is_regular`,
`is_eulerian`, `degeneracy`, `n_biconnected_components`,
`crossing_number_lb_euler`, `crossing_number_lb_bipartite`, `diameter`,
`radius`, `avg_shortest_path_length`, `n_triangles`, `average_clustering`,
`transitivity`, `degree_assortativity`.

Distance-based properties (`diameter`, `radius`, `avg_shortest_path_length`)
handle disconnected graphs by aggregating per connected component, weighted
by component node count.

## Graph data model

A GEG graph, once loaded, is a `networkx.Graph` (or `DiGraph` when
`graph.directed = true`) with these attribute conventions:

| Level | Attribute           | Meaning                                                          |
| ----- | ------------------- | ---------------------------------------------------------------- |
| node  | `x`, `y`            | Coordinates (float). Required by every layout-dependent metric.  |
| node  | `width`, `height`   | Optional bounding-box size; used by `node_edge_occlusion`.       |
| node  | `radius`            | Optional disk radius; preferred by `node_edge_occlusion`.        |
| node  | `shape`, `colour`   | Optional visual hints carried through SVG rendering.             |
| edge  | `path`              | SVG path string (e.g. `M 0,0 L 10,10` or with `C` cubics).       |
| edge  | `polyline`          | Bool: `True` when the path is a pure M/L polyline.               |

Straight edges still carry an explicit `path` attribute of the form
`M x0,y0 L x1,y1`, which keeps the geometry-handling code uniform.

## `curves_promotion` — shared preprocessing

Curved/polyline edges are linearised into straight segments before metric
computation. `curves_promotion(G)` returns a *new* graph `H` where each
curved edge is replaced by synthetic intermediate nodes (`is_segment=True`,
IDs shaped `{edge_id}_pt_{i}`) joined by straight `M x,y L x,y` segments.

Sampling is **adaptive by default**: the flattening tolerance is a fixed
fraction (`flatness_fraction`, default 0.005) of the node-bbox diagonal, so
highly curved segments receive more intermediate nodes and nearly-straight
ones receive fewer — avoiding both under-sampling of tight curves and
over-sampling of gentle ones. A fixed-density mode is available via
`samples_per_curve=N` for reproducibility against older versions.

Which metrics run on `G` vs. the promoted `H` is metric-specific and
follows the GD 2025 paper. Users typically do not need to call
`curves_promotion` directly — each metric applies it as needed.

## The GEG file format

A minimal GEG document:

```json
{
  "graph": { "directed": false },
  "nodes": [
    { "id": "a", "position": [0, 0] },
    { "id": "b", "position": [100, 0] }
  ],
  "edges": [
    { "id": "e0", "source": "a", "target": "b", "path": "M 0,0 L 100,0" }
  ]
}
```

The authoritative JSON Schema is `schema.json`. Fields not listed here
(`shape`, `colour`, `polyline`, `graph.doi`, `graph.license`, …) round-trip
through the reader/writer when present.

## License

MIT. See `LICENSE`.

## Citing

If you use this library in academic work, please cite the GD 2025 paper:

Gavin J. Mooney, Tim Hegemann, Alexander Wolff, Michael Wybrow, and Helen C. Purchase. Universal Quality Metrics for Graph Drawings: Which Graphs Excite Us Most?. In 33rd International Symposium on Graph Drawing and Network Visualization (GD 2025). Leibniz International Proceedings in Informatics (LIPIcs), Volume 357, pp. 30:1-30:20, Schloss Dagstuhl – Leibniz-Zentrum für Informatik (2025) https://doi.org/10.4230/LIPIcs.GD.2025.30



```bibtex
@InProceedings{mooney_et_al:LIPIcs.GD.2025.30,
  author =	{Mooney, Gavin J. and Hegemann, Tim and Wolff, Alexander and Wybrow, Michael and Purchase, Helen C.},
  title =	{{Universal Quality Metrics for Graph Drawings: Which Graphs Excite Us Most?}},
  booktitle =	{33rd International Symposium on Graph Drawing and Network Visualization (GD 2025)},
  pages =	{30:1--30:20},
  series =	{Leibniz International Proceedings in Informatics (LIPIcs)},
  ISBN =	{978-3-95977-403-1},
  ISSN =	{1868-8969},
  year =	{2025},
  volume =	{357},
  editor =	{Dujmovi\'{c}, Vida and Montecchiani, Fabrizio},
  publisher =	{Schloss Dagstuhl -- Leibniz-Zentrum f{\"u}r Informatik},
  address =	{Dagstuhl, Germany},
  URL =		{https://drops.dagstuhl.de/entities/document/10.4230/LIPIcs.GD.2025.30},
  URN =		{urn:nbn:de:0030-drops-250162},
  doi =		{10.4230/LIPIcs.GD.2025.30},
  annote =	{Keywords: Graph drawing metrics, metric landscape, straight-line drawings, polyline drawings, curved drawings, automated extraction of graph drawings}
}
```

## A note on generative AI
Thanks to advances in generative AI for software development, we can greatly improve the maintainability and robustness of repositories at minimal cost. Claude Opus 4.6/4.7 was used to refactor the codebase using red/green test driven development practices, find errors, correct ambiguities and improve the robustness/quality of I/O operations (particularly for outputting SVGs). All code and tests have been manually verified and the scientific content remains the sole responsibility of the author.

Code co-authored by Claude <noreply@anthropic.com> (Claude code running models Opus 4.6/4.7).