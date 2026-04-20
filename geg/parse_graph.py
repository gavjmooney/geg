"""Backcompat shim — kept so existing callers that do::

    from geg.parse_graph import read_graphml, write_graphml

still work. The real implementations live in `geg.io.graphml` as of the
Phase 5 refactor.
"""

from .io.graphml import (
    read_graphml,
    write_graphml,
    convert_gml_to_graphml,
    convert_graphml_to_gml,
)

__all__ = [
    "read_graphml",
    "write_graphml",
    "convert_gml_to_graphml",
    "convert_graphml_to_gml",
]
