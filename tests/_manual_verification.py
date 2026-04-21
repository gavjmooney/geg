"""Generate per-test manual-verification SVGs + a browseable HTML viewer.

Each test gets an SVG with the graph(s) it operates on rendered from the
test's actual code (executed in a sandboxed namespace), plus the test
docstring and source. A single `viewer.html` at the output-folder root
provides a sidebar / prev-next / keyboard-shortcut UI so a reviewer can
flick through all tests without losing context.

Not a pytest test itself — the leading underscore keeps pytest's
collection from picking this file up. Run from the package root:

    python -m tests._manual_verification

Output goes to `manual_verification/` (gitignored). Regenerate whenever
test expectations or bodies change.

## Graph extraction

The old regex approach was too fragile. The new approach runs each
test's body in a sandbox:
  - The sandbox inherits the test module's full namespace, so module-
    level helpers like `_layout` and `_straight` are available.
  - `self` is bound to an instance of the test's class (when the test
    is a method), so class helpers like `self._bezier_graph()` work.
  - Common pytest primitives (`pytest.approx`, `pytest.raises`,
    `pytest.mark.parametrize`) are stubbed so assertions and context
    managers don't abort the exec prematurely.
  - Fixture args (`tmp_path`, `monkeypatch`) are stubbed.
  - Any exception raised partway through is swallowed — we still
    capture whatever `nx.Graph` objects were built before the abort.

For tests that build several graphs (typical for invariance tests
— `G` and `G_rotated`, etc.), the SVG renders all of them in a
gallery so the reviewer sees both sides of the comparison.
"""

from __future__ import annotations

import ast
import importlib
import inspect
import math
import re
import sys
import tempfile
import textwrap
import traceback
from html import escape as html_escape
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

import networkx as nx


ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "manual_verification"
TESTS_DIR = ROOT / "tests"


# =====================================================================
# Pytest / fixture stubs for the sandboxed exec.
# =====================================================================


class _StubApprox:
    def __init__(self, *a, **kw):
        self.val = a[0] if a else None

    def __eq__(self, other): return True
    def __ne__(self, other): return False
    def __repr__(self): return f"approx({self.val!r})"


class _StubRaises:
    def __init__(self, *a, **kw): pass
    def __enter__(self): return self
    def __exit__(self, *a): return True  # swallow
    def __call__(self, *a, **kw): return self


class _StubMark:
    def __getattr__(self, name):
        # Any decorator access (pytest.mark.parametrize, .skip, etc.)
        # returns a no-op passthrough decorator.
        def passthrough(*a, **kw):
            def decorator(f): return f
            return decorator
        return passthrough


class _StubPytest:
    approx = _StubApprox
    raises = _StubRaises
    fixture = staticmethod(lambda *a, **kw: (lambda f: f))
    param = staticmethod(lambda *a, **kw: a)
    mark = _StubMark()

    class warns:
        def __init__(self, *a, **kw): pass
        def __enter__(self): return self
        def __exit__(self, *a): return True


class _StubSelf:
    """Fallback `self` for when we can't instantiate the test class.
    Every attribute access yields another stub, so chained helper
    lookups don't crash."""
    def __getattr__(self, name): return _StubSelf()
    def __call__(self, *a, **kw): return _StubSelf()


class _StubMonkeypatch:
    def setattr(self, *a, **kw): pass
    def setenv(self, *a, **kw): pass
    def delattr(self, *a, **kw): pass
    def delenv(self, *a, **kw): pass
    def chdir(self, *a, **kw): pass
    def syspath_prepend(self, *a, **kw): pass


# =====================================================================
# Test enumeration + sandboxed execution.
# =====================================================================


TestInfo = Tuple[str, Optional[str], str, str,
                 Optional[str], Optional[str], Optional[str]]
# (module_stem, class_name_or_None, func_name, source,
#  module_doc, class_doc, function_doc)


def _iter_tests() -> List[TestInfo]:
    """Collect every test function from tests/test_*.py (without running)."""
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    out: List[TestInfo] = []
    for test_file in sorted(TESTS_DIR.glob("test_*.py")):
        mod_name = f"tests.{test_file.stem}"
        try:
            mod = importlib.import_module(mod_name)
        except Exception as exc:
            print(f"  skip {mod_name}: {type(exc).__name__}: {exc}")
            continue
        for name, obj in inspect.getmembers(mod):
            if (
                name.startswith("Test")
                and inspect.isclass(obj)
                and getattr(obj, "__module__", None) == mod_name
            ):
                for mname, mobj in inspect.getmembers(obj):
                    if mname.startswith("test_") and inspect.isfunction(mobj):
                        out.append((
                            test_file.stem, name, mname, _safe_source(mobj),
                            mod.__doc__, obj.__doc__, mobj.__doc__,
                        ))
            elif (
                name.startswith("test_")
                and inspect.isfunction(obj)
                and getattr(obj, "__module__", None) == mod_name
            ):
                out.append((
                    test_file.stem, None, name, _safe_source(obj),
                    mod.__doc__, None, obj.__doc__,
                ))
    return out


def _safe_source(obj) -> str:
    try:
        return inspect.getsource(obj)
    except (OSError, TypeError):
        return "# (source unavailable)"


def _sandbox_namespace(test_file: str, cls_name: Optional[str]) -> Dict:
    """Build the execution namespace: test-module globals + pytest stubs
    + fixture stubs + a reasonable `self`."""
    mod = importlib.import_module(f"tests.{test_file}")
    ns: Dict = dict(vars(mod))
    ns["pytest"] = _StubPytest()
    # Stub `tmp_path` in the OS temp directory so the sandbox doesn't
    # leak files into the repo. Shared across all test execs — fine
    # since we only care about side-effects on nx.Graph objects, not
    # on disk state.
    tmp = Path(tempfile.gettempdir()) / "geg_manual_verification_sandbox"
    tmp.mkdir(exist_ok=True)
    ns["tmp_path"] = tmp
    ns["monkeypatch"] = _StubMonkeypatch()

    if cls_name:
        cls = getattr(mod, cls_name, None)
        if cls is not None:
            try:
                self_obj: object = cls()
            except Exception:
                self_obj = _StubSelf()
        else:
            self_obj = _StubSelf()
        ns["self"] = self_obj
    return ns


