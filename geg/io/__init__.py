"""I/O subpackage: readers, writers, and format converters.

Public entry points are re-exported from the top-level `geg` package, so
callers should continue to write:

    from geg import read_geg, write_geg, read_gml, write_gml, read_graphml, write_graphml
    from geg import convert, read_drawing, write_drawing
    from geg import gml_to_geg, graphml_to_geg

Internally this package is organised by format plus a shared
`convert` module that hosts every cross-format entry point.
"""

from .geg import (
    read_geg,
    write_geg,
    has_self_loops_file,
    is_multigraph_file,
)
from .gml import read_gml, write_gml
from .graphml import read_graphml, write_graphml
from .convert import (
    convert,
    read_drawing,
    write_drawing,
    gml_to_geg,
    graphml_to_geg,
    convert_gml_to_graphml,
    convert_graphml_to_gml,
)

__all__ = [
    # format readers / writers
    "read_geg",
    "write_geg",
    "has_self_loops_file",
    "is_multigraph_file",
    "read_gml",
    "write_gml",
    "read_graphml",
    "write_graphml",
    # format conversion
    "convert",
    "read_drawing",
    "write_drawing",
    "gml_to_geg",
    "graphml_to_geg",
    "convert_gml_to_graphml",
    "convert_graphml_to_gml",
]
