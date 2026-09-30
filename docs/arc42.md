# 1. Einführung und Ziele

## 1.1 Aufgabenstellung

„Train to Call with AI" ist ein KI-gestütztes Telefontraining-System, das als Gesprächspartner (Gegenpart) in simulierten Kundengesprächen agiert. Nutzer können damit im Telefonie-Kontext trainieren, mit einer KI-Persona zu kommunizieren, z. B. in Support-Situationen, beratenden Projektgesprächen oder auch Angebots- und Preisgespräche(F-03).

Im Gegensatz zu klassischen Verkaufstrainern liegt der Fokus nicht auf Abschlussquoten, sondern auf Kommunikation, Klarheit und Wirkung des Sprechenden, ohne dass umfangreiche kundenspezifische Fachkenntnisse vorausgesetzt werden (C-05):

- Kommunikation, Klarheit und Wirkung des Sprechenden
- Erkennung von Sprechverhalten über 16 Kennzahlen: Redeanteil, Fragen, Sprechtempo, gesprochene Wörter, Füllwörter, Gesprächseinstieg, Gesprächsabschluss, Wiederholungen, Verzögerungslaute, Reaktionszeit, Sprechpausen, Redefluss, Sprechlänge am Stück, Lautstärke, Sprachmelodie und Unterbrechungen (ADR 0051, ADR 0077, ADR 0078, ADR 0083 bis ADR 0086, ADR 0089). Angezeigt werden sie in zwei Hälften, *wie* und *was* gesprochen wurde (ADR 0082); fünf davon werden zusätzlich getrennt nach fordernden und übrigen Gesprächsabschnitten gemessen (ADR 0081).
- Vermeidung von überlangen/überkomplexen Erklärungen

Nach jedem Trainingsgespräch erhält der Nutzer ein qualitatives Wrap-up mit konkreten Verbesserungsvorschlägen statt eines reinen Scores. Jede Kennzahl lässt sich bis zu den Gesprächsstellen aufklappen, aus denen sie gewonnen wurde (ADR 0098).

Über das einzelne Gespräch hinaus bietet das System:

- **Eigene Szenarien:** Nutzer verfassen Szenarien selbst, auch aus hochgeladenen PDF-Dokumenten, und können sie mit ihrem Unternehmen teilen (F-34, F-58, F-59; ADR 0058, ADR 0060).
- **Aus einem Gespräch abgeleitete Übungen:** ein Folgeszenario, das denselben Fall zeitlich später fortführt und die Verbesserungspunkte verlangt (F-60, ADR 0069), und den Rollentausch, in dem der Nutzer anruft und die Persona seine Seite übernimmt (F-61, ADR 0070).
- **Zufallsszenario** und **Anruf annehmen:** Ein Gespräch kann mit unbekanntem Anlass beginnen; ein gewöhnliches Gespräch beginnt mit einem klingelnden Telefon (F-62, F-63).
- **Fokusziele und Vorschläge:** Nutzer wählen bis zu fünf Trainingsziele; daraus und aus ihrer Rolle ergeben sich Szenario-Vorschläge und nach jedem Gespräch bis zu zwei Angebote für das nächste (F-62, F-64; ADR 0076, ADR 0087).
- **Historie und Fortschritt:** vergangene Trainings im Profil, eine Fortschrittsansicht über viele Trainings ohne Bewertung (F-13, F-48; ADR 0064, ADR 0065), Wrap-up und Fortschritt jeweils als PDF (F-64, ADR 0093).

## 1.2 Qualitätsziele

| Prio | Qualitätsziel | Bedeutung | Herkunft |
|---|---|---|---|
| 1 | Q-01 Genauigkeit und Nachvollziehbarkeit der Gesprächsanalyse | Die Analyse des Sprechverhaltens muss zutreffend sein und ihre Befunde auf konkrete Gesprächsstellen zurückführen können. Ohne Nachvollziehbarkeit verliert der Nutzer das Vertrauen in die Rückmeldung, insbesondere weil Gespräche subjektiv wahrgenommen werden. | R-19, R-25, R-26 |
| 2 | Q-02 Bedienbarkeit ohne Einarbeitung | Ein Erstnutzer muss ohne Anleitung ein Training starten können. Eine unklare oder überladene Oberfläche wurde in beiden Erhebungen als zentrales Nutzungshemmnis genannt. | R-32, R-33, R-34 |
| 3 | Q-03 Echtzeitfähigkeit des Gesprächsflusses | Die Verarbeitungskette aus Spracherkennung, Antwortgenerierung und Sprachsynthese muss schnell genug sein, dass ein natürlicher Gesprächsfluss entsteht. Das Ziel hat die Technologieentscheidungen in Kapitel 4 getrieben. | Systementwurf |

Datenschutzkonformität ist kein Qualitätsziel, sondern eine nicht verhandelbare Randbedingung und als C-04 in Kapitel 2 geführt.

Weitere Qualitätsanforderungen geringerer Priorität sind in Kapitel 10 aufgeführt.

## 1.3 Stakeholder

| Rolle | Kontakt | Erwartung an das System |
|---|---|---|
| Fachlicher Ansprechpartner und Pilotnutzer | Ansprechpartner, Pilotunternehmen A (Entwicklung und Kundenkontakt) | Möchte eigene blinde Flecken im Sprechverhalten erkennen. Legt Wert auf einfache Bedienung und qualitatives Feedback statt auf Kennzahlen. Lehnt einen vertrieblichen Fokus für seine Rolle ab. |
| Fachlicher Ansprechpartner und Pilotnutzer | Ansprechpartner, Pilotunternehmen B (CIO und Gründungsmitglied) | Möchte flüssiger und spontaner sprechen und den Umgang mit Einwänden trainieren. Erwartet eine visuelle Auswertung und Verbesserungsvorschläge entlang des eigenen Gesprächsleitfadens. Trainiert Angebots- und Preisgespräche. |
| Support-Mitarbeitende | Pilotunternehmen A | Nutzen das Training für kurze, lösungsorientierte Kundengespräche, etwa telefonische Problemklärung. |
| Entwicklungs- und Projektteam | Pilotunternehmen A | Nutzen das Training für längere, beratende Gesprächssituationen, etwa Schnittstellenthemen und Weiterentwicklung. |
| Technisch geprägte Nutzer ohne vertriebliche Vorerfahrung | Pilotunternehmen B | Führen Follow-up-Gespräche nach der Kaltakquise und müssen dabei technische Inhalte adressatengerecht vermitteln. |
| Umsetzungsteam | Projektgruppe (intern) | Entwickelt das System iterativ, benötigt eine klare Architektur- und Anforderungsgrundlage. |

# 2. Randbedingungen

## 2.1 Technische Randbedingungen

| ID | Randbedingung | Beschreibung | Quelle |
|---|---|---|---|
| C-02 | Nutzung am PC mit Headset | Das Training ist am Arbeitsplatzrechner mit angeschlossenem Headset durchführbar; besondere Hardware ist nicht erforderlich. | R-36 |
| C-03 | Nutzung am Smartphone | Das Training ist auch auf einem mobilen Gerät nutzbar. Mobile Telefonie ist in beiden Pilotunternehmen im Einsatz. | R-37 |

Aus dem Projektumfeld kommen weitere technische Vorgaben hinzu, die keine eigene Anforderung haben:

- **Betrieb in der DiReKT-Infrastruktur.** Die Anwendung läuft auf dem DiReKT-Host bei Hetzner; der Stack wird im Repository `direkt-infrastructure` geführt, nicht in diesem (ADR 0020 mit Statusvermerk, ADR 0108).
- **Modellzugang über das DiReKT-Gateway.** Spracherkennung und Dialogmodell sind über den OpenAI-kompatiblen Endpunkt des Projekts erreichbar; welche Modelle dort bereitstehen, entscheidet nicht dieses Projekt (ADR 0011, ADR 0103).
- **Anmeldung über den DiReKT-Keycloak.** Konten und Unternehmenszugehörigkeit werden dort verwaltet, nicht in der Anwendung (ADR 0009, ADR 0031, ADR 0060).
- **HTTPS.** Der Browser gibt das Mikrofon nur in einem sicheren Kontext frei.
- **amd64.** Die Messbibliothek `praat-parselmouth` liefert kein Linux-Paket für arm64; die Images werden deshalb nur für amd64 gebaut.

## 2.2 Organisatorische Randbedingungen

| ID | Randbedingung | Beschreibung | Quelle |
|---|---|---|---|
| C-01 | Sprache konfigurierbar | Das Training findet in der Sprache statt, in der die Kundengespräche des jeweiligen Unternehmens geführt werden. Die Sprache ist an die Persona gebunden und ergibt sich aus deren Auswahl; Szenarien sind sprachneutral und mit jeder Persona kombinierbar. Belegt sind Deutsch bei Pilotunternehmen A sowie Englisch und teilweise Spanisch bei Pilotunternehmen B. Umgesetzt sind Deutsch und Englisch; eine weitere Sprache ist ein Sprachpaket plus eine Persona, die sie spricht. Siehe ADR 0043 (löst ADR 0022 ab). | R-35 |
| C-04 | Datenschutz nach DSGVO | Alle Daten, insbesondere Sprachaufzeichnungen und personenbezogene Daten, werden DSGVO-konform verarbeitet. Die Randbedingung begrenzt die Umsetzung aller übrigen Ziele und steht nicht als gleichrangiges Ziel neben ihnen. Wie sie umgesetzt ist, beschreibt Kapitel 8.1. | rechtliche Vorgabe |
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

### Nutzer

Führt simulierte Telefongespräche mit einer KI-Persona in Szenarien unterschiedlicher Art (F-03): Betrieb und Störung, Beratung und Anforderung, Preis und Kondition, Abschluss und Einwand (ADR 0072). Gibt Sprache ein und erhält Sprache der Persona zurück, nach dem Gespräch das Transkript und, sofern er der Speicherung zugestimmt hat, ein qualitatives Wrap-up mit Kennzahlen. Legt eigene Szenarien an, wählt Fokusziele, sieht seine Historie und seinen Fortschritt und entscheidet über Speicherung und Löschung seiner Daten (ADR 0066, ADR 0067).

### Unternehmen (Mandant)

Das Unternehmen, dem ein Nutzer angehört. Von Nutzern verfasste Szenarien können mit dem eigenen Unternehmen geteilt werden, sodass Kollegen damit trainieren (F-59, ADR 0060). Die Zugehörigkeit legt ein Administrator im Keycloak fest; die Anwendung verwaltet sie nicht.

### KI-Gesprächspartner (Persona)

Simuliert den Gesprächspartner: in einem gewöhnlichen Gespräch den Anrufer mit seinem Anliegen, im Rollentausch die Seite, die abnimmt (ADR 0070). Die Persona stammt aus einer kuratierten Bibliothek mit fester Sprache und Stimme (F-04, ADR 0041, ADR 0043); Nutzer legen keine eigenen Personas an. Reagiert auf Inhalt und Gesprächsführung des Nutzers.

### Feedback-/Auswertungskomponente

Erstellt nach Gesprächsende das qualitative Wrap-up (F-09) inkl. konkreter Verbesserungsvorschläge (F-10), basierend auf den Kennzahlen des Gesprächs (F-53) und dem Transkript. Die Kennzahlen beschreiben das ganze Gespräch, nicht einzelne Redebeiträge (ADR 0051); fünf davon werden zusätzlich über die fordernden Gesprächsabschnitte und den Rest gemessen (ADR 0081). Ergänzend entstehen im selben Modellaufruf ein Textblock zur phasengerechten Sprache (F-42, ADR 0056) und eine Einschätzung, ob der Ton zum Anlass des Gesprächs passte (ADR 0079). Beide sind bewusst Fließtext und keine Kennzahl. Das Modell deutet die gemessenen Werte, erzeugt sie aber nicht (ADR 0049).

## 3.2 Technischer Kontext

Der technische Kontext beschreibt die technischen Schnittstellen und Kanäle, über die die fachliche Kommunikation stattfindet.

