"""Generates the ER diagram from Base.metadata (backend/db/models.py); needs no database.

Usage (project root, .venv active):  python scripts/generate_erd.py
Writes docs/diagrams/er_model.svg (gitignored, never committed). Needs requirements.txt
(sqlalchemy-schemadisplay, pydot), Graphviz `dot`, optionally the IBM Plex Mono font."""
import os
import sys

from sqlalchemy import create_engine
from sqlalchemy_schemadisplay import create_schema_graph

# pylint: disable=wrong-import-position  # same sys.path reason as the noqa markers below
# pylint: disable=no-member  # pydot's Dot builds its set_*/write_* methods at runtime
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from backend.db.models import Base  # noqa: E402

OUTPUT_SVG = os.path.join(PROJECT_ROOT, "docs", "diagrams", "er_model.svg")

# --- Design tokens (blue ramp) -------------------------------------------
NAVY    = "#03253E"   # Blue 900 -> headers
BODY    = "#33454F"   # Body     -> attribute text
BLUE600 = "#325F7F"   # Blue 600 -> connections
BLUE700 = "#1F4A6B"   # Blue 700 -> table borders
PAPER   = "#F5F8FB"   # Blue 50  -> surface
FONT    = "IBM Plex Mono"


def main() -> None:
    """Renders docs/diagrams/er_model.svg from the ORM metadata (ADR 0030)."""
    os.makedirs(os.path.dirname(OUTPUT_SVG), exist_ok=True)

    engine = create_engine("sqlite://")  # empty -> only the Python models count

    graph = create_schema_graph(
        engine=engine,
        metadata=Base.metadata,
        show_datatypes=True,
        show_indexes=False,
        show_column_keys=True,   # mark PK/FK on the columns
        rankdir="TB",            # "LR" = left-to-right, if a wider layout is wanted
        concentrate=False,
        font=FONT,
        format_table_name={"color": NAVY, "bold": True},
    )

    # --- Tidy up the layout -----------------------------------------------
    graph.set_splines("ortho")   # orthogonal connections (blueprint look)
    graph.set_nodesep("0.55")    # horizontal spacing between tables
    graph.set_ranksep("0.85")    # vertical spacing between the levels
    graph.set_pad("0.4")         # margin around the diagram
    graph.set_bgcolor(PAPER)

    for node in graph.get_nodes():
        node.set_color(BLUE700)
        node.set_fontcolor(BODY)
    for edge in graph.get_edges():
        edge.set_headlabel("")   # drop the "+ column" labels (visual clutter)
        edge.set_taillabel("")
        edge.set_color(BLUE600)

    graph.write_svg(OUTPUT_SVG)
    print(f"ER diagram saved to {OUTPUT_SVG}")


if __name__ == "__main__":
    main()