def _extract_func_body(src: str) -> Optional[ast.Module]:
    """Parse `src` and return an ast.Module containing just the test
    function's body statements — no decorators, no def line, no return
    type annotation. Subsequent `compile()` can turn this straight into
    bytecode.

    `inspect.getsource` on a class method preserves the class-level
    indent, which `ast.parse` rejects. Dedent first.
    """
    src = textwrap.dedent(src)
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return None
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            # Strip decorators; they may reference pytest.mark.parametrize
            # with data that isn't usefully executable in our sandbox.
            node.decorator_list = []
            return ast.Module(body=node.body, type_ignores=[])
    return None


def _exec_and_capture_graphs(
    test_file: str, cls_name: Optional[str], src: str,
) -> Tuple[List[Tuple[str, nx.Graph]], Optional[str]]:
    """Execute the test's body in a sandbox, returning any captured
    graphs and, if execution aborted, the exception name."""
    body = _extract_func_body(src)
    if body is None:
        return [], "parse failed"
    try:
        ns = _sandbox_namespace(test_file, cls_name)
    except Exception as exc:
        return [], f"{type(exc).__name__} (namespace): {exc}"

    pre_ids = {id(v) for v in ns.values()
               if isinstance(v, (nx.Graph, nx.DiGraph, nx.MultiGraph))}

    err: Optional[str] = None
    try:
        code = compile(body, f"<{test_file}:{cls_name}:exec>", "exec")
        exec(code, ns)
    except Exception as exc:
        err = f"{type(exc).__name__}: {exc}"

    graphs: List[Tuple[str, nx.Graph]] = []
    for name, val in ns.items():
        if name.startswith("__"):
            continue
        if isinstance(val, (nx.Graph, nx.DiGraph, nx.MultiGraph)):
            if id(val) in pre_ids:
                continue
            if val.number_of_nodes() == 0:
                continue
            graphs.append((name, val))
    return graphs, err


# =====================================================================
# Graph rendering.
# =====================================================================


def _ensure_coords(G: nx.Graph) -> None:
    """If nodes lack x/y attributes, compute a spring layout in place."""
    has_coords = all(
        "x" in a and "y" in a
        for _, a in G.nodes(data=True)
    )
    if has_coords or G.number_of_nodes() == 0:
        return
    try:
        pos = nx.spring_layout(G, seed=0)
    except Exception:
        pos = nx.circular_layout(G)
    for n, (x, y) in pos.items():
        G.nodes[n]["x"] = float(x) * 100.0
        G.nodes[n]["y"] = float(y) * 100.0


def _path_extent_samples(path_str: str) -> List[Tuple[float, float]]:
    """Return a set of (x, y) samples representing the extent of an SVG
    path. Includes polyline vertices plus coarsely-sampled points from
    each curved segment. Used to extend the rendering bbox so paths
    aren't clipped."""
    try:
        import svgpathtools as svgp
        p = svgp.parse_path(path_str)
    except Exception:
        return []
    pts: List[Tuple[float, float]] = []
    for seg in p:
        try:
            # Sample 10 points per segment; covers Q/C/S/T/A reasonably.
            for k in range(11):
                t = k / 10
                z = seg.point(t)
                pts.append((z.real, z.imag))
        except Exception:
            # Fall back to endpoints only.
            for attr in ("start", "end"):
                if hasattr(seg, attr):
                    z = getattr(seg, attr)
                    pts.append((z.real, z.imag))
    return pts


def _graph_bbox(G: nx.Graph) -> Tuple[float, float, float, float]:
    """Bbox (min_x, min_y, max_x, max_y) across both node positions AND
    any sampled geometry from edge path attrs. Ensures polyline bends /
    curved arcs that reach outside the node hull aren't clipped."""
    xs: List[float] = []
    ys: List[float] = []
    for _, a in G.nodes(data=True):
        xs.append(float(a["x"])); ys.append(float(a["y"]))
    for _, _, attrs in G.edges(data=True):
        path = attrs.get("path")
        if not path:
            continue
        for px, py in _path_extent_samples(path):
            xs.append(px); ys.append(py)
    if not xs:
        return 0.0, 0.0, 1.0, 1.0
    return min(xs), min(ys), max(xs), max(ys)


def _split_far_components(G: nx.Graph) -> Optional[List[Tuple[str, nx.Graph]]]:
    """If G's connected components are so far apart that rendering them
    at a single scale would compress each one into a dot, split into
    per-component subgraphs. Returns None if the components are already
    comparably-sized (or there's only one)."""
    # Undirected view for component analysis.
    try:
        if G.is_directed():
            components = list(nx.weakly_connected_components(G))
        else:
            components = list(nx.connected_components(G))
    except Exception:
        return None
    if len(components) < 2:
        return None

    def extent_of(nodes: set) -> float:
        xs = [float(G.nodes[n]["x"]) for n in nodes if "x" in G.nodes[n]]
        ys = [float(G.nodes[n]["y"]) for n in nodes if "y" in G.nodes[n]]
        if not xs:
            return 0.0
        return max(max(xs) - min(xs), max(ys) - min(ys))

    extents = [extent_of(c) for c in components]
    max_extent = max(extents)
    # Compute overall bbox extent to compare.
    full_xs, full_ys = [], []
    for _, a in G.nodes(data=True):
        full_xs.append(float(a["x"])); full_ys.append(float(a["y"]))
    overall = max(max(full_xs) - min(full_xs), max(full_ys) - min(full_ys), 1e-9)

    # Heuristic: if the biggest single component is less than 30% of the
    # overall extent, single-scale rendering loses too much local detail.
    if max_extent / overall > 0.3:
        return None

    # Split. Each sub-component gets a subgraph + its own label.
    subs: List[Tuple[str, nx.Graph]] = []
    for i, c in enumerate(components, start=1):
        Gi = G.subgraph(c).copy()
        subs.append((f"component {i}", Gi))
    return subs


def _render_self_loop(nx_: float, ny_: float, r_node: float) -> str:
    """Visible self-loop: a small circle tangent to the node, above-right."""
    r_loop = max(r_node * 2.0, 6.0)
    cx = nx_ + r_loop * 0.9
    cy = ny_ - r_loop * 0.9
    return (
        f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="{r_loop:.2f}" '
        f'fill="none" stroke="#24292e" stroke-width="1.5"/>'
    )


def _render_one_graph(G: nx.Graph, x0: float, y0: float, w: float, h: float,
                      label: Optional[str] = None) -> str:
    """Render a single graph into the given rectangle. Handles:
      - node bbox extended with path geometry (curves / polylines don't clip)
      - self-loops drawn as visible small circles
      - component auto-split when clusters would otherwise be dot-sized
    """
    _ensure_coords(G)
    parts: List[str] = [
        f'<rect x="{x0}" y="{y0}" width="{w}" height="{h}" '
        f'fill="#fafbfc" stroke="#e1e4e8" stroke-width="1"/>'
    ]
    if G.number_of_nodes() == 0:
        parts.append(
            f'<text x="{x0 + w / 2}" y="{y0 + h / 2}" '
            f'font-family="sans-serif" font-size="14" fill="#8b949e" '
            f'text-anchor="middle">(empty graph)</text>'
        )
        return "\n".join(parts)

    # Auto-split disconnected graphs whose components are far apart.
    sub = _split_far_components(G)
    if sub is not None:
        # Recurse into a sub-gallery within this panel; skip the normal
        # single-scale render to avoid the "dot cluster" problem.
        if label:
            parts.append(
                f'<text x="{x0 + 8}" y="{y0 + 16}" '
                f'font-family="monospace" font-size="12" fill="#0366d6" '
                f'font-weight="600">{html_escape(label)} '
                f'<tspan fill="#6a737d">({len(sub)} components)</tspan></text>'
            )
        inner_y = y0 + (24 if label else 8)
        inner_h = h - (24 if label else 8) - 8
        # Delegate to gallery layout for per-component sub-panels.
        parts.append(_render_gallery(sub, x0 + 4, inner_y,
                                     w - 8, inner_h))
        return "\n".join(parts)

    # Path-inclusive bbox.
    min_x, min_y, max_x, max_y = _graph_bbox(G)
    bbox_w = max(max_x - min_x, 1e-9)
    bbox_h = max(max_y - min_y, 1e-9)
    pad = max(bbox_w, bbox_h) * 0.10
    min_x -= pad; max_x += pad
    min_y -= pad; max_y += pad
    scale = min(w - 30, h - 30) / max(max_x - min_x, max_y - min_y, 1e-9)

    dx = (w - (max_x - min_x) * scale) / 2
    dy = (h - (max_y - min_y) * scale) / 2
    ox = x0 + dx - min_x * scale
    oy = y0 + dy - min_y * scale

    def tx(a: dict) -> Tuple[float, float]:
        return float(a["x"]) * scale + ox, float(a["y"]) * scale + oy

    if label:
        parts.append(
            f'<text x="{x0 + 8}" y="{y0 + 16}" '
            f'font-family="monospace" font-size="12" '
            f'fill="#0366d6" font-weight="600">{html_escape(label)}</text>'
        )

    # Edges.
    for u, v, attrs in G.edges(data=True):
        if u == v:
            # Defer — draw after we know the node's render position.
            continue
        path = attrs.get("path")
        if path:
            try:
                import svgpathtools as svgp
                p = svgp.parse_path(path)
                for seg in p:
                    for sattr in ("start", "control", "control1",
                                  "control2", "end"):
                        if hasattr(seg, sattr):
                            z = getattr(seg, sattr)
                            setattr(seg, sattr, complex(
                                z.real * scale + ox,
                                z.imag * scale + oy,
                            ))
                parts.append(
                    f'<path d="{p.d()}" fill="none" '
                    f'stroke="#24292e" stroke-width="1.5"/>'
                )
                continue
            except Exception:
                pass
        ux, uy = tx(G.nodes[u])
        vx, vy = tx(G.nodes[v])
        parts.append(
            f'<line x1="{ux:.2f}" y1="{uy:.2f}" '
            f'x2="{vx:.2f}" y2="{vy:.2f}" '
            f'stroke="#24292e" stroke-width="1.5"/>'
        )

    # Nodes with labels, and self-loops (drawn on top of the node).
    r = 5
    for n, a in G.nodes(data=True):
        nx_, ny_ = tx(a)
        # Any self-loop incident to this node?
        if G.has_edge(n, n):
            parts.append(_render_self_loop(nx_, ny_, r))
        parts.append(
            f'<circle cx="{nx_:.2f}" cy="{ny_:.2f}" r="{r}" '
            f'fill="#ffffff" stroke="#24292e" stroke-width="1.5"/>'
        )
        parts.append(
            f'<text x="{nx_:.2f}" y="{ny_ - r - 3:.2f}" '
            f'font-family="sans-serif" font-size="10" fill="#586069" '
            f'text-anchor="middle">{html_escape(str(n))}</text>'
        )

    # Footer: node/edge counts.
    nn, mm = G.number_of_nodes(), G.number_of_edges()
    parts.append(
        f'<text x="{x0 + w - 8}" y="{y0 + h - 8}" '
        f'font-family="monospace" font-size="10" fill="#6a737d" '
        f'text-anchor="end">'
        f'{nn} nodes · {mm} edges</text>'
    )
    return "\n".join(parts)


def _render_gallery(graphs: List[Tuple[str, nx.Graph]],
                    x0: float, y0: float,
                    total_w: float, total_h: float) -> str:
    """Arrange 1–4+ graphs in a grid inside the left panel."""
    if not graphs:
        return (
            f'<rect x="{x0}" y="{y0}" width="{total_w}" height="{total_h}" '
            f'fill="#fafbfc" stroke="#e1e4e8" stroke-width="1"/>'
            f'<text x="{x0 + total_w / 2}" y="{y0 + total_h / 2}" '
            f'font-family="sans-serif" font-size="14" fill="#8b949e" '
            f'text-anchor="middle">(no graph built by this test)</text>'
        )
    n = len(graphs)
    if n == 1:
        rows, cols = 1, 1
    elif n == 2:
        rows, cols = 1, 2
    elif n <= 4:
        rows, cols = 2, 2
    elif n <= 6:
        rows, cols = 2, 3
    else:
        rows, cols = 3, 3
    cell_w = total_w / cols
    cell_h = total_h / rows
    parts: List[str] = []
    for i, (name, G) in enumerate(graphs[: rows * cols]):
        r, c = divmod(i, cols)
        parts.append(_render_one_graph(
            G,
            x0 + c * cell_w + 4, y0 + r * cell_h + 4,
            cell_w - 8, cell_h - 8,
            label=name,
        ))
    if len(graphs) > rows * cols:
        parts.append(
            f'<text x="{x0 + total_w / 2}" y="{y0 + total_h - 4}" '
            f'font-family="sans-serif" font-size="10" fill="#6a737d" '
            f'text-anchor="middle">'
            f'(showing {rows * cols} of {len(graphs)} captured graphs)</text>'
        )
    return "\n".join(parts)


# =====================================================================
# Per-test SVG layout.
# =====================================================================


GRAPH_W = 560
GRAPH_H = 560
TEXT_X = GRAPH_W + 40
TEXT_W = 760
HEADER_H = 50
BODY_H = 720
FOOTER_H = 30
CANVAS_W = TEXT_X + TEXT_W + 40
CANVAS_H = HEADER_H + BODY_H + FOOTER_H


def _text_panel_foreign(qual: str, loc: str,
                        cls_doc: Optional[str], func_doc: Optional[str],
                        src: str, x0: int, y0: int,
                        exec_err: Optional[str]) -> str:
    html = [
        f'<h2 style="margin:0 0 6px 0;font-size:15px;color:#24292e;'
        f'font-family:sans-serif;">{html_escape(qual)}</h2>',
        f'<p style="margin:0 0 10px 0;font-size:11px;color:#6a737d;'
        f'font-family:monospace;">{html_escape(loc)}</p>',
    ]
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
    if exec_err:
        html.append(
            f'<div style="background:#fff5f5;border-left:3px solid #d73a49;'
            f'padding:6px 10px;margin:0 0 8px 0;font-size:11px;color:#86181d;'
            f'font-family:monospace;">'
            f'<b>Sandbox exec raised:</b> {html_escape(exec_err)}'
            f'<br/>Graphs captured before the error are still shown.</div>'
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
        f'style="width:100%;height:100%;overflow:auto;box-sizing:border-box;">'
        f'{inner}</div></foreignObject>'
    )


def _render_test_svg(
    out_path: Path,
    test_file: str, cls_name: Optional[str], func_name: str,
    src: str, cls_doc: Optional[str], func_doc: Optional[str],
    graphs: List[Tuple[str, nx.Graph]], exec_err: Optional[str],
) -> None:
    qual = f"{cls_name}.{func_name}" if cls_name else func_name
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" version="1.1" '
        f'width="{CANVAS_W}" height="{CANVAS_H}" '
        f'viewBox="0 0 {CANVAS_W} {CANVAS_H}">',
        f'<rect width="{CANVAS_W}" height="{CANVAS_H}" fill="#ffffff"/>',
        f'<rect x="0" y="0" width="{CANVAS_W}" height="{HEADER_H}" fill="#f6f8fa"/>',
        f'<line x1="0" y1="{HEADER_H}" x2="{CANVAS_W}" y2="{HEADER_H}" '
        f'stroke="#e1e4e8" stroke-width="1"/>',
        f'<text x="20" y="32" font-family="sans-serif" font-size="18" '
        f'font-weight="600" fill="#24292e">{html_escape(qual)}</text>',
        f'<text x="{CANVAS_W - 20}" y="32" font-family="monospace" '
        f'font-size="12" fill="#6a737d" text-anchor="end">'
        f'tests/{test_file}.py</text>',
        _render_gallery(graphs, 20, HEADER_H + 20, GRAPH_W, GRAPH_H),
        _text_panel_foreign(
            qual, f"tests/{test_file}.py::{qual}",
            cls_doc, func_doc, src, TEXT_X, HEADER_H + 20, exec_err,
        ),
        f'<line x1="0" y1="{CANVAS_H - FOOTER_H}" x2="{CANVAS_W}" '
        f'y2="{CANVAS_H - FOOTER_H}" stroke="#e1e4e8" stroke-width="1"/>',
        f'<text x="20" y="{CANVAS_H - 10}" font-family="sans-serif" '
        f'font-size="11" fill="#6a737d">'
        f'Graph(s) rendered from sandboxed exec of the test body. '
        f'Regenerate via `python -m tests._manual_verification`.</text>',
        '</svg>',
    ]
    out_path.write_text("\n".join(parts), encoding="utf-8")


# =====================================================================
# Browseable viewer.
# =====================================================================


REVIEW_FILE = OUT_DIR / "review.json"


def _load_review_state() -> Dict[str, Dict]:
    """Load the reviewer's verified/comment state from disk, if present.
    The file is the source of truth across regenerations — on gen, we
    embed its contents as the viewer's initial state, so the reviewer's
    annotations survive `python -m tests._manual_verification` reruns.
    """
    import json
    if not REVIEW_FILE.exists():
        return {}
    try:
        raw = REVIEW_FILE.read_text(encoding="utf-8")
        data = json.loads(raw)
        # Only keep keys that match current entries schema.
        return {
            k: {
                "verified": bool(v.get("verified", False)),
                "comment": str(v.get("comment", "")),
            }
            for k, v in data.items()
            if isinstance(v, dict)
        }
    except (OSError, ValueError):
        return {}


