"""
Generiert das ER-Diagramm AUS den SQLAlchemy-Modellen (backend/db/models.py).

Single Source of Truth: aus Base.metadata abgeleitet, kann nie vom echten
Schema abweichen. Benoetigt KEINE laufende DB (leere In-Memory-SQLite).

Optik nach Design-System (Blue-Ramp): Navy traegt Header, Mid-Blue die
Verbindungen, Paper die Flaeche, IBM Plex Mono fuer "Labels & Daten".
PK/FK an den Spalten markiert; Layout rechtwinklig und luftig (Clear by default).

Aufruf (Projekt-Wurzel, aktive .venv):
    python scripts/generate_erd.py

Voraussetzungen:
    pip install -r requirements-dev.txt      (sqlalchemy-schemadisplay, pydot)
    brew install graphviz                    (Programm "dot")
    brew install --cask font-ibm-plex-mono   (optional, fuer exakte Schrift)
"""
import os
import sys

from sqlalchemy import create_engine
from sqlalchemy_schemadisplay import create_schema_graph

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from backend.db.models import Base  # noqa: E402

OUTPUT_PNG = os.path.join(PROJECT_ROOT, "docs", "er_modell.png")
OUTPUT_SVG = os.path.join(PROJECT_ROOT, "docs", "er_modell.svg")

# --- Design-Tokens (Blue-Ramp) -------------------------------------------
NAVY    = "#03253E"   # Blue 900 -> Header
BODY    = "#33454F"   # Body     -> Attribut-Text
BLUE600 = "#325F7F"   # Blue 600 -> Verbindungen
BLUE700 = "#1F4A6B"   # Blue 700 -> Tabellenrahmen
PAPER   = "#F5F8FB"   # Blue 50  -> Flaeche
FONT    = "IBM Plex Mono"


def main() -> None:
    os.makedirs(os.path.dirname(OUTPUT_PNG), exist_ok=True)

    engine = create_engine("sqlite://")  # leer -> nur die Python-Modelle zaehlen

    graph = create_schema_graph(
        engine=engine,
        metadata=Base.metadata,
        show_datatypes=True,
        show_indexes=False,
        show_column_keys=True,   # PK/FK an den Spalten
        rankdir="TB",            # "LR" = links-rechts, falls breiter gewuenscht
        concentrate=False,
        font=FONT,
        format_table_name={"color": NAVY, "bold": True},
    )

    # --- Layout aufraeumen ------------------------------------------------
    graph.set_splines("ortho")   # rechtwinklige Verbindungen (Blueprint)
    graph.set_nodesep("0.55")    # horizontaler Abstand zwischen Tabellen
    graph.set_ranksep("0.85")    # vertikaler Abstand zwischen den Ebenen
    graph.set_pad("0.4")         # Rand um das Diagramm
    graph.set_bgcolor(PAPER)

    for node in graph.get_nodes():
        node.set_color(BLUE700)
        node.set_fontcolor(BODY)
    for edge in graph.get_edges():
        edge.set_headlabel("")   # die "+ spalte"-Labels entfernen (Wirrwarr)
        edge.set_taillabel("")
        edge.set_color(BLUE600)

    graph.write_png(OUTPUT_PNG)
    graph.write_svg(OUTPUT_SVG)
    print(f"Geschrieben:\n  {OUTPUT_PNG}\n  {OUTPUT_SVG}")


if __name__ == "__main__":
    main()