# 1. Einführung und Ziele

## 1.1 Aufgabenstellung

„Train to Call with AI" ist ein KI-gestütztes Telefontraining-System, das als Gesprächspartner (Gegenpart) in simulierten Kundengesprächen agiert. Nutzer können damit im Telefonie-Kontext trainieren, mit einer KI-Persona zu kommunizieren, z. B. in Support-Situationen, beratenden Projektgesprächen oder auch Angebots- und Preisgespräche(F-03).

Im Gegensatz zu klassischen Verkaufstrainern liegt der Fokus nicht auf Abschlussquoten, sondern auf Kommunikation, Klarheit und Wirkung des Sprechenden, ohne dass umfangreiche kundenspezifische Fachkenntnisse vorausgesetzt werden (C-05):

- Kommunikation, Klarheit und Wirkung des Sprechenden
- Erkennung von Sprechverhalten (Redeanteil, Fragen, Sprechtempo, Wortanzahl, Reaktionszeit, Sprechpausen, Lautstärke — ADR 0051)
- Vermeidung von überlangen/überkomplexen Erklärungen

Nach jedem Trainingsgespräch erhält der Nutzer ein qualitatives Wrap-up mit konkreten Verbesserungsvorschlägen statt eines reinen Scores.

## 1.2 Qualitätsziele

| Prio | Qualitätsziel | Bedeutung | Herkunft |
|---|---|---|---|
| 1 | Q-01 Genauigkeit und Nachvollziehbarkeit der Gesprächsanalyse | Die Analyse des Sprechverhaltens muss zutreffend sein und ihre Befunde auf konkrete Gesprächsstellen zurückführen können. Ohne Nachvollziehbarkeit verliert der Nutzer das Vertrauen in die Rückmeldung, insbesondere weil Gespräche subjektiv wahrgenommen werden. | R-19, R-25, R-26 |
| 2 | Q-02 Bedienbarkeit ohne Einarbeitung | Ein Erstnutzer muss ohne Anleitung ein Training starten können. Eine unklare oder überladene Oberfläche wurde in beiden Erhebungen als zentrales Nutzungshemmnis genannt. | R-32, R-33, R-34 |
| 3 | Q-03 Echtzeitfähigkeit des Gesprächsflusses | Die Verarbeitungskette aus Spracherkennung, Antwortgenerierung und Sprachsynthese muss schnell genug sein, dass ein natürlicher Gesprächsfluss entsteht. Das Ziel treibt die offenen Technologieentscheidungen. | Systementwurf |

Datenschutzkonformität ist kein Qualitätsziel, sondern eine nicht verhandelbare Randbedingung und als C-04 in Kapitel 2 geführt.

Weitere Qualitätsanforderungen geringerer Priorität sind in Kapitel 10 aufgeführt.

## 1.3 Stakeholder

| Rolle | Kontakt | Erwartung an das System |
|---|---|---|
| Fachlicher Ansprechpartner und Pilotnutzer | Nicolas Heyne, Solox GmbH (Entwicklung und Kundenkontakt) | Möchte eigene blinde Flecken im Sprechverhalten erkennen. Legt Wert auf einfache Bedienung und qualitatives Feedback statt auf Kennzahlen. Lehnt einen vertrieblichen Fokus für seine Rolle ab. |
| Fachlicher Ansprechpartner und Pilotnutzer | Eckhard Herdt, APPOLLO Systems (CIO und Gründungsmitglied) | Möchte flüssiger und spontaner sprechen und den Umgang mit Einwänden trainieren. Erwartet eine visuelle Auswertung und Verbesserungsvorschläge entlang des eigenen Gesprächsleitfadens. Trainiert Angebots- und Preisgespräche. |
| Support-Mitarbeitende | Solox GmbH | Nutzen das Training für kurze, lösungsorientierte Kundengespräche, etwa telefonische Problemklärung. |
| Entwicklungs- und Projektteam | Solox GmbH | Nutzen das Training für längere, beratende Gesprächssituationen, etwa Schnittstellenthemen und Weiterentwicklung. |
| Technisch geprägte Nutzer ohne vertriebliche Vorerfahrung | APPOLLO Systems | Führen Follow-up-Gespräche nach der Kaltakquise und müssen dabei technische Inhalte adressatengerecht vermitteln. |
| Umsetzungsteam | Projektgruppe (intern) | Entwickelt das System iterativ, benötigt eine klare Architektur- und Anforderungsgrundlage. |

# 2. Randbedingungen

## 2.1 Technische Randbedingungen

| ID | Randbedingung | Beschreibung | Quelle |
|---|---|---|---|
| C-02 | Nutzung am PC mit Headset | Das Training ist am Arbeitsplatzrechner mit angeschlossenem Headset durchführbar; besondere Hardware ist nicht erforderlich. | R-36 |
| C-03 | Nutzung am Smartphone | Das Training ist auch auf einem mobilen Gerät nutzbar. Mobile Telefonie ist in beiden Pilotunternehmen im Einsatz. | R-37 |

## 2.2 Organisatorische Randbedingungen

| ID | Randbedingung | Beschreibung | Quelle |
|---|---|---|---|
| C-01 | Sprache konfigurierbar | Das Training findet in der Sprache statt, in der die Kundengespräche des jeweiligen Unternehmens geführt werden. Die Sprache ist an die Persona gebunden und ergibt sich aus deren Auswahl; Szenarien sind sprachneutral und mit jeder Persona kombinierbar. Belegt sind Deutsch bei Solox sowie Englisch und teilweise Spanisch bei APPOLLO Systems. Siehe ADR 0043 (löst ADR 0022 ab). | R-35 |
| C-04 | Datenschutz nach DSGVO | Alle Daten, insbesondere Sprachaufzeichnungen und personenbezogene Daten, werden DSGVO-konform verarbeitet. Die Randbedingung begrenzt die Umsetzung aller übrigen Ziele und steht nicht als gleichrangiges Ziel neben ihnen. | rechtliche Vorgabe |
| C-05 | Kein kundenspezifisches Fachwissen vorausgesetzt | Fachliches Know-how zu einzelnen Kunden oder Systemen wird nicht abgebildet, da sich die Fachlichkeit je Kundenlandschaft unterscheidet. Der Fokus liegt auf Kommunikation statt Fachlichkeit. | R-40, R-41 |
| C-06 | Gesprächsdauer | Die zu trainierenden Gespräche reichen von kurzen Rückfragen bis zu Gesprächen von einer Stunde. | R-03 |
| C-07 | Zielgruppe | Zur Zielgruppe gehören Personen mit direktem Kundenkontakt in Support- sowie beratenden Projektrollen und Personen mit technischem Hintergrund ohne vertriebliche Vorerfahrung. | R-01, R-02 |
| C-08 | Rückkopplung mit den Pilotunternehmen | Weitere Anforderungen und Rückmeldungen werden gebündelt mit den Ansprechpartnern beider Pilotunternehmen abgestimmt. Der bevorzugte Kanal unterscheidet sich je Unternehmen. | R-48 |

