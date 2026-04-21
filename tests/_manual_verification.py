"""Generate per-test SVGs for human review.

Each SVG shows:
  - **Left column** — the graph the test operates on, where it can be
    reconstructed from the test source; else a placeholder.
  - **Right column** — test docstring (plain-English "what this checks")
    and the test's source code.

Graph extraction is best-effort heuristic. The text panel is exhaustive —
every test gets its full source + docstring regardless. The idea is that
a human can open any SVG, glance at the graph (if present), read the
description, and verify the assertions make sense without having to jump
between files.

Not a pytest test itself (leading underscore in module name keeps it out
of collection). Run from the package root:

    python -m tests._manual_verification

Output goes to `manual_verification/` at the repo root; that directory
is gitignored. Regenerate whenever test expectations change.
"""

from __future__ import annotations

import ast
import importlib
import inspect
import math
import re
import sys
from html import escape as html_escape
from pathlib import Path
from typing import Callable, Dict, Iterator, Optional, Tuple

import networkx as nx


ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "manual_verification"
TESTS_DIR = ROOT / "tests"


TestInfo = Tuple[str, Optional[str], str, str, Optional[str], Optional[str], Optional[str]]
# (module_stem, class_name_or_None, func_name, source_code,
#  module_docstring, class_docstring, function_docstring)


# ---------- test enumeration ----------

def _iter_tests() -> Iterator[TestInfo]:
    """Walk every `tests/test_*.py`, yielding one record per test function.

    Test-class methods are emitted individually; module-level test functions
    are emitted with `class_name = None`.
    """
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    for test_file in sorted(TESTS_DIR.glob("test_*.py")):
        mod_name = f"tests.{test_file.stem}"
        try:
            mod = importlib.import_module(mod_name)
        except Exception as exc:
            print(f"  skipping {mod_name}: {type(exc).__name__}: {exc}")
            continue

        for name, obj in inspect.getmembers(mod):
            # Test classes.
            if (
                name.startswith("Test")
                and inspect.isclass(obj)
                and getattr(obj, "__module__", None) == mod_name
            ):
                for mname, mobj in inspect.getmembers(obj):
                    if not mname.startswith("test_"):
                        continue
                    if not inspect.isfunction(mobj):
                        continue
                    yield (
                        test_file.stem, name, mname,
                        _safe_source(mobj),
                        mod.__doc__, obj.__doc__, mobj.__doc__,
                    )
            # Module-level test functions.
            elif (
                name.startswith("test_")
                and inspect.isfunction(obj)
                and getattr(obj, "__module__", None) == mod_name
            ):
                yield (
                    test_file.stem, None, name,
                    _safe_source(obj),
                    mod.__doc__, None, obj.__doc__,
                )


def _safe_source(obj) -> str:
    try:
        return inspect.getsource(obj)
    except (OSError, TypeError):
        return "# (source unavailable)"


# ---------- graph extraction (best-effort heuristic) ----------

_GRAPH_CTORS: Dict[str, Callable[[int], nx.Graph]] = {
    "path_graph":         nx.path_graph,
    "cycle_graph":        nx.cycle_graph,
    "complete_graph":     nx.complete_graph,
    "star_graph":         nx.star_graph,
    "wheel_graph":        nx.wheel_graph,
    "petersen_graph":     lambda _n: nx.petersen_graph(),
}


def _layout_coords(G: nx.Graph) -> None:
    """Attach x/y attributes via NetworkX spring layout (deterministic seed)."""
    try:
        pos = nx.spring_layout(G, seed=0)
    except Exception:
        # Disconnected / tiny graphs — fall back to a simple circular layout.
        pos = nx.circular_layout(G)
    for n, (x, y) in pos.items():
        G.nodes[n]["x"] = float(x) * 100.0
        G.nodes[n]["y"] = float(y) * 100.0