def _write_viewer(entries: List[Dict]) -> None:
    """Single-page HTML viewer: sidebar, SVG frame, per-test review pane
    (verified checkbox + comment textarea), filter dropdown, import/export,
    prev-next navigation with keyboard shortcuts."""
    import json

    manifest = json.dumps(entries, ensure_ascii=False)
    initial_review = json.dumps(_load_review_state(), ensure_ascii=False)

    # Escape `</script>` in JSON embed to prevent premature termination.
    manifest_safe = manifest.replace("</", "<\\/")
    initial_review_safe = initial_review.replace("</", "<\\/")

    html = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<title>geg — manual test verification</title>
<style>
  * { box-sizing: border-box; }
  html, body { margin: 0; padding: 0; height: 100%; overflow: hidden;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
                 Oxygen, Ubuntu, Cantarell, sans-serif; color: #24292e; }
  #app { display: flex; height: 100vh; }
  #sidebar {
    width: 360px; flex: 0 0 360px; background: #fafbfc;
    border-right: 1px solid #e1e4e8; overflow-y: auto;
    font-size: 13px;
  }
  #sidebar header {
    padding: 14px 16px; border-bottom: 1px solid #e1e4e8;
    background: #ffffff; position: sticky; top: 0; z-index: 1;
  }
  #sidebar h1 { margin: 0; font-size: 15px; font-weight: 600; }
  #sidebar .meta { margin-top: 4px; color: #6a737d; font-size: 11px;
                   font-family: monospace; }
  #filter {
    width: 100%; margin-top: 8px; padding: 6px 8px;
    border: 1px solid #d1d5da; border-radius: 3px; font-size: 12px;
    font-family: inherit;
  }
  #statusFilter {
    width: 100%; margin-top: 6px; padding: 4px 6px;
    border: 1px solid #d1d5da; border-radius: 3px; font-size: 12px;
    background: #ffffff;
  }
  #reviewProgress {
    margin-top: 8px; padding: 4px 8px; background: #f1f8ff;
    border-radius: 3px; font-family: monospace; font-size: 11px;
    color: #0366d6;
  }
  #sidebar .module {
    font-weight: 600; color: #24292e; padding: 10px 16px 4px;
    font-size: 11px; text-transform: uppercase; letter-spacing: 0.04em;
    color: #6a737d;
  }
  #sidebar .cls {
    padding: 4px 16px 4px 22px; font-size: 11px; color: #6f42c1;
    font-family: monospace; text-transform: none;
  }
  #sidebar a {
    display: flex; align-items: center; gap: 6px;
    padding: 3px 16px 3px 28px;
    color: #0366d6; text-decoration: none; font-family: monospace;
    font-size: 12px; border-left: 3px solid transparent;
  }
  #sidebar a .label { flex: 1 1 auto; overflow: hidden;
                      text-overflow: ellipsis; white-space: nowrap; }
  #sidebar a .indicator { flex: 0 0 auto; font-size: 11px; color: #6a737d; }
  #sidebar a.no-graph .label { color: #959da5; }
  #sidebar a:hover { background: #eef2f6; }
  #sidebar a.active {
    background: #eef2f6; border-left-color: #0366d6;
    color: #0366d6; font-weight: 600;
  }
  #sidebar a.verified .indicator.check { color: #28a745; }
  #sidebar a.commented .indicator.comment { color: #f6a100; }
  #main { flex: 1 1 auto; display: flex; flex-direction: column; min-width: 0; }
  #toolbar {
    display: flex; align-items: center; gap: 10px; flex-wrap: wrap;
    padding: 8px 16px; background: #f6f8fa;
    border-bottom: 1px solid #e1e4e8; font-size: 13px;
  }
  #toolbar button {
    background: #ffffff; border: 1px solid #d1d5da; border-radius: 3px;
    padding: 4px 10px; cursor: pointer; font-family: inherit;
    font-size: 12px; color: #24292e;
  }
  #toolbar button:hover { background: #eaecef; }
  #toolbar button:disabled { color: #959da5; cursor: not-allowed; }
  #toolbar .hint { color: #6a737d; font-size: 11px; }
  #toolbar .pos { margin-left: auto; color: #6a737d; font-family: monospace; }
  #toolbar .sep { width: 1px; background: #e1e4e8; align-self: stretch; }
  #viewer {
    flex: 1 1 auto; overflow: auto; padding: 18px 18px 6px 18px;
    background: #eef2f6;
    display: flex; justify-content: center; align-items: flex-start;
  }
  #viewer object {
    background: #ffffff; border: 1px solid #d1d5da; border-radius: 3px;
    box-shadow: 0 1px 3px rgba(27,31,35,0.06);
    max-width: 100%;
  }
  #reviewPane {
    flex: 0 0 auto; padding: 10px 18px 14px 18px;
    background: #ffffff; border-top: 1px solid #e1e4e8;
  }
  #reviewPane .row1 {
    display: flex; align-items: center; gap: 14px; margin-bottom: 6px;
  }
  #reviewPane label.verif {
    display: flex; align-items: center; gap: 6px; cursor: pointer;
    font-size: 13px; font-weight: 600;
  }
  #reviewPane input[type="checkbox"] {
    width: 18px; height: 18px; cursor: pointer;
  }
  #reviewPane #saveStatus {
    color: #6a737d; font-size: 11px; font-family: monospace;
  }
  #reviewPane textarea {
    width: 100%; min-height: 48px; max-height: 120px; resize: vertical;
    padding: 6px 8px; border: 1px solid #d1d5da; border-radius: 3px;
    font-family: Consolas, Menlo, monospace; font-size: 12px;
    line-height: 1.4; color: #24292e;
  }
  kbd {
    display: inline-block; padding: 1px 5px; font-size: 10px;
    font-family: monospace; background: #f6f8fa; border: 1px solid #d1d5da;
    border-radius: 3px; color: #24292e;
  }
  input[type="file"] { display: none; }
</style>
</head>
<body>
<div id="app">
  <nav id="sidebar">
    <header>
      <h1>manual test verification</h1>
      <div class="meta" id="count"></div>
      <input id="filter" type="text" placeholder="filter tests (regex)…" autocomplete="off"/>
      <select id="statusFilter">
        <option value="all">Show: all tests</option>
        <option value="unverified">Show: unverified only</option>
        <option value="verified">Show: verified only</option>
        <option value="commented">Show: with comments</option>
      </select>
      <div id="reviewProgress"></div>
    </header>
    <div id="list"></div>
  </nav>
  <section id="main">
    <div id="toolbar">
      <button id="prev">◀ Prev</button>
      <button id="next">Next ▶</button>
      <span class="sep"></span>
      <button id="exportBtn" title="Download review.json — place in manual_verification/ to persist across regenerations">⬇ Export review.json</button>
      <button id="importBtn" title="Load review state from a JSON file">⬆ Import…</button>
      <input id="importFile" type="file" accept=".json"/>
      <span class="sep"></span>
      <span class="hint">
        <kbd>←</kbd>/<kbd>→</kbd> nav &nbsp; <kbd>v</kbd> toggle verified &nbsp; <kbd>c</kbd> focus comment &nbsp; <kbd>/</kbd> filter
      </span>
      <span class="pos" id="pos"></span>
    </div>
    <div id="viewer">
      <object id="frame" type="image/svg+xml" width="1400" height="800"></object>
    </div>
    <div id="reviewPane">
      <div class="row1">
        <label class="verif">
          <input id="verifiedBox" type="checkbox"/>
          <span>Verified</span>
        </label>
        <span id="saveStatus">&nbsp;</span>
      </div>
      <textarea id="commentBox" placeholder="Comments, TODOs, questions for the author — saved automatically (browser) and to review.json via Export."></textarea>
    </div>
  </section>
</div>
<script>
const ENTRIES = __MANIFEST__;
const INITIAL_REVIEW = __INITIAL_REVIEW__;
const LS_KEY = "geg_manual_verification_review_v1";

// --- Review state -------------------------------------------------------
// Shape: { [key]: { verified: bool, comment: string } }
// Merged on load: localStorage (most recent in-browser edits) overrides
// the at-gen-time snapshot from review.json, so no one-way data loss when
// regeneration rebuilds the viewer from a stale review.json.

function loadReviewState() {
  const embedded = INITIAL_REVIEW || {};
  let local = {};
  try {
    const raw = localStorage.getItem(LS_KEY);
    if (raw) local = JSON.parse(raw);
  } catch (e) { /* ignore parse errors */ }
  const merged = Object.assign({}, embedded, local);
  return merged;
}
function saveReviewState(state) {
  try { localStorage.setItem(LS_KEY, JSON.stringify(state)); }
  catch (e) { /* quota exceeded — rare, tolerable */ }
}
function getRecord(key) {
  if (!review[key]) review[key] = { verified: false, comment: "" };
  return review[key];
}
function hasAnnotation(key) {
  const r = review[key];
  return r && (r.verified || (r.comment && r.comment.trim().length > 0));
}

let review = loadReviewState();

// --- DOM refs -----------------------------------------------------------
const list = document.getElementById("list");
const filter = document.getElementById("filter");
const statusFilter = document.getElementById("statusFilter");
const frame = document.getElementById("frame");
const prevBtn = document.getElementById("prev");
const nextBtn = document.getElementById("next");
const pos = document.getElementById("pos");
const count = document.getElementById("count");
const progress = document.getElementById("reviewProgress");
const verifiedBox = document.getElementById("verifiedBox");
const commentBox = document.getElementById("commentBox");
const saveStatus = document.getElementById("saveStatus");
const exportBtn = document.getElementById("exportBtn");
const importBtn = document.getElementById("importBtn");
const importFile = document.getElementById("importFile");

count.textContent = ENTRIES.length + " tests · " +
  ENTRIES.filter(e => e.has_graph).length + " with graphs";

let filtered = ENTRIES.slice();
let cursor = 0;

// --- Rendering ----------------------------------------------------------
function applyFilters() {
  const q = filter.value.trim();
  let re = null;
  if (q) {
    try { re = new RegExp(q, "i"); }
    catch { re = new RegExp(q.replace(/[.*+?^${}()|[\\]\\\\]/g, "\\\\$&"), "i"); }
  }
  const status = statusFilter.value;
  filtered = ENTRIES.filter(e => {
    if (re && !(re.test(e.func) || re.test(e.cls || "") || re.test(e.module))) {
      return false;
    }
    const r = review[e.key] || {};
    if (status === "verified" && !r.verified) return false;
    if (status === "unverified" && r.verified) return false;
    if (status === "commented" && !(r.comment && r.comment.trim())) return false;
    return true;
  });
  if (cursor >= filtered.length) cursor = Math.max(0, filtered.length - 1);
  render();
}

function render() {
  list.innerHTML = "";
  let lastModule = null;
  let lastClass = null;
  filtered.forEach((e, i) => {
    if (e.module !== lastModule) {
      const h = document.createElement("div");
      h.className = "module";
      h.textContent = e.module;
      list.appendChild(h);
      lastModule = e.module;
      lastClass = null;
    }
    if (e.cls && e.cls !== lastClass) {
      const h = document.createElement("div");
      h.className = "cls";
      h.textContent = e.cls;
      list.appendChild(h);
      lastClass = e.cls;
    }
    const a = document.createElement("a");
    a.href = "#" + e.key;
    const labelSpan = document.createElement("span");
    labelSpan.className = "label";
    labelSpan.textContent = e.func;
    a.appendChild(labelSpan);
    const indicator = document.createElement("span");
    indicator.className = "indicator";
    const r = review[e.key] || {};
    let indicatorText = "";
    if (r.verified) {
      indicatorText += "✓";
      a.classList.add("verified");
    }
    if (r.comment && r.comment.trim()) {
      indicatorText += (indicatorText ? " " : "") + "💬";
      a.classList.add("commented");
    }
    indicator.textContent = indicatorText;
    a.appendChild(indicator);
    if (!e.has_graph) a.classList.add("no-graph");
    a.dataset.idx = i;
    a.addEventListener("click", (ev) => {
      ev.preventDefault();
      go(i);
    });
    list.appendChild(a);
  });
  updateProgress();
  show();
}