## 2.3 Konventionen

| ID | Konvention | Beschreibung |
|---|---|---|
| C-09 | Anforderungsmanagement nach MoSCoW | Funktionale Anforderungen werden nach Must, Should, Could und Won't priorisiert. Priorität und Release-Zuordnung werden getrennt geführt. |
| C-10 | Anforderungsdokumentation nach ISO/IEC/IEEE 29148 | Anforderungen werden in einer Anforderungsliste in Bedarfssprache geführt, mit Quelle und Typ. Aus dem Typ ergibt sich der Zielort: Funktionen in den Feature-Katalog, Qualitätsziele nach Kapitel 10, Randbedingungen nach Kapitel 2 |

# 3. Kontextabgrenzung

## 3.1 Fachlicher Kontext

Der fachliche Kontext beschreibt, mit welchen Kommunikationspartnern das System aus fachlicher/inhaltlicher Sicht interagiert.

### Nutzer (Support-Mitarbeitende / Projekt- & Entwicklungsmitarbeitende)

Führt ein simuliertes Telefongespräch mit der KI-Persona, sowohl in kürzeren Support-Szenarien als auch in längeren Beratungsgesprächen (F-03). Gibt Sprache ein, erhält Sprache/Antworten der KI zurück sowie im Anschluss ein qualitatives Wrap-up mit Verbesserungsvorschlägen.

### KI-Gesprächspartner (Persona)

Simuliert einen externen Kunden im Gespräch. Die Persona kann aus einer erweiterbaren Persona-Bibliothek stammen (F-04). Reagiert auf Inhalt, Tonfall und Gesprächsführung des Nutzers.

### Feedback-/Auswertungskomponente

Erstellt nach Gesprächsende das qualitative Wrap-up (F-09) inkl. konkreter Verbesserungsvorschläge (F-10), basierend auf den Kennzahlen des Gesprächs (F-53) und dem Lautstärkeverlauf (F-37). Die Kennzahlen beschreiben jeweils das ganze Gespräch, nicht einzelne Redebeiträge (ADR 0051). Ergänzend entsteht im selben Modellaufruf ein Textblock zur phasengerechten Sprache (F-42): ob der Sprachstil über Einstieg, Kernanliegen und Abschluss hinweg mitgewandert ist. Er ist bewusst Fließtext und keine Kennzahl, weil er eine Veränderung über das Gespräch hinweg beschreibt, die keine einzelne Zahl trägt (ADR 0056).

## 3.2 Technischer Kontext

Der technische Kontext beschreibt die technischen Schnittstellen und Kanäle, über die die fachliche Kommunikation stattfindet.

### Nutzer-Endgerät (PC + Headset)

**Kanal / Schnittstelle:** Audio-Ein-/Ausgabe (Mikrofon, Lautsprecher/Headset)

Primärer Zugangsweg im MVP (C-02). Erfasst Sprachsignal des Nutzers, gibt Sprachausgabe der KI wieder.

### Spracherkennung (Speech-to-Text)

**Kanal / Schnittstelle:** Interne Schnittstelle

Wandelt die gesprochene Nutzereingabe in Text um, als Grundlage für Sprachanalyse (F-36, F-41, F-08, F-51) und KI-Antwortgenerierung.

### Sprachsynthese (Text-to-Speech)

**Kanal / Schnittstelle:** Interne Schnittstelle

Wandelt die KI-Antwort in gesprochene Sprache um, um ein reales Telefongespräch zu simulieren.

### KI-/Sprachmodell-Backend

**Kanal / Schnittstelle:** API (z. B. LLM-Anbieter)

Generiert die inhaltlichen Antworten der simulierten Persona sowie das Wrap-up/Feedback am Ende des Gesprächs.

### Datenspeicher

**Kanal / Schnittstelle:** Interne Schnittstelle

Speichert ggf. Gesprächsaufzeichnungen (F-12, SHOULD) und Fortschrittsdaten (F-13, COULD) DSGVO-konform (C-04).

# 4. Lösungsstrategie

Dieses Kapitel fasst die tragenden Entscheidungen des ersten Prototyps zusammen. Es begründet sie nicht — die Begründung steht jeweils im zugehörigen ADR, indiziert in Kapitel 9. Der Prototyp ist lauffähig; die hier genannten Entscheidungen sind damit umgesetzt und nicht mehr nur vorgesehen.

## 4.1 Technologieentscheidungen

| Bereich | Entscheidung | ADR |
|---|---|---|
| Frontend | Single-Page-Anwendung in React und TypeScript, vom Backend mit ausgeliefert | 0008 |
| Backend | Python mit FastAPI | 0012 |
| Architekturstil | Geschichteter modularer Monolith für den Echtzeitpfad, asynchroner Worker für die Nachbereitung | 0018 |
| Sprach- und Dialogmodelle | Uni-gehostetes DiReKT-Gateway für STT und LLM; getrennt selbst gehostete lokale Modelle statt eines externen Anbieters | 0011, 0021 |
| Sprachsynthese | KugelAudio als Standard, DiReKT als Rückfallebene | 0040 |
| Sprecherwechsel | Silero-VAD im Browser; das Turn-Ende wird erkannt, nicht per Knopfdruck gesetzt | 0036 |
| Transport | Eine WebSocket-Verbindung je Session, Audio in Chunks in beide Richtungen | 0033, 0044 |
| Persistenz | Eigene PostgreSQL-Instanz, SQLAlchemy 2.0, Alembic-Migrationen aus den ORM-Metadaten | 0010, 0025, 0026, 0027 |
| Hintergrundverarbeitung | Redis mit RQ als Job-Queue | 0019 |
| Authentifizierung | Keycloak, OIDC Authorization Code Flow mit PKCE | 0009 |
| Paraverbale Messung | Praat über Parselmouth | 0047 |
| Betrieb | Uni-gehosteter Server, Docker Compose | 0020 |

## 4.2 Ansatz je Qualitätsziel

### Q-03 Echtzeitfähigkeit des Gesprächsflusses

Der Engpass ist die Kette aus Spracherkennung, Antwortgenerierung und Sprachsynthese. Sie wird nicht als Blockkette abgearbeitet, sondern an jeder Stelle überlappt:

- Die Antwort wird gestreamt erzeugt und abschnittsweise synthetisiert; jeder Teilabschnitt geht an den Client, sobald er entsteht. Die Wiedergabe beginnt, bevor die Antwort fertig generiert ist (ADR 0033, ADR 0044).
- Der Eröffnungssatz wird vorgewärmt, während der Nutzer den Mikrofontest durchläuft — die Wartezeit wird in eine Phase gelegt, in der ohnehin gewartet wird (ADR 0042).
- Der Nutzer kann die Persona unterbrechen, statt ihre Antwort abwarten zu müssen (ADR 0035).
- Alles Blockierende — Datenbankzugriffe, akustische Messung, Erzeugung der Rückmeldung — läuft außerhalb des Event-Loops, der das Audio streamt; die Nachbereitung erst nach Gesprächsende im Worker (ADR 0018, ADR 0019, ADR 0034).
- Die Modelle laufen im eigenen Netz statt bei einem externen Anbieter, wodurch die Latenz kontrollierbar bleibt (ADR 0011, ADR 0021).

