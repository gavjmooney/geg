# Metric test fixtures

Each fixture is a small hand-designed drawing at unit scale, chosen so that
one or more metrics have a clean analytical value. Every fixture has:

- `<name>.geg` — JSON drawing (written by `geg.write_geg`).
- `<name>.svg` — visual rendering with a faint integer-coordinate grid
  (produced by `geg.to_svg(..., grid=True)`).
- `<name>.md` — expected-value table + derivations.

The expected values are checked in `tests/test_fixtures.py` (parametrized
over every fixture × metric pair).

## Regenerating the artefacts

```
python -m tests.fixtures._builder
```

`_builder.py` is the single source of truth for fixture definitions and
their expected metric values. If you add a new fixture or change an
existing one, update `_builder.py` (NetworkX construction + expected
values) and re-run the command above to refresh the `.geg` / `.svg` files.

## Current fixtures

| Fixture | What it exercises |
|---|---|
| `single_edge` | Trivial smoke test — every metric returns 1. |
| `path_stretched` | Non-uniform collinear path (lengths 1, 2, 3); ELD=3/4, NR=1/6. Non-uniform spacing avoids k-NN ties. |
| `equilateral_triangle` | AR=1/3 (60° interior), EO=5/9, KSM=1, NP=1. |
| `unit_square_k4` | EC=2/3 (diagonals cross at 90°), EO=2/3, NU=1, symbolic ELD. |
| `unit_square_cycle` | 4-cycle (planar, 0-crossing, perfect orthogonality); AR=0.5. |
| `grid_3x3` | Structured 3×3 grid with 12 edges; AR_min=2/3, AR_avg=17/27, NR=1/(2√2), NU=1. |
| `star_k1_4` | Axis-aligned star; perfect AR at centre; NR=0.5. |
| `pentagon` | Regular 5-gon (sides only): AR=0.6 (108° interior gaps). |
| `diagonal_45` | Single 45° edge — EO=0 boundary case. |
| `long_edge_path` | Collinear path with one 10× stretched edge; ELD=1/2, NR=1/12. |
| `polyline_bend` | L-shaped polyline — exercises bends-promotion path of EO / bbox. |
