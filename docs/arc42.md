# Einführung und Ziele

## Aufgabenstellung

„Train to Call with AI" ist ein KI-gestütztes Telefontraining-System, das als Gesprächspartner (Gegenpart) in simulierten Kundengesprächen agiert. Nutzer können damit im Telefonie-Kontext trainieren, mit einer KI-Persona zu kommunizieren, z. B. in Support-Situationen oder beratenden Projektgesprächen (F-03).

Im Gegensatz zu klassischen Verkaufstrainern liegt der Fokus nicht auf Abschlussquoten oder Verhandlungstechnik, sondern auf Kommunikation, Klarheit und Wirkung des Sprechenden – ohne dass umfangreiche kundenspezifische Fachkenntnisse vorausgesetzt werden (F-06):

- Kommunikation, Klarheit und Wirkung des Sprechenden
- Erkennung von Sprechverhalten (Intonation, Tempo, Lautstärke, Artikulation)
- Vermeidung von überlangen/überkomplexen Erklärungen

Nach jedem Trainingsgespräch erhält der Nutzer ein qualitatives Wrap-up mit konkreten Verbesserungsvorschlägen statt eines reinen Scores.

## Qualitätsziele

### Verständlichkeit & Wirkung

**Priorität:** 1

Kernziel des Trainings ist es, dem Nutzer zu helfen, klarer und wirkungsvoller zu kommunizieren, nicht Fachwissen zu prüfen.

### Einfache, intuitive Bedienbarkeit

**Priorität:** 2

Laut Stakeholder-Interview ist eine überladene UI ein zentrales Nutzungshemmnis. Pflichteinstellungen sollen minimal und übersichtlich sein.

### Echtzeitfähigkeit

**Priorität:** 3

Ein natürlicher Gesprächsfluss erfordert Antworten der KI in Echtzeit.

### Datenschutzkonformität (DSGVO)

**Priorität:** 4

Sprachaufzeichnungen und personenbezogene Daten müssen rechtskonform verarbeitet werden.

### Qualitatives statt quantitatives Feedback

**Priorität:** 5

Der Stakeholder lehnt eine Reduktion auf einen einzelnen Score explizit ab. Feedback muss differenziert und nachvollziehbar sein.

## Stakeholder

### Fachlicher Ansprechpartner / Pilotnutzer

**Kontakt:** Nicolas Heyne (Solox GmbH, Entwicklung/Kundenkontakt)

Möchte eigene „blinde Flecken" im Sprechverhalten erkennen. Legt Wert auf einfache Bedienung und qualitatives Feedback statt KPIs.

### Support-Mitarbeitende

**Kontakt:** Solox GmbH

Nutzen das Training für kurze, lösungsorientierte Kundengespräche (z. B. telefonische Problemklärung).

### Entwicklungs-/Projektteam

**Kontakt:** Solox GmbH

Nutzen das Training für längere, beratende Gesprächssituationen (z. B. Schnittstellenthemen, Weiterentwicklung).

### Umsetzungsteam

**Kontakt:** Projektgruppe (intern)

Entwickelt das System iterativ, benötigt klare Architektur- und Anforderungsgrundlage.

# Randbedingungen

## Technische Randbedingungen

### Echtzeitverarbeitung

**Quelle:** F-21

Das Gespräch muss in Echtzeit verarbeitet werden, um einen natürlichen Gesprächsfluss zu ermöglichen.

### Nutzung am PC mit Headset

**Quelle:** F-19

Das Training muss primär am PC mit Headset durchführbar sein.

### Mobile Nutzung (optional)

**Quelle:** F-20

Eine Nutzung am Mobiltelefon ist möglich, aber nicht verpflichtend für den MVP.

## Organisatorische Randbedingungen

### Sprache Deutsch

Das Training muss auf Deutsch stattfinden (F-18). Englisch ist zunächst explizit kein Ziel.

### Kein Aufbau einer kundenspezifischen Wissensbasis

Fachliches Know-how zu einzelnen Kunden/Systemen wird bewusst nicht abgebildet. Fokus liegt auf Kommunikation statt Fachlichkeit.