| Partner | Kanal / Schnittstelle | Was übertragen wird |
|---|---|---|
| Browser des Nutzers (PC mit Headset, C-02) | HTTPS: REST unter `/api`, WebSocket `/ws/session` | Ein- und Ausgabe des Gesprächs als Audio in Stücken, das Ende eines Redebeitrags erkennt der Browser selbst (Silero-VAD, ADR 0036); dazu alle Bildschirmdaten über REST. |
| DiReKT-Gateway | OpenAI-kompatible HTTP-API | Spracherkennung: die Aufnahme eines Redebeitrags, eine Anfrage je Turn (Whisper). Dialogmodell: der Prompt mit Verlauf, die Antwort wird gestreamt; dasselbe Modell schreibt Wrap-up, Folgeszenario, Rollentausch-Briefing und Dokument-Zusammenfassung (ADR 0011, ADR 0103). |
| KugelAudio | Anbieter-SDK über eine gepoolte WebSocket-Verbindung | Der Text der Persona-Antwort, abschnittsweise; zurück kommt Audio in Teilstücken, die sofort an den Browser weitergereicht werden (ADR 0040, ADR 0044). Keine Rückfallebene (ADR 0103). |
| Keycloak | OIDC (Authorization Code Flow mit PKCE) | Anmeldung im Browser; das Backend prüft das Zugriffstoken gegen die Schlüssel des Realms und liest daraus Nutzerkennung und Organisation (ADR 0009, ADR 0060). |
| PostgreSQL | SQL | Sessions, Transkripte, Messungen, Wrap-ups, Bibliothek, Einwilligungen, Fokusziele. Keine Audiodaten (ADR 0048). |
| Redis | RQ-Warteschlange | Die Kennung einer gespeicherten Session für den Wrap-up-Job (ADR 0019). |

Die Stimme des Nutzers und die Transkripte gehen nur an das Gateway, das im Stack als `litellm` auf demselben Host erreicht wird und an die Modelle der Universität weiterreicht. KugelAudio erhält den Text der Persona, nicht die Stimme des Nutzers.

# 4. Lösungsstrategie

Dieses Kapitel fasst die tragenden Entscheidungen zusammen. Es begründet sie nicht — die Begründung steht jeweils im zugehörigen ADR, indiziert in Kapitel 9. Der Prototyp ist lauffähig; die hier genannten Entscheidungen sind damit umgesetzt und nicht mehr nur vorgesehen.

## 4.1 Technologieentscheidungen

| Bereich | Entscheidung | ADR |
|---|---|---|
| Frontend | Single-Page-Anwendung in React und TypeScript, gebaut mit Vite und in einem eigenen Image von nginx ausgeliefert; das Backend läuft auf einem eigenen Host und erlaubt den Zugriff per CORS | 0008, 0104, 0107 |
| Backend | Python mit FastAPI | 0012 |
| Architekturstil | Geschichteter modularer Monolith für den Echtzeitpfad, asynchroner Worker für die Nachbereitung; drei Python-Pakete (`shared`, `backend`, `worker`) in einem uv-Workspace | 0018, 0108 |
| Sprach- und Dialogmodelle | Uni-gehostetes DiReKT-Gateway für STT und LLM, je ein Modellname in `.env`; getrennt selbst gehostete lokale Modelle statt eines externen Anbieters | 0011, 0021, 0103 |
| Sprachsynthese | KugelAudio, ohne Rückfallebene | 0040, 0103 |
| Sprecherwechsel | Silero-VAD im Browser; das Turn-Ende wird erkannt, nicht per Knopfdruck gesetzt | 0036 |
| Transport | Eine WebSocket-Verbindung je Session, Audio in Chunks in beide Richtungen | 0033, 0044 |
| Persistenz | Eigene PostgreSQL-Instanz, SQLAlchemy 2.0, Alembic-Migrationen aus den ORM-Metadaten | 0010, 0025, 0026, 0027 |
| Hintergrundverarbeitung | Redis mit RQ als Job-Queue | 0019 |
| Authentifizierung | Keycloak, OIDC Authorization Code Flow mit PKCE; die Unternehmenszugehörigkeit kommt aus Keycloak Organizations | 0009, 0060 |
| Paraverbale Messung | Praat über Parselmouth | 0047 |
| Konfiguration und Logging | Jede Einstellung ist Pflicht und kann aus einer Datei kommen; Logs nur auf stdout, in den Images als JSON | 0105, 0106 |
| Betrieb | DiReKT-Host bei Hetzner, Docker Compose hinter Traefik (`direkt-infrastructure`), drei Images aus einer Registry | 0020, 0104, 0107, 0108 |

## 4.2 Ansatz je Qualitätsziel

### Q-03 Echtzeitfähigkeit des Gesprächsflusses

Der Engpass ist die Kette aus Spracherkennung, Antwortgenerierung und Sprachsynthese. Sie wird nicht als Blockkette abgearbeitet, sondern an jeder Stelle überlappt:

- Die Antwort wird gestreamt erzeugt und abschnittsweise synthetisiert; jeder Teilabschnitt geht an den Client, sobald er entsteht. Die Wiedergabe beginnt, bevor die Antwort fertig generiert ist (ADR 0033, ADR 0044).
- Der Eröffnungssatz wird vorgewärmt, sobald sich der Nutzer auf ein Gespräch festlegt, und bis zur Annahme des Anrufs zurückgehalten — die Wartezeit liegt in Mikrofontest und Klingeln, in denen ohnehin gewartet wird (ADR 0042).
- Die akustische Messung eines Redebeitrags läuft auf einem eigenen Thread parallel zur Spracherkennung und kostet keine Wartezeit (ADR 0048).
- Das Dialogmodell liest statt des ganzen Verlaufs die letzten Wechsel und kurze Gesprächsnotizen, die im Hintergrund nach jedem Wechsel fortgeschrieben werden (ADR 0071).
- Der Nutzer kann die Persona unterbrechen, statt ihre Antwort abwarten zu müssen (ADR 0035).
- Alles Blockierende — Datenbankzugriffe, Erzeugung der Rückmeldung — läuft außerhalb des Event-Loops, der das Audio streamt; die Nachbereitung erst nach Gesprächsende im Worker (ADR 0018, ADR 0019, ADR 0034). Die Gesprächsschleife hängt von der Auswertung nicht ab (ADR 0090).

### Q-01 Genauigkeit und Nachvollziehbarkeit der Gesprächsanalyse

- **Messen und Deuten sind getrennt.** Kennzahlen werden deterministisch berechnet; das Modell interpretiert sie, erzeugt sie aber nicht (ADR 0049).
- **Keine erfundenen Normen.** Es gibt keinen Score und keine Zielkorridore auf einer Rohzahl, weil für diese Nutzergruppe keiner validiert ist; eine erfundene Schwelle wäre ein verkappter Score (ADR 0004, ADR 0051). Die einzige Ausnahme ist eine Ampel auf einer *Einordnung* im einzelnen Gespräch, unter sieben Bedingungen — heute bei Sprachmelodie und Unterbrechungen (ADR 0078).
- **Jede Kennzahl zeigt, woraus sie gewonnen wurde.** Jede Kachel führt auf eine eigene Seite mit den Gesprächsstellen oder dem Verlauf dahinter, gelesen aus den gespeicherten Daten und nie neu berechnet (ADR 0098). Eine Messung wird einmal gespeichert, ihre Einordnung bei jedem Lesen abgeleitet (ADR 0091).
- **Nichts wird gegen die Persona gemessen.** Sie ist eine synthetische Stimme; ein Vergleich mit ihr würde eine TTS-Einstellung als Aussage über den Nutzer ausgeben (ADR 0051).
- **Fortschritt ohne Urteil.** Die Fortschrittsansicht zeigt Werte über die Zeit, aber keine Zielbänder, keine Wertungsfarben und keinen Gesamtwert (ADR 0065, ADR 0095).
- **Rückmeldung erst nach dem Gespräch**, damit sie den Gesprächsfluss nicht stört und im Zusammenhang beurteilt werden kann (ADR 0014).

### Q-02 Bedienbarkeit ohne Einarbeitung

- Pflicht vor dem Training sind nur Persona und Szenario. Jede Kombination ist zulässig (ADR 0001, ADR 0015). Die Szenarien lassen sich nach Herkunft und Art des Gesprächs filtern (ADR 0072); die Bibliothek öffnet auf den Vorschlägen, wenn es welche gibt.
- Kartenauswahl statt Liste; die Sprache ist keine eigene Auswahl, sondern ergibt sich aus der Persona (ADR 0015, ADR 0043).
- Der Weg durch ein Training ist eine einzige Übergangstabelle (ADR 0096). Ein Gespräch beginnt erst auf einen eigenen Knopfdruck: im gewöhnlichen Gespräch nimmt der Nutzer den klingelnden Anruf an (F-63), im Rollentausch bestätigt er, dass er sein Briefing gelesen hat.
- Während des Gesprächs gibt es keine Mitschrift, nur den Zustand *zuhören / denken / sprechen* und, wo das Szenario sie hat, die Fakten des Falls; im Rollentausch das Briefing des Nutzers (ADR 0014, ADR 0070). Das Transkript erscheint vollständig danach.
- Bewegung folgt der Systemeinstellung, Ton lässt sich abschalten, Diagramme tragen ihre Zahlen auch als Text (ADR 0097).

### C-04 Datenschutz als begrenzende Randbedingung

- Gespeichert wird nur mit Einwilligung; ohne sie läuft das Training vollständig, nur ohne Speicherung, Wrap-up und Historie (ADR 0066).
- Gespeicherte Trainings laufen nach sechs Monaten ab; der Nutzer kann einzelne löschen, alle mit dem Widerruf löschen und seine Daten exportieren (ADR 0066, ADR 0067).
- Sprachaufzeichnungen werden nicht gespeichert. Sie werden im Arbeitsspeicher gemessen und danach verworfen (ADR 0048). Gesprochenes wird nicht geloggt.
- Sessiondaten werden einmalig am Gesprächsende geschrieben, nicht fortlaufend während des Gesprächs (ADR 0034).
- Eine Session wird über eine nicht erratbare Kennung adressiert; der Primärschlüssel bleibt intern, und auf fremde Daten antwortet die API wie auf nicht vorhandene (ADR 0031, ADR 0050).

## 4.3 Organisatorische Ansätze

- **Jede Architekturentscheidung wird als ADR festgehalten** (ADR 0000). Kapitel 9 ist nur der Index. Auch verworfene Umbauten werden festgehalten, damit sie nicht ohne neue Gründe wieder vorgeschlagen werden (ADR 0092, ADR 0101).
- **Bibliotheksinhalte liegen in der Datenbank, nicht im Code** (ADR 0041). Neue Personas und mitgelieferte Szenarien sind Seed-Daten, eigene Szenarien legen Nutzer selbst an (ADR 0058).
- **Bewusst keine Abstraktionsschicht über STT, LLM und TTS** (ADR 0017), und je Strecke genau ein Backend ohne Umschalter (ADR 0103). Ein Wechsel ist eine überschaubare Änderung an einer bekannten Stelle.
- **Eine Tatsache wird an einer Stelle entschieden**, und alle, die sie brauchen, fragen dort (ADR 0102): etwa was ein Feedback-Bericht enthält, wie eine gespeicherte Session gelesen wird, in welcher Reihenfolge gelöscht wird.
- **Der Aufrufer öffnet die Transaktion**, eine Domänenfunktion nimmt sie entgegen und committet nie (ADR 0099).
- **Tests belegen Anforderungen.** Jede Testdatei nennt das Feature, die Anforderung oder den ADR, den sie belegt; im Frontend ist die Suite bewusst schmal und deckt Audiopfad, Ablaufsteuerung und die Rechnungen der Fortschrittsansicht ab (ADR 0094).

# 5. Bausteinsicht

## 5.1 Whitebox Gesamtsystem

Das System besteht aus einem browserbasierten Frontend, dem FastAPI-Backend, einem asynchronen Worker sowie den angebundenen Sprach- und Dialogdiensten. Der Echtzeitpfad des Trainings läuft zwischen Frontend und Backend über eine WebSocket-Verbindung; die Nachbereitung wird nach Gesprächsende getrennt davon verarbeitet (ADR 0018, ADR 0019, ADR 0033). Backend und Worker teilen sich den Code für Datenbank, Messung und Sprachmodell über das Paket `shared` (ADR 0108).

```text
                          Browser
            ┌────────────────────────────────┐
            │  Frontend (React/TypeScript)   │
            └───────┬────────────────┬───────┘
          REST /api │                │ WebSocket /ws/session
                    ▼                ▼          OIDC ┌──────────┐
            ┌────────────────────────────────┐ ◄──── │ Keycloak │
            │        Backend (FastAPI)       │       └──────────┘
            │ API · Live-Gespräch · Löschung │ ──── STT ────► ┌──────────────────┐
            └──┬──────────────┬──────────────┘ ──── LLM ────► │ DiReKT-Gateway   │
               │ Job-ID       │ SQL            ──── TTS ──┐   └──────────────────┘
               ▼              ▼                           ▼            ▲
          ┌─────────┐   ┌────────────┐           ┌────────────┐        │ LLM
          │  Redis  │   │ PostgreSQL │           │ KugelAudio │        │
          └────┬────┘   └─────▲──────┘           └────────────┘        │
               │ Job          │ SQL                                    │
               ▼              │                                        │
            ┌────────────────────────────────┐                         │
            │   Worker (Wrap-up-Erzeugung)   │ ────────────────────────┘
            └────────────────────────────────┘
        Backend und Worker importieren beide das Paket `shared`.
```

**Begründung.** Der Echtzeitpfad (Sprechen, Erkennen, Antworten, Ausgeben) darf durch nichts verlangsamt werden, was erst nach dem Gespräch gebraucht wird. Deshalb liegt die Erzeugung des Wrap-ups in einem eigenen Prozess, der über eine Warteschlange angestoßen wird (ADR 0018, ADR 0019). Was beide Prozesse brauchen, steht in `shared`; `shared` importiert keines der beiden anderen Pakete, und Backend und Worker importieren einander nicht. Den Job übergibt das Backend dem Worker über dessen Namen, nicht über einen Import (ADR 0108; `backend/tests/test_module_dependencies.py` hält das fest).

**Enthaltene Bausteine**

| Baustein | Verantwortung |
|---|---|
| Frontend (`frontend/`) | Single-Page-Anwendung: Trainingsablauf, Mikrofon und Sprechererkennung (VAD) im Browser, Wiedergabe der Persona-Stimme, Darstellung von Wrap-up, Verlauf und Fortschritt (Kapitel 5.2.1). |
| Backend (`backend/`) | REST-API und die WebSocket-Route des Live-Gesprächs; führt je Turn Spracherkennung, Antwortgenerierung und Sprachsynthese aus, misst die Sprechweise, speichert die Session nach Gesprächsende und stellt den Wrap-up-Job ein. Verwaltet Bibliothek, Einwilligung, Löschung und Aufbewahrung (Kapitel 5.2.2). |
| Worker (`worker/`) | Erzeugt je eingestelltem Job das Wrap-up einer abgeschlossenen Session und die Kennzahlen über die fordernden Gesprächsabschnitte (Kapitel 5.2.3). |
| Shared (`shared/`) | Datenbankschema, Datenbankzugriff, Seed-Daten und Migrationen; der Messcode und das Kennzahlen-Inventar; der Client für das Sprachmodell; Job-Status und Warteschlange; Sprachpakete, Logging und das Lesen der Einstellungen (Kapitel 5.2.4). |

**Externe Systeme**

| System | Rolle |
|---|---|
| PostgreSQL | Speichert Sessions, Transkripte, Messungen, Wrap-ups, Bibliothek, Einwilligungen und Fokusziele (ADR 0010). |
| Redis | Warteschlange zwischen Backend und Worker (ADR 0019). Übergeben wird nur der Primärschlüssel der Session, nie Transkript oder Audio. |
| Keycloak | Anmeldung per OIDC mit PKCE (ADR 0009); liefert über Organizations die Unternehmenszugehörigkeit (ADR 0060). |
| DiReKT-Gateway | OpenAI-kompatibler Endpunkt für Spracherkennung (Whisper) und Dialogmodell (ADR 0011, ADR 0103). |
| KugelAudio | Sprachsynthese, ohne Rückfallebene (ADR 0040, ADR 0103). |

**Wichtige Schnittstellen**

| Schnittstelle | Zwischen | Beschreibung |
|---|---|---|
| REST unter `/api` | Frontend → Backend | Bibliothek (`/api/personas`, `/api/scenarios`, `/api/tenant`), gespeicherte Trainings (`/api/sessions`), Einwilligung (`/api/consent`), Fokusziele (`/api/focus`) und die eigenen Daten (`/api/me`). Jede Route verlangt ein Bearer-Token; auf fremde Ressourcen antwortet sie mit 404 (ADR 0031, ADR 0050). |
| WebSocket `/ws/session` | Frontend ↔ Backend | Eine Verbindung je Session. Das Token reist in der ersten Nachricht (`session.start`), weil ein Browser einem WebSocket keinen Header mitgeben kann. Audio geht in beide Richtungen in Stücken; die Antwort der Persona wird abschnittsweise gestreamt (ADR 0033, ADR 0044). |
| `/health`, `/health/ready` | Betrieb → Backend | Lebendigkeit ohne Abhängigkeiten, Bereitschaft mit Datenbankprüfung. |
| Job-Warteschlange | Backend → Worker | Ein Job je gespeicherter Session, adressiert über den Funktionsnamen `worker.generator.generate_feedback` (`shared/feedback/queue.py`). |
| Datenbank | Backend, Worker → PostgreSQL | SQLAlchemy über `shared/db/session.py`. Eine Domänenfunktion bekommt die offene Session übergeben und committet nie; die Transaktion öffnet der Aufrufer (ADR 0099). |

## 5.2 Ebene 2

### 5.2.1 Frontend

Das Frontend ist als Single-Page-Anwendung mit React und TypeScript umgesetzt (ADR 0008). Es bildet den vollständigen Trainingsablauf aus Sicht des Nutzers ab und übernimmt die Darstellung der einzelnen Trainingsschritte, die clientseitige Zustandsverwaltung sowie die Kommunikation mit den HTTP- und WebSocket-Schnittstellen des Backends.

`App.tsx` koordiniert den Trainingsablauf. Der Wechsel zwischen den einzelnen Ansichten wird über die in `trainingFlow.ts` definierte Ablaufsteuerung bestimmt (ADR 0096). Zustände, die mehrere Ansichten betreffen, werden in spezialisierte Hooks und Contexts ausgelagert.

Die wichtigsten Frontend-Bausteine sind:

- `SetupView`: Auswahl von Szenario und Persona sowie Vorbereitung des Trainings. Erst der bewusste Start erzeugt eine Session; die reine Auswahl löst noch keine Verbindung zum Backend aus (ADR 0042).
- `MicCheck`: Prüfung des Mikrofonzugriffs und des ausgewählten Eingabegeräts vor Gesprächsbeginn.
- `CallView`: Darstellung des laufenden Trainingsgesprächs. Während des Gesprächs werden nur die für den Gesprächszustand notwendigen Informationen angezeigt; das vollständige Transkript erscheint erst nach Gesprächsende (ADR 0014).
- `BriefScreen` und `IncomingCall`: die Ausgangslage des Falls bzw. im Rollentausch das Briefing des Nutzers, dann das klingelnde Telefon, dessen Annahme das Gespräch beginnt (F-63, ADR 0070).
- `FeedbackWaiting`: Warte-Bildschirm, solange das Wrap-up erzeugt wird; das Transkript bleibt erreichbar.
- `FeedbackView`: Darstellung des qualitativen Wrap-ups sowie der berechneten Gesprächskennzahlen nach Abschluss einer Session (F-09, F-10, F-53). Jede Kennzahl führt auf eine eigene Seite mit ihren Belegen (`SessionMetricView`, ADR 0098).
- `PastSessionView` und `SessionHistory`: ein vergangenes Training und die Liste aller Trainings im Profil (F-48).
- `ScenarioEditor`: Anlegen und Bearbeiten eigener Szenarien, auch aus hochgeladenen PDFs (F-34, F-58).
- `FocusDialog`: die Frage nach Fokuszielen, Rolle und Gesprächsarten beim ersten Start (F-62).
- `ProgressView` und zugehörige Detailansichten: Darstellung mehrerer abgeschlossener Trainings und ihrer Entwicklung über die Zeit (F-13).

Die Logik des Trainingsablaufs ist von der Darstellung getrennt. `useTrainingRun` verwaltet die aktuell gebundene Session sowie die Daten, die über das Gesprächsende hinaus benötigt werden. `useLiveCall` bündelt die Logik des laufenden Gesprächs und verbindet WebSocket-Kommunikation, Audiowiedergabe und Unterbrechungsverhalten. Dadurch bleiben die sichtbaren Komponenten weitgehend auf Darstellung und Benutzerinteraktion beschränkt.

API-Aufrufe liegen je Ressource in einem eigenen Modul (`sessions.ts`, `scenarioLibrary.ts`, `personas.ts`); `api.ts` ist nur der Transport und stellt jeder Anfrage die Adresse des Backends aus `/config.js` voran (ADR 0107). Die Anzeigeeigenschaften jeder Kennzahl stehen an einer Stelle (`utils/metrics.ts`), ebenso, was Feedback-Seite und PDF sagen (`utils/reportOutline.ts`, ADR 0102). Das Feedback-PDF entsteht im Browser (ADR 0093).

Die Authentifizierung liegt außerhalb des eigentlichen Trainingsablaufs. `AuthGate` schützt die geschützten Routen und bindet die Anwendung über OIDC an Keycloak an (ADR 0009). Die Routen für Training, Profil, Fortschritt und vergangene Sessions werden zentral in `main.tsx` aufgebaut.

### 5.2.2 Backend

| Baustein | Verantwortung |
|---|---|
| `app.py` | FastAPI-Anwendung. Beim Start: Prüfung der drei Modellstrecken (`clients/health.py`), Migration und Seeding der Datenbank (`db/provision.py`), täglicher Aufbewahrungslauf (`retention.py`). Ein Fehlschlag in Prüfung oder Provisionierung wird protokolliert, verhindert den Start aber nicht. |
| `auth.py`, `cors.py` | Prüft das Bearer-Token gegen Keycloak und liest daraus Nutzerkennung (`sub`) und Organisation; erlaubt den Zugriff vom Host des Frontends (ADR 0107). |
| `api/` | Ein Router je Ressource. `session_ws.py` ist die Route des Live-Gesprächs; `served.py` baut die drei Formen, in denen eine gespeicherte Session ausgeliefert wird (Verlaufszeile, Detail, Export); `_loading.py` ist das gemeinsame Laden mit Eigentumsprüfung in der Abfrage. |
| `session/` | Das Live-Gespräch (Kapitel 5.3). |
| `clients/` | Spracherkennung (`stt.py`) über das Gateway und Sprachsynthese (`tts.py`) über KugelAudio, jeweils ohne Rückfallebene; `speech_text.py` bereitet Zahlen und Daten für die Aussprache auf. |
| `feedback/` | Die Lesart einer gespeicherten Messung: Erklärung, Skala und Stufe je Kennzahl (`readings.py`, `explanations.py`). Die Stufe wird bei jedem Lesen abgeleitet, nicht gespeichert (ADR 0091). |
| `library.py`, `personas.py`, `scenarios.py` | Die einzige Stelle, die die Tabellen `persona` und `scenario` liest und schreibt, eingeschränkt auf Nutzer und Unternehmen des Aufrufers (ADR 0041, ADR 0058, ADR 0060); dazu die Wertobjekte ohne Datenbankzugriff. |
| `authored_text.py`, `documents.py` | Bereinigt selbst verfasste Szenario-Texte, bevor sie Prompt-Inhalt werden (ADR 0059); verdichtet hochgeladene PDFs zu einer Faktenliste, ohne sie zu speichern (F-58). |
| `followups.py`, `reversals.py` | Folgeszenario und Rollentausch aus einer abgeschlossenen Session, auf Anforderung des Nutzers (ADR 0069, ADR 0070, ADR 0100). |
| `recommendations.py`, `focus.py` | Szenario-Vorschläge aus Rolle, Gesprächsarten und Fokuszielen; die Fokusziele selbst (ADR 0076, ADR 0087). |
| `tenants.py` | Ordnet den Aufrufer einem Unternehmen zu und legt dessen Zeile beim ersten Login an (ADR 0060). |
| `consent.py`, `deletion.py`, `retention.py` | Ob gespeichert werden darf (ADR 0066), die eine Stelle, die Nutzerdaten löscht (`deletion.remove`, ADR 0102), und die Aufbewahrungsfrist von sechs Monaten (ADR 0067). |
| `scripts/` | Betriebswerkzeuge: Prüfung der Modellstrecken, erneutes Einstellen von Wrap-ups, Aufbewahrung, Nachberechnung von Kennzahlen für ältere Sessions, Lasttest der Datenbank. |

### 5.2.3 Worker

| Baustein | Verantwortung |
|---|---|
| `__main__.py` | Startet den RQ-Worker (`python -m worker`). Kein Request-Zyklus, dieselbe Datenbank wie das Backend. |
| `generator.py` | Schreibt das Wrap-up einer Session mit einem Modellaufruf: Zusammenfassung, Stärken, Verbesserungen, phasengerechte Sprache (ADR 0056), Passung des Tons zum Anlass (ADR 0079) und die fordernden Gesprächsstellen (ADR 0081). Das Modell deutet gemessene Kennzahlen, es erzeugt keine (ADR 0049). |
| `segments.py` | Misst fünf Kennzahlen getrennt über die fordernden Abschnitte und den Rest des Gesprächs, mit derselben Ableitung wie für das ganze Gespräch (ADR 0081). |

### 5.2.4 Shared

| Baustein | Verantwortung |
|---|---|
| `db/` | Schema (`models.py`, ADR 0026), Datenbankzugriff (`session.py`), Seed-Inhalte für Personas, Szenarien und Fokusziele (`seed_data.py`, ADR 0041) und die Alembic-Migrationen (ADR 0027). |
| `feedback/` | Messung und Kennzahlen: `acoustics.py` misst ein Turn-Audio mit Praat und ist der einzige Import von Parselmouth (ADR 0047); `metrics.py` ist das Inventar aller Kennzahlen samt Ableitung; `intonation.py`, `interruptions.py` und `hesitations.py` sind Einzelauswertungen; `calls.py`, `rows.py` und `stored.py` bringen ein Gespräch in die Datenbank und wieder heraus; `jobs.py` und `queue.py` sind Status und Warteschlange des Wrap-up-Jobs. |
| `clients/` | Konfiguration des Gateways und der Client für das Dialogmodell (`llm.py`), den Backend und Worker beide nutzen. |
| `turn.py` | Die Zeitachse eines laufenden Gesprächs, die das Live-Gespräch füllt und die Auswertung liest. |
| `language_packs.py` | Was am Prompt nicht englisch sein kann: Beispiele, Muster für Verabschiedung und Wiederholung, gesprochene Sätze — je Sprache ein Paket (ADR 0043). |
| `env.py`, `logging_config.py` | Die einzige Stelle, die Einstellungen liest; jede ist Pflicht und kann aus einer Datei kommen (ADR 0106). Logging nur auf stdout, in den Images als JSON (ADR 0105). |

## 5.3 Ebene 3

### 5.3.1 Live-Gespräch (`backend/session/`)

| Baustein | Verantwortung |
|---|---|
| `orchestrator.py` | Ein Gespräch: je Turn Spracherkennung, Antwortgenerierung und Sprachsynthese; die Schutzmechanismen gegen Wiederholung, verfrühtes oder ausbleibendes Gesprächsende. Spracherkennung und Dialogmodell bekommen einen Wiederholungsversuch, die Sprachsynthese keinen; danach endet der Turn sauber mit einem Fehlercode (ADR 0016, ADR 0033, ADR 0103). |
| `prompting.py` | Systemprompt der Persona, Eröffnungsanweisung und der Prompt für die Gesprächsnotizen (ADR 0043, ADR 0045, ADR 0071). |
| `nudges.py` | Anweisungen, die nur für eine einzige Antwort gelten und nie gespeichert werden (ADR 0035, ADR 0037, ADR 0038). |
| `reply_checks.py`, `repetition.py` | Urteile über eine Antwort gegen die bisherigen Antworten — Wiederholung, erneute Begrüßung, Gesprächsende. Was ein Urteil auslöst und in welcher Reihenfolge, entscheidet der Orchestrator. |
| `history.py`, `call_notes.py` | Der vollständige Verlauf eines Gesprächs, nur über benannte Operationen änderbar; die Gesprächsnotizen, die das Modell statt des älteren Verlaufs liest (ADR 0071, ADR 0075). |
| `heard.py` | Was der Nutzer von einer gestreamten Antwort tatsächlich gehört hat, wenn er sie unterbricht (ADR 0035). |
| `chunking.py` | Teilt den Token-Strom des Modells in satzgroße Stücke für die Synthese (ADR 0033). |
| `measuring.py` | Hängt die akustische Messung einer Äußerung an ihren Turn; gemessen wird parallel zur Spracherkennung (ADR 0048). |
| `persistence.py` | Schreibt die Session nach Gesprächsende in einer Transaktion, sofern eine Einwilligung vorliegt, und legt den Wrap-up-Job an (ADR 0034, ADR 0066). |
| `events.py` | Die Ereignisse, die der Orchestrator an die WebSocket-Route liefert. |

Die Gesprächsschleife importiert aus der Auswertung nur `acoustics` und nie das ORM; erst `persistence.py` verbindet beide, nach Gesprächsende (ADR 0090).

# 6. Laufzeitsicht

Die Szenarien binden die Schritte an die Bausteine aus Kapitel 5. Frontend-Bausteine stehen in Kapitel 5.2.1, Backend-Bausteine in 5.2.2 und 5.3, der Worker in 5.2.3.

## 6.1 Szenario 1: Start und Ablauf eines Trainingsgesprächs

- Der Nutzer öffnet die Trainingsvorbereitung. `SetupView` stellt die verfügbaren Szenarien und Personas dar (`GET /api/scenarios`, `GET /api/personas`, gelesen über `library.py`) und übergibt die Auswahl an den in `App.tsx` gehaltenen Trainingszustand. Beim Zufallsszenario wird erst beim Start gezogen (F-62).
- Erst mit dem bewussten Start des Trainings wird über `useTrainingRun` eine Session gebunden. `useSessionSocket` öffnet die WebSocket-Verbindung und sendet `session.start` mit Token, Persona und Szenario. `session_ws.py` prüft das Token, lädt beide über `library.py`, eingeschränkt auf Nutzer und Unternehmen, und lässt den Orchestrator den Eröffnungssatz der Persona schon jetzt erzeugen und synthetisieren (ADR 0042).
- Währenddessen prüft `MicCheck` Mikrofonzugriff und Eingabegerät. Danach zeigt der Client, wo vorhanden, die Ausgangslage des Falls und dann das klingelnde Telefon (`IncomingCall`, F-63); im Rollentausch stattdessen das Briefing des Nutzers (ADR 0070). Den Wechsel zwischen diesen Schritten bestimmt `trainingFlow.ts` (ADR 0096).
- Mit der Annahme des Anrufs sendet der Client `session.activate`. Ab hier läuft die Zeitachse der Session, und der zurückgehaltene Eröffnungssatz wird abgespielt.
- Im Gespräch stellt `CallView` den Zustand dar; `useLiveCall` verbindet Socket, Wiedergabe und Unterbrechen. Silero-VAD im Browser erkennt das Ende eines Redebeitrags und schickt die Aufnahme als einen Turn (ADR 0036).
- Je Turn ruft der Orchestrator die Spracherkennung (`stt.py`, Gateway) auf, streamt die Antwort des Dialogmodells (`shared/clients/llm.py`), prüft sie mit `reply_checks.py`, teilt sie in `chunking.py` in Sätze und lässt jeden Satz von `tts.py` bei KugelAudio synthetisieren. Die Audio-Teilstücke gehen sofort als `turn.audio.chunk` an den Client (ADR 0033, ADR 0044).
- Spricht der Nutzer in eine Antwort hinein, verstummt die Wiedergabe im Client sofort, und der Client meldet, wie viel er gehört hat. `heard.py` kürzt die Antwort im Verlauf auf das Gehörte; die nächste Antwort bekommt einen einmaligen Hinweis aus `nudges.py` (ADR 0035).
- Das Gespräch endet, wenn der Nutzer auflegt (nach Rückfrage), die Persona sich verabschiedet (ADR 0037) oder eine Strecke endgültig scheitert (ADR 0016). Der Client erhält `session.ended` mit dem vollständigen Transkript.

Besonderheiten: Der gesamte Zyklus muss in Echtzeit ablaufen (Q-03). Nichts Blockierendes läuft auf dem Event-Loop, der das Audio streamt; Datenbankzugriffe gehen über `asyncio.to_thread`. Die Gesprächsnotizen, die das Modell statt des älteren Verlaufs liest, werden nach jedem Wechsel im Hintergrund fortgeschrieben (`call_notes.py`, ADR 0071).

## 6.2 Szenario 2: Analyse des Sprechverhaltens während des Gesprächs

- Während die Spracherkennung läuft, misst `measuring.py` mit `shared/feedback/acoustics.py` (Praat) auf einem eigenen Thread die Rohgrößen des Redebeitrags: Aufnahmedauer, reine Sprechzeit, Pausen, Lautstärke- und Tonhöhenverlauf. Die Ergebnisse hängen an der Zeitachse des Turns (`shared/turn.py`); das Audio wird danach verworfen (ADR 0048).
- Redeanteil und Sprechtempo teilen durch verschiedene Größen: der Redeanteil durch die Aufnahmedauer, weil nur diese mit der synthetisierten Persona-Stimme vergleichbar ist, das Sprechtempo durch die reine Sprechzeit.
- Die Antwortzeit der KI wird mitgemessen und keinem Sprecher zugerechnet, damit sie nicht als Gesprächslücke des Nutzers erscheint (ADR 0051).
- Die Kennzahlen entstehen erst am Gesprächsende: `shared/feedback/calls.py` fasst alle Turns zu einem Gespräch zusammen, `shared/feedback/metrics.py` leitet daraus die 16 Kennzahlen ab, die jeweils das ganze Gespräch beschreiben (ADR 0051).
- Schlägt die Messung eines Redebeitrags fehl, hält der Redebeitrag das fest, und die Kennzahlen, die davon abhängen, entfallen für das ganze Gespräch. Findet die Messung in der Aufnahme keine Stille, entfallen die fünf Kennzahlen, die auf der Trennung von Sprache und Stille beruhen (ADR 0085). Eine fehlende Zahl ist ehrlicher als eine, die still falsch ausfällt.
- Ergebnisse werden für das spätere Wrap-up gesammelt, nicht während des Gesprächs angezeigt (ADR 0014).

Besonderheiten: Die Gesprächsschleife importiert aus der Auswertung nur `acoustics` und nie das ORM (ADR 0090). Erst nach Gesprächsende verbindet `persistence.py` beide Seiten.

## 6.3 Szenario 3: Speicherung und Wrap-up nach Gesprächsende

- Nach Gesprächsende ruft `session_ws.py` `persistence.persist_session` auf. Innerhalb derselben Transaktion fragt `consent.py`, ob der Nutzer der Speicherung zugestimmt hat; ohne Zustimmung wird nichts geschrieben, und der Nutzer behält nur das Transkript auf dem Bildschirm (ADR 0066).
- Mit Zustimmung werden Session, Äußerungen, Messungen, Unterbrechungs-Befunde und eine Job-Zeile mit Status `queued` in einer Transaktion geschrieben (ADR 0034). Danach stellt `shared/feedback/queue.py` den Job in Redis ein; gelingt das nicht, wird die Job-Zeile auf `failed` gesetzt.
- Der Worker (`worker/generator.py`) liest die gespeicherte Session über `shared/feedback/stored.py` und schreibt mit einem Modellaufruf das Wrap-up: Zusammenfassung, Stärken und Verbesserungen mit Bezug auf konkrete Gesprächsstellen und Fokusziele (F-09, F-10, ADR 0080), phasengerechte Sprache (F-42, ADR 0056), Passung des Tons zum Anlass (ADR 0079) und die fordernden Gesprächsstellen. Das Modell deutet die Messungen, es erzeugt keine (ADR 0049).
- `worker/segments.py` misst anhand dieser Stellen fünf Kennzahlen getrennt über die fordernden Abschnitte und den Rest (ADR 0081).
- Der Client zeigt währenddessen einen Warte-Bildschirm (`FeedbackWaiting`) und fragt `GET /api/sessions/{id}` in Abständen ab (`useSessionFeedback`), bis das Wrap-up vorliegt; danach zeigt `FeedbackView` Wrap-up, Kennzahlen und Transkript. Das Transkript ist auch während des Wartens erreichbar.
- Ist die Erzeugung gescheitert, kann der Nutzer sie neu anstoßen (`POST /api/sessions/{id}/feedback`). Das Wrap-up entsteht dabei aus Transkript und gespeicherten Messungen, nie aus Audio.

Besonderheiten: Die Qualität dieses Szenarios ist zentral für die Akzeptanz des Tools (siehe Qualitätsziele, Kapitel 1). Ein Score (F-14, COULD) ist nicht umgesetzt; ADR 0004 und ADR 0051 schließen ihn aus.

## 6.4 Szenario 4: Folgeszenario und Rollentausch anfordern

- Unter dem Wrap-up bietet der Feedback-Bericht (`FeedbackReport`) zwei Übungen an, sofern der Nutzer im Gespräch mindestens dreimal gesprochen hat: das Folgeszenario und den Rollentausch. Dieselben Angebote stehen auf der Seite eines vergangenen Trainings.
- Ein Knopfdruck ruft `POST /api/sessions/{id}/follow-up` bzw. `POST /api/sessions/{id}/reverse` auf. `followups.py` entwirft aus den Verbesserungspunkten den nächsten Anruf in derselben Sache; `reversals.py` übersetzt den gespielten Fall in ein Briefing für den Nutzer. Beides ist ein Modellaufruf; das Ergebnis wird über `library.py` als eigenes Szenario des Nutzers gespeichert (ADR 0069, ADR 0070).
- Beide Routen sind idempotent: ein zweiter Knopfdruck liefert das bereits geschriebene Szenario zurück (ADR 0100).
- Ein zweiter Knopfdruck startet das Gespräch mit derselben Persona, ohne erneuten Mikrofontest.
- Daneben schlägt `recommendations.py` bis zu zwei bestehende Szenarien für das nächste Gespräch vor (F-64, ADR 0087).

## 6.5 Szenario 5: Historie, Fortschritt und Löschung

- Das Profil lädt die eigenen Trainings seitenweise über `GET /api/sessions`; die Abfrage ist auf die Kennung des Nutzers eingeschränkt (ADR 0064). Ein Eintrag öffnet die Seite des vergangenen Trainings, die die Session einmal liest und nicht abfragt.
- Die Fortschrittsansicht lädt dieselbe Liste und rechnet im Browser; es gibt keinen eigenen Endpunkt dafür. Sie zeigt Werte über die Zeit ohne Zielbänder und Wertungsfarben (ADR 0065, ADR 0095).
- Löscht der Nutzer ein Training (`DELETE /api/sessions/{id}`) oder widerruft er seine Einwilligung (`POST /api/consent`), entfernt `deletion.remove` die Sessions samt allem, was daran hängt; beim Widerruf in derselben Transaktion wie die Entscheidung (ADR 0066, ADR 0102). Das Einwilligungsprotokoll selbst bleibt erhalten (ADR 0068).
- `app.py` startet beim Hochfahren und danach täglich den Aufbewahrungslauf, der Sessions nach sechs Monaten löscht, sofern der Nutzer das nicht abgeschaltet hat (ADR 0067).

# 7. Verteilungssicht

## 7.1 Infrastruktur Ebene 1

Betrieben wird auf dem DiReKT-Host bei Hetzner, neben der Dataplatform (ADR 0020 mit Statusvermerk, ADR 0108). Der Stack, der die Anwendung ausführt, steht nicht in diesem Repository, sondern in `direkt-infrastructure` (`public/calltrainer/compose.yml`). Dieses Repository baut nur die drei Images und legt sie in der Registry ab. Die Schritte zur Inbetriebnahme stehen in `docs/deployment.md`.

```text
 Browser ──HTTPS──► calltrainer.efre-direkt.de ─────────► calltrainer-frontend (nginx, SPA)
    │
    ├──HTTPS/WSS──► calltrainer-backend.efre-direkt.de ─► calltrainer-backend (gunicorn/uvicorn)
    │                        (Traefik, TLS)                    │   │   │
    └──HTTPS──► keycloak.efre-direkt.de                        │   │   └──► KugelAudio (TTS, extern)
                                                               │   └──────► litellm:4000 (DiReKT-Gateway: STT, LLM)
                                                               ▼                     ▲
                          calltrainer-db (Postgres 17) ◄── calltrainer-worker ───────┘
                          calltrainer-redis           ◄──┘
```

**Begründung.** Frontend, Backend und Worker sind drei Images aus einem gemeinsamen `Dockerfile` (ADR 0104, ADR 0108), damit jedes nur enthält, was es braucht, und der Worker ohne Request-Zyklus neben dem Backend laufen kann. SPA und API liegen auf zwei Hosts; das Backend erlaubt den Zugriff vom Host des Frontends per CORS (ADR 0107). HTTPS ist Pflicht, weil der Browser das Mikrofon nur in einem sicheren Kontext freigibt.

**Qualitäts- und Leistungsmerkmale**

- Das Backend läuft mit einem gunicorn-Prozess. Wie viele gleichzeitige Gespräche er trägt, ist nicht gemessen.
- Die Images sind nur für amd64 gebaut, weil `praat-parselmouth` kein Linux-Paket für arm64 liefert.
- Jeder Dienst trägt `restart: unless-stopped`. Fällt der Worker aus, laufen Gespräche weiter und Wrap-ups bleiben in der Warteschlange.
- Es gibt keine regelmäßigen Backups (siehe RI-02, TS-17).

**Zuordnung der Bausteine**

| Baustein (Kapitel 5) | Container | Host / Netz |
|---|---|---|
| Frontend | `calltrainer-frontend` (nginx, Port 80) | `calltrainer.efre-direkt.de` über Traefik |
| Backend | `calltrainer-backend` (gunicorn mit uvicorn-Worker, Port 8000) | `calltrainer-backend.efre-direkt.de` über Traefik |
| Worker | `calltrainer-worker` | kein eigener Host |
| PostgreSQL | `calltrainer-db` (Postgres 17) | nur im Stack-Netz `calltrainer_internal` |
| Redis | `calltrainer-redis` | nur im Stack-Netz `calltrainer_internal` |
| DiReKT-Gateway | `litellm` auf demselben Host, erreicht als `http://litellm:4000` über das Netz `proxy` | außerhalb des Stacks |
| Keycloak | `keycloak.efre-direkt.de`, Realm `direkt` | außerhalb des Stacks |
| KugelAudio | Dienst im Internet | extern |

## 7.2 Infrastruktur Ebene 2

### Netze

Worker, Postgres und Redis liegen im Netz `calltrainer_internal` des Stacks. Backend und Worker sind zusätzlich im Netz `proxy`, über das sie das Gateway auf demselben Host erreichen, ohne über die öffentliche Adresse zu gehen. Frontend und Backend hängen hinter Traefik, der TLS mit dem Wildcard-Zertifikat für `*.efre-direkt.de` beendet und auf beiden Routern Sicherheits-Header setzt (unter anderem `Strict-Transport-Security` und eine `Permissions-Policy`, die das Mikrofon nur für die eigene Seite erlaubt).

### Konfiguration und Geheimnisse

Jede Einstellung ist Pflicht und kann aus einer Datei gelesen werden (ADR 0106). Die drei Geheimnisse — Gateway-Schlüssel, KugelAudio-Schlüssel, Datenbankpasswort — sind Docker Secrets; alle übrigen Werte stehen im `compose.yml` des Stacks. Das Frontend-Image ist in jeder Umgebung dasselbe: Issuer und Adresse des Backends schreibt es beim Containerstart in `/config.js`.

### Auslieferung

`scripts/build-and-push.sh` baut die drei Images, nur von einem Commit mit gepushtem `v*`-Tag, und legt sie unter `registry.internal.efre-direkt.de/calltrainer-{frontend,backend,worker}` mit Versions-Tag und `latest` ab. WUD prüft stündlich, zieht ein neues `latest` und erzeugt die Container neu. Das Backend migriert das Schema beim Start selbst. Weil es keinen Rückweg für ein migriertes Schema gibt, wird vor jeder Auslieferung ein Dump gezogen und nach erfolgreicher Auslieferung wieder gelöscht, da er Transkripte enthält. Ein Rollback der Anwendung pinnt den vorherigen Versions-Tag im Stack.

### Logs

Die Container schreiben nur auf stdout, ein JSON-Objekt je Zeile (ADR 0105). Alloy sammelt die Ausgabe in Loki (`direkt-infrastructure/internal/`). Gesprochene Inhalte werden nicht geloggt.

### Lokale Entwicklung

Lokal laufen Backend, Worker und Frontend direkt auf dem Rechner; `dev-compose.yaml` startet nur Postgres, Redis und Keycloak, jeweils nur auf der Loopback-Adresse. Vite leitet `/api`, `/ws` und `/health` an das Backend weiter, sodass der Browser nur einen Origin sieht und kein CORS nötig ist.

# 8. Querschnittliche Konzepte

Querschnittliche Konzepte betreffen mehrere Bausteine gleichzeitig und werden deshalb zentral dokumentiert statt in jedem Baustein wiederholt.

## 8.1 Datenschutz

Da Sprache und personenbezogene Daten verarbeitet werden, ist das System durchgängig auf die DSGVO ausgerichtet (C-04).

**Was gespeichert wird.** Gespeichert werden Session-Metadaten, Transkripte, Messungen, Befunde und Wrap-ups, einmal am Ende des Gesprächs (ADR 0034). Sprachaufnahmen werden nie gespeichert: Sie werden im Arbeitsspeicher gemessen und danach verworfen (ADR 0048). Gesprochenes wird in keinem Log festgehalten, weder die Worte des Nutzers noch die der Persona (`backend/tests/test_transcript_logging.py`).

**Einwilligung.** Gespeichert wird nur mit Einwilligung (ADR 0066). `consent.py` ist die einzige Stelle, die das beantwortet; die Schreibroutine fragt innerhalb ihrer eigenen Transaktion und unter einer Sperre je Nutzer, sodass ein Widerruf nicht zwischen Prüfung und Schreiben fallen kann. Bei einem Fehler wird nicht gespeichert. Ohne Einwilligung bleibt das Training vollständig nutzbar, nur ohne Speicherung, Wrap-up und Historie; so ist die Einwilligung freiwillig. Entscheidungen werden angehängt, nie überschrieben, und sind versioniert: Ändert sich der Hinweistext, wird `CURRENT_VERSION` erhöht und die Einwilligung neu erfragt.

**Aufbewahrung und Löschung.** Gespeicherte Trainings laufen nach sechs Monaten ab, sofern der Nutzer das nicht abschaltet (ADR 0067). Der Nutzer kann ein einzelnes Training löschen, mit dem Widerruf alle löschen und seine Daten als Datei exportieren. Alle Löschpfade laufen über `deletion.remove`, das die Reihenfolge festlegt (ADR 0102): Folgeszenarien werden deaktiviert, Rollentausch-Szenarien bei Widerruf und Ablauf gelöscht, beim Löschen eines einzelnen Trainings nicht (ADR 0069, ADR 0070). Das Einwilligungsprotokoll wird nie gelöscht, weil es der einzige Nachweis ist, dass die erfolgte Speicherung erlaubt war (ADR 0068). Fokusziele sind eine Einstellung, keine Trainingsdaten, und bleiben von der Löschung unberührt (ADR 0076).

**Auftragsverarbeitung.** Die Datenschutzerklärung nennt Hetzner (Hosting) und KugelAudio (Sprachausgabe) als Auftragsverarbeiter. Die Stimme des Nutzers und die Transkripte gehen an das DiReKT-Gateway, der Text der Persona an KugelAudio. Die Prüfung der Datenschutzerklärung durch den Datenschutzbeauftragten steht aus (RI-02).

**Backups.** Es gibt keine regelmäßigen Backups. Die Löschpfade sind heute vollständig, weil keine Kopien existieren; wer Backups einführt, muss im selben Schritt eine Aufbewahrungsregel in ADR 0066 festhalten.

## 8.2 Sicherheit, Eigentum und Sichtbarkeit

- **Authentifizierung.** Jede Route unter `/api` und der Aufbau des Gesprächs verlangen ein Keycloak-Token; das Backend prüft Signatur und Zielgruppe (ADR 0009). Beim WebSocket reist das Token in der ersten Nachricht. Es gibt keine Rollenprüfung.
- **Eigentum.** Die Anwendung hat keine eigene Nutzertabelle; Daten gehören der Nutzerkennung (`sub`) aus dem Token (ADR 0031). Eigentum ist eine Bedingung in der Abfrage, keine Prüfung danach. Auf eine fremde Session antwortet die API mit 404 wie auf eine nicht vorhandene, weil 403 die Existenz bestätigen würde (ADR 0050). Nach außen sichtbar ist nur die nicht erratbare `extern_id`, nie der Primärschlüssel.
- **Unternehmen und Sichtbarkeit.** Ein eigenes Szenario ist privat oder mit dem Unternehmen geteilt (ADR 0058, ADR 0060). Die Unternehmenszugehörigkeit kommt aus Keycloak Organizations; Mitglieder werden von einem Administrator verwaltet, der Client kann sie weder senden noch setzen. Mitgelieferte Szenarien und alle Personas gehören keinem Unternehmen.
- **Eigene Texte im Prompt.** Selbst verfasster Szenariotext wird beim Schreiben bereinigt (Steuerzeichen, das Ende-Signal der Persona und ähnliche Marker) und im Prompt als Information, nicht als Anweisung gerahmt (ADR 0059). Feldlängen kommen aus einer einzigen Quelle im Backend (ADR 0063).
- **Angriffsfläche.** Die automatische API-Dokumentation von FastAPI ist abgeschaltet. CORS erlaubt nur den Host des Frontends und keine Cookies (ADR 0107). Geheimnisse liegen im Betrieb als Docker Secrets vor (ADR 0106).

## 8.3 Umgang mit Feedback und Bewertung

Gespräche werden von den Beteiligten unterschiedlich wahrgenommen (R-25). Für alle Bausteine, die Feedback erzeugen oder anzeigen, gilt deshalb:

- **Kein Score.** Es gibt keinen Gesamtwert für ein Gespräch oder einen Nutzer (ADR 0004); F-14 ist bewusst nicht umgesetzt.
- **Keine erfundenen Normen.** Keine Kennzahl trägt einen Zielbereich, weil keiner für diese Nutzergruppe validiert ist (ADR 0051). Das Wrap-up darf eine Zahl nicht gegen eine Norm beurteilen, und Zusammenfassung und Phasen-Absatz nennen keine Zahlen.
- **Ampeln nur unter Bedingungen.** Eine Einordnung im einzelnen Gespräch darf eine Ampel tragen, wenn sie ADR 0078s sieben Bedingungen erfüllt: Farbe auf einer Einordnung, nie auf einer Rohzahl; die ganze Skala sichtbar; nie Farbe allein; als *Einschätzung* bezeichnet samt der Population, aus der die Grenzen stammen; Farbe und Wortlaut kommen aus dem Backend; die Richtung jeder Farbe ist festgehalten; nur im einzelnen Gespräch. Heute gilt das für Sprachmelodie und Unterbrechungen.
- **Messung und Lesart getrennt.** Eine Messung wird einmal gespeichert, ihre Einordnung bei jedem Lesen abgeleitet, sodass eine neu kalibrierte Skala auch alte Sessions erreicht (ADR 0091).
- **Jede Zahl zeigt ihre Belege.** Jede Kennzahl hat eine Erklärung und eine eigene Seite mit den Gesprächsstellen, aus denen sie gewonnen wurde, gelesen aus den gespeicherten Daten und nie neu berechnet (ADR 0098).
- **Nichts gegen die Persona.** Die Persona ist synthetisch; ein Vergleich mit ihr würde eine TTS-Einstellung als Aussage über den Nutzer ausgeben (ADR 0051).
- **Beschreibung als Fließtext.** Was sich nicht als einzelne Zahl sagen lässt — ob der Ton mit der Phase des Gesprächs mitging, ob er zum Anlass passte —, steht als Absatz des Modells, ausdrücklich als dessen Lesart gekennzeichnet (ADR 0056, ADR 0079).
- **Fortschritt ohne Urteil.** Die Fortschrittsansicht zeigt Werte über die Zeit und den eigenen üblichen Bereich, aber keine Zielbänder, keine Pfeile und keine Wertungsfarben. Farbe bezeichnet dort eine Familie von Kennzahlen, nie einen Wert (ADR 0065, ADR 0095). Die Lautstärke wird nie zwischen Gesprächen verglichen, weil sie ebenso vom Mikrofon wie vom Sprecher abhängt.

## 8.4 Benutzerführung und Barrierefreiheit

- Pflicht vor einem Training sind nur Persona und Szenario; alles Weitere hat Vorgaben (Q-02, ADR 0013).
- Der Weg durch ein Training ist eine einzige, reine Übergangstabelle (`trainingFlow.ts`); nur ein Helfer wechselt den Bildschirm (ADR 0096). Während Mikrofontest und Gespräch ist die Navigation aus dem Kopfbereich gesperrt, weil das Verlassen der Seite die Verbindung abbrechen würde.
- Was nicht rückgängig zu machen ist — Gespräch beenden, ein Szenario löschen —, fragt vorher nach.
- Bewegung folgt der Systemeinstellung (`prefers-reduced-motion`), automatisch startender Ton lässt sich abschalten, Diagramme tragen ihre Zahlen auch als Text; eine Farbe steht nie allein (ADR 0097). Die Erklärung zur Barrierefreiheit nennt EN 301 549; eine BITV-Selbstbewertung der Anwendung steht aus.
- Die Oberfläche ist deutsch. Ein Stylesheet für alle Komponenten, bewusst nicht aufgeteilt (ADR 0092).

## 8.5 Echtzeitverarbeitung

Betrifft alle Bausteine, die am Gesprächsfluss beteiligt sind:

- Überlappende statt sequenzielle Verarbeitung der Kette aus Spracherkennung, Antwortgenerierung und Sprachsynthese; die Einzelheiten stehen in Kapitel 4.2 (Q-03).
- Nichts Blockierendes auf dem Event-Loop, der das Audio streamt: Datenbankzugriffe und Messung laufen in eigenen Threads, die Nachbereitung im Worker (ADR 0018, ADR 0034).
- Spracherkennung und Dialogmodell bekommen einen Wiederholungsversuch (das Dialogmodell nur, solange noch nichts gesendet wurde), die Sprachsynthese keinen, weil ein zweiter Versuch auf der gepoolten Verbindung in unbekanntem Zustand liefe. Danach endet der Turn mit einem Fehlercode statt zu hängen (ADR 0016, ADR 0044). Es gibt keine Rückfallebene auf ein anderes Backend (ADR 0103).
- Unterbrechen ist jederzeit möglich; gespeichert wird nur, was der Nutzer tatsächlich gehört hat (ADR 0035).

## 8.6 Prompt und Modellverhalten

- **Englische Prompts, Sprache aus der Persona.** Prompt-Inhalte sind englisch; was nicht englisch sein kann (Beispiele, Muster für Verabschiedung und Wiederholung, gesprochene Sätze), liefert ein Sprachpaket je Sprache (ADR 0043).
- **Ein Systemprompt, kurz und gegliedert.** Jede Regel darin geht auf ein Transkript zurück, in dem das Modell ohne sie falsch lag (ADR 0071). Anweisungen, die nur für eine Antwort gelten, werden je Turn eingefügt und nie gespeichert (ADR 0035, ADR 0037, ADR 0038).
- **Schutzmechanismen in Code, nicht nur im Prompt.** Wiederholungen, erneute Begrüßung und das Gesprächsende werden an der fertigen Antwort geprüft; was daraus folgt und in welcher Reihenfolge, entscheidet der Orchestrator (ADR 0037, ADR 0038, ADR 0073).
- **Was das Modell nie liest.** Das Briefing des Nutzers, das Rollentausch-Briefing, die Kategorie eines Szenarios und den Zweck eines Folgeszenarios (ADR 0045, ADR 0054, ADR 0069, ADR 0070, ADR 0072). Ein Ziel, das man dem Anrufer gibt, verfolgt er — und verrät die Lösung.
- **Deuten, nicht messen.** Das Modell bekommt die gemessenen Werte und deutet sie; Zahlen erzeugt es nicht (ADR 0049).

## 8.7 Persistenz

- Tabellen, Spalten und die Schnittstelle zum Frontend sind durchgängig englisch benannt; Deutsch steht nur in nutzersichtbaren Inhalten (ADR 0026, ADR 0057, ADR 0061).
- Constraint- und Indexnamen kommen aus einer Namenskonvention (ADR 0053); jede Fremdschlüsselspalte ist indiziert (ADR 0052). Vokabulare wie Status oder Sprecher sind CHECK-Constraints, keine Postgres-Enums.
- Eigentumskanten löschen kaskadierend, Referenztabellen nicht; eine Session lässt sich damit per ORM wie per SQL samt allem Zugehörigen löschen.
- Migrationen werden aus dem ORM erzeugt und vor dem Anwenden gelesen (ADR 0027). Beim Start migriert und befüllt das Backend die Datenbank selbst, unter einer Postgres-Advisory-Sperre, damit zwei Instanzen nicht gleichzeitig migrieren. Der Abgleich mit den Seed-Daten deaktiviert nur mitgelieferte Zeilen, nie von Nutzern verfasste.
- Zeitstempel sind zeitzonenbehaftet und werden in UTC geschrieben.
- Eine Domänenfunktion bekommt die offene Datenbanksitzung und committet nie; die Transaktion öffnet der Aufrufer — Route, Job oder Skript (ADR 0099).

## 8.8 Konfiguration, Logging und Betrieb

- Jede Einstellung ist Pflicht und wird nur über `shared/env.py` gelesen; es gibt keine Standardwerte im Code, und jede Einstellung kann aus einer Datei kommen (`NAME_FILE`), so übergibt der Betrieb seine Geheimnisse (ADR 0106).
- Logs gehen nur auf stdout, in den Images als ein JSON-Objekt je Zeile mit der Session-Kennung (ADR 0105).
- Beim Start prüft das Backend jede der drei Modellstrecken mit einer echten Anfrage und protokolliert Ausfälle, ohne den Start zu verhindern. `/health` meldet nur, dass der Prozess lebt; `/health/ready` prüft zusätzlich die Datenbank.

## 8.9 Testbarkeit

- Jede Testdatei nennt das Feature, die Anforderung oder den ADR, den sie belegt; die Zuordnung steht in `docs/testing.md`.
- Die meisten Backend-Tests brauchen weder Netz noch Datenbank noch Zugangsdaten: STT, LLM und TTS sind gefälscht. Persistenztests legen je Lauf eine eigene Wegwerf-Datenbank an und überspringen sich ohne erreichbaren Server (TS-04).
- Paketgrenzen und die Abhängigkeitsrichtung zwischen Gesprächsschleife und Auswertung sind per Test festgehalten (ADR 0090, ADR 0108).
- Das Frontend wird durch einen strikten TypeScript-Compiler, eine bewusst schmale Vitest-Suite und ESLint mit den React-Hook-Regeln geprüft (ADR 0094).
- flake8 und pylint laufen ohne Befund; eine bewusste Ausnahme trägt ihre Begründung in der Zeile.

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
| ADR 0008 | Frontend Built with React and TypeScript | angenommen (geändert durch ADR 0104: eigenes Frontend-Image statt Auslieferung durch FastAPI) | F-46, F-50 |
| ADR 0009 | Authentication via Keycloak (OIDC Authorization Code Flow + PKCE) | angenommen | C-04, F-31, F-50 |
| ADR 0010 | Own PostgreSQL Instance for Session Persistence | angenommen | C-04, F-12, F-13 |
| ADR 0011 | LLM Backend Is the University-Hosted DiReKT Gateway, Self-Contained | angenommen (durch ADR 0021 eingegrenzt; durch ADR 0103 wieder für STT und Dialog gültig) | Q-03, C-04, F-01 |
| ADR 0012 | Backend Built with Python and FastAPI | angenommen | Q-03 |
| ADR 0013 | Minimal Required Setup, Advanced Options Separate | angenommen | Q-02, F-43, R-34 |
| ADR 0014 | Speech-Behavior Feedback Surfaces Only in the Post-Call Wrap-Up | angenommen (eingegrenzt durch ADR 0051) | F-09, F-36, F-37, F-51, F-53 |
| ADR 0015 | Persona Selection via Card View, Not a List | angenommen | Q-02, F-04, F-44 |
| ADR 0016 | One Retry, Then Graceful Session End on Pipeline Failure | angenommen | Q-03, F-46 |
| ADR 0017 | No Provider Abstraction Layer for STT/LLM/TTS | angenommen | |
| ADR 0018 | Layered Modular Monolith for the Real-Time Path, Async Feedback Worker | angenommen | Q-03, F-09 |
| ADR 0019 | Redis + RQ for the Feedback Job Queue | angenommen | F-09 |
| ADR 0020 | Deployment on a University-Hosted Server | angenommen, mit Statusvermerk: betrieben wird auf dem DiReKT-Host bei Hetzner; der Deployment-Teil ist durch ADR 0108 überholt | C-04 |
| ADR 0021 | STT and TTS Run as Separately Self-Hosted Local Models | angenommen | Q-03, C-04, F-01 |
| ADR 0022 | Language as Independent Session Parameter | abgelöst durch ADR 0043 (löst ADR 0006 ab) | C-01, R-35 |
| ADR 0023 | No Session Data Persisted Beyond the MVP; Consent-Gated Storage After | abgelöst durch ADR 0034 | C-04, F-12, F-13, F-48, F-49 |
| ADR 0024 | User-Authored Scenario Context and Personas (Post-MVP) | angenommen (für Szenarien umgesetzt durch ADR 0058) | F-04, F-26, F-34, F-45 |
| ADR 0025 | SQLAlchemy 2.0 as ORM | angenommen | |
| ADR 0026 | Normalized Relational Schema for Session Persistence | angenommen | F-12, F-13 |
| ADR 0027 | Alembic Migrations Autogenerated from ORM Metadata | angenommen | |
| ADR 0028 | No Secondary Indexes Beyond Primary/Foreign Keys Yet | abgelöst durch ADR 0052 | |
| ADR 0029 | JSONB for Flexible Per-Measurement Detail Data | angenommen | |
| ADR 0030 | ER Diagram Generated from ORM Metadata | angenommen, geändert | |
| ADR 0031 | Pseudonymous subject_id Placeholder Instead of a User Foreign Key | angenommen | C-04, F-31 |
| ADR 0032 | AnalysisJob as a Persisted Entity for Async Job Status | angenommen | Q-07, F-09 |
| ADR 0033 | Streaming Session Pipeline via Chunked TTS over WebSocket | angenommen | Q-03, F-01, F-46 |
| ADR 0034 | Session Data Is Persisted in the MVP, Written Once at Session End | angenommen (löst ADR 0023 ab) | C-04, Q-03, F-12, F-13, F-48, F-49 |
| ADR 0035 | Eager Client-Driven Barge-In Interruption | angenommen | Q-03, F-01, F-46 |
| ADR 0036 | VAD Confirmed-Speech Threshold Instead of a Backchannel Word List | angenommen | Q-03, F-01 |
| ADR 0037 | Closing-Intent Detection Is Regex-Based, Not an LLM Classifier | angenommen | Q-07, F-01 |
| ADR 0038 | Guard Against Degenerate Repetition; Guarantee a Closing Line on Backstopped Endings | angenommen | Q-07, F-01 |
| ADR 0039 | Centralized Logging — Colored Console, Per-Session-Truncated File, Not Committed | angenommen (Datei-Truncation überarbeitet durch ADR 0055, Logdatei entfallen durch ADR 0105) | |
| ADR 0040 | TTS Defaults to KugelAudio with a DiReKT Fallback; Gemini Removed | angenommen, Rückfallebene später entfernt (ADR 0103); grenzt die TTS-Hälfte von ADR 0021 ein | Q-03, Q-07, C-04, F-01 |
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
| ADR 0054 | The Scenario Briefs the Trainee, Not Only the Persona | angenommen und umgesetzt (erweitert ADR 0045) | Q-01, C-05, R-43 |
| ADR 0055 | Log File Kept for the Whole Run, Not Truncated per Session | abgelöst durch ADR 0105 (überarbeitete ADR 0039) | |
| ADR 0056 | Phase-Appropriate Language Is a Paragraph, Not a Metric | angenommen (ergänzt ADR 0049/0051) | F-42, F-09 |
| ADR 0057 | English Wire Vocabulary | angenommen (ergänzt ADR 0026, erweitert durch ADR 0061) | |
| ADR 0058 | User-Authored Scenarios | angenommen und umgesetzt (setzt ADR 0024 für Szenarien um) | F-34, F-58 |
| ADR 0059 | User-Authored Scenario Text Is Information, Not Instructions | angenommen (ergänzt ADR 0058) | F-34, F-58 |
| ADR 0060 | Tenant Model and Company Sharing for Authored Scenarios | angenommen, bis Phase 2 umgesetzt, zweimal ergänzt (Unternehmen über Keycloak Organizations, Anlage beim ersten Login) | F-59, R-58, C-04 |
| ADR 0061 | English Wire Vocabulary for the Scenario Library | angenommen (erweitert ADR 0057) | |
| ADR 0062 | A Scenario Read View, Withholding the Caller's Intent | angenommen (ändert ADR 0058) | F-34 |
| ADR 0063 | Scenario Field Limits Served From One Source | angenommen (verfeinert ADR 0059) | F-34 |
| ADR 0064 | A Per-User Session History, With Ownership as the Query | angenommen (löst die „kein Listing"-Position ab) | F-13, F-48, F-31, C-04 |
| ADR 0065 | Progress Is Shown Without Being Judged | angenommen (erweitert ADR 0004/0051) | Q-01, F-13 |
| ADR 0066 | Consent Is What Permits a Session to Be Stored | angenommen (schränkt ADR 0034 ein) | C-04, F-49, F-31, F-12 |
| ADR 0067 | Stored Sessions Expire After Six Months, Unless the User Says Otherwise | angenommen (schließt ADR 0031s offene Frist) | C-04, F-49, F-12 |
| ADR 0068 | The Consent Log Outlives the Data It Permitted | angenommen (präzisiert ADR 0066) | C-04, F-49 |
| ADR 0069 | The Follow-up Scenario Is Written From the Feedback and Stored | angenommen, zweimal ergänzt (der Nutzer fragt ihn an; der Entwurf führt denselben Fall fort) | F-60, F-09, F-10, F-58 |
| ADR 0070 | Reverse — Replaying a Session With the Roles Swapped | angenommen (setzt ADR 0043 und ADR 0033 punktuell aus, ergänzt ADR 0066) | F-61, F-09, F-49 |
| ADR 0071 | The Model Reads Its Notes and the Last Exchanges, Not the Whole History | angenommen (eingeschränkt durch ADR 0075; seit ADR 0103 wieder ohne Einschränkung, da es nur noch ein Dialogmodell gibt) | Q-03, Q-07 |
| ADR 0072 | The Scenario Category as a Closed Vocabulary | angenommen | F-03, F-43, F-44 |
| ADR 0073 | The Settlement Check Rides on the Per-Turn Nudge | angenommen (verfeinert ADR 0037 und ADR 0038) | Q-01, Q-03 |
| ADR 0074 | Dialogue Generation May Run on Gemini, Under One Switch and on Two Models | ersetzt durch ADR 0103 | Q-03, Q-08, C-04 |
| ADR 0075 | The Caller’s Notes Are Kept Only Where the Model Cannot Read Its Own History | durch ADR 0103 eingegrenzt: die Notizen werden immer geführt | Q-03, Q-08 |
| ADR 0076 | Focus Goals as a Stored Selection | angenommen, ergänzt (das Ziel zur Lautstärke ist zurückgezogen; die Auswahl steuert die Szenario-Empfehlungen) | F-62, F-13, C-04 |
| ADR 0077 | The Liveliness Reading Moves to the Pitch Variation Quotient | angenommen (ändert ADR 0051s Ausnahme für F-35) | F-35, Q-01, Q-04 |
| ADR 0078 | A Classification May Carry a Traffic Light | angenommen (ändert ADR 0004 und ADR 0051, lässt ADR 0065 unberührt) | Q-01, Q-04, F-35, F-51 |
| ADR 0079 | Whether the Tone Suited the Occasion, as Prose | angenommen (folgt ADR 0056s Muster für F-42) | F-09, F-35, F-42, Q-01 |
| ADR 0080 | Feedback Points Carry a Focus Goal | angenommen (Stufe 2 des Dashboard-Konzepts, eingeschränkt durch ADR 0004 und ADR 0065) | F-13, F-62, F-10 |
| ADR 0081 | Measurements Over the Demanding Stretches of a Call | angenommen (ändert ADR 0051 in zwei Punkten) | F-62, F-13, F-53, Q-01 |
| ADR 0082 | The Kennzahlen Are Shown in Two Halves, How and What | angenommen (reine Anzeige, ADR 0051 unberührt) | F-53 |
| ADR 0083 | Metrics That Read Words Take the Session's Language | angenommen | F-41, F-51, F-08, F-62 |
| ADR 0084 | Hesitation Sounds Are Estimated From the Pitch Contour; Articulation Is Not Measured | angenommen (Schwellen vorläufig) | F-51, F-38, F-62 |
| ADR 0085 | A Recording Without Detectable Silence Drops What Rests on Silence | angenommen (präzisiert ADR 0047/0048) | F-51, F-36, F-37 |
| ADR 0086 | The Opening Turn Is Read as Three Parts, Depending on Who Rang | angenommen (löst ADR 0080s Einordnung des Gesprächseinstiegs ab) | F-63, F-62 |
| ADR 0087 | What to Play Next Is Chosen From the Library | angenommen | F-64, F-62 |
| ADR 0088 | Sprachmelodie Is a Tile, and Its Page Carries the Drawing | angenommen (kehrt die Block-Darstellung um) | F-35, F-53 |
| ADR 0089 | The Closing Is Read as Three Parts, in the User's Last Two Turns | angenommen (Gegenstück zu ADR 0086; löst ADR 0080s Einordnung des Gesprächsabschlusses ab) | F-65, F-62 |
| ADR 0090 | The Live Call Does Not Depend on the Analysis of a Finished One | angenommen | Q-03 |
| ADR 0091 | A Measurement Is Stored; a Reading Is Derived on Every Read | angenommen | Q-01, F-35, F-51 |
| ADR 0092 | One Stylesheet, Not One per Component | angenommen (gemessene und verworfene Umstellung) | |
| ADR 0093 | The Feedback PDF Is Built in the Browser | angenommen | F-64, C-04 |
| ADR 0094 | The Frontend Is Checked by a Strict Compiler, a Narrow Test Suite and the Hook Rules | angenommen, alle drei Teile umgesetzt | |
| ADR 0095 | On the Progress View, Colour Names a Family and Never a Value | angenommen (ergänzt ADR 0065, lässt ADR 0078 unberührt) | F-13, Q-01 |
| ADR 0096 | The Training Flow Is One Transition Table | angenommen, ergänzt am 19.09.2026 | Q-02, F-60, F-61, F-62, F-63 |
| ADR 0097 | Motion Yields to the System Setting, Sound Can Be Stopped, Charts Carry Their Numbers in Text | angenommen, ergänzt am 19.09.2026 | Q-02, F-61, F-62, F-63 |
| ADR 0098 | Every Kennzahl Opens Onto Its Evidence, and the Evidence Is Never Recomputed | angenommen (baut auf ADR 0091 auf) | Q-01, F-51, F-53 |
| ADR 0099 | The Caller Opens the Transaction, a Domain Function Takes It | angenommen | C-04 |
| ADR 0100 | The Follow-Up and the Reverse Stay Two Routes, Sharing What Must Not Drift | angenommen | F-60, F-61 |
| ADR 0101 | Four Structural Proposals Declined, So That They Are Not Proposed Again | angenommen | F-64 |
| ADR 0102 | One Place Decides a Shared Fact — Five Seams From the Tenth Review | angenommen | C-04, F-13, F-64 |
| ADR 0103 | One OpenAI-Compatible Gateway, One Voice, and No Switches Between Them | angenommen (löst ADR 0074 ab, ändert ADR 0040 und ADR 0075, stellt ADR 0011 für beide Modellstrecken wieder her) | Q-03, Q-07, Q-08 |
| ADR 0104 | Frontend, Backend and Worker as Three Images | angenommen (ändert ADR 0008; gemeinsamer Origin abgelöst durch ADR 0107, Build durch ADR 0108) | |
| ADR 0105 | Logs Go to Stdout Only, JSON in the Images | angenommen (löst ADR 0055 ab, ändert ADR 0039) | |
| ADR 0106 | Every Setting Required, Any From a File | angenommen | |
| ADR 0107 | The API on Its Own Host, Behind CORS | angenommen (löst den Teil „ein Origin“ von ADR 0104 ab) | |
| ADR 0108 | Three Packages, One Dockerfile, Deployed From the Infrastructure Repository | angenommen (ändert ADR 0104; überholt den Deployment-Teil von ADR 0020) | |

Leere Zellen in *Betrifft* sind bewusst gesetzt: ADR 0000 ist eine Dokumentationskonvention ohne Anforderungsbezug; ADR 0017, 0025, 0027 bis 0030, 0039, 0055, 0057, 0061, 0092, 0094 sowie 0104 bis 0108 sind reine Wartbarkeits-, Werkzeug- oder Schemaentscheidungen ohne Entsprechung in Anforderungsliste oder Feature-Katalog.

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
| RI-01 | Echtzeitfähigkeit der Sprach- und LLM-Schnittstellen | Die Kombination aus Spracherkennung, Antwortgenerierung und Sprachsynthese muss in Echtzeit ablaufen (Q-03). Externe Schnittstellen können Latenzschwankungen aufweisen, die den natürlichen Gesprächsfluss beeinträchtigen. | Die technische Festlegung ist erfolgt (Kapitel 4): Spracherkennung und Dialogmodell auf dem Uni-gehosteten DiReKT-Gateway, gestreamte Verarbeitung statt Blockkette, Vorwärmen des Eröffnungssatzes. Das Risiko ist damit gemindert, aber nicht ausgeräumt — jede der drei Strecken hat genau ein Backend und keine Rückfallebene (ADR 0103), und die Latenz je Teilstrecke wird bislang nicht systematisch gemessen. Offen: Messpunkte je Teilstrecke, um den Engpass unter Last zu bestimmen. |
| RI-02 | Datenschutz-Umsetzung | Datenschutzkonformität ist eine nicht verhandelbare Randbedingung (C-04). Die technischen Voraussetzungen sind umgesetzt: Gespeichert wird nur mit Einwilligung (ADR 0066), gespeicherte Trainings laufen nach sechs Monaten ab (ADR 0067), der Nutzer kann einzelne Trainings löschen, seine Daten exportieren und mit dem Widerruf alles löschen; Audio wird nie gespeichert (ADR 0048), und Gesprochenes wird nicht geloggt. Offen ist, was kein Code liefern kann: Die Datenschutzerklärung ist noch nicht vom Datenschutzbeauftragten geprüft. Außerdem gibt es keine Backups — wer sie einführt, schafft eine Kopie, die kein Löschpfad erreicht. | Prüfung durch den Datenschutzbeauftragten, bevor Nutzer außerhalb der Pilotgruppe das System verwenden. Backups nur zusammen mit einer Aufbewahrungsregel in ADR 0066 einführen. |

### Fachliche Risiken

| Nr. | Risiko | Beschreibung | Gegenmaßnahme |
|---|---|---|---|
| RI-03 | Widersprüchliche Erwartungen der Pilotunternehmen — **gelöst** | Pilotunternehmen A lehnt einen vertrieblichen Fokus für die eigenen Rollen ab (R-46), Pilotunternehmen B will ausdrücklich Angebots- und Preisgespräche sowie Einwandbehandlung trainieren (R-10, R-12). Beide sind Pilotnutzer. Das Risiko bestand darin, das System auf eine der beiden Erwartungen zuzuschneiden und damit für die andere Seite unpassend zu machen. Es wurde kurz nach seinem Aufkommen ausgeräumt. | **Gelöst durch das Führen mehrerer passender Szenarien statt einer Produktausrichtung.** F-03 führt ohnehin drei Szenario-Typen nebeneinander; das Angebots- und Preisgespräch ist einer davon und nicht der Zuschnitt des Werkzeugs. Jede Seite wählt die Szenarien, die zu ihren Rollen passen: Verhandlungsnahes Training steht bereit, ohne dass es jemand wählen muss. Damit gibt es keine Ausrichtung, gegen die sich ein Pilotunternehmen wehren müsste, und keine gesonderte Entscheidung zu treffen. Voraussetzung ist allein, dass beide Seiten in der Bibliothek tatsächlich besetzt sind — nachgewiesen im [Szenario- und Persona-Katalog](scenario-catalogue.md). |
| RI-04 | Fehlende kundenspezifische Fachlichkeit | Der bewusste Verzicht auf eine kundenspezifische Wissensbasis (C-05) vereinfacht die Umsetzung, könnte aber dazu führen, dass Gespräche für erfahrene Nutzer zu oberflächlich oder unrealistisch wirken. Abgefedert wird das durch die optionale, nutzergesteuerte Bereitstellung eigener Dokumente (F-26, F-45). | Frühes Nutzerfeedback beider Pilotunternehmen einholen. Umfang und Wirkung der nutzergesteuerten Dokumentenbereitstellung früh mit beiden Pilotunternehmen abgleichen. |
| RI-05 | Subjektivität des Feedbacks | Gespräche werden von den Beteiligten unterschiedlich wahrgenommen (R-25). Ein maschinell erzeugtes qualitatives Feedback (F-09, F-10) könnte als unpassend, ungenau oder demotivierend empfunden werden, wenn es nicht sorgfältig formuliert ist. Betrifft unmittelbar Q-01, da Nachvollziehbarkeit die Voraussetzung für Vertrauen in die Rückmeldung ist. | Feedback als Wirkung auf den Gesprächspartner formulieren, nicht als objektives Urteil. Tonalität und Formulierungsrichtlinien festlegen und iterativ anhand echten Nutzerfeedbacks verfeinern. |
| RI-06 | Geringe Akzeptanz bei komplexer Bedienung | In beiden Erhebungen wurde eine unklare oder überladene Benutzeroberfläche als zentrales Nutzungshemmnis genannt. Wird Q-02 nicht ausreichend beachtet, sinkt die Akzeptanz erheblich, unabhängig von der fachlichen Qualität des Trainings. | Frühzeitige Usability-Tests. Minimale Pflichteinstellungen bereits im ersten benutzbaren Prototyp umsetzen. |

## 11.2 Technische Schulden

Stand: main vom 30.09.2026. Die Spalte *Art* unterscheidet, ob eine Schuld bewusst eingegangen wurde oder nachträglich aufgefallen ist — nur die zweite Sorte ist ein Versäumnis.

### Architekturdokumentation

| Nr. | Schuld | Art | Wirkung | Abtragen durch |
|---|---|---|---|---|
| TS-01 | Kapitel 5 (Bausteinsicht) war unausgefüllt, Kapitel 6 (Laufzeitsicht) deshalb nicht an Bausteine gebunden — **abgetragen** | aufgefallen | Neue Mitwirkende mussten die Struktur aus dem Code erschließen. | **Abgetragen:** Kapitel 5 beschreibt Frontend, Backend, Worker und `shared` bis zur dritten Ebene, Kapitel 6 bindet die Szenarien an diese Bausteine, Kapitel 7 beschreibt die Verteilung. |

### Prüfbarkeit

| Nr. | Schuld | Art | Wirkung | Abtragen durch |
|---|---|---|---|---|
| TS-02 | Es gibt kein Eval-Setup für Prompt-Änderungen. | bewusst | Jede Änderung am Systemprompt — und damit an F-01 — ist argumentiert, nicht gemessen. Ob eine Kürzung oder eine neue Regel das Gespräch verbessert, ist derzeit Meinung. | Kleines Eval-Skript: dieselbe Persona × Szenario, N Läufe mit und ohne Änderung, Vergleich von Antwortlänge und Turn-Anzahl. Der Rücklauf synthetisierter Sprache durch die Spracherkennung hat sich bereits als objektiver Prüfgriff bewährt. |
| TS-03 | Das Frontend hat keinen Testrunner — **abgetragen** | bewusst | Sprecherwechsel, Wiedergabe-Warteschlange und Unterbrechen waren ausschließlich manuell geprüft. Genau dort lagen bereits Fehler, die kein Backend-Test finden konnte. | **Abgetragen durch ADR 0094:** Vitest deckt die Nebenläufigkeit des Live-Gesprächs (`useStreamedAudioPlayback`, `useSessionSocket`, `useBargeIn`, `useLiveCall`, `useTrainingRun`), die Übergangstabelle des Trainingsablaufs und die reinen Funktionen hinter den Aussagen der Fortschrittsansicht ab. |
| TS-04 | Tests konnten sich stillschweigend selbst überspringen: Datenbanktests fanden ihre Zugangsdaten im Container nicht und meldeten sich als *übersprungen* statt als Fehler. | aufgefallen | 49 Tests prüften über längere Zeit nichts, ohne dass es auffiel; nach Behebung fanden sie vier echte Fehler. | Ein übersprungener Test darf im Regellauf nicht unbemerkt bleiben — Zugangsdaten im Container verfügbar machen und die Suite mit einer Mindestzahl ausgeführter Tests absichern. |
| TS-05 | Der Vite-Dev-Server startet die Anwendung nicht mehr; die WASM-Bausteine der Spracherkennung im Browser scheitern dort. | aufgefallen | Änderungen am Gespräch sind nur über den Produktionsbuild prüfbar (`npm run build:watch` und `npm run preview`). Das verlängert jede Rückkopplungsschleife spürbar. | Ursache im Zusammenspiel von Vite und onnxruntime-web klären, sonst dauerhaft auf den Containerpfad festlegen und den Dev-Server aus der Dokumentation nehmen. |
| TS-15 | Die Schwellen zweier Einordnungen sind vorläufige Arbeitswerte: die Ampel der Unterbrechungen (`GREEN_MAX_COUNT`, `YELLOW_MAX_COUNT` in `interruptions.py`) und die beiden Konstanten der Verzögerungslaute (ADR 0084). | bewusst | Die Einordnungen erfüllen die Bedingungen aus ADR 0078, die Zahlen dahinter sind nicht belegt. Das berührt Q-01 unmittelbar. | Gegen reale Aufnahmen kalibrieren, sobald der Pilotbetrieb Daten liefert. |

### Umsetzung

| Nr. | Schuld | Art | Wirkung | Abtragen durch |
|---|---|---|---|---|
| TS-06 | Datenbankmigrationen kollidieren, ohne dass die Versionsverwaltung einen Konflikt meldet — die Dateien heißen verschieden und werden kommentarlos vereinigt. | aufgefallen | Der Fehler zeigt sich erst beim Anwendungsstart. Einmal aufgetreten, mit dem Ergebnis, dass Gespräche unbemerkt nicht gespeichert wurden. | Nach jedem Zusammenführen die Anzahl der Migrations-Endpunkte prüfen, nicht die Konfliktliste. Automatisierbar. |
| TS-07 | Das Schema ist englisch benannt, die Schnittstelle zum Frontend deutsch; eine Übersetzungsschicht liegt dazwischen — **abgetragen** | bewusst | Jede Umbenennung musste an zwei Stellen gedacht werden. | **Abgetragen durch ADR 0057 und ADR 0061:** Schema und Schnittstelle sind durchgängig englisch; Deutsch steht nur noch in nutzersichtbaren Inhalten. |
| TS-08 | Eine Tabelle für Einzelbefunde besteht im Schema, hat aber weder Schreiber noch Leser — **abgetragen** | bewusst | Totes Schema, das eine Funktion vortäuschte, die es nicht gab. | **Abgetragen durch F-51:** Jede harte Unterbrechung schreibt einen `Finding` (live in `persistence.py`, für ältere Sessions über `backfill_interruptions`); gelesen wird er auf der Detailroute und im Export. |
| TS-09 | Die Python-Version ist festgenagelt, weil die verwendete ORM-Fassung auf neueren Fassungen nicht mehr lädt. | aufgefallen | Sicherheitsaktualisierungen der Sprachumgebung sind blockiert. | ORM anheben, danach die Festlegung nachziehen. |
| TS-10 | Für die Zeilenenden gibt es keine im Projekt hinterlegte Konvention, obwohl auf verschiedenen Betriebssystemen gearbeitet wird. | aufgefallen | Änderungen erscheinen größer, als sie sind; Zeilenenden verrauschen die Historie. Die `.gitattributes` legt LF bisher nur für Shell-Skripte fest, weil ein CRLF-Skript den Frontend-Container am Start hindert. | Konvention auf alle Textdateien ausweiten. |
| TS-11 | Für die Sprachsynthese besteht nur auf Deutsch eine funktionierende Rückfallebene — **abgetragen** | aufgefallen | Fiel der Standardanbieter aus, las bei einer englischsprachigen Persona ein deutsches Stimmmodell den englischen Text. Es kam Audio, es wurde kein Fehler gemeldet, und auffallen wäre es nur am Klang. | **Abgetragen durch ADR 0103: die Rückfallebene ist entfernt.** Von den beiden vorgeschlagenen Wegen — englische Rückfallebene beschaffen oder den Ausfall hörbar machen — ist der zweite gegangen: Ein Ausfall von KugelAudio beendet den Turn mit `tts_failed`, statt ihn still in der falschen Stimme zu synthetisieren. |
| TS-16 | `.env.example` nennt `gemma-4-26B-A4B-it` als Dialogmodell, `shared/clients/llm.py` sendet aber auf Qwen3 abgestimmte Sampling-Parameter (`chat_template_kwargs`, `top_k`, `min_p`, `presence_penalty` 1,5). | aufgefallen | Ob das eingetragene Modell diese Parameter so annimmt und wie sie dort wirken, ist nicht gemessen. Die Abstimmung in `docs/research/model-parameters.md` gilt für ein anderes Modell. | Parameter gegen das eingesetzte Modell messen und entweder anpassen oder die Wahl des Modells begründen. |

### Inhalt

| Nr. | Schuld | Art | Wirkung | Abtragen durch |
|---|---|---|---|---|
| TS-12 | Von den drei Szenario-Typen aus F-03 ist in der Bibliothek bislang einer belegt — **abgetragen** | bewusst | F-03 war ein nicht erfülltes MUST; die Bibliothek bildete die Arbeitswirklichkeit nur eines der beiden Pilotunternehmen ab. | **Abgetragen:** Die Bibliothek enthält 17 Szenarien in den vier Kategorien der ADR 0072 (Betrieb & Störung, Beratung & Anforderung, Preis & Kondition, Abschluss & Einwand), siehe [Szenario- und Persona-Katalog](scenario-catalogue.md). |
| TS-13 | Der Trainee erhält vor dem Gespräch keine Einweisung in seinen Fall, während die Persona Fallfakten, Anrufziel und Erfolgsbedingung im Prompt hat — **abgetragen** | aufgefallen | Der Nutzer verteidigte eine Position, die er nicht kannte. | **Abgetragen durch ADR 0054:** Jedes Szenario trägt ein `briefing` für den Trainee, das nie in einen Prompt gelangt. |

### Betrieb und Datenschutz

| Nr. | Schuld | Art | Wirkung | Abtragen durch |
|---|---|---|---|---|
| TS-14 | Der technische Löschpfad besteht, aber es gibt weder eine Aufbewahrungsfrist noch eine Selbstbedienungsfunktion — **abgetragen** | bewusst | Gespeicherte Sessiondaten wuchsen unbegrenzt. | **Abgetragen durch ADR 0066 und ADR 0067:** Speicherung nur mit Einwilligung, Löschung beim Widerruf, Ablauf nach sechs Monaten mit täglichem Lauf, Löschen einzelner Trainings und Datenexport im Profil. Alle Löschpfade laufen über `deletion.remove` (ADR 0102). |
| TS-17 | Es gibt keine Backups und keinen erprobten Rückweg für ein ausgerolltes Schema: Die Migrationskette ist in beide Richtungen nur auf einer leeren Datenbank getestet, und das Downgrade über `d7f41c9b3a26` scheitert auf befüllten Daten absichtlich. | bewusst | Ein verlorenes Volume verliert alle gespeicherten Trainings; eine fehlerhafte Migration lässt sich nicht zurückrollen. Backups einzuführen ist zugleich eine Datenschutzfrage (RI-02). | Vor jedem Deployment einen Dump ziehen; Backups nur zusammen mit einer Aufbewahrungsregel in ADR 0066 einführen. |

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