def _try_fixture_graph(src: str) -> Optional[nx.Graph]:
    """If source references `all_fixtures()["NAME"]`, build that fixture."""
    m = re.search(r'all_fixtures\(\)\[\s*["\']([\w_]+)["\']\s*\]', src)
    if not m:
        return None
    try:
        from tests.fixtures._builder import all_fixtures
        return all_fixtures()[m.group(1)].build()
    except (ImportError, KeyError):
        return None


def _try_nx_ctor(src: str) -> Optional[nx.Graph]:
    """Recognise a few common `nx.<ctor>(N)` patterns."""
    for ctor, fn in _GRAPH_CTORS.items():
        m = re.search(rf"nx\.{ctor}\(\s*(\d*)\s*\)", src)
        if not m:
            continue
        try:
            n = int(m.group(1)) if m.group(1) else 5
            G = fn(n)
            _layout_coords(G)
            return G
        except Exception:
            continue
    return None


def _try_bipartite(src: str) -> Optional[nx.Graph]:
    m = re.search(r"nx\.complete_bipartite_graph\(\s*(\d+)\s*,\s*(\d+)\s*\)", src)
    if not m:
        return None
    try:
        G = nx.complete_bipartite_graph(int(m.group(1)), int(m.group(2)))
        _layout_coords(G)
        return G
    except Exception:
        return None


_INLINE_ADD_NODE = re.compile(
    r"""add_node\(\s*         # G.add_node(
        (?P<id>["']?[\w_]+["']?|\d+)
        \s*,\s*x\s*=\s*(?P<x>-?\d+(?:\.\d+)?)
        \s*,\s*y\s*=\s*(?P<y>-?\d+(?:\.\d+)?)""",
    re.VERBOSE,
)
_INLINE_ADD_EDGE = re.compile(
    r"""add_edge\(\s*
        (?P<u>["']?[\w_]+["']?|\d+)
        \s*,\s*(?P<v>["']?[\w_]+["']?|\d+)""",
    re.VERBOSE,
)


def _try_inline_graph(src: str) -> Optional[nx.Graph]:
    """Parse simple inline `G.add_node(..., x=X, y=Y)` + `G.add_edge(...)`
    patterns. Misses a lot of real tests but catches the common case
    where a test builds a small named graph with explicit coordinates."""
    nodes = list(_INLINE_ADD_NODE.finditer(src))
    if len(nodes) < 2:
        return None
    G = nx.Graph()
    for m in nodes:
        nid = m.group("id").strip("'\"")
        try:
            nid_cast: object = int(nid) if nid.isdigit() else nid
            G.add_node(nid_cast, x=float(m.group("x")), y=float(m.group("y")))
        except ValueError:
            continue
    for m in _INLINE_ADD_EDGE.finditer(src):
        u = m.group("u").strip("'\"")
        v = m.group("v").strip("'\"")
        u_c: object = int(u) if u.isdigit() else u
        v_c: object = int(v) if v.isdigit() else v
        if u_c in G and v_c in G:
            G.add_edge(u_c, v_c)
    return G if G.number_of_nodes() >= 2 else None


def try_extract_graph(src: str) -> Optional[nx.Graph]:
    for strategy in (_try_fixture_graph, _try_nx_ctor, _try_bipartite, _try_inline_graph):
        G = strategy(src)
        if G is not None and G.number_of_nodes() > 0:
            return G
    return None


# ---------- SVG rendering ----------

GRAPH_W = 560
GRAPH_H = 560
TEXT_X = GRAPH_W + 40
TEXT_W = 760
CANVAS_W = TEXT_X + TEXT_W + 40   # 1400
HEADER_H = 50
BODY_H = 720
FOOTER_H = 30
CANVAS_H = HEADER_H + BODY_H + FOOTER_H  # 800