### Kein Fokus auf klassische Vertriebs-KPIs

Abschlussquote/Umsatz sind explizit keine Erfolgsmetriken.

### Enge Rückkopplung mit Pilotkunde Solox

Weitere Anforderungen und Feedback sollen gebündelt mit Nicolas Heyne abgestimmt werden (z. B. via Teams).

## Konventionen

### Anforderungsmanagement nach MoSCoW

Anforderungen werden nach Must/Should/Could/Won't priorisiert (bereits in der Feature-Spezifikation etabliert).

### Datenschutz nach DSGVO

Alle Daten, insbesondere Sprachaufzeichnungen und personenbezogene Daten, müssen DSGVO-konform verarbeitet werden (F-22).

# Kontextabgrenzung

## Fachlicher Kontext

Der fachliche Kontext beschreibt, mit welchen Kommunikationspartnern das System aus fachlicher/inhaltlicher Sicht interagiert.

### Nutzer (Support-Mitarbeitende / Projekt- & Entwicklungsmitarbeitende)

Führt ein simuliertes Telefongespräch mit der KI-Persona, sowohl in kürzeren Support-Szenarien als auch in längeren Beratungsgesprächen (F-03, F-05). Gibt Sprache ein, erhält Sprache/Antworten der KI zurück sowie im Anschluss ein qualitatives Wrap-up mit Verbesserungsvorschlägen.

### KI-Gesprächspartner (Persona)

Simuliert einen externen Kunden im Gespräch, u. a. mit kostenkritischer/preisbewusster Reaktion (F-02). Die Persona kann aus einer erweiterbaren Persona-Bibliothek stammen (F-04). Reagiert auf Inhalt, Tonfall und Gesprächsführung des Nutzers.

### Feedback-/Auswertungskomponente

Erstellt nach Gesprächsende das qualitative Wrap-up (F-09) inkl. konkreter Verbesserungsvorschläge (F-10), basierend auf der Analyse des Sprechverhaltens (F-07, F-08).

## Technischer Kontext

Der technische Kontext beschreibt die technischen Schnittstellen und Kanäle, über die die fachliche Kommunikation stattfindet.

### Nutzer-Endgerät (PC + Headset)

**Kanal / Schnittstelle:** Audio-Ein-/Ausgabe (Mikrofon, Lautsprecher/Headset)

Primärer Zugangsweg im MVP (F-19). Erfasst Sprachsignal des Nutzers, gibt Sprachausgabe der KI wieder.

### Spracherkennung (Speech-to-Text)

**Kanal / Schnittstelle:** Interne Schnittstelle

Wandelt die gesprochene Nutzereingabe in Text um, als Grundlage für Sprachanalyse (F-07) und KI-Antwortgenerierung.

### Sprachsynthese (Text-to-Speech)

**Kanal / Schnittstelle:** Interne Schnittstelle

Wandelt die KI-Antwort in gesprochene Sprache um, um ein reales Telefongespräch zu simulieren.

### KI-/Sprachmodell-Backend

**Kanal / Schnittstelle:** API (z. B. LLM-Anbieter)

Generiert die inhaltlichen Antworten der simulierten Persona sowie das Wrap-up/Feedback am Ende des Gesprächs.

### Datenspeicher

**Kanal / Schnittstelle:** Interne Schnittstelle

Speichert ggf. Gesprächsaufzeichnungen (F-12, SHOULD) und Fortschrittsdaten (F-13, COULD) DSGVO-konform (F-22).

# Lösungsstrategie

*TODO: Zentrale Technologie-Entscheidungen und architektonischer Ansatz zur Erreichung der Qualitätsziele (z. B. Echtzeit-Audio-Pipeline, LLM-basierte Feedback-Generierung).*

# Bausteinsicht

## Whitebox Gesamtsystem

*TODO: Komponenten der obersten Ebene (z. B. Engine für Anrufsimulation, Sprachanalyse, Feedback-Engine, Frontend).*

*\<Übersichtsdiagramm\>*

*Begründung: \<Erläuternder Text\>*

*Enthaltene Bausteine: \<Beschreibung der enthaltenen Bausteine (Blackboxen)\>*