### Q-01 Genauigkeit und Nachvollziehbarkeit der Gesprächsanalyse

- **Messen und Deuten sind getrennt.** Kennzahlen werden deterministisch berechnet; das Modell interpretiert sie, erzeugt sie aber nicht (ADR 0049).
- **Keine erfundenen Normen.** Es gibt keinen Score und keine Zielkorridore, weil für diese Nutzergruppe keiner validiert ist; eine erfundene Schwelle wäre ein verkappter Score (ADR 0004, ADR 0051).
- **Nichts wird gegen die Persona gemessen.** Sie ist eine synthetische Stimme; ein Vergleich mit ihr würde eine TTS-Einstellung als Aussage über den Nutzer ausgeben (ADR 0051).
- **Rückmeldung erst nach dem Gespräch**, damit sie den Gesprächsfluss nicht stört und im Zusammenhang beurteilt werden kann (ADR 0014).

### Q-02 Bedienbarkeit ohne Einarbeitung

- Vor dem Training sind genau zwei Entscheidungen zu treffen: Persona und Szenario. Jede Kombination ist zulässig, es gibt nichts zu filtern und nichts falsch zu machen (ADR 0001, ADR 0015).
- Kartenauswahl statt Liste; die Sprache ist keine eigene Auswahl, sondern ergibt sich aus der Persona (ADR 0015, ADR 0043).
- Während des Gesprächs wird kein Text angezeigt, nur der Zustand *zuhören / denken / sprechen*. Das Transkript erscheint vollständig danach (ADR 0014).

### C-04 Datenschutz als begrenzende Randbedingung

- Sprachaufzeichnungen werden nicht gespeichert. Sie werden im Arbeitsspeicher gemessen und danach verworfen (ADR 0048).
- Sessiondaten werden einmalig am Gesprächsende geschrieben, nicht fortlaufend während des Gesprächs (ADR 0034).
- Eine Session wird über eine nicht erratbare Kennung adressiert; der Primärschlüssel bleibt intern (ADR 0050).

## 4.3 Organisatorische Ansätze

- **Jede Architekturentscheidung wird als ADR festgehalten** (ADR 0000). Kapitel 9 ist nur der Index.
- **Bibliotheksinhalte liegen in der Datenbank, nicht im Code** (ADR 0041). Neue Personas und Szenarien sind Daten, kein Deployment — Voraussetzung dafür, dass Nutzer sie später selbst anlegen (ADR 0024).
- **Bewusst keine Abstraktionsschicht über STT, LLM und TTS** (ADR 0017). Bei drei Anbietern kostet sie mehr, als sie einbringt; ein Wechsel ist eine überschaubare Änderung an einer bekannten Stelle.

# 5. Bausteinsicht

## 5.1 Whitebox Gesamtsystem

*TODO: Komponenten der obersten Ebene (z. B. Engine für Anrufsimulation, Sprachanalyse, Feedback-Engine, Frontend).*

*\<Übersichtsdiagramm\>*

*Begründung: \<Erläuternder Text\>*

*Enthaltene Bausteine: \<Beschreibung der enthaltenen Bausteine (Blackboxen)\>*

*Wichtige Schnittstellen: \<Beschreibung wichtiger Schnittstellen\>*

## 5.2 Ebene 2

*TODO: Detaillierung der einzelnen Bausteine aus Kapitel 5.1.*

## 5.3 Ebene 3

*TODO: Detaillierung der einzelnen Bausteine aus Kapitel 5.2.*

# 6. Laufzeitsicht

*Hinweis: Die Laufzeitsicht baut methodisch auf der Bausteinsicht (Kapitel 5) auf, die noch nicht ausgearbeitet ist. Die technischen Grundentscheidungen stehen inzwischen fest und sind in Kapitel 4 beschrieben; die Szenarien hier sind aber weiterhin auf funktionaler Ebene formuliert und nicht an konkrete Bausteine gebunden. Sobald Kapitel 5 vorliegt, sind sie entsprechend zu binden (siehe TS-01).*

## 6.1 Szenario 1: Start und Ablauf eines Trainingsgesprächs

- Der Nutzer startet ein neues Training und wählt (minimal) eine Persona bzw. ein Szenario aus (z. B. Support-Fall oder Beratungsgespräch, F-03, Q-02: möglichst wenige Pflichtangaben).
- Das System initiiert die Gesprächssimulation: Der Nutzer spricht über PC/Headset, die Sprache wird in Echtzeit in Text umgewandelt (Speech-to-Text).
- Das KI-Backend generiert eine Antwort der simulierten Persona (F-01, F-04), die per Text-to-Speech in gesprochene Sprache umgewandelt und ausgegeben wird.
- Dieser Zyklus (Sprechen → Erkennen → Antworten → Aussprechen) wiederholt sich fortlaufend, bis der Nutzer das Gespräch beendet. Sowohl kurze Support-Calls als auch längere Beratungsgespräche werden dabei unterstützt (F-03).

Besonderheiten: Der gesamte Zyklus muss in Echtzeit ablaufen (Q-03), da Verzögerungen den natürlichen Gesprächsfluss stören. Parallel zur eigentlichen Konversation läuft die Analyse des Sprechverhaltens (Szenario 2) mit.

## 6.2 Szenario 2: Analyse des Sprechverhaltens während des Gesprächs

- Während der Nutzer spricht, misst die Analyse-Komponente je Redebeitrag nur die Rohgrößen, die am Audio ablesbar sind (Aufnahmedauer, reine Sprechzeit ohne Pausen, Pausen, Lautstärke) und rechnet sie auf die Zeitachse der Session um.
- Redeanteil und Sprechtempo teilen durch verschiedene Größen: der Redeanteil durch die Aufnahmedauer, weil nur diese mit der synthetisierten Persona-Stimme vergleichbar ist, das Sprechtempo durch die reine Sprechzeit.
- Die Kennzahlen entstehen erst am Gesprächsende aus allen Redebeiträgen zusammen und beschreiben jeweils das ganze Gespräch — Menge und Begründung siehe ADR 0051, Kennzahlenliste F-53.
- Die Antwortzeit der KI wird mitgemessen und keinem Sprecher zugerechnet, damit sie nicht als Gesprächslücke des Nutzers erscheint (ADR 0051).
- Schlägt die Messung eines Redebeitrags fehl, hält der Redebeitrag das fest: Redeanteil und Sprechtempo entfallen dann für das ganze Gespräch, und aus diesem Beitrag wird keine Reaktionszeit abgeleitet. Eine fehlende Zahl ist ehrlicher als eine, die still zu niedrig ausfällt (ADR 0048, ADR 0051).
- Ergebnisse werden für das spätere Wrap-up gesammelt, nicht während des Gesprächs angezeigt (ADR 0014).