def _graph_panel_svg(G: Optional[nx.Graph], x0: int, y0: int) -> str:
    """Render the graph (nodes + edges) into a region of the SVG."""
    box_border = (
        f'<rect x="{x0}" y="{y0}" width="{GRAPH_W}" height="{GRAPH_H}" '
        f'fill="#fafbfc" stroke="#e1e4e8" stroke-width="1"/>'
    )
    if G is None or G.number_of_nodes() == 0:
        return (
            box_border
            + f'<text x="{x0 + GRAPH_W // 2}" y="{y0 + GRAPH_H // 2}" '
            f'font-family="sans-serif" font-size="16" fill="#8b949e" '
            f'text-anchor="middle">(no graph extracted — see source)</text>'
        )

    # Compute bbox from node x/y (if present) else spring layout.
    xs, ys = [], []
    missing = False
    for _, attrs in G.nodes(data=True):
        x, y = attrs.get("x"), attrs.get("y")
        if x is None or y is None:
            missing = True
            break
        try:
            xs.append(float(x)); ys.append(float(y))
        except (TypeError, ValueError):
            missing = True; break
    if missing or not xs:
        _layout_coords(G)
        xs = [float(a["x"]) for _, a in G.nodes(data=True)]
        ys = [float(a["y"]) for _, a in G.nodes(data=True)]

    pad = max(max(xs) - min(xs), max(ys) - min(ys), 1.0) * 0.15
    min_x, max_x = min(xs) - pad, max(xs) + pad
    min_y, max_y = min(ys) - pad, max(ys) + pad
    extent = max(max_x - min_x, max_y - min_y, 1e-9)
    scale = (GRAPH_W - 40) / extent
    cx_off = x0 + 20 - min_x * scale + (GRAPH_W - 40 - (max_x - min_x) * scale) / 2
    cy_off = y0 + 20 - min_y * scale + (GRAPH_H - 40 - (max_y - min_y) * scale) / 2

    def tx(a):
        return a["x"] * scale + cx_off, a["y"] * scale + cy_off

    parts = [box_border]
    # Edges first (so nodes overlay).
    for u, v, attrs in G.edges(data=True):
        ux, uy = tx(G.nodes[u])
        vx, vy = tx(G.nodes[v])
        path = attrs.get("path")
        if path:
            # Rescale path coords via svgpathtools (robust for Q / C / H / V).
            try:
                import svgpathtools as svgp
                p = svgp.parse_path(path)
                for seg in p:
                    for sattr in ("start", "control", "control1", "control2", "end"):
                        if hasattr(seg, sattr):
                            z = getattr(seg, sattr)
                            setattr(seg, sattr, complex(
                                z.real * scale + cx_off,
                                z.imag * scale + cy_off,
                            ))
                parts.append(
                    f'<path d="{p.d()}" fill="none" '
                    f'stroke="#24292e" stroke-width="1.5"/>'
                )
                continue
            except Exception:
                pass
        parts.append(
            f'<line x1="{ux:.2f}" y1="{uy:.2f}" x2="{vx:.2f}" y2="{vy:.2f}" '
            f'stroke="#24292e" stroke-width="1.5"/>'
        )

    # Nodes.
    r = 5
    for n, attrs in G.nodes(data=True):
        nx_, ny_ = tx(attrs)
        parts.append(
            f'<circle cx="{nx_:.2f}" cy="{ny_:.2f}" r="{r}" '
            f'fill="#ffffff" stroke="#24292e" stroke-width="1.5"/>'
        )
        parts.append(
            f'<text x="{nx_:.2f}" y="{ny_ - r - 3:.2f}" '
            f'font-family="sans-serif" font-size="10" fill="#586069" '
            f'text-anchor="middle">{html_escape(str(n))}</text>'
        )

    n = G.number_of_nodes(); m = G.number_of_edges()
    parts.append(
        f'<text x="{x0 + 10}" y="{y0 + GRAPH_H - 10}" '
        f'font-family="monospace" font-size="11" fill="#586069">'
        f'{n} node{"s" if n != 1 else ""}, {m} edge{"s" if m != 1 else ""}</text>'
    )
    return "\n".join(parts)