*Wichtige Schnittstellen: \<Beschreibung wichtiger Schnittstellen\>*

## Ebene 2

*TODO: Detaillierung der einzelnen Bausteine aus Kapitel 5.1.*

## Ebene 3

*TODO: Detaillierung der einzelnen Bausteine aus Kapitel 5.2.*

# Laufzeitsicht

*Hinweis: Die Laufzeitsicht baut methodisch auf der Bausteinsicht (Kapitel 5) auf, die noch nicht final ausgearbeitet ist, da hierfür noch technische Grundentscheidungen (u. a. LLM-Anbieter, konkrete Systemarchitektur, siehe Kapitel 4) ausstehen. Die folgenden Szenarien sind daher auf funktionaler Ebene beschrieben und noch nicht an konkrete Bausteine/Komponenten gebunden. Sobald Kapitel 4 und 5 konkretisiert sind, sollten die Szenarien entsprechend angepasst und die Bausteine referenziert werden.*

## Szenario 1: Start und Ablauf eines Trainingsgesprächs

- Der Nutzer startet ein neues Training und wählt (minimal) eine Persona bzw. ein Szenario aus (z. B. Support-Fall oder Beratungsgespräch, F-03, F-16/F-17: möglichst wenige Pflichtangaben).
- Das System initiiert die Gesprächssimulation: Der Nutzer spricht über PC/Headset, die Sprache wird in Echtzeit in Text umgewandelt (Speech-to-Text).
- Das KI-Backend generiert eine Antwort der simulierten Persona (F-01, F-02), die per Text-to-Speech in gesprochene Sprache umgewandelt und ausgegeben wird.
- Dieser Zyklus (Sprechen → Erkennen → Antworten → Aussprechen) wiederholt sich fortlaufend, bis der Nutzer das Gespräch beendet. Sowohl kurze Support-Calls als auch längere Beratungsgespräche werden dabei unterstützt (F-05).

Besonderheiten: Der gesamte Zyklus muss in Echtzeit ablaufen (F-21), da Verzögerungen den natürlichen Gesprächsfluss stören. Parallel zur eigentlichen Konversation läuft die Analyse des Sprechverhaltens (Szenario 2) mit.

## Szenario 2: Analyse des Sprechverhaltens während des Gesprächs

- Während der Nutzer spricht, analysiert die Analyse-Komponente laufend Intonation, Sprechtempo, Lautstärke und Artikulation (F-07).
- Zusätzlich wird erkannt, ob ein Thema zu lang, zu kompliziert oder mit zu vielen Informationen erklärt wird (F-08).
- Auffälligkeiten werden für das spätere Wrap-up gesammelt, nicht sofort während des Gesprächs unterbrochen oder angezeigt.

Besonderheiten: Diese Analyse läuft parallel zur eigentlichen Gesprächssimulation (Szenario 1), ohne den Gesprächsfluss zu unterbrechen. Die gesammelten Daten dienen als Grundlage für Szenario 3.

## Szenario 3: Erstellung des Wrap-ups nach Gesprächsende

- Nach Beendigung des Gesprächs durch den Nutzer wertet die Feedback-Komponente die gesammelten Analyseergebnisse aus Szenario 2 aus.
- Es wird eine qualitative Zusammenfassung (Wrap-up) erstellt – keine reine Zahl/Score (F-09).
- Konkrete, umsetzbare Verbesserungsvorschläge werden formuliert und nach Möglichkeit mit konkreten Gesprächsstellen verknüpft (F-10).
- Das Wrap-up wird dem Nutzer angezeigt.

Besonderheiten: Die Qualität dieses Szenarios ist zentral für die Akzeptanz des Tools (siehe Qualitätsziele, Kapitel 1). Ein optionaler Score (F-14, COULD) kann ergänzend angezeigt werden, ersetzt aber nie das qualitative Feedback.

## Szenario 4: Aufzeichnung und langfristige Nutzung (optional/should)

