# cubic_bezier

Single cubic Bézier edge from `a = (0, 0)` to `b = (4, 0)` with control
points `(1, 3)` and `(3, 3)`. The curve is symmetric about `x = 2` and
peaks at `y = 2.25` (at `t = 0.5`, derivable from `y(t) = 9·t·(1 − t)`).

Purpose: exercise the cubic (C) SVG-path command — the most common
curved-edge format emitted by real graph-drawing tools (yEd, force-
directed layouts with curve output, Sugiyama with routed edges).

Pinned metrics are those that are invariant under the curve's shape
(vacuous 1 on a single-edge drawing) or that only care about the node
positions. Everything that depends on sampling the curve's interior
is deliberately left open for the same reason as `bezier_curve` —
sampling-sensitivity drift would tie the fixture to the current
`samples_per_curve=100` default.

| Metric | Expected | Reason |
|---|---|---|
| AR (min/avg) | 1 | Both vertices degree 1; AR is vacuous. |
| CA | 1 | A single edge cannot cross anything. |
| EC | 1 | No crossings with one edge. |
| ELD | 1 | Single edge → ideal = actual → zero deviation. |
| NEO | 1 | No non-endpoint vertex exists. |

Not pinned: `Asp` (depends on promoted bbox; peak y ≈ 2.25), `EO`
(depends on per-segment angles after sampling), `NU` (node-only bbox
is degenerate here since the two endpoints have `y = 0`; `NU` returns
1.0 on the 1D node bbox regardless).
