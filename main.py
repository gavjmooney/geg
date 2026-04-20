#!/usr/bin/env python3
"""Example usage of the `geg` metrics library.

This script is intentionally self-contained so it can double as the
tutorial: every library entry point the end-user cares about is exercised
below. Five subcommands:

    python main.py demo      --input FILE [--output-dir DIR]
        Load the drawing, print every metric, write a plain SVG, a
        grid-background SVG, and a GEG JSON copy into `--output-dir`.

    python main.py metrics   --input FILE
        Print every metric for one file; useful for quick sanity checks.

    python main.py render    --input FILE --output FILE.svg [--grid]
        Render a drawing to SVG, optionally with the integer-coordinate
        grid overlay used by the test fixtures.

    python main.py convert   --input SRC --output DST
        Convert between supported formats. Dispatch is by file extension
        on both sides: .geg / .graphml / .gml for input, .geg / .graphml /
        .gml / .svg for output. Uses `geg.convert` under the hood.

    python main.py batch     --input-dir DIR --output-csv metrics.csv
        Walk `DIR` recursively, load every .geg / .graphml / .gml file
        found, and append one row per file to the CSV. Each row contains
        the relative path, the detected format, every graph property
        (topology: node counts, degree stats, planarity, …), and every
        layout metric. Failures are logged but never abort the run.
        All-pairs-shortest-path is computed once per file and shared
        between kruskal_stress and the three distance properties.

Accepted input formats: `.geg`, `.graphml`, `.gml` (case-insensitive).
"""

from __future__ import annotations

import argparse
import csv
import logging
import sys
import warnings
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional, Tuple

import networkx as nx

import geg


SUPPORTED_INPUT_EXTENSIONS = {".geg", ".graphml", ".gml"}
SUPPORTED_OUTPUT_EXTENSIONS = {".geg", ".graphml", ".gml", ".svg"}

# The canonical metric set driving `compute_metrics`, `demo`, and the batch
# CSV columns. Curation rules:
#   - Angular Resolution uses the paper §3.2 eq. (1) min-angle variant.
#     `angular_resolution_avg_angle` is a library extension (mean absolute
#     deviation of angular gaps) and remains callable as
#     `geg.angular_resolution_avg_angle` for users who want it.
#   - Gabriel Ratio is excluded: paper §3.2 omits it ("not applicable for
#     drawings with curves"). The two variants remain callable as
#     `geg.gabriel_ratio_edges` / `geg.gabriel_ratio_nodes` for straight-line
#     drawings.
# Ordering is the CSV column order.
METRICS: List[Tuple[str, Callable[[nx.Graph], float]]] = [
    ("angular_resolution", geg.angular_resolution_min_angle),
    ("aspect_ratio", geg.aspect_ratio),
    ("crossing_angle", geg.crossing_angle),
    ("edge_crossings", geg.edge_crossings),
    ("edge_length_deviation", geg.edge_length_deviation),
    ("edge_orthogonality", geg.edge_orthogonality),
    ("kruskal_stress", geg.kruskal_stress),
    ("neighbourhood_preservation", geg.neighbourhood_preservation),
    ("node_edge_occlusion", geg.node_edge_occlusion),
    ("node_resolution", geg.node_resolution),
    ("node_uniformity", geg.node_uniformity),
]
METRIC_NAMES: List[str] = [name for name, _ in METRICS]

# Graph-property column list (topology, not layout). Ordered by
# `geg.graph_properties.PROPERTY_NAMES`.
PROPERTY_NAMES: List[str] = list(geg.graph_properties.PROPERTY_NAMES)


# ---------- Loading ----------

def load_drawing(path: Path) -> nx.Graph:
    """Load a drawing, dispatching on file extension via `geg.read_drawing`."""
    ext = path.suffix.lower()
    if ext not in SUPPORTED_INPUT_EXTENSIONS:
        raise ValueError(f"Unsupported input extension {ext!r} for {path}")
    return geg.read_drawing(path)


def find_drawings(root: Path) -> Iterable[Path]:
    """Yield every file under `root` (recursively) with a supported
    extension. If `root` is a file, yield it directly when supported.
    """
    if root.is_file():
        if root.suffix.lower() in SUPPORTED_INPUT_EXTENSIONS:
            yield root
        return
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.suffix.lower() in SUPPORTED_INPUT_EXTENSIONS:
            yield path


# ---------- Metrics ----------