function updateProgress() {
  const total = ENTRIES.length;
  const verified = ENTRIES.filter(e => (review[e.key] || {}).verified).length;
  const commented = ENTRIES.filter(e => {
    const r = review[e.key] || {};
    return r.comment && r.comment.trim();
  }).length;
  const pct = total ? Math.round(100 * verified / total) : 0;
  progress.textContent =
    `${verified}/${total} verified (${pct}%) · ${commented} with comments`;
}

function show() {
  filtered.forEach((_, i) => {
    const a = document.querySelector(`#list a[data-idx="${i}"]`);
    if (a) a.classList.toggle("active", i === cursor);
  });
  const active = filtered[cursor];
  if (!active) {
    frame.data = "";
    verifiedBox.checked = false;
    commentBox.value = "";
    pos.textContent = "0 / 0";
    prevBtn.disabled = nextBtn.disabled = true;
    return;
  }
  frame.data = active.path;
  history.replaceState(null, "", "#" + active.key);
  pos.textContent = (cursor + 1) + " / " + filtered.length;
  prevBtn.disabled = cursor === 0;
  nextBtn.disabled = cursor === filtered.length - 1;
  const activeElem = document.querySelector(`#list a.active`);
  if (activeElem) activeElem.scrollIntoView({ block: "nearest" });
  // Populate review panel for the current test.
  const r = getRecord(active.key);
  verifiedBox.checked = !!r.verified;
  commentBox.value = r.comment || "";
  saveStatus.textContent = "";
}

function go(i) {
  cursor = Math.max(0, Math.min(filtered.length - 1, i));
  show();
}

// --- Review-state mutation ---------------------------------------------
function flashSaved() {
  saveStatus.textContent = "saved ✓";
  setTimeout(() => { saveStatus.textContent = ""; }, 1200);
}

function touchCurrent(mutate) {
  const active = filtered[cursor];
  if (!active) return;
  const r = getRecord(active.key);
  mutate(r);
  // Clean up: if both empty, drop the record so review.json stays small.
  if (!r.verified && !(r.comment && r.comment.trim())) {
    delete review[active.key];
  }
  saveReviewState(review);
  // Update sidebar indicator for this entry without re-rendering all.
  const elem = document.querySelector(`#list a[data-idx="${cursor}"]`);
  if (elem) {
    const rec = review[active.key] || {};
    elem.classList.toggle("verified", !!rec.verified);
    elem.classList.toggle("commented", !!(rec.comment && rec.comment.trim()));
    const ind = elem.querySelector(".indicator");
    let t = "";
    if (rec.verified) t += "✓";
    if (rec.comment && rec.comment.trim()) t += (t ? " " : "") + "💬";
    ind.textContent = t;
  }
  updateProgress();
  flashSaved();
}

verifiedBox.addEventListener("change", () => {
  touchCurrent(r => { r.verified = verifiedBox.checked; });
});

let commentTimer = null;
commentBox.addEventListener("input", () => {
  saveStatus.textContent = "saving…";
  clearTimeout(commentTimer);
  commentTimer = setTimeout(() => {
    touchCurrent(r => { r.comment = commentBox.value; });
  }, 400);
});

// --- Import / export ----------------------------------------------------
exportBtn.addEventListener("click", () => {
  // Strip empty entries for a tidy file.
  const out = {};
  for (const [k, v] of Object.entries(review)) {
    if (v.verified || (v.comment && v.comment.trim())) out[k] = v;
  }
  const blob = new Blob([JSON.stringify(out, null, 2)], {type: "application/json"});
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "review.json";
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
});

importBtn.addEventListener("click", () => importFile.click());
importFile.addEventListener("change", async (ev) => {
  const file = ev.target.files[0];
  if (!file) return;
  try {
    const text = await file.text();
    const data = JSON.parse(text);
    // Merge (import does not wipe local state; user can re-export to drop).
    for (const [k, v] of Object.entries(data)) {
      if (typeof v === "object" && v !== null) {
        review[k] = {
          verified: !!v.verified,
          comment: String(v.comment || ""),
        };
      }
    }
    saveReviewState(review);
    applyFilters();
    alert("Imported review state from " + file.name);
  } catch (e) {
    alert("Failed to import: " + e.message);
  }
  importFile.value = "";
});

// --- Navigation + keyboard ---------------------------------------------
prevBtn.addEventListener("click", () => go(cursor - 1));
nextBtn.addEventListener("click", () => go(cursor + 1));

document.addEventListener("keydown", (ev) => {
  // Never hijack keys when typing in a form control.
  const active = document.activeElement;
  const typing = active === filter || active === commentBox ||
                 active === statusFilter;
  if (typing) {
    if (ev.key === "Escape") active.blur();
    return;
  }
  if (ev.key === "ArrowLeft")  { ev.preventDefault(); go(cursor - 1); }
  if (ev.key === "ArrowRight") { ev.preventDefault(); go(cursor + 1); }
  if (ev.key === "/")          { ev.preventDefault(); filter.focus(); filter.select(); }
  if (ev.key === "v" || ev.key === "V") {
    ev.preventDefault();
    verifiedBox.checked = !verifiedBox.checked;
    verifiedBox.dispatchEvent(new Event("change"));
  }
  if (ev.key === "c" || ev.key === "C") {
    ev.preventDefault();
    commentBox.focus();
  }
});

filter.addEventListener("input", applyFilters);
statusFilter.addEventListener("change", applyFilters);

// Restore from URL hash on load.
const initialHash = decodeURIComponent(location.hash.replace(/^#/, ""));
if (initialHash) {
  const i = ENTRIES.findIndex(e => e.key === initialHash);
  if (i >= 0) cursor = i;
}
render();
</script>
</body>
</html>
"""
    html = html.replace("__MANIFEST__", manifest_safe)
    html = html.replace("__INITIAL_REVIEW__", initial_review_safe)
    (OUT_DIR / "viewer.html").write_text(html, encoding="utf-8")


# =====================================================================
# Parametrised-test expansions.
# =====================================================================


def _emit_fixture_metric_cases(subdir: Path, src: str) -> List[Dict]:
    """`test_fixture_metric` is parametrised over ~130 (fixture, metric,
    expected) tuples. Emit one SVG per case so the reviewer sees the
    actual graph and expected value, not just the driver loop."""
    from tests.fixtures._builder import all_fixtures
    entries: List[Dict] = []
    for fx in all_fixtures().values():
        G = fx.build()
        for metric_name, expected in fx.expected.items():
            if expected is None:
                continue
            case_src = (
                f"# Parametrised case of test_fixture_metric:\n"
                f"#   fixture  = {fx.name}\n"
                f"#   metric   = {metric_name}\n"
                f"#   expected = {expected}\n"
                f"#   tolerance = {fx.tol}\n\n"
                f"# Shared driver body:\n"
                f"{src}"
            )
            case_doc = (
                f"Case {fx.name} × {metric_name}.\n\n"
                f"Asserts: {metric_name}({fx.name}) == {expected} "
                f"(abs/rel tol = {fx.tol}).\n\n"
                f"Fixture description:\n  {fx.description}"
            )
            filename = f"test_fixture_metric__{fx.name}__{metric_name}.svg"
            out_path = subdir / filename
            _render_test_svg(
                out_path,
                "test_fixtures", None,
                f"test_fixture_metric[{fx.name}.{metric_name}]",
                case_src, None, case_doc,
                [(fx.name, G)], None,
            )
            entries.append({
                "module": "test_fixtures",
                "cls": None,
                "func": f"test_fixture_metric[{fx.name}.{metric_name}]",
                "key": f"test_fixtures/test_fixture_metric__{fx.name}__{metric_name}",
                "path": f"test_fixtures/{filename}",
                "has_graph": True,
            })
    return entries


def _parametrised_fixture_names(src: str) -> List[str]:
    """Return fixture names if the test is parametrised over `fx_name`
    or similar; else empty list."""
    m = re.search(
        r'@pytest\.mark\.parametrize\(\s*["\'](fx_name|name|fixture_name)["\']'
        r'\s*,\s*\[([^\]]+)\]',
        src,
    )
    if not m:
        return []
    items = m.group(2)
    return re.findall(r'["\']([\w_]+)["\']', items)


def _emit_parametrised_fixture_cases(
    subdir: Path, test_file: str, cls_name: Optional[str], func_name: str,
    src: str, cls_doc: Optional[str], func_doc: Optional[str],
    fixture_names: List[str],
) -> List[Dict]:
    """For parametrised tests keyed by fixture name, one SVG per fixture."""
    try:
        from tests.fixtures._builder import all_fixtures
        fixtures = all_fixtures()
    except ImportError:
        return []
    entries: List[Dict] = []
    for fx_name in fixture_names:
        if fx_name not in fixtures:
            continue
        G = fixtures[fx_name].build()
        case_src = f"# Parametrised case: fx_name = {fx_name!r}\n\n{src}"
        extended_doc = (
            (func_doc.strip() + "\n\n") if func_doc else ""
        ) + f"Current fixture: {fx_name}"
        label_base = f"{cls_name}_{func_name}" if cls_name else func_name
        filename = f"{label_base}__{fx_name}.svg"
        out_path = subdir / filename
        _render_test_svg(
            out_path, test_file, cls_name,
            f"{func_name}[{fx_name}]",
            case_src, cls_doc, extended_doc,
            [(fx_name, G)], None,
        )
        qual = f"{cls_name}.{func_name}[{fx_name}]" if cls_name else f"{func_name}[{fx_name}]"
        entries.append({
            "module": test_file,
            "cls": cls_name,
            "func": f"{func_name}[{fx_name}]",
            "key": f"{test_file}/{label_base}__{fx_name}",
            "path": f"{test_file}/{filename}",
            "has_graph": True,
        })
    return entries


# =====================================================================
# Entry point.
# =====================================================================


def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)
    entries: List[Dict] = []
    n_graphs_extracted = 0
    n_text_only = 0
    n_parametrised = 0

    for info in _iter_tests():
        test_file, cls_name, func_name, src, _mod_doc, cls_doc, func_doc = info
        subdir = OUT_DIR / test_file
        subdir.mkdir(exist_ok=True)

        # Special case: test_fixtures.test_fixture_metric → ~130 cases.
        if test_file == "test_fixtures" and func_name == "test_fixture_metric":
            expanded = _emit_fixture_metric_cases(subdir, src)
            entries.extend(expanded)
            n_parametrised += len(expanded)
            continue

        # Parametrised over a fixture-name list?
        fixture_names = _parametrised_fixture_names(src)
        if fixture_names:
            expanded = _emit_parametrised_fixture_cases(
                subdir, test_file, cls_name, func_name,
                src, cls_doc, func_doc, fixture_names,
            )
            if expanded:
                entries.extend(expanded)
                n_parametrised += len(expanded)
                continue

        # Default: sandboxed exec to capture graphs.
        graphs, err = _exec_and_capture_graphs(test_file, cls_name, src)
        if graphs:
            n_graphs_extracted += 1
        else:
            n_text_only += 1

        filename = f"{cls_name}_{func_name}.svg" if cls_name else f"{func_name}.svg"
        out_path = subdir / filename
        _render_test_svg(
            out_path, test_file, cls_name, func_name,
            src, cls_doc, func_doc, graphs, err,
        )
        qual = f"{cls_name}.{func_name}" if cls_name else func_name
        entries.append({
            "module": test_file,
            "cls": cls_name,
            "func": func_name,
            "key": f"{test_file}/{(cls_name + '_' + func_name) if cls_name else func_name}",
            "path": f"{test_file}/{filename}",
            "has_graph": bool(graphs),
        })

    _write_viewer(entries)
    total = len(entries)
    print(
        f"Wrote {total} SVGs + viewer.html to {OUT_DIR}:\n"
        f"  graph captured via sandbox exec: {n_graphs_extracted}\n"
        f"  parametrised-case expansions:    {n_parametrised}\n"
        f"  text-only (no graph built):      {n_text_only}\n"
        f"Open `{OUT_DIR / 'viewer.html'}` to browse."
    )


if __name__ == "__main__":
    main()
