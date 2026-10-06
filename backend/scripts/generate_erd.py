"""Draw docs/diagrams/er_model.svg from the models (ADR 0030); needs Graphviz."""
import os

from sqlalchemy import create_engine
from sqlalchemy_schemadisplay import create_schema_graph

from shared.db.models import Base

# pylint: disable=no-member  # pydot's Dot builds its set_*/write_* methods at runtime
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUTPUT_SVG = os.path.join(PROJECT_ROOT, "docs", "diagrams", "er_model.svg")

NAVY    = "#03253E"   # Blue 900 -> headers
BODY    = "#33454F"   # Body     -> attribute text
BLUE600 = "#325F7F"   # Blue 600 -> connections
BLUE700 = "#1F4A6B"   # Blue 700 -> table borders
PAPER   = "#F5F8FB"   # Blue 50  -> surface
FONT    = "IBM Plex Mono"


def main() -> None:
    os.makedirs(os.path.dirname(OUTPUT_SVG), exist_ok=True)

    engine = create_engine("sqlite://")

    graph = create_schema_graph(
        engine=engine,
        metadata=Base.metadata,
        show_datatypes=True,
        show_indexes=False,
        show_column_keys=True,
        rankdir="TB",
        concentrate=False,
        font=FONT,
        format_table_name={"color": NAVY, "bold": True},
    )

    graph.set_splines("ortho")
    graph.set_nodesep("0.55")
    graph.set_ranksep("0.85")
    graph.set_pad("0.4")
    graph.set_bgcolor(PAPER)

    for node in graph.get_nodes():
        node.set_color(BLUE700)
        node.set_fontcolor(BODY)
    for edge in graph.get_edges():
        edge.set_headlabel("")
        edge.set_taillabel("")
        edge.set_color(BLUE600)

    graph.write_svg(OUTPUT_SVG)
    print(f"ER diagram saved to {OUTPUT_SVG}")


if __name__ == "__main__":
    main()