Besonderheiten: Diese Analyse läuft parallel zur eigentlichen Gesprächssimulation (Szenario 1), ohne den Gesprächsfluss zu unterbrechen. Die gesammelten Daten dienen als Grundlage für Szenario 3.

## 6.3 Szenario 3: Erstellung des Wrap-ups nach Gesprächsende

- Nach Beendigung des Gesprächs durch den Nutzer wertet die Feedback-Komponente die gesammelten Analyseergebnisse aus Szenario 2 aus.
- Es wird eine qualitative Zusammenfassung (Wrap-up) erstellt – keine reine Zahl/Score (F-09).
- Konkrete, umsetzbare Verbesserungsvorschläge werden formuliert und nach Möglichkeit mit konkreten Gesprächsstellen verknüpft (F-10).
- Ein eigener Textblock beurteilt die phasengerechte Sprache (F-42): Der Abschluss wird darin stärker gewichtet als die Gesprächsmitte, weil er die Erinnerung an das ganze Gespräch überproportional prägt – als Textgewicht, nicht als Punktabzug (ADR 0056).
- Das Wrap-up wird dem Nutzer angezeigt.

Besonderheiten: Die Qualität dieses Szenarios ist zentral für die Akzeptanz des Tools (siehe Qualitätsziele, Kapitel 1). Ein optionaler Score (F-14, COULD) kann ergänzend angezeigt werden, ersetzt aber nie das qualitative Feedback.

## 6.4 Szenario 4: Aufzeichnung und langfristige Nutzung (optional/should)

- Sofern vorgesehen (F-12, SHOULD), wird das Gespräch aufgezeichnet und dokumentiert.
- Die Aufzeichnung ermöglicht dem Nutzer eine spätere, fundiertere Reflexion über die reine Erinnerung hinaus.
- Bei mehrteiligen Projektgesprächen (F-23, COULD) kann diese Aufzeichnung über mehrere Termine hinweg referenziert werden.
- Alle gespeicherten Daten müssen DSGVO-konform verarbeitet werden (C-04).

Besonderheiten: Dieses Szenario ist für den MVP nicht zwingend erforderlich (SHOULD/COULD), aber relevant für die kontinuierliche Nutzung als Trainingsinstrument (F-13), die Herr Heyne explizit gewünscht hat.

# 7. Verteilungssicht

## 7.1 Infrastruktur Ebene 1

*TODO: Übersichtsdiagramm, Begründung, Qualitäts-/Leistungsmerkmale sowie Zuordnung von Bausteinen zu Infrastruktur ergänzen, sobald Kapitel 4/5 vorliegen.*

## 7.2 Infrastruktur Ebene 2

*TODO: Detaillierung einzelner Infrastrukturelemente (Diagramm + Erläuterungen).*

# 8. Querschnittliche Konzepte

Querschnittliche Konzepte betreffen mehrere Bausteine/Komponenten gleichzeitig und werden deshalb zentral dokumentiert statt in jedem Baustein wiederholt. Basierend auf dem Erstgespräch und der Feature-Liste lassen sich folgende Konzepte bereits jetzt beschreiben:

## 8.1 Datenschutz und Datensicherheit

Da Sprachaufzeichnungen und personenbezogene Daten verarbeitet werden, muss das System durchgängig DSGVO-konform gestaltet sein (C-04). Dies betrifft insbesondere:

- Verarbeitung und Speicherung von Sprachdaten (Gesprächsaufzeichnungen, F-12)
- Speicherung von Fortschrittsdaten einzelner Nutzer (F-13)
- Übertragung von Sprachdaten an externe Dienste (z. B. Speech-to-Text-, Text-to-Speech- oder LLM-APIs)

Sessiondaten werden bereits im MVP dauerhaft gespeichert, und zwar einmalig am Ende der Session in die projekteigene, uni-gehostete PostgreSQL-Datenbank (ADR 0010): Session-Metadaten, Transkripte, Messungen und Feedback. Sprachaufzeichnungen werden nicht gespeichert und existieren nur für die Dauer der laufenden Session. Sobald Nutzerkonten existieren (ADR 0009), ist die Einwilligung des Nutzers die alleinige Grundlage dafür, eine Session einer identifizierten Person zuzuordnen; der Nutzer kann sie jederzeit widerrufen und seine Daten selbst löschen. Solange es keine Konten gibt, ist der Datenschutzhinweis vor der ersten Aufzeichnung (F-49) Voraussetzung für die Nutzung (siehe ADR 0034, der ADR 0023 ablöst).

## 8.2 Umgang mit Feedback und Bewertung

Da Gespräche laut Herrn Heyne subjektiv wahrgenommen werden können, sollte das Feedback-Konzept durchgängig folgende Prinzipien verfolgen (gilt für alle Komponenten, die Feedback erzeugen oder anzeigen):

- Kein reiner Score als alleinige Bewertung (F-09)
- Konkrete, nachvollziehbare Verbesserungsvorschläge statt abstrakter Metriken (F-10)
- Optionaler Score nur ergänzend, nie ersetzend (F-14)

## 8.3 Benutzerführung und UI-Konsistenz

Gilt übergreifend für alle Bildschirme/Interaktionspunkte des Systems:

- Pflichteinstellungen vor einem Training werden auf ein Minimum reduziert und deutlich sichtbar dargestellt (Q-02)
- Zusatz- und Spezialoptionen werden getrennt und weniger prominent angeboten (Q-02)
- Einfache, intuitive Bedienung ohne Einarbeitungsaufwand (Q-02)

## 8.4 Echtzeitverarbeitung

Betrifft alle Komponenten, die am Gesprächsfluss beteiligt sind (Spracherkennung, KI-Antwortgenerierung, Sprachsynthese):

- Durchgängige Anforderung an geringe Latenz, um einen natürlichen Gesprächsfluss zu ermöglichen (Q-03)
- Umgesetzt wird das durch überlappende statt sequenzielle Verarbeitung der Kette aus Spracherkennung, Antwortgenerierung und Sprachsynthese; die Einzelheiten stehen in Kapitel 4.2

# 9. Architekturentscheidungen

Die Architekturentscheidungen werden als eigenständige Dokumente (ADRs) im Ordner `docs/adr` geführt, jeweils mit Kontext, Entscheidung, Status und Konsequenzen. Dieses Kapitel indiziert sie nur; die Spalte *Betrifft* verweist auf die berührten Anforderungen, Qualitätsziele und Randbedingungen der übrigen Dokumentation.