def _text_panel_svg(
    test_file: str, cls_name: Optional[str], func_name: str,
    src: str, cls_doc: Optional[str], func_doc: Optional[str],
    x0: int, y0: int,
) -> str:
    qual = f"{cls_name}.{func_name}" if cls_name else func_name
    loc = f"tests/{test_file}.py::{qual}"

    html = []
    html.append(
        f'<h2 style="margin:0 0 6px 0;font-size:15px;color:#24292e;'
        f'font-family:sans-serif;">{html_escape(qual)}</h2>'
    )
    html.append(
        f'<p style="margin:0 0 10px 0;font-size:11px;color:#6a737d;'
        f'font-family:monospace;">{html_escape(loc)}</p>'
    )
    if cls_doc:
        html.append(
            f'<div style="background:#f1f8ff;border-left:3px solid #0366d6;'
            f'padding:6px 10px;margin:0 0 8px 0;font-size:12px;color:#24292e;'
            f'font-family:sans-serif;white-space:pre-wrap;">'
            f'<b>Class context:</b>\n{html_escape(cls_doc.strip())}</div>'
        )
    if func_doc:
        html.append(
            f'<div style="background:#f6f8fa;border-left:3px solid #28a745;'
            f'padding:6px 10px;margin:0 0 8px 0;font-size:12px;color:#24292e;'
            f'font-family:sans-serif;white-space:pre-wrap;">'
            f'<b>What this checks:</b>\n{html_escape(func_doc.strip())}</div>'
        )
    html.append(
        f'<pre style="background:#0d1117;color:#c9d1d9;padding:10px;'
        f'border-radius:4px;font-size:11px;line-height:1.4;'
        f'font-family:Consolas,Menlo,monospace;white-space:pre-wrap;'
        f'word-break:break-word;overflow-wrap:break-word;margin:0;">'
        f'{html_escape(src)}</pre>'
    )
    inner = "".join(html)
    return (
        f'<foreignObject x="{x0}" y="{y0}" width="{TEXT_W}" height="{BODY_H}">'
        f'<div xmlns="http://www.w3.org/1999/xhtml" '
        f'style="width:100%;height:100%;overflow:auto;'
        f'box-sizing:border-box;padding:0;">'
        f'{inner}'
        f'</div></foreignObject>'
    )


def render_test_svg(
    out_path: Path,
    test_file: str, cls_name: Optional[str], func_name: str,
    src: str, cls_doc: Optional[str], func_doc: Optional[str],
    graph: Optional[nx.Graph],
) -> None:
    x_graph, y_graph = 20, HEADER_H + 20
    x_text, y_text = TEXT_X, HEADER_H + 20
    qual = f"{cls_name}.{func_name}" if cls_name else func_name
    parts = [
        f'<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" version="1.1" '
        f'width="{CANVAS_W}" height="{CANVAS_H}" '
        f'viewBox="0 0 {CANVAS_W} {CANVAS_H}">',
        f'<rect width="{CANVAS_W}" height="{CANVAS_H}" fill="#ffffff"/>',
        # Header.
        f'<rect x="0" y="0" width="{CANVAS_W}" height="{HEADER_H}" fill="#f6f8fa"/>',
        f'<line x1="0" y1="{HEADER_H}" x2="{CANVAS_W}" y2="{HEADER_H}" '
        f'stroke="#e1e4e8" stroke-width="1"/>',
        f'<text x="20" y="32" font-family="sans-serif" font-size="18" '
        f'font-weight="600" fill="#24292e">{html_escape(qual)}</text>',
        f'<text x="{CANVAS_W - 20}" y="32" font-family="monospace" '
        f'font-size="12" fill="#6a737d" text-anchor="end">'
        f'tests/{test_file}.py</text>',
        # Panels.
        _graph_panel_svg(graph, x_graph, y_graph),
        _text_panel_svg(test_file, cls_name, func_name, src, cls_doc, func_doc,
                        x_text, y_text),
        # Footer.
        f'<line x1="0" y1="{CANVAS_H - FOOTER_H}" x2="{CANVAS_W}" y2="{CANVAS_H - FOOTER_H}" '
        f'stroke="#e1e4e8" stroke-width="1"/>',
        f'<text x="20" y="{CANVAS_H - 10}" font-family="sans-serif" '
        f'font-size="11" fill="#6a737d">'
        f'Graph on left (best-effort extraction); docstring + test code on right. '
        f'Regenerate via `python -m tests._manual_verification`.</text>',
        '</svg>',
    ]
    out_path.write_text("\n".join(parts), encoding="utf-8")