def compute_metrics(
    G: nx.Graph,
    *,
    apsp=None,
    weight: Optional[str] = None,
) -> Dict[str, float]:
    """Compute every metric on `G`, sharing expensive intermediates.

    Shared work computed once per call:
      - `get_bounding_box(G)` — used by `aspect_ratio`, `node_uniformity`,
        and `node_edge_occlusion`. Internally runs `curves_promotion(G)`.
      - `edge_crossings(G, return_crossings=True)` — gives both the
        `edge_crossings` score and the crossings list that
        `crossing_angle` needs.

    `apsp` is an optional precomputed all-pairs-shortest-path-length dict
    forwarded to `kruskal_stress`; useful in batch contexts where the
    same APSP also feeds graph-property metrics (diameter, radius,
    avg_shortest_path_length).

    `weight` — edge attribute name routed to `kruskal_stress` (weighted
    shortest paths) and to `edge_length_deviation` (per-edge ideal length
    proportional to weight). Default `None` leaves both metrics
    unweighted.

    Any per-metric exception becomes NaN so one bad metric never kills the
    rest of the row.
    """
    out: Dict[str, float] = {}

    try:
        bbox = geg.get_bounding_box(G)
    except Exception as exc:
        logging.warning("get_bounding_box failed: %s", exc)
        bbox = None

    try:
        ec_score, crossings = geg.edge_crossings(G, return_crossings=True)
    except Exception as exc:
        logging.warning("edge_crossings failed: %s", exc)
        ec_score, crossings = float("nan"), None

    def _safe(name: str, fn: Callable[[], float]) -> None:
        try:
            out[name] = float(fn())
        except Exception as exc:
            logging.warning("metric %s failed: %s", name, exc)
            out[name] = float("nan")

    _safe("angular_resolution", lambda: geg.angular_resolution_min_angle(G))
    _safe("aspect_ratio", lambda: geg.aspect_ratio(G, bbox=bbox))
    _safe("crossing_angle", lambda: geg.crossing_angle(G, crossings=crossings))
    out["edge_crossings"] = ec_score
    _safe("edge_length_deviation", lambda: geg.edge_length_deviation(G, weight=weight))
    _safe("edge_orthogonality", lambda: geg.edge_orthogonality(G))
    _safe("kruskal_stress", lambda: geg.kruskal_stress(G, apsp=apsp, weight=weight))
    _safe("neighbourhood_preservation", lambda: geg.neighbourhood_preservation(G))
    _safe("node_edge_occlusion", lambda: geg.node_edge_occlusion(G, bbox=bbox))
    _safe("node_resolution", lambda: geg.node_resolution(G))
    _safe("node_uniformity", lambda: geg.node_uniformity(G, bbox=bbox))
    return out


# ---------- Subcommands ----------