- Sofern vorgesehen (F-12, SHOULD), wird das Gespräch aufgezeichnet und dokumentiert.
- Die Aufzeichnung ermöglicht dem Nutzer eine spätere, fundiertere Reflexion über die reine Erinnerung hinaus.
- Bei mehrteiligen Projektgesprächen (F-23, COULD) kann diese Aufzeichnung über mehrere Termine hinweg referenziert werden.
- Alle gespeicherten Daten müssen DSGVO-konform verarbeitet werden (F-22).

Besonderheiten: Dieses Szenario ist für den MVP nicht zwingend erforderlich (SHOULD/COULD), aber relevant für die kontinuierliche Nutzung als Trainingsinstrument (F-11), die Herr Heyne explizit gewünscht hat.

# Verteilungssicht

## Infrastruktur Ebene 1

*TODO: Übersichtsdiagramm, Begründung, Qualitäts-/Leistungsmerkmale sowie Zuordnung von Bausteinen zu Infrastruktur ergänzen, sobald Kapitel 4/5 vorliegen.*

## Infrastruktur Ebene 2

*TODO: Detaillierung einzelner Infrastrukturelemente (Diagramm + Erläuterungen).*

# Querschnittliche Konzepte

Querschnittliche Konzepte betreffen mehrere Bausteine/Komponenten gleichzeitig und werden deshalb zentral dokumentiert statt in jedem Baustein wiederholt. Basierend auf dem Erstgespräch und der Feature-Liste lassen sich folgende Konzepte bereits jetzt beschreiben:

## Datenschutz und Datensicherheit

Da Sprachaufzeichnungen und personenbezogene Daten verarbeitet werden, muss das System durchgängig DSGVO-konform gestaltet sein (F-22). Dies betrifft insbesondere:

- Verarbeitung und Speicherung von Sprachdaten (Gesprächsaufzeichnungen, F-12)
- Speicherung von Fortschrittsdaten einzelner Nutzer (F-13)
- Übertragung von Sprachdaten an externe Dienste (z. B. Speech-to-Text-, Text-to-Speech- oder LLM-APIs)

*Offene Punkte: Wo werden Daten verarbeitet/gespeichert (EU-Hosting)? Wie lange werden Aufzeichnungen aufbewahrt? Wird eine Einwilligung des Nutzers eingeholt? Diese Fragen sollten spätestens mit Kapitel 4 (Lösungsstrategie) konkretisiert werden.*

## Umgang mit Feedback und Bewertung

Da Gespräche laut Herrn Heyne subjektiv wahrgenommen werden können, sollte das Feedback-Konzept durchgängig folgende Prinzipien verfolgen (gilt für alle Komponenten, die Feedback erzeugen oder anzeigen):

- Kein reiner Score als alleinige Bewertung (F-09)
- Konkrete, nachvollziehbare Verbesserungsvorschläge statt abstrakter Metriken (F-10)
- Optionaler Score nur ergänzend, nie ersetzend (F-14)

## Benutzerführung und UI-Konsistenz

Gilt übergreifend für alle Bildschirme/Interaktionspunkte des Systems:

- Pflichteinstellungen vor einem Training werden auf ein Minimum reduziert und deutlich sichtbar dargestellt (F-16, F-17)
- Zusatz- und Spezialoptionen werden getrennt und weniger prominent angeboten (F-16)
- Einfache, intuitive Bedienung ohne Einarbeitungsaufwand (F-15)

## Echtzeitverarbeitung

Betrifft alle Komponenten, die am Gesprächsfluss beteiligt sind (Spracherkennung, KI-Antwortgenerierung, Sprachsynthese):

- Durchgängige Anforderung an geringe Latenz, um einen natürlichen Gesprächsfluss zu ermöglichen (F-21)
- Dieses Konzept wird bei der technischen Umsetzung aller Echtzeit-relevanten Bausteine berücksichtigt werden müssen (relevant für Kapitel 4/5)

# Architekturentscheidungen

*Hinweis: Architekturentscheidungen (ADRs) dokumentieren normalerweise konkrete technische Entscheidungen aus Kapitel 4 (Lösungsstrategie) im Detail, mit Begründung und Alternativen. Da Kapitel 4 noch nicht ausgearbeitet ist, sind hier nur die grundsätzlichen/fachlichen Entscheidungen erfasst, die bereits aus dem Erstgespräch klar hervorgehen. Technische Architekturentscheidungen (z. B. LLM-Anbieter, Speech-to-Text-/Text-to-Speech-Technologie, Hosting-Modell) fehlen noch und sollten nach Ausarbeitung von Kapitel 4 ergänzt werden.*

