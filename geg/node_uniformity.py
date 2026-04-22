from . import geg_parser
import math
import networkx as nx
from typing import Optional, Tuple

def node_uniformity(
    G: nx.Graph,
    *,
    bbox: Optional[Tuple[float, float, float, float]] = None,
    include_curves: bool = False,
) -> float:
    """
    Node placement uniformity in [0, 1] using a grid occupancy model.

    Partitions the drawing area into rows*cols cells where rows*cols >= N. The
    score is 1 minus the normalized L1 deviation of per-cell counts from the
    ideal mean N/(rows*cols). Degenerate single-point drawings return 1.0.

    The grid defaults to the **node-position bounding box only** — curves
    bulging outside the node hull do not stretch the grid. This treats NU
    as a statement about how evenly the nodes themselves are distributed,
    regardless of curve geometry. Set `include_curves=True` to use the full
    curve-promoted drawing bounding box instead, which penalises layouts
    whose nodes cluster in one corner of a drawing while edge curves span
    the full canvas.

    Args:
        G: A NetworkX graph with node coordinates 'x' and 'y'.
        bbox: Optional pre-computed (min_x, min_y, max_x, max_y). If None,
            computed via `geg_parser.get_bounding_box(G, promote=include_curves)`.
            A caller-supplied `bbox` always wins over `include_curves`.
        include_curves: When True and no `bbox` is supplied, use the
            curve-promoted drawing bbox so that edge curves extending beyond
            the node hull expand the grid's extent. Default False.

    Returns:
        A float in [0, 1], where higher indicates more uniform distribution.
    """
    # Node points
    pts = [(data['x'], data['y']) for _, data in G.nodes(data=True)]
    N = len(pts)
    if N <= 1:
        return 1.0

    if bbox is None:
        bbox = geg_parser.get_bounding_box(G, promote=include_curves)
    x_min, y_min, x_max, y_max = bbox
    width, height = x_max - x_min, y_max - y_min

    # If all nodes are on top of each other
    if width == 0 and height == 0:
        return 1.0

    # Select rows and cols so rows * cols >= N
    rows = max(1, int(math.floor(math.sqrt(N))))
    cols = int(math.ceil(N / rows))

    # Collapse to 1D axis if one dimension has zero length
    if width == 0:
        cols = 1
        rows = N
    if height == 0:
        rows = 1
        cols = N

    # Compute size of cells
    cell_w = width  / cols if width  > 0 else 1.0
    cell_h = height / rows if height > 0 else 1.0

    # Create cells to count nodes, initially 0
    grid = [[0]*cols for _ in range(rows)]
    for x,y in pts:
        c = int((x - x_min) / cell_w) if width  > 0 else 0
        r = int((y - y_min) / cell_h) if height > 0 else 0
        # Incase points lie on right boundary
        if c >= cols:
            c = cols - 1
        if r >= rows: 
            r = rows - 1
        grid[r][c] += 1

    # Sum absolute deviations
    T = rows * cols # total cells
    mean = N / T # ideal number of nodes per cell
    D = sum(abs(count - mean) for row in grid for count in row)

    # Worst‐case: all nodes in one cell, zero in the others
    D_max = 2 * N * (T - 1) / T

    return 1 - (D / D_max)