# ---------- index page ----------

def _write_index(all_tests) -> None:
    """Emit an index.html so the human can click through by module."""
    by_module: Dict[str, list] = {}
    for (mod, cls, fn, *_rest) in all_tests:
        by_module.setdefault(mod, []).append((cls, fn))
    html = ['<!DOCTYPE html>', '<html><head><meta charset="utf-8"/>',
            '<title>geg — manual test verification</title>',
            '<style>',
            'body{font-family:sans-serif;max-width:1000px;margin:30px auto;'
            'padding:0 20px;color:#24292e;}',
            'h1{border-bottom:2px solid #e1e4e8;padding-bottom:10px;}',
            'h2{margin-top:30px;border-bottom:1px solid #e1e4e8;'
            'padding-bottom:6px;font-size:18px;}',
            'ul{list-style:none;padding-left:0;}',
            'li{padding:2px 0;}',
            'a{color:#0366d6;text-decoration:none;font-family:monospace;'
            'font-size:13px;}',
            'a:hover{text-decoration:underline;}',
            '.cls{color:#6f42c1;margin-left:8px;}',
            '</style></head><body>',
            '<h1>geg — manual test verification</h1>',
            f'<p>One SVG per test across the <b>{len(all_tests)}</b> '
            f'collected tests. Click to open.</p>']
    for mod in sorted(by_module):
        html.append(f'<h2>{mod}</h2><ul>')
        for cls, fn in sorted(by_module[mod], key=lambda p: (p[0] or "", p[1])):
            label = f"{cls}.{fn}" if cls else fn
            filename = f"{cls}_{fn}.svg" if cls else f"{fn}.svg"
            html.append(
                f'<li><a href="{mod}/{filename}">{label}</a></li>'
            )
        html.append('</ul>')
    html.append('</body></html>')
    (OUT_DIR / "index.html").write_text("\n".join(html), encoding="utf-8")


# ---------- parametrised-test expansions ----------

def _emit_fixture_metric_cases(subdir: Path, src: str, cls_doc, func_doc) -> int:
    """`test_fixture_metric` is parametrised over 124+ (fixture, metric,
    expected) cases. Emit one SVG per case so the reviewer sees the
    actual graph and the specific expected value, not just the generic
    parametrised driver source."""
    from tests.fixtures._builder import all_fixtures
    count = 0
    for fx in all_fixtures().values():
        G = fx.build()
        for metric_name, expected in fx.expected.items():
            if expected is None:
                continue
            case_src = (
                f"# Parametrised case of test_fixture_metric:\n"
                f"# fixture: {fx.name}\n"
                f"# metric:  {metric_name}\n"
                f"# expected: {expected}\n"
                f"# tolerance: {fx.tol}\n"
                f"#\n"
                f"# Shared driver:\n{src}"
            )
            case_doc = (
                f"Case {fx.name} × {metric_name}:\n"
                f"  {metric_name}({fx.name}) should equal {expected} "
                f"(abs/rel tol = {fx.tol}).\n\n"
                f"Fixture description:\n  {fx.description}"
            )
            filename = f"test_fixture_metric__{fx.name}__{metric_name}.svg"
            out_path = subdir / filename
            render_test_svg(
                out_path,
                "test_fixtures", None, f"test_fixture_metric[{fx.name}.{metric_name}]",
                case_src, cls_doc, case_doc, G,
            )
            count += 1
    return count


