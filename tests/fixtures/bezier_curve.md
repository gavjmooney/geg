# bezier_curve

Single quadratic Bézier edge from `a=(0,0)` to `b=(4,0)` with control
point `(2, 2)`. Parabolic arch peaking at `(2, 1)` at `t = 0.5`.

Purpose: force DQ-2 (curved / Bézier handling per metric) into a concrete
drawing with pinned expected values. Each metric's behaviour on curves is
audited in `ISSUES.md`; the values below are the ones that are robust
to the sampling density chosen for curve promotion.

| Metric | Expected | Reason |
|---|---|---|
| AR (min/avg) | 1 | Both vertices degree 1; AR is vacuous. |
| CA | 1 | A single edge cannot cross anything. |
| EC | 1 | No crossings with one edge. |
| ELD | 1 | Single edge → ideal = actual → zero deviation. |
| NEO | 1 | No non-endpoint vertex exists. |

Not pinned (sampling-sensitive; the library's current default is
`target_segments=10` in `curves_promotion` and `samples_per_curve=50`
in EO):

- `aspect_ratio`, `edge_orthogonality`, `node_uniformity`: depend on the
  promoted bounding box / segment orientations. They're deterministic at
  a fixed sampling density but not analytical closed forms; values drift
  if the sampling density changes. See `METRIC_DELTAS.md` entries added
  when DQ-2 is fully resolved.
