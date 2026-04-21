# orthogonal_hv

Single edge from `a = (0, 0)` to `b = (4, 2)` drawn with an L-bend
via `(4, 0)`, encoded using SVG `H` and `V` commands:

    M0,0 H4 V2

Purpose: pin parser / sampler handling of the `H` (horizontal
lineto) and `V` (vertical lineto) commands. Geometrically identical
to `polyline_bend` but via different path syntax. If the flattening
pipeline (`_paths.flatten_path_to_polyline`) correctly expands `H`
and `V` into `Line` segments, every metric here matches the L-form
expectation; if it doesn't, at least EO will flag the issue
(the sampler would treat the corner as a curve and produce
intermediate samples, yielding non-orthogonal short segments).

| Metric | Expected | Reason |
|---|---|---|
| Asp | 1/2 | Promoted bbox `4 × 2` → `h/w = 0.5`. |
| AR (min/avg) | 1 | Both vertices degree 1; AR is vacuous. |
| CA | 1 | No crossings. |
| EC | 1 | Single edge. |
| ELD | 1 | Single edge. |
| EO | 1 | Both segments are axis-aligned after H/V expansion → `δ = 0`. |
| NEO | 1 | No non-endpoint vertex. |