def _emit_parametrized_fixture_tests(subdir: Path, func_name: str,
                                      src: str, cls_doc, func_doc,
                                      cls_name: Optional[str]) -> int:
    """For parametrised tests that iterate over fixture names (e.g.
    TestTVCGReproduction.test_line_only_fixtures_adaptive_matches_fixed_N),
    emit one SVG per fixture with the actual graph embedded."""
    # Look for @pytest.mark.parametrize("fx_name", [...])
    m = re.search(
        r'@pytest\.mark\.parametrize\(\s*["\'](fx_name|name)["\']\s*,\s*\[([^\]]+)\]',
        src,
    )
    if not m:
        return 0
    raw_items = m.group(2)
    fixture_names = re.findall(r'["\']([\w_]+)["\']', raw_items)
    if not fixture_names:
        return 0
    try:
        from tests.fixtures._builder import all_fixtures
        fixtures = all_fixtures()
    except ImportError:
        return 0
    count = 0
    for fx_name in fixture_names:
        if fx_name not in fixtures:
            continue
        G = fixtures[fx_name].build()
        case_src = f"# Parametrised case: fx_name = {fx_name!r}\n\n{src}"
        case_doc = (
            (func_doc.strip() + "\n\n") if func_doc else ""
        ) + f"Current fixture: {fx_name}"
        label = f"{cls_name}_{func_name}[{fx_name}]" if cls_name else f"{func_name}[{fx_name}]"
        filename = f"{label}.svg"
        out_path = subdir / filename
        render_test_svg(
            out_path,
            "test_paths" if cls_name and cls_name.startswith("TestTVCG") else subdir.name,
            cls_name, f"{func_name}[{fx_name}]",
            case_src, cls_doc, case_doc, G,
        )
        count += 1
    return count


# ---------- entry point ----------

def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)
    all_tests = []
    extracted, fallback, expanded = 0, 0, 0
    for info in _iter_tests():
        test_file, cls_name, func_name, src, _mod_doc, cls_doc, func_doc = info
        subdir = OUT_DIR / test_file
        subdir.mkdir(exist_ok=True)

        # Special-case parametrised tests that iterate over fixtures so
        # each case gets its own SVG with the actual graph.
        if test_file == "test_fixtures" and func_name == "test_fixture_metric":
            n = _emit_fixture_metric_cases(subdir, src, cls_doc, func_doc)
            expanded += n
            all_tests.append(info)  # keep one row in the index for the driver
            continue
        if "@pytest.mark.parametrize" in src and re.search(
            r'parametrize\(\s*["\'](fx_name|name)["\']', src,
        ):
            n = _emit_parametrized_fixture_tests(
                subdir, func_name, src, cls_doc, func_doc, cls_name,
            )
            if n > 0:
                expanded += n
                all_tests.append(info)
                continue
            # Fall through — parametrisation wasn't fixture-driven.

        filename = f"{cls_name}_{func_name}.svg" if cls_name else f"{func_name}.svg"
        out_path = subdir / filename
        graph = try_extract_graph(src)
        if graph is not None:
            extracted += 1
        else:
            fallback += 1
        render_test_svg(
            out_path,
            test_file, cls_name, func_name, src, cls_doc, func_doc, graph,
        )
        all_tests.append(info)
    _write_index(all_tests)
    total_svgs = extracted + fallback + expanded
    print(
        f"Wrote {total_svgs} SVGs ({len(all_tests)} test functions) to {OUT_DIR}:\n"
        f"  graph extracted inline:       {extracted}\n"
        f"  parametrised-case expansions: {expanded}\n"
        f"  text-only (no graph):         {fallback}\n"
        f"Open `manual_verification/index.html` to browse."
    )


if __name__ == "__main__":
    main()