def cmd_demo(args: argparse.Namespace) -> None:
    """Exercise the whole library on one file: load, metrics, SVGs, GEG save."""
    src = Path(args.input)
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Loading {src}")
    G = load_drawing(src)
    print(f"  {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
    print(f"  directed={isinstance(G, (nx.DiGraph, nx.MultiDiGraph))}  "
          f"multigraph={isinstance(G, (nx.MultiGraph, nx.MultiDiGraph))}")

    print("\nMetrics")
    metrics = compute_metrics(G)
    width = max(len(n) for n in METRIC_NAMES)
    for name in METRIC_NAMES:
        print(f"  {name:<{width}}  {metrics[name]:.6f}")

    print("\nRendering SVGs")
    plain = out_dir / f"{src.stem}.svg"
    grid = out_dir / f"{src.stem}_grid.svg"
    geg.to_svg(G, str(plain))
    geg.to_svg(G, str(grid), grid=True)
    print(f"  plain -> {plain}")
    print(f"  grid  -> {grid}")

    print("\nSaving GEG JSON copy")
    geg_out = out_dir / f"{src.stem}.geg"
    geg.write_geg(G, str(geg_out))
    print(f"  -> {geg_out}")


def cmd_metrics(args: argparse.Namespace) -> None:
    G = load_drawing(Path(args.input))
    metrics = compute_metrics(G)
    width = max(len(n) for n in METRIC_NAMES)
    for name in METRIC_NAMES:
        print(f"{name:<{width}}  {metrics[name]:.6f}")


def cmd_render(args: argparse.Namespace) -> None:
    G = load_drawing(Path(args.input))
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    geg.to_svg(
        G, str(out),
        grid=args.grid,
        width=args.width,
        height=args.height,
        margin=args.margin,
        scale=args.scale,
    )
    print(f"Wrote {out}")


def cmd_convert(args: argparse.Namespace) -> None:
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    kwargs = {"grid": args.grid} if out.suffix.lower() == ".svg" else {}
    geg.convert(args.input, str(out), **kwargs)
    print(f"Wrote {out}")


def cmd_batch(args: argparse.Namespace) -> None:
    root = Path(args.input_dir)
    if not root.exists():
        sys.exit(f"input-dir does not exist: {root}")

    out_csv = Path(args.output_csv)
    out_csv.parent.mkdir(parents=True, exist_ok=True)

    # Suppress deprecation warnings from the library (e.g. curved_edge_
    # orthogonality is aliased to edge_orthogonality) so stdout stays clean.
    warnings.filterwarnings("ignore", category=DeprecationWarning)

    header = ["file", "format"] + PROPERTY_NAMES + METRIC_NAMES
    ok = fail = 0
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(header)

        weight = args.weight  # None by default → unweighted
        for path in find_drawings(root):
            try:
                rel = path.relative_to(root)
            except ValueError:
                rel = path
            try:
                G = load_drawing(path)
                # APSP is the shared intermediate between kruskal_stress
                # (a layout metric) and the three distance properties
                # (diameter / radius / avg_shortest_path_length). Compute
                # it once per file and thread into both.
                apsp = _safe_apsp(G, weight=weight)
                properties = geg.compute_properties(G, apsp=apsp, weight=weight)
                metrics = compute_metrics(G, apsp=apsp, weight=weight)
                writer.writerow(
                    [str(rel), path.suffix.lstrip(".").lower()]
                    + [_fmt(properties[n]) for n in PROPERTY_NAMES]
                    + [_fmt(metrics[n]) for n in METRIC_NAMES]
                )
                ok += 1
                print(f"[ok]   {rel}")
            except Exception as exc:
                fail += 1
                writer.writerow(
                    [str(rel), path.suffix.lstrip(".").lower()]
                    + ["" for _ in PROPERTY_NAMES]
                    + ["" for _ in METRIC_NAMES]
                )
                logging.error("[fail] %s: %s", rel, exc)

    print(f"\nWrote {out_csv}  ({ok} ok, {fail} failed)")


def _safe_apsp(G: nx.Graph, weight: Optional[str] = None):
    """Compute APSP on G (undirected view). Returns None on failure so the
    downstream metrics / properties fall back to their internal paths.
    `weight` is forwarded to `compute_apsp` for weighted shortest paths."""
    try:
        return geg.graph_properties.compute_apsp(G, weight=weight)
    except Exception as exc:
        logging.warning("compute_apsp failed: %s", exc)
        return None


def _fmt(value) -> str:
    """Format a value for CSV output.

    Booleans become 'True' / 'False' (readable); numeric values use the
    short general-format '%.9g' that the batch has always used; NaN passes
    through as 'nan'; anything else is stringified.
    """
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, (int, float)):
        return f"{value:.9g}"
    return str(value)


# ---------- CLI wiring ----------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Example usage of the geg metrics library.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Accepted input formats: .geg, .graphml, .gml",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    p_demo = sub.add_parser("demo", help="Exercise every library feature on one file.")
    p_demo.add_argument("--input", required=True)
    p_demo.add_argument("--output-dir", default="demo_out")
    p_demo.set_defaults(func=cmd_demo)

    p_metrics = sub.add_parser("metrics", help="Print metrics for one file.")
    p_metrics.add_argument("--input", required=True)
    p_metrics.set_defaults(func=cmd_metrics)

    p_batch = sub.add_parser(
        "batch",
        help="Recursively scan a directory and write per-file metrics to CSV.",
    )
    p_batch.add_argument("--input-dir", required=True)
    p_batch.add_argument("--output-csv", required=True)
    p_batch.add_argument(
        "--weight",
        default=None,
        help=(
            "Edge attribute name for weighted shortest paths and weighted "
            "edge-length deviation. Default unweighted."
        ),
    )
    p_batch.set_defaults(func=cmd_batch)

    p_convert = sub.add_parser(
        "convert",
        help="Convert between formats (.geg / .graphml / .svg output).",
    )
    p_convert.add_argument("--input", required=True)
    p_convert.add_argument("--output", required=True)
    p_convert.add_argument(
        "--grid",
        action="store_true",
        help="SVG only: draw integer-coordinate grid background.",
    )
    p_convert.set_defaults(func=cmd_convert)

    p_render = sub.add_parser("render", help="Render a drawing to SVG.")
    p_render.add_argument("--input", required=True)
    p_render.add_argument("--output", required=True)
    p_render.add_argument("--grid", action="store_true")
    p_render.add_argument("--width", type=float, default=None,
                           help="Target SVG width in pixels (default 800).")
    p_render.add_argument("--height", type=float, default=None,
                           help="Target SVG height in pixels (default: aspect-ratio).")
    p_render.add_argument("--margin", type=float, default=50.0,
                           help="Margin around the drawing, in pixels (default 50).")
    p_render.add_argument("--scale", type=float, default=None,
                           help="Pixels per GEG unit. Overrides auto-fit when set.")
    p_render.set_defaults(func=cmd_render)

    return p


def main(argv: List[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    args.func(args)


if __name__ == "__main__":
    main()