| Nr. | Titel | Status | Betrifft |
|---|---|---|---|
| ADR 0000 | Record Architecture Decisions | angenommen | |
| ADR 0001 | Separate Scenario and Persona Concepts | angenommen | F-03, F-04 |
| ADR 0002 | Personas as an Extensible Library | angenommen | F-04, R-07, R-08 |
| ADR 0003 | No Human Trainer — Feedback Is Fully AI-Generated | angenommen | F-09, F-10 |
| ADR 0004 | Feedback Is Qualitative, Not Score-Based | angenommen | Q-01, F-09, F-14, R-21 |
| ADR 0005 | No Automated Enterprise/CRM Integration, No Sales KPIs | angenommen | C-05, F-26, F-45, R-45 |
| ADR 0006 | Training Language Is German Only for the MVP | abgelöst durch ADR 0022 | C-01, R-35 |
| ADR 0007 | Primary Access via PC + Headset, Mobile Optional | angenommen | C-02, C-03 |
| ADR 0008 | Frontend Built with React and TypeScript | angenommen | F-46, F-50 |
| ADR 0009 | Authentication via Keycloak (OIDC Authorization Code Flow + PKCE) | angenommen | C-04, F-31, F-50 |
| ADR 0010 | Own PostgreSQL Instance for Session Persistence | angenommen | C-04, F-12, F-13 |
| ADR 0011 | LLM Backend Is the University-Hosted DiReKT Gateway, Self-Contained | angenommen (durch ADR 0021 eingegrenzt) | Q-03, C-04, F-01 |
| ADR 0012 | Backend Built with Python and FastAPI | angenommen | Q-03 |
| ADR 0013 | Minimal Required Setup, Advanced Options Separate | angenommen | Q-02, F-43, R-34 |
| ADR 0014 | Speech-Behavior Feedback Surfaces Only in the Post-Call Wrap-Up | angenommen (eingegrenzt durch ADR 0051) | F-09, F-36, F-37, F-51, F-53 |
| ADR 0015 | Persona Selection via Card View, Not a List | angenommen | Q-02, F-04, F-44 |
| ADR 0016 | One Retry, Then Graceful Session End on Pipeline Failure | angenommen | Q-03, F-46 |
| ADR 0017 | No Provider Abstraction Layer for STT/LLM/TTS | angenommen | |
| ADR 0018 | Layered Modular Monolith for the Real-Time Path, Async Feedback Worker | angenommen | Q-03, F-09 |
| ADR 0019 | Redis + RQ for the Feedback Job Queue | angenommen | F-09 |
| ADR 0020 | Deployment on a University-Hosted Server | angenommen | C-04 |
| ADR 0021 | STT and TTS Run as Separately Self-Hosted Local Models | angenommen | Q-03, C-04, F-01 |
| ADR 0022 | Language as Independent Session Parameter | abgelöst durch ADR 0043 (löst ADR 0006 ab) | C-01, R-35 |
| ADR 0023 | No Session Data Persisted Beyond the MVP; Consent-Gated Storage After | abgelöst durch ADR 0034 | C-04, F-12, F-13, F-48, F-49 |
| ADR 0024 | User-Authored Scenario Context and Personas (Post-MVP) | angenommen | F-04, F-26, F-34, F-45 |
| ADR 0025 | SQLAlchemy 2.0 as ORM | angenommen | |
| ADR 0026 | Normalized Relational Schema for Session Persistence | angenommen | F-12, F-13 |
| ADR 0027 | Alembic Migrations Autogenerated from ORM Metadata | angenommen | |
| ADR 0028 | No Secondary Indexes Beyond Primary/Foreign Keys Yet | abgelöst durch ADR 0052 | |
| ADR 0029 | JSONB for Flexible Per-Measurement Detail Data | angenommen | |
| ADR 0030 | ER Diagram Generated from ORM Metadata | angenommen | |
| ADR 0031 | Pseudonymous subject_id Placeholder Instead of a User Foreign Key | angenommen | C-04, F-31 |
| ADR 0032 | AnalysisJob as a Persisted Entity for Async Job Status | angenommen | Q-07, F-09 |
| ADR 0033 | Streaming Session Pipeline via Chunked TTS over WebSocket | angenommen | Q-03, F-01, F-46 |
| ADR 0034 | Session Data Is Persisted in the MVP, Written Once at Session End | angenommen (löst ADR 0023 ab) | C-04, Q-03, F-12, F-13, F-48, F-49 |
| ADR 0035 | Eager Client-Driven Barge-In Interruption | angenommen | Q-03, F-01, F-46 |
| ADR 0036 | VAD Confirmed-Speech Threshold Instead of a Backchannel Word List | angenommen | Q-03, F-01 |
| ADR 0037 | Closing-Intent Detection Is Regex-Based, Not an LLM Classifier | angenommen | Q-07, F-01 |
| ADR 0038 | Guard Against Degenerate Repetition; Guarantee a Closing Line on Backstopped Endings | angenommen | Q-07, F-01 |
| ADR 0039 | Centralized Logging — Colored Console, Per-Session-Truncated File, Not Committed | angenommen (Datei-Truncation überarbeitet durch ADR 0055) | |
| ADR 0040 | TTS Defaults to KugelAudio with a DiReKT Fallback; Gemini Removed | angenommen (grenzt die TTS-Hälfte von ADR 0021 ein) | Q-03, Q-07, C-04, F-01 |
| ADR 0041 | Personas and Scenarios Loaded from the Database | angenommen | F-03, F-04 |
| ADR 0042 | Opening Turn Pre-Warmed at Session Commitment, Not on Selection | angenommen | Q-03, F-01 |
| ADR 0043 | English Prompt Content, Session Language Bound to the Persona | angenommen (löst ADR 0022 ab) | C-01, R-35, F-03, F-04 |
| ADR 0044 | Forward KugelAudio's Audio Sub-Chunks; No Persistent Streaming Session | angenommen (verfeinert die TTS-Strecke aus ADR 0033) | Q-03, F-01, F-46 |
| ADR 0045 | Case Facts, Call Goal and Success Condition on the Scenario; Objections on the Persona | angenommen (erweitert ADR 0001) | F-01, F-03, F-04, R-12 |
| ADR 0046 | Liveliness Is Pursued at the Prompt Layer Before the Turn-Taking Layer | vorgeschlagen | F-01 |
| ADR 0047 | Praat via Parselmouth as the Paraverbal Measurement Engine | angenommen (eingegrenzt durch ADR 0051) | F-36, F-37, F-51, F-08 |
| ADR 0048 | Paraverbal Analysis Runs Inline on In-Memory Audio; Audio Is Never Persisted | angenommen | Q-03, C-04, F-12, F-36, F-37, F-51 |
| ADR 0049 | The Model Interprets Measurements, It Does Not Produce Them | angenommen | F-09, F-10, R-19, R-22 |
| ADR 0050 | A Session Is Addressed by an Unguessable Id | angenommen | C-04, F-12 |
| ADR 0051 | Statistics Describe the Whole Session and Carry No Invented Norms | angenommen (grenzt ADR 0014/0047/0048 ein) | Q-01, F-53, F-12 |
| ADR 0052 | Index Every Foreign-Key Column | angenommen (löst ADR 0028 ab) | Q-03, F-12 |
| ADR 0053 | Deterministic Constraint Names and Database-Enforced Vocabularies | angenommen | |
| ADR 0054 | The Scenario Briefs the Trainee, Not Only the Persona | vorgeschlagen (erweitert ADR 0045) | Q-01, C-05, R-43 |
| ADR 0055 | Log File Kept for the Whole Run, Not Truncated per Session | angenommen (überarbeitet ADR 0039) | |
| ADR 0056 | Phase-Appropriate Language Is a Paragraph, Not a Metric | angenommen (ergänzt ADR 0049/0051) | F-42, F-09 |
| ADR 0057 | English Wire Vocabulary | angenommen (ergänzt ADR 0026) | |
| ADR 0064 | A Per-User Session History, With Ownership as the Query | angenommen (löst die „kein Listing"-Position ab) | F-13, F-48, F-31, C-04 |
| ADR 0065 | Progress Is Shown Without Being Judged | angenommen (erweitert ADR 0004/0051) | Q-01, F-13 |
| ADR 0066 | Consent Is What Permits a Session to Be Stored | angenommen (schränkt ADR 0034 ein) | C-04, F-49, F-31, F-12 |
| ADR 0067 | Stored Sessions Expire After Six Months, Unless the User Says Otherwise | angenommen (schließt ADR 0031s offene Frist) | C-04, F-49, F-12 |
| ADR 0068 | The Consent Log Outlives the Data It Permitted | angenommen (präzisiert ADR 0066) | C-04, F-49 |

Leere Zellen in *Betrifft* sind bewusst gesetzt: ADR 0000 ist eine Dokumentationskonvention ohne Anforderungsbezug; ADR 0017, 0025, 0027 bis 0030, 0039, 0055 und 0057 sind reine Wartbarkeits-, Werkzeug- oder Schemaentscheidungen ohne Entsprechung in Anforderungsliste oder Feature-Katalog.

# 10. Qualitätsanforderungen

## 10.1 Quality Requirements Overview

| ID | Kategorie | ISO 25010 | Beschreibung | Herkunft |
|---|---|---|---|---|
| Q-01 | Genauigkeit und Nachvollziehbarkeit der Gesprächsanalyse | Funktionale Korrektheit | Die Analyse erkennt auffälliges Sprechverhalten zutreffend und führt ihre Befunde auf konkrete Gesprächsstellen zurück. Die Rückmeldung ist als Wirkung auf den Gesprächspartner formuliert, nicht als objektives Urteil. | R-19, R-25, R-26 |
| Q-02 | Bedienbarkeit ohne Einarbeitung | Interaktionsfähigkeit | Ein Erstnutzer startet ein Training ohne Anleitung. Pflichteinstellungen sind minimal und klar sichtbar, Zusatzoptionen treten zurück. | R-32, R-33, R-34 |
| Q-03 | Echtzeitfähigkeit des Gesprächsflusses | Leistungseffizienz | Die Kette aus Spracherkennung, Antwortgenerierung und Sprachsynthese antwortet ohne wahrnehmbare Verzögerung. | Systementwurf |
| Q-04 | Qualitative statt quantitative Bewertung | Funktionale Angemessenheit | Die Rückmeldung ist differenziert und reduziert das Ergebnis nicht auf einen einzelnen Zahlenwert. | R-21 |
| Q-05 | Regelmäßigkeit der Rückmeldung | Interaktionsfähigkeit | Der Nutzer erhält bei fortlaufender Nutzung regelmäßig Rückmeldung. Ohne diese Regelmäßigkeit ist die Annahme des Werkzeugs nicht zu erwarten. | R-27 |
| Q-06 | Flexibilität der Trainingssituation | Funktionale Angemessenheit | Das System unterstützt unterschiedliche Szenario-Typen und Gesprächslängen von kurzen Support-Fällen bis zu einstündigen Gesprächen. | R-03, R-09 |
| Q-07 | Zuverlässigkeit der Verarbeitungskette | Zuverlässigkeit | Der Ausfall einer Komponente führt nicht zum unbemerkten Abbruch des Gesprächs. | Systementwurf |
| Q-08 | Austauschbarkeit der Sprach- und Modellkomponenten | Wartbarkeit | Sprachmodell, Spracherkennung und Sprachsynthese sind wechselbar, ohne die übrige Anwendung anzupassen. | Systementwurf |
| Q-09 | Schutz der Sprach- und Personendaten | Sicherheit | Sprachdaten werden nur innerhalb des dokumentierten Rahmens verarbeitet. Konkretisiert die Randbedingung C-04. | C-04 |

## 10.2 Qualitätsszenarien

TODO

# 11. Risiken und technische Schulden

Die Risiken in 11.1 begleiten das Vorhaben unabhängig vom Umsetzungsstand. Die technischen Schulden in 11.2 sind demgegenüber Befunde am gebauten Prototyp: bewusst in Kauf genommene oder nachträglich erkannte Verkürzungen, die heute tragen, aber Folgekosten haben.

## 11.1 Risiken

### Technische Risiken

| Nr. | Risiko | Beschreibung | Gegenmaßnahme |
|---|---|---|---|
| RI-01 | Echtzeitfähigkeit der Sprach- und LLM-Schnittstellen | Die Kombination aus Spracherkennung, Antwortgenerierung und Sprachsynthese muss in Echtzeit ablaufen (Q-03). Externe Schnittstellen können Latenzschwankungen aufweisen, die den natürlichen Gesprächsfluss beeinträchtigen. | Die technische Festlegung ist erfolgt (Kapitel 4): Modelle im eigenen Netz, gestreamte Verarbeitung statt Blockkette, Vorwärmen des Eröffnungssatzes. Das Risiko ist damit gemindert, aber nicht ausgeräumt — die Modelle laufen auf geteilter Hardware (ADR 0020), und die Latenz je Teilstrecke wird bislang nicht systematisch gemessen. Offen: Messpunkte je Teilstrecke, um den Engpass unter Last zu bestimmen. |
| RI-02 | Unklare Datenschutz-Umsetzung | Datenschutzkonformität ist eine nicht verhandelbare Randbedingung (C-04). Hosting-Ort und Einwilligungsprozess sind grundsätzlich entschieden (ADR 0034). Das Risiko ist gestiegen, seit Sessiondaten bereits im MVP gespeichert werden: Es gibt damit auch im MVP dauerhaft gespeicherte Daten, aber noch keine festgelegte Speicherdauer, keine Aufbewahrungsfrist und mangels Nutzerkonten keine Einwilligungsverwaltung. Der technische Löschpfad existiert inzwischen — die Fremdschlüssel kaskadieren in der Datenbank (ADR 0052/0053) —, aber niemand ruft ihn auf: Es fehlen die Frist und die Selbstbedienungsfunktion. | Speicherdauer festlegen und Löschfunktion umsetzen, bevor Nutzer außerhalb der Pilotgruppe das System verwenden. Datenschutzhinweis (F-49) vor der ersten Aufzeichnung als Voraussetzung behandeln. Einwilligungsoberfläche zusammen mit der Authentifizierung (ADR 0009) planen, nicht nachträglich ergänzen. |

### Fachliche Risiken

| Nr. | Risiko | Beschreibung | Gegenmaßnahme |
|---|---|---|---|
| RI-03 | Widersprüchliche Erwartungen der Pilotunternehmen — **gelöst** | Solox lehnt einen vertrieblichen Fokus für die eigenen Rollen ab (R-46), APPOLLO Systems will ausdrücklich Angebots- und Preisgespräche sowie Einwandbehandlung trainieren (R-10, R-12). Beide sind Pilotnutzer. Das Risiko bestand darin, das System auf eine der beiden Erwartungen zuzuschneiden und damit für die andere Seite unpassend zu machen. Es wurde kurz nach seinem Aufkommen ausgeräumt. | **Gelöst durch das Führen mehrerer passender Szenarien statt einer Produktausrichtung.** F-03 führt ohnehin drei Szenario-Typen nebeneinander; das Angebots- und Preisgespräch ist einer davon und nicht der Zuschnitt des Werkzeugs. Jede Seite wählt die Szenarien, die zu ihren Rollen passen: Verhandlungsnahes Training steht bereit, ohne dass es jemand wählen muss. Damit gibt es keine Ausrichtung, gegen die sich ein Pilotunternehmen wehren müsste, und keine gesonderte Entscheidung zu treffen. Voraussetzung ist allein, dass beide Seiten in der Bibliothek tatsächlich besetzt sind — nachgewiesen im [Szenario- und Persona-Katalog](scenario-catalogue.md). |
| RI-04 | Fehlende kundenspezifische Fachlichkeit | Der bewusste Verzicht auf eine kundenspezifische Wissensbasis (C-05) vereinfacht die Umsetzung, könnte aber dazu führen, dass Gespräche für erfahrene Nutzer zu oberflächlich oder unrealistisch wirken. Abgefedert wird das durch die optionale, nutzergesteuerte Bereitstellung eigener Dokumente (F-26, F-45). | Frühes Nutzerfeedback beider Pilotunternehmen einholen. Umfang und Wirkung der nutzergesteuerten Dokumentenbereitstellung früh mit beiden Pilotunternehmen abgleichen. |
| RI-05 | Subjektivität des Feedbacks | Gespräche werden von den Beteiligten unterschiedlich wahrgenommen (R-25). Ein maschinell erzeugtes qualitatives Feedback (F-09, F-10) könnte als unpassend, ungenau oder demotivierend empfunden werden, wenn es nicht sorgfältig formuliert ist. Betrifft unmittelbar Q-01, da Nachvollziehbarkeit die Voraussetzung für Vertrauen in die Rückmeldung ist. | Feedback als Wirkung auf den Gesprächspartner formulieren, nicht als objektives Urteil. Tonalität und Formulierungsrichtlinien festlegen und iterativ anhand echten Nutzerfeedbacks verfeinern. |
| RI-06 | Geringe Akzeptanz bei komplexer Bedienung | In beiden Erhebungen wurde eine unklare oder überladene Benutzeroberfläche als zentrales Nutzungshemmnis genannt. Wird Q-02 nicht ausreichend beachtet, sinkt die Akzeptanz erheblich, unabhängig von der fachlichen Qualität des Trainings. | Frühzeitige Usability-Tests. Minimale Pflichteinstellungen bereits im ersten benutzbaren Prototyp umsetzen. |

## 11.2 Technische Schulden

Stand: erster lauffähiger Prototyp. Die Spalte *Art* unterscheidet, ob eine Schuld bewusst eingegangen wurde oder nachträglich aufgefallen ist — nur die zweite Sorte ist ein Versäumnis.

### Architekturdokumentation

| Nr. | Schuld | Art | Wirkung | Abtragen durch |
|---|---|---|---|---|
| TS-01 | Kapitel 5 (Bausteinsicht) ist unausgefüllt, Kapitel 6 (Laufzeitsicht) ist deshalb nicht an Bausteine gebunden. | aufgefallen | Der Prototyp ist gebaut, aber seine Struktur ist nirgends dokumentiert. Neue Mitwirkende müssen sie aus dem Code erschließen. | Kapitel 5 aus dem bestehenden Code nachziehen, danach die Szenarien in Kapitel 6 an die Bausteine binden. |

### Prüfbarkeit

| Nr. | Schuld | Art | Wirkung | Abtragen durch |
|---|---|---|---|---|
| TS-02 | Es gibt kein Eval-Setup für Prompt-Änderungen. | bewusst | Jede Änderung am Systemprompt — und damit an F-01 — ist argumentiert, nicht gemessen. Ob eine Kürzung oder eine neue Regel das Gespräch verbessert, ist derzeit Meinung. | Kleines Eval-Skript: dieselbe Persona × Szenario, N Läufe mit und ohne Änderung, Vergleich von Antwortlänge und Turn-Anzahl. Der Rücklauf synthetisierter Sprache durch die Spracherkennung hat sich bereits als objektiver Prüfgriff bewährt. |
| TS-03 | Das Frontend hat keinen Testrunner. | bewusst | Sprecherwechsel, Wiedergabe-Warteschlange und Unterbrechen sind ausschließlich manuell geprüft. Genau dort lagen bereits Fehler, die kein Backend-Test finden konnte. | Testrunner einrichten und zuerst die Wiedergabe-Warteschlange abdecken. |
| TS-04 | Tests konnten sich stillschweigend selbst überspringen: Datenbanktests fanden ihre Zugangsdaten im Container nicht und meldeten sich als *übersprungen* statt als Fehler. | aufgefallen | 49 Tests prüften über längere Zeit nichts, ohne dass es auffiel; nach Behebung fanden sie vier echte Fehler. | Ein übersprungener Test darf im Regellauf nicht unbemerkt bleiben — Zugangsdaten im Container verfügbar machen und die Suite mit einer Mindestzahl ausgeführter Tests absichern. |
| TS-05 | Der Vite-Dev-Server startet die Anwendung nicht mehr; die WASM-Bausteine der Spracherkennung im Browser scheitern dort. | aufgefallen | Frontend-Änderungen sind nur über den Produktionsbuild im Container prüfbar. Das verlängert jede Rückkopplungsschleife spürbar. | Ursache im Zusammenspiel von Vite und onnxruntime-web klären, sonst dauerhaft auf den Containerpfad festlegen und den Dev-Server aus der Dokumentation nehmen. |

### Umsetzung

| Nr. | Schuld | Art | Wirkung | Abtragen durch |
|---|---|---|---|---|
| TS-06 | Datenbankmigrationen kollidieren, ohne dass die Versionsverwaltung einen Konflikt meldet — die Dateien heißen verschieden und werden kommentarlos vereinigt. | aufgefallen | Der Fehler zeigt sich erst beim Anwendungsstart. Einmal aufgetreten, mit dem Ergebnis, dass Gespräche unbemerkt nicht gespeichert wurden. | Nach jedem Zusammenführen die Anzahl der Migrations-Endpunkte prüfen, nicht die Konfliktliste. Automatisierbar. |
| TS-07 | Das Schema ist englisch benannt, die Schnittstelle zum Frontend deutsch; eine Übersetzungsschicht liegt dazwischen. | bewusst | Jede Umbenennung muss an zwei Stellen gedacht werden. Wird die Schicht übersehen, bricht die Oberfläche, ohne dass ein Backend-Test anschlägt. | Vor der ersten externen Schnittstelle entscheiden, welche der beiden Sprachen die Schnittstelle führt. |
| TS-08 | Eine Tabelle für Einzelbefunde besteht im Schema, hat aber weder Schreiber noch Leser. | bewusst | Totes Schema. Es kostet nichts im Betrieb, täuscht aber eine Funktion vor, die es nicht gibt. | Entweder mit dem Pilotbetrieb befüllen oder entfernen. |
| TS-09 | Die Python-Version ist festgenagelt, weil die verwendete ORM-Fassung auf neueren Fassungen nicht mehr lädt. | aufgefallen | Sicherheitsaktualisierungen der Sprachumgebung sind blockiert. | ORM anheben, danach die Festlegung nachziehen. |
| TS-10 | Für die Zeilenenden gibt es keine im Projekt hinterlegte Konvention, obwohl auf verschiedenen Betriebssystemen gearbeitet wird. | aufgefallen | Änderungen erscheinen größer, als sie sind; Zeilenenden verrauschen die Historie. | Konvention hinterlegen. |
| TS-11 | Für die Sprachsynthese besteht nur auf Deutsch eine funktionierende Rückfallebene. | aufgefallen | Fällt der Standardanbieter aus, liest bei einer englischsprachigen Persona ein deutsches Stimmmodell den englischen Text. Es kommt Audio, es wird kein Fehler gemeldet, und auffallen würde es nur am Klang. | Englische Rückfallebene beschaffen oder den Ausfall hörbar machen, statt still falsch zu synthetisieren. |

### Inhalt

| Nr. | Schuld | Art | Wirkung | Abtragen durch |
|---|---|---|---|---|
| TS-12 | Von den drei Szenario-Typen aus F-03 ist in der Bibliothek bislang einer belegt. | bewusst | F-03 ist ein MUST und noch nicht erfüllt. Die Bibliothek bildet die Arbeitswirklichkeit nur eines der beiden Pilotunternehmen ab — was RI-03 entgegensteht. | Die im Szenario- und Persona-Katalog aufbereiteten Kandidaten anlegen; die Belege dafür liegen vor. |
| TS-13 | Der Trainee erhält vor dem Gespräch keine Einweisung in seinen Fall, während die Persona Fallfakten, Anrufziel und Erfolgsbedingung im Prompt hat. | aufgefallen | Der Nutzer verteidigt eine Position, die er nicht kennt. Betrifft unmittelbar Q-01: Eine Rückmeldung zur Argumentation ist nicht haltbar, wenn nie gesagt wurde, wofür argumentiert werden sollte. | Umsetzung nach ADR 0054. |

### Betrieb und Datenschutz

| Nr. | Schuld | Art | Wirkung | Abtragen durch |
|---|---|---|---|---|
| TS-14 | Der technische Löschpfad besteht, aber es gibt weder eine Aufbewahrungsfrist noch eine Selbstbedienungsfunktion. | bewusst | Gespeicherte Sessiondaten wachsen unbegrenzt. Voraussetzung für jede Nutzung außerhalb der Pilotgruppe. | Frist festlegen und Löschfunktion umsetzen; siehe RI-02, mit dem diese Schuld denselben Gegenstand hat. |

# 12. Glossar

| Begriff | Definition |
|---|---|
| Architecture Decision Record (ADR) | Kurzes, fortlaufend nummeriertes Dokument, das genau eine architektonisch bedeutsame Entscheidung mit Kontext, Status und Konsequenzen festhält. Wird eine Entscheidung revidiert, bleibt der alte Eintrag bestehen und wird als abgelöst gekennzeichnet. |
| Data Platform | Extern betriebener, über OIDC authentifizierter Dienst, über den das System hochgeladene Dokumente und große Dateien wie Gesprächsaufzeichnungen überträgt. Der Dienst dient allein dem Datentransfer; gespeichert werden die Daten in der projekteigenen PostgreSQL-Datenbank (ADR 0010). |
| DiReKT | Von der Hochschule bereitgestellter Dienst zur Erzeugung der Persona-Dialoge. Seine Nutzung ist eine Rahmenbedingung des Projekts und nicht das Ergebnis einer Auswahl unter konkurrierenden Anbietern. |
| Feedback | Qualitative, verhaltensbezogene Rückmeldung zu einer abgeschlossenen Session mit konkreten Verbesserungsvorschlägen. Sie wird vollständig vom KI-System erzeugt; eine menschliche Trainerrolle ist im Produkt nicht vorgesehen. |
| Persona | Charakterprofil des KI-Gesprächspartners einer Session, das dessen Rolle, Verhalten und Schwierigkeitsgrad beschreibt. Die Persona ist unabhängig vom Szenario konfigurierbar und legt zugleich die Sprache und die Stimme des Gesprächs fest. |
| Persona-Bibliothek | Offene, erweiterbare Sammlung der auswählbaren Personas. Neue Personas können aufgenommen werden, ohne die Session- oder Szenario-Logik zu verändern. |
| Session | Ein einzelnes simuliertes Telefongespräch zwischen Nutzer und KI-Gesprächspartner, konfiguriert über Szenario und Persona. Die Sprache ergibt sich aus der Persona und ist kein eigener Auswahlparameter. Die Session ist die zentrale Trainings- und Auswertungseinheit, auf die sich das Feedback bezieht. |
| Sprache | Die Sprache, in der das Trainingsgespräch geführt wird. Sie ist eine Eigenschaft der Persona und wird mit deren Auswahl festgelegt (ADR 0043); Szenarien sind sprachneutral. Davon zu unterscheiden ist die Sprache der Prompt-Inhalte, die einheitlich Englisch ist. |
| Szenario | Situativer Rahmen einer Session, also Anlass und beabsichtigter Verlauf des Gesprächs. Das Szenario ist unabhängig von der Persona konfigurierbar. |