Bereits getroffene fachliche Grundsatzentscheidung: Personas werden nicht als feste, einmalige Konfiguration umgesetzt, sondern als erweiterbare Kundenpersona-Bibliothek angelegt (F-04), sodass zukünftig weitere Persönlichkeitstypen ergänzt werden können, ohne die Kernarchitektur zu verändern.

# Qualitätsanforderungen

Dieses Kapitel konkretisiert die Qualitätsziele aus Kapitel 1 in überprüfbare Anforderungen. Häufig wird dafür ein Qualitätsbaum sowie konkrete Szenarien nach dem Muster „Stimulus → Reaktion" verwendet.

## Qualitätsbaum (Übersicht)

Die zentralen Qualitätsziele aus Kapitel 1, heruntergebrochen auf konkretere Teilaspekte:

- Verständlichkeit & Wirkung – Erkennung von Sprechverhalten (Intonation, Tempo, Lautstärke, Artikulation); Erkennung von zu komplexen/langen Erklärungen
- Benutzbarkeit – Einfache, intuitive Bedienung ohne Einarbeitung; minimale, klar sichtbare Pflichteinstellungen
- Performance – Echtzeitfähigkeit des Gesprächsflusses
- Datenschutz – DSGVO-Konformität aller Sprach- und Personendaten
- Feedback-Qualität – Qualitative statt rein quantitative Bewertung; konkrete, umsetzbare Verbesserungsvorschläge
- Flexibilität der Trainingssituation – Unterstützung unterschiedlicher Szenario-Typen und variabler Gesprächslängen (F-03, F-05)

## Qualitätsszenarien

*Hinweis: Die nachfolgenden Qualitätsszenarien beschreiben die Qualitätsziele derzeit auf qualitativer Ebene und sind noch nicht durchgängig messbar formuliert. Konkrete Schwellwerte und Messpunkte setzen voraus, dass die offenen Technologieentscheidungen (LLM-Anbieter, STT/TTS-Technologie, Hosting-Modell) getroffen sind, da sich Messpunkte an den daraus resultierenden Architekturgrenzen ergeben. Die Szenarien werden nach Klärung dieser Entscheidungen auf Testbarkeit überarbeitet und um überprüfbare Kriterien ergänzt. Dies betrifft insbesondere F-21 (Latenz), dessen Zielkorridor derzeit noch nicht belastbar bestimmt werden kann.*

### Verständlichkeit & Wirkung

#### Sprechverhalten erkennen

**Stimulus:** Nutzer spricht während eines Trainingsgesprächs mit auffälliger Lautstärke oder Sprechtempo

**Erwartete Reaktion:** System erfasst dies und berücksichtigt es im späteren Wrap-up (F-07)

#### Überkomplexe Erklärung

**Stimulus:** Nutzer erklärt einen Sachverhalt sehr lang oder mit vielen Informationen

**Erwartete Reaktion:** System erkennt dies und weist im Wrap-up konkret darauf hin (F-08)

### Benutzbarkeit

#### Erststart ohne Einarbeitung

**Stimulus:** Neuer Nutzer öffnet das Tool zum ersten Mal

**Erwartete Reaktion:** Nutzer kann ohne Anleitung ein Training starten (F-15)

#### Minimale Pflichtangaben

**Stimulus:** Nutzer möchte ein Training starten

**Erwartete Reaktion:** Nur notwendige Einstellungen werden abgefragt; Spezialoptionen sind separat und unauffällig (F-16, F-17)

### Performance

#### Echtzeit-Antwort

**Stimulus:** Nutzer spricht einen Satz im simulierten Gespräch

**Erwartete Reaktion:** KI antwortet ohne wahrnehmbare Verzögerung, sodass ein natürlicher Gesprächsfluss entsteht (F-21)

### Datenschutz

#### Verarbeitung von Sprachdaten

**Stimulus:** Sprachdaten werden erfasst, übertragen oder gespeichert

**Erwartete Reaktion:** Verarbeitung erfolgt durchgehend DSGVO-konform (F-22)

### Feedback-Qualität

#### Gesprächsende

**Stimulus:** Nutzer beendet ein Trainingsgespräch

**Erwartete Reaktion:** System liefert ein qualitatives Wrap-up mit konkreten Verbesserungsvorschlägen statt eines reinen Scores (F-09, F-10)

### Flexibilität der Trainingssituation

#### Szenario-Auswahl

**Stimulus:** Nutzer startet ein Training und wählt einen Gesprächskontext (Support vs. Beratung)

**Erwartete Reaktion:** System stellt passende Szenario-Typen bereit und passt Ablauf/Dauer entsprechend an (F-03, F-05)

# Risiken und technische Schulden

Da die technische Lösungsstrategie (Kapitel 4) noch nicht final festgelegt ist, sind einige Risiken hier bewusst allgemeiner formuliert und sollten nach Konkretisierung von Kapitel 4/5 präzisiert werden.

## Risiken

### Echtzeitfähigkeit von LLM-/Sprach-APIs

Die Kombination aus Speech-to-Text, LLM-Antwortgenerierung und Text-to-Speech muss in Echtzeit ablaufen (F-21). Externe APIs können Latenzschwankungen aufweisen, die einen natürlichen Gesprächsfluss beeinträchtigen.

*Mögliche Gegenmaßnahme: Frühzeitige Latenz-Tests mit den infrage kommenden Anbietern vor finaler technischer Festlegung (Kapitel 4).*

### Fehlende kundenspezifische Fachlichkeit

Der bewusste Verzicht auf eine kundenspezifische Wissensbasis (siehe Kapitel 9) vereinfacht die Umsetzung, könnte aber dazu führen, dass Gespräche für erfahrene Nutzer wie Herrn Heyne zu oberflächlich oder unrealistisch wirken, wenn Fachinhalte fehlen.

*Mögliche Gegenmaßnahme: Frühes Nutzerfeedback (z. B. durch Herrn Heyne als Pilotnutzer) einholen, ob der Fokus auf Kommunikation ohne Fachtiefe im Trainingsalltag als ausreichend realistisch empfunden wird.*

### Subjektivität von Feedback

Herr Heyne wies selbst darauf hin, dass Gespräche subjektiv wahrgenommen werden. Ein KI-generiertes qualitatives Feedback (F-09, F-10) könnte von Nutzern als unpassend, ungenau oder demotivierend empfunden werden, wenn es nicht sorgfältig formuliert ist.

*Mögliche Gegenmaßnahme: Iterative Verfeinerung der Feedback-Formulierung basierend auf echtem Nutzerfeedback; ggf. Tonalität und Formulierungsrichtlinien für die Feedback-Komponente definieren.*

### Geringe Akzeptanz bei komplexer Bedienung

Laut Erstgespräch ist eine unklare oder überladene Benutzeroberfläche ein zentrales Nutzungshemmnis. Wird dies im MVP nicht ausreichend beachtet, sinkt die Akzeptanz bei den Mitarbeitenden erheblich.

*Mögliche Gegenmaßnahme: Frühzeitige Usability-Tests, Fokus auf minimale Pflichteinstellungen (F-16, F-17) bereits im ersten Prototyp.*

### Unklare Datenschutz-Umsetzung

DSGVO-Konformität (F-22) ist eine MUST-Anforderung, aber die konkrete technische Umsetzung (Hosting-Ort, Speicherdauer, Einwilligungsprozesse) ist noch nicht festgelegt.

*Mögliche Gegenmaßnahme: Datenschutzkonzept möglichst parallel zur technischen Lösungsstrategie (Kapitel 4) erarbeiten, nicht erst nachträglich.*

## Technische Schulden

Aktuell keine, da sich das Projekt noch in der Konzeptionsphase befindet und noch keine Implementierung begonnen wurde.

# Glossar

| Begriff | Definition |
|---|---|
| TODO | TODO |
