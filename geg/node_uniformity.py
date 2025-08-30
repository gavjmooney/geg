from . import geg_parser
import math
import networkx as nx
from typing import List, Tuple

def node_uniformity(G: nx.Graph) -> float:
    """
    Node placement uniformity in [0, 1] using a grid occupancy model.

    Partitions the drawing area into rows*cols cells where rows*cols >= N. The
    score is 1 minus the normalized L1 deviation of per-cell counts from the
    ideal mean N/(rows*cols). Degenerate single-point drawings return 1.0.

    Args:
        G: A NetworkX graph with node coordinates 'x' and 'y'.

    Returns:
        A float in [0, 1], where higher indicates more uniform distribution.
    """
    # Node points
    pts = [(data['x'], data['y']) for _, data in G.nodes(data=True)]
    N = len(pts)
    if N <= 1:
        return 1.0

    # Bounding box (includes curves)
    x_min, y_min, x_max, y_max = geg_parser.get_bounding_box(G)
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
