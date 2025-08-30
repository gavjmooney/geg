# GEG Encodes Graphs

GEG Encodes Graphs is a JSON based storage format for encoding graph drawings which contain complex edge geometries using SVG path commands. GEG enables readability metric calculations on drawings containing curved/polygonal edges. 

This package contains code for reading/writing GEG files, converting to/from other common formats, and several readability metric implementations.

## Installation
Install from PyPI (distribution name is `geg-metrics`):

```bash
pip install geg-metrics
```

Then import as:

```python
import geg
```

## Usage

### Read a GEG file and compute a metric
```python
import geg

G = geg.read_geg("example.geg")
print("Aspect ratio:", geg.aspect_ratio(G))
```

### Convert GraphML to GEG and compute metrics
```python
import geg

# Read GraphML into an internal graph, convert to a GEG-like NetworkX graph
G = geg.graphml_to_geg("example.graphml")

# Optionally write out a .geg file
geg.write_geg(G, "example_converted.geg")

# Compute metrics
print("Aspect ratio:", geg.aspect_ratio(G))
print("Angular resolution (avg):", geg.angular_resolution_avg_angle(G))
print("Edge length deviation:", geg.edge_length_deviation(G))
```

### Render to SVG
```python
import geg

G = geg.read_geg("example.geg")
geg.to_svg(G, "example.svg", margin=50)
```

### Notes
- Install name on PyPI is `geg-metrics`, but the import is `import geg`.
- Most metrics expect node coordinates (`x`, `y`) and edge paths (`path`) to be present.

### For more information, see the following publication:
G. J. Mooney, T. Hegemann, A. Wolff, M. Wybrow, and H. Purchase, "Universal Quality Metrics for Graph Drawings: Which Graphs Excite Us Most?," in Graph Drawing and Network Visualization (GD 2025), 2025.