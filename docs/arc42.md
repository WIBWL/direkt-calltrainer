# 1. Einführung und Ziele

## 1.1 Aufgabenstellung

Der Calltrainer ist ein KI-gestütztes Telefontraining. Eine KI-Persona simuliert den Gesprächspartner in Support-, Beratungs- und Preisgesprächen (F-03). Im Fokus stehen Kommunikation, Klarheit und Wirkung des Sprechenden, nicht Abschlussquoten oder kundenspezifisches Fachwissen (C-05).

Nach jedem Gespräch erhält der Nutzer ein qualitatives Wrap-up und gemessene Kennzahlen. Es gibt keinen Score. Jede Kennzahl führt zu ihren Belegen (ADR 0098). Dazu kommen:

- eigene und geteilte Szenarien, auch aus einem PDF (ADR 0058, ADR 0060)
- Folgeszenario und Rollentausch, aus einem Gespräch abgeleitet (ADR 0069, ADR 0070)
- Fokusziele und Szenario-Vorschläge (ADR 0076, ADR 0087)
- Historie, eine Fortschrittsansicht ohne Bewertung und beides als PDF (ADR 0064, ADR 0065, ADR 0093, ADR 0113)

## 1.2 Qualitätsziele

| Prio | Qualitätsziel | Bedeutung |
|---|---|---|
| 1 | Q-01 Genauigkeit und Nachvollziehbarkeit der Gesprächsanalyse | Befunde sind zutreffend und auf Gesprächsstellen rückführbar. |
| 2 | Q-02 Bedienbarkeit ohne Einarbeitung | Ein Erstnutzer startet ein Training ohne Anleitung. |
| 3 | Q-03 Echtzeitfähigkeit des Gesprächsflusses | Spracherkennung, Antwort und Sprachsynthese sind schnell genug für ein natürliches Gespräch. |

Datenschutz ist kein Qualitätsziel. Er ist eine nicht verhandelbare Randbedingung (C-04). Weitere Qualitätsanforderungen stehen in Kapitel 10.

## 1.3 Stakeholder

| Rolle | Erwartung |
|---|---|
| Pilotunternehmen A (Entwicklung, Support, Kundenkontakt) | Blinde Flecken im Sprechverhalten erkennen; einfache Bedienung; qualitatives Feedback statt Kennzahlen; kein vertrieblicher Fokus. |
| Pilotunternehmen B (CIO, technische Nutzer ohne Vertriebserfahrung) | Flüssiger sprechen, Einwände und Preisgespräche üben; visuelle Auswertung. |
| Umsetzungsteam | Klare Architektur- und Anforderungsgrundlage. |

# 2. Randbedingungen

| ID | Randbedingung | Quelle |
|---|---|---|
| C-01 | Die Sprache ist an die Persona gebunden; Szenarien sind sprachneutral (ADR 0043). Umgesetzt sind Deutsch und Englisch. | R-35 |
| C-02 | Nutzung am PC mit Headset (ADR 0007). | R-36 |
| C-03 | Nutzung am Smartphone (nicht unterstützt, ADR 0007). | R-37 |
| C-04 | Datenschutz nach DSGVO, begrenzt alle übrigen Ziele (Kapitel 8.1). | rechtlich |
| C-05 | Kein kundenspezifisches Fachwissen (ADR 0005). | R-40, R-41 |
| C-06 | Gespräche von kurzen Rückfragen bis zu einer Stunde. | R-03 |
| C-07 | Zielgruppe: Support- und Beratungsrollen, technische Nutzer ohne Vertriebserfahrung. | R-01, R-02 |
| C-08 | Anforderungen werden mit beiden Pilotunternehmen abgestimmt. | R-48 |
| C-09 | Priorisierung nach MoSCoW. | Konvention |
| C-10 | Anforderungen nach ISO/IEC/IEEE 29148, siehe [Anforderungsliste](initial-requirements.md) und [Feature-Katalog](features.md). | Konvention |

Aus dem Projektumfeld kommen weitere Vorgaben hinzu:

- Betrieb auf dem DiReKT-Host bei Hetzner, mit dem Stack in `direkt-infrastructure` (ADR 0108).
- Spracherkennung und Dialogmodell über das DiReKT-Gateway (ADR 0011).
- Anmeldung über den DiReKT-Keycloak (ADR 0009).
- HTTPS, weil das Mikrofon einen sicheren Kontext braucht.
- Images nur für amd64 (ADR 0047).

# 3. Kontextabgrenzung

## 3.1 Fachlicher Kontext

- **Nutzer:** führt simulierte Gespräche. Nach dem Gespräch erhält er das Transkript und, mit Einwilligung, ein Wrap-up mit Kennzahlen. Er verwaltet eigene Szenarien, Fokusziele und seine Daten.
- **Unternehmen (Mandant):** teilt Szenarien unter seinen Mitgliedern. Die Mitgliedschaft wird im Keycloak verwaltet (ADR 0060).
- **Persona:** simuliert den Anrufer, im Rollentausch die Seite, die abnimmt. Personas sind kuratiert, mit fester Sprache und Stimme.
- **Auswertung:** misst das Sprechverhalten deterministisch. Ein Modell deutet die Messungen im Wrap-up, erzeugt sie aber nicht (ADR 0049).

## 3.2 Technischer Kontext

| Partner | Schnittstelle | Inhalt |
|---|---|---|
| Browser | HTTPS-REST `/api`, WebSocket `/ws/session` | Audio in beide Richtungen; das Turn-Ende erkennt der Browser selbst (Silero-VAD, ADR 0036). |
| DiReKT-Gateway | OpenAI-kompatible API | Spracherkennung (Whisper) und Dialogmodell für Gespräch und Nachbereitung (ADR 0103). |
| KugelAudio | SDK, gepoolte WebSocket-Verbindung | Text der Persona hin, Audio zurück, ohne Rückfallebene (ADR 0044). |
| Keycloak | OIDC mit PKCE | Anmeldung; das Token liefert Nutzerkennung, Rolle und Organisation. |
| PostgreSQL | SQL | Alle gespeicherten Daten, nie Audio (ADR 0048). |
| Redis | RQ | Job-Kennung für das Wrap-up (ADR 0019). |

Stimme und Transkripte gehen nur an das Gateway. KugelAudio erhält nur den Text der Persona.

# 4. Lösungsstrategie

Die Begründungen stehen in den ADRs.

| Bereich | Entscheidung | ADR |
|---|---|---|
| Frontend | React + TypeScript (Vite), eigenes nginx-Image, API auf eigenem Host mit CORS | 0008, 0107 |
| Backend | Python, FastAPI | 0012 |
| Architekturstil | Modularer Monolith für den Echtzeitpfad, Worker für die Nachbereitung, drei Pakete in einem uv-Workspace | 0018, 0108 |
| Modelle | Ein OpenAI-kompatibles Gateway, ein Backend je Strecke, keine Umschalter | 0011, 0017, 0103 |
| Transport | Eine WebSocket-Verbindung je Session, gestreamtes Audio | 0033, 0044 |
| Persistenz | Eigenes PostgreSQL, SQLAlchemy, Alembic | 0010, 0025–0027 |
| Hintergrund | Redis + RQ | 0019 |
| Zugang | Keycloak mit PKCE, Client-Rolle, Kontingente je Konto | 0009, 0109 |
| Messung | Praat über Parselmouth | 0047 |
| Betrieb | Pflichteinstellungen aus Umgebung oder Datei, Logs auf stdout | 0105, 0106 |

**Q-03 (Echtzeit):** Die Kette überlappt an jeder Stelle. Die Antwort wird gestreamt und satzweise synthetisiert (ADR 0033, ADR 0044). Die Messung läuft parallel zur Spracherkennung (ADR 0048). Das Modell liest Notizen statt des ganzen Verlaufs (ADR 0071). Der Nutzer kann unterbrechen (ADR 0035). Nichts Blockierendes läuft auf dem Event-Loop.

**Q-01 (Nachvollziehbarkeit):** Messen und Deuten sind getrennt (ADR 0049). Es gibt keine erfundenen Normen (ADR 0004, ADR 0051); eine Ampel gibt es nur unter den Bedingungen von ADR 0078. Jede Kennzahl zeigt ihre Belege (ADR 0098). Nichts wird gegen die Persona gemessen.

**Q-02 (Bedienbarkeit):** Pflicht sind nur Persona und Szenario (ADR 0013). Der Ablauf ist eine einzige Übergangstabelle (ADR 0096). Während des Gesprächs gibt es keine Mitschrift (ADR 0014).

**C-04 (Datenschutz):** Gespeichert wird nur mit Einwilligung (ADR 0066). Nach sechs Monaten läuft die Speicherung ab (ADR 0067). Audio wird nie gespeichert (ADR 0048).

# 5. Bausteinsicht

```text
                          Browser
            ┌────────────────────────────────┐
            │  Frontend (React/TypeScript)   │
            └───────┬────────────────┬───────┘
          REST /api │                │ WebSocket /ws/session
                    ▼                ▼          OIDC ┌──────────┐
            ┌────────────────────────────────┐ ◄──── │ Keycloak │
            │        Backend (FastAPI)       │       └──────────┘
            │ API · Live-Gespräch · Löschung │ ── STT/LLM ──► DiReKT-Gateway
            └──┬──────────────┬──────────────┘ ── TTS ──────► KugelAudio
               │ Job          │ SQL                               ▲
               ▼              ▼                                   │ LLM
          ┌─────────┐   ┌────────────┐                            │
          │  Redis  │──►│ PostgreSQL │◄── Worker (Wrap-up) ───────┘
          └─────────┘   └────────────┘
        Backend und Worker importieren beide das Paket `shared`.
```

| Baustein | Verantwortung |
|---|---|
| Frontend | Trainingsablauf, Mikrofon und VAD, Wiedergabe, Darstellung von Wrap-up, Historie und Fortschritt; beide PDFs. |
| Backend | REST-API und Live-Gespräch: je Turn STT, LLM, TTS und Messung. Speichert die Session, stellt den Wrap-up-Job ein und verwaltet Bibliothek, Einwilligung, Löschung und Aufbewahrung. |
| Worker | Schreibt das Wrap-up und misst die fordernden Gesprächsabschnitte (ADR 0081). |
| Shared | Schema, Migrationen, Seed-Daten, Messcode und Kennzahlen, LLM-Client, Warteschlange, Sprachpakete, Einstellungen. |

`shared` importiert keines der anderen Pakete, und Backend und Worker importieren einander nicht. Der Job wird über seinen Namen eingestellt. Die Gesprächsschleife importiert aus der Auswertung nur `acoustics` (ADR 0090, ADR 0108).

# 6. Laufzeitsicht

## 6.1 Ein Trainingsgespräch

1. Der Nutzer wählt Persona und Szenario. Erst der Start öffnet den WebSocket mit `session.start` und dem Token.
2. Nach Mikrofontest und Ausgangslage klingelt das Telefon. Der Nutzer nimmt ab und meldet sich zuerst (ADR 0110). Im Rollentausch nimmt die Persona ab (ADR 0042).
3. Je Turn erkennt die VAD das Ende des Redebeitrags. Das Backend misst die Aufnahme parallel zur Spracherkennung, streamt die Antwort und synthetisiert sie satzweise.
4. Unterbricht der Nutzer, verstummt die Wiedergabe, und im Verlauf bleibt nur das Gehörte (ADR 0035).
5. Das Gespräch endet durch Auflegen, Verabschiedung oder Ausfall einer Strecke. Der Client erhält das Transkript.

## 6.2 Speicherung und Wrap-up

1. Mit Einwilligung wird die Session samt Messungen und einer Job-Zeile in einer Transaktion geschrieben (ADR 0034, ADR 0066).
2. Der Worker schreibt das Wrap-up mit einem Modellaufruf und misst die fordernden Abschnitte.
3. Der Client fragt den Status ab, bis das Wrap-up vorliegt. Ein gescheiterter Job lässt sich neu anstoßen.

## 6.3 Abgeleitete Übungen

Unter dem Wrap-up erzeugt je ein Knopfdruck ein Folgeszenario oder einen Rollentausch als eigenes Szenario (ADR 0069, ADR 0070, ADR 0100). Daneben bietet die App bis zu zwei bestehende Szenarien an (ADR 0087).

## 6.4 Historie, Fortschritt, Löschung

Historie und Fortschritt lesen dieselbe Liste eigener Sessions; der Fortschritt wird im Browser berechnet (ADR 0064, ADR 0112). Alle Löschpfade laufen über `deletion.remove` (ADR 0102). Der Aufbewahrungslauf läuft täglich (ADR 0067).

# 7. Verteilungssicht

```text
 Browser ──HTTPS──► calltrainer.efre-direkt.de ─────────► calltrainer-frontend (nginx)
    ├──HTTPS/WSS──► calltrainer-backend.efre-direkt.de ─► calltrainer-backend ──► KugelAudio
    └──HTTPS──► keycloak.efre-direkt.de                        │      └──► litellm (Gateway)
                         calltrainer-db, calltrainer-redis ◄───┴── calltrainer-worker
```

Der Stack läuft auf dem DiReKT-Host bei Hetzner hinter Traefik, definiert in `direkt-infrastructure`. Dieses Repository baut nur die drei Images (ADR 0108). WUD rollt jedes neue `latest` aus. Die Inbetriebnahme beschreibt [Deployment](deployment.md).

- Das Backend läuft in **einem** gunicorn-Prozess, weil die Kontingente im Prozess gezählt werden (ADR 0109). Die Kapazität ist nicht gemessen.
- Fällt der Worker aus, laufen Gespräche weiter, und Wrap-ups bleiben in der Warteschlange.
- Es gibt keine Backups (RI-02).
- Lokal laufen die Anwendungen auf dem Rechner. `dev-compose.yaml` startet nur Postgres, Redis und Keycloak.

# 8. Querschnittliche Konzepte

## 8.1 Datenschutz

- Gespeichert wird nur mit Einwilligung, geprüft in der schreibenden Transaktion. Schlägt die Prüfung fehl, wird nicht gespeichert (ADR 0066).
- Audio wird nie gespeichert (ADR 0048), und Gesprochenes wird nie geloggt.
- Daten laufen nach sechs Monaten ab. Der Nutzer kann einzelne Trainings löschen, alles durch Widerruf löschen und exportieren (ADR 0066, ADR 0067).
- Das Einwilligungsprotokoll bleibt erhalten (ADR 0068). Fokusziele sind eine Einstellung und keine Trainingsdaten (ADR 0076).

## 8.2 Sicherheit und Eigentum

- Jede Route verlangt ein Keycloak-Token und die Client-Rolle `calltrainer-user`. Für den WebSocket reist das Token in der ersten Nachricht (ADR 0009, ADR 0109).
- Eigentum ist eine Bedingung in der Abfrage. Auf eine fremde Ressource antwortet die API mit 404, nie mit 403. Nach außen geht nur die `extern_id` (ADR 0050).
- Geteilte Szenarien sind nur im eigenen Unternehmen sichtbar (ADR 0060). Selbst verfasster Text wird beim Schreiben bereinigt (ADR 0059).
- Kontingente je Konto, Grenzen für Request-Bodies, PDF-Lesen im Kindprozess und eine CSP (ADR 0109).

## 8.3 Feedback und Bewertung

Kein Score, keine Zielbereiche und keine Wertung über Gespräche hinweg (ADR 0004, ADR 0051, ADR 0065). Ampeln gibt es nur auf Einordnungen im einzelnen Gespräch (ADR 0078). Einordnungen werden bei jedem Lesen abgeleitet (ADR 0091). Was sich nicht als Zahl sagen lässt, schreibt das Modell als gekennzeichneten Absatz (ADR 0056, ADR 0079).

## 8.4 Benutzerführung und Barrierefreiheit

Pflicht sind nur Persona und Szenario. Der Ablauf ist eine Übergangstabelle (ADR 0096). Bewegung folgt der Systemeinstellung, der Ton lässt sich abschalten, und Diagramme tragen ihre Zahlen auch als Text (ADR 0097). Die BITV-Selbstbewertung steht aus.

## 8.5 Prompt und Modellverhalten

Prompts sind englisch, und Sprachpakete liefern, was nicht englisch sein kann (ADR 0043). Schutzmechanismen gegen Wiederholung und Gesprächsende stecken im Code (ADR 0037, ADR 0038, ADR 0073). Nie in einen Prompt gelangen das Briefing des Nutzers, das Rollentausch-Briefing, die Kategorie und der Zweck eines Folgeszenarios.

## 8.6 Persistenz

Bezeichner sind englisch (ADR 0026, ADR 0057). Constraint-Namen folgen einer Konvention, Vokabulare sind CHECK-Constraints (ADR 0053), und jeder Fremdschlüssel ist indiziert (ADR 0052). Das Backend migriert und befüllt die Datenbank beim Start. Der Aufrufer öffnet die Transaktion (ADR 0099).

## 8.7 Testbarkeit

Jede Testdatei nennt das Feature oder den ADR, den sie belegt. Die Backend-Tests fälschen STT, LLM und TTS; Persistenztests nutzen eine Wegwerf-Datenbank. Das Frontend prüfen ein strikter Compiler, eine schmale Vitest-Suite und die Hook-Regeln (ADR 0094).

# 9. Architekturentscheidungen

Jede Entscheidung steht als ADR in `docs/adr/`, in der Navigation unter *Adr* (ADR 0000).

# 10. Qualitätsanforderungen

| ID | Qualität | Beschreibung | Herkunft |
|---|---|---|---|
| Q-01 | Nachvollziehbarkeit | Befunde sind zutreffend und auf Gesprächsstellen rückführbar. | R-19, R-25, R-26 |
| Q-02 | Bedienbarkeit | Ein Erstnutzer startet ohne Anleitung. | R-32–R-34 |
| Q-03 | Echtzeit | Keine wahrnehmbare Verzögerung im Gespräch. | Systementwurf |
| Q-04 | Qualitative Bewertung | Kein einzelner Zahlenwert. | R-21 |
| Q-05 | Regelmäßige Rückmeldung | Fortlaufende Nutzung bringt fortlaufend Rückmeldung. | R-27 |
| Q-06 | Flexible Trainingssituation | Verschiedene Gesprächsarten und -längen. | R-03, R-09 |
| Q-07 | Zuverlässigkeit | Ein Komponentenausfall bricht das Gespräch nicht unbemerkt ab. | Systementwurf |
| Q-08 | Austauschbarkeit | Modelle sind ohne Codeänderung wechselbar. | Systementwurf |
| Q-09 | Datenschutz | Sprachdaten bleiben im dokumentierten Rahmen. | C-04 |

| Nr. | Qualität | Szenario | Reaktion |
|---|---|---|---|
| QS-01 | Q-01 | Ein Nutzer will wissen, woher eine Kennzahl kommt. | Jede Kennzahl führt zu ihren gespeicherten Belegen (ADR 0098). |
| QS-02 | Q-01 | Eine Einordnung trägt eine Ampel. | Die Stufe steht in Worten da, die ganze Skala ist sichtbar, und die Farbe kommt aus dem Backend (ADR 0078). |
| QS-03 | Q-02 | Ein Nutzer will ein Gespräch beginnen. | Es gibt nur einen Weg hinein: den eigenen Knopfdruck (ADR 0096). |
| QS-04 | Q-03 | Die Persona antwortet mit mehreren Sätzen. | Die Wiedergabe beginnt mit dem ersten Satz (ADR 0033). |
| QS-05 | Q-03 | Der Nutzer unterbricht. | Die Wiedergabe verstummt, und gespeichert wird nur das Gehörte (ADR 0035). |
| QS-06 | Q-07 | Eine Modellstrecke fällt aus. | Ein Wiederholungsversuch, dann ein sauberes Ende, nie eine andere Stimme (ADR 0016, ADR 0103). |
| QS-07 | Q-07 | Der Worker läuft nicht. | Gespräche laufen weiter, und der Job ist neu anstoßbar. |
| QS-08 | Q-08 | Ein anderes Modell soll eingesetzt werden. | Eine Konfigurationsänderung; die Parameter müssen neu gemessen werden (ADR 0103). |
| QS-09 | Q-09 | Keine oder widerrufene Einwilligung. | Nichts wird gespeichert (ADR 0066). |
| QS-10 | Q-09 | Zugriff auf eine fremde Session. | 404 (ADR 0050). |

# 11. Risiken und technische Schulden

## 11.1 Risiken

| Nr. | Risiko | Gegenmaßnahme |
|---|---|---|
| RI-01 | Latenz der Modellstrecken; jede hat genau ein Backend. | Gestreamte Verarbeitung. Offen sind Messpunkte je Teilstrecke unter Last. |
| RI-02 | Datenschutz: Die Datenschutzerklärung ist nicht vom Datenschutzbeauftragten geprüft, und es gibt keine Backups. | Prüfung vor der Nutzung außerhalb der Pilotgruppe; Backups nur mit Aufbewahrungsregel in ADR 0066. |
| RI-04 | Ohne kundenspezifische Fachlichkeit wirken Gespräche oberflächlich. | Eigene Szenarien, auch aus PDFs; Feedback der Pilotunternehmen einholen. |
| RI-05 | Maschinelles Feedback wirkt unpassend oder demotivierend. | Wirkung statt Urteil, Belege zu jeder Zahl, gekennzeichnete Modell-Absätze. |
| RI-06 | Komplexe Bedienung senkt die Akzeptanz. | Minimaler Pflichtumfang. Usability-Tests stehen aus. |

## 11.2 Technische Schulden

| Nr. | Schuld | Abtragen durch |
|---|---|---|
| TS-02 | Kein Vorher-Nachher-Vergleich für Prompt-Änderungen; `play_scenarios.py` zeigt nur kaputte Paarungen. | Vergleich zweier Stände über N Läufe. |
| TS-04 | Persistenztests überspringen sich ohne Postgres. | Mindestzahl ausgeführter Tests erzwingen. |
| TS-05 | Unter `npm run dev` läuft kein Gespräch (Vite und onnxruntime-web). | Ursache klären. Bis dahin `build:watch` mit `preview` verwenden. |
| TS-06 | Migrationen können kollidieren, ohne dass git einen Konflikt meldet. | Nach jedem Merge die Zahl der Alembic-Heads prüfen. |
| TS-09 | Python ist auf 3.12 festgelegt (SQLAlchemy 2.0.36). | ORM anheben. |
| TS-10 | LF ist nur für Shell-Skripte festgelegt. | `.gitattributes` auf alle Textdateien ausweiten. |
| TS-15 | Die Schwellen für Unterbrechungen und Verzögerungslaute sind unbelegte Arbeitswerte. | Mit Pilotdaten kalibrieren. |
| TS-16 | Die Sampling-Parameter sind auf Qwen3 abgestimmt, konfiguriert ist Gemma. | Gegen das eingesetzte Modell messen. |
| TS-17 | Keine Backups. Das Downgrade über `d7f41c9b3a26` scheitert auf befüllten Daten. | Dump vor jedem Deployment; Backups mit Aufbewahrungsregel. |

# 12. Glossar

Die Fachbegriffe stehen in [`CONTEXT.md`](https://github.com/WIBWL/direkt-calltrainer/blob/main/CONTEXT.md).
