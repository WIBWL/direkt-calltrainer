# Dashboard-Konzept (F-13)

Dieses Dokument legt fest, **was** das Dashboard zeigt und **warum**. Die
Rechenlogik einzelner Kennzahlen und Auswertungen wird hier bewusst nicht
ausgearbeitet, sondern nur benannt, wo sie gebraucht wird.

**Umsetzungsstand:** Stufe 1 ist gebaut und liegt unter `/fortschritt`, über die
volle Breite der Anwendung (1440 px, Kopfzeile mitgeführt). Der Bildschirm
selbst ist `frontend/src/components/ProgressView.tsx`, die Detailebene
`ProgressMetricView.tsx`, der Rechenteil `frontend/src/utils/progressStats.ts`.
Er greift ausschließlich auf echte, gespeicherte Werte zu und kommt ohne neuen
Endpunkt aus, weil `GET /api/sessions` die Messwerte je Sitzung bereits
mitliefert.

Zwei Grafiken oben tragen den Bildschirm, solange kaum gemessen wurde: die
Trainings im Zeitverlauf (`ActivityChart.tsx`, Balken je Tag, Woche oder Monat
je nach Zeitraum, abgebrochene Gespräche als hellerer Anteil) und das Raster
Szenario × Persona (`VarietyGrid.tsx`). Beide brauchen nur die Sitzungsdaten,
keine Messwerte. Die Gesprächsdauer läuft als abgeleitete Reihe neben den
gemessenen Kennzahlen mit.

Die Bereiche D und E aus Abschnitt 5 sind als sichtbar gekennzeichnete
Beispielansicht angelegt (`ProgressPreview.tsx`), weil ihnen die Datengrundlage
fehlt. Stufe 2 steht aus. Aus Stufe 3 sind die Sprachmelodie und die
Unterbrechungen inzwischen gebaut (Abschnitt 4.1).

## 1. Zweck

Das Dashboard beantwortet für eine Nutzerin drei Fragen zu ihrem eigenen
Training:

1. Was habe ich getan? (Aktivität, Vielfalt, Zeitraum)
2. Wie hat sich mein Sprechverhalten entwickelt? (Kennzahlen und Verläufe)
3. Woran arbeite ich als Nächstes? (Fokusziele, wiederkehrende Punkte aus den
   Auswertungen, ein konkreter nächster Übungsschritt)

Es ersetzt nicht die Auswertung eines einzelnen Gesprächs. Diese bleibt der Ort,
an dem inhaltlich etwas gesagt wird (ADR 0003, ADR 0004). Das Dashboard fasst
zusammen, was über mehrere Trainings hinweg sichtbar wird, und führt zurück ins
Training.

## 2. Was das Dashboard nicht tut

Drei Entscheidungen liegen bereits vor und tragen die Gestaltung. Sie sind keine
Einschränkung, die man umgeht, sondern der Grund, warum dieser Bildschirm
überhaupt vertretbar ist.

| Entscheidung | Was daraus folgt |
|---|---|
| ADR 0004 | Kein Score, keine Note, keine Sterne. Feedback ist qualitativ und verhaltensbezogen. |
| ADR 0051 | Keine Kennzahl trägt einen Zielbereich, weil für diese Nutzergruppe kein belegter Normwert existiert. Nichts wird gegen die Persona gemessen, sie ist eine synthetische Stimme. |
| ADR 0065 | Der Fortschrittsbildschirm zeigt eigene Werte über die Zeit und bewertet sie nicht. Verboten ohne neue, ausdrückliche Entscheidung: Zielbänder, Ampelfarben, Pfeile, Deltas mit „besser“ oder „schlechter“, Rangfolgen gegenüber anderen Nutzern, jede Gesamtnote über Sitzungen hinweg. |

Zwei weitere Grenzen kommen aus dem Einsatzkontext:

* **Kein Vergleich mit Kolleginnen und Kollegen.** Der Mandantenbezug der
  Szenario-Bibliothek (ADR 0060) macht einen solchen Vergleich technisch
  denkbar. Er bleibt ausgeschlossen. Ein Werkzeug, das Beschäftigte
  untereinander in eine Rangfolge bringt, ist Verhaltens- und
  Leistungskontrolle und wäre in einem Unternehmenskontext mitbestimmungs- und
  datenschutzrechtlich eine völlig andere Anwendung als diese.
* **Nur die eigenen Daten.** Das Dashboard liest ausschließlich Sitzungen des
  angemeldeten Kontos, wie die Historie auch (ADR 0064).

Die Konsequenz aus ADR 0065 gilt weiterhin: „Fortschritt“ heißt hier
*sichtbar gemachte Entwicklung*, nicht *gemessene Verbesserung*. Diese Lücke
muss in der Oberfläche benannt werden, sonst ergänzen Nutzer die fehlende
Bewertung selbst und nehmen an, oben sei gut.

## 3. Wissenschaftliche Einordnung

Die Gestaltung stützt sich auf folgende Arbeiten. Jede Zeile nennt, was daraus
konkret folgt, nicht nur, dass es sie gibt.

| Grundlage | Folgt daraus für den Entwurf |
|---|---|
| Hattie & Timperley (2007), *The Power of Feedback*: wirksames Feedback beantwortet „Feed Up“ (wohin), „Feed Back“ (wie läuft es), „Feed Forward“ (was als Nächstes) | Die drei Bereiche des Bildschirms sind genau diese drei Fragen, in dieser Reihenfolge: Fokusziele oben, Verläufe in der Mitte, Übungsvorschlag unten. |
| Zimmerman (2002), zyklisches Modell selbstregulierten Lernens (Planung, Ausführung, Selbstreflexion) | Das Dashboard bedient die Reflexionsphase und muss in die Planungsphase zurückführen. Ein Dashboard ohne Weg zurück ins Training endet in der Betrachtung. |
| Locke & Latham (2002), Zielsetzungstheorie: spezifische Ziele wirken, aber nur mit Rückmeldung zum Zielfortschritt | Die Fokusziele (F-62) sind der spezifische Teil. Das Dashboard ist die Rückmeldung dazu. Ohne diesen Bereich blieben die Fokusziele folgenlos. |
| Ericsson et al. (1993), deliberate practice: gezielte Wiederholung an der Schwachstelle, mit unmittelbarer Rückmeldung | Der Bereich „Üben“ verknüpft einen wiederkehrenden Verbesserungspunkt mit genau einem passenden Szenario und einer passenden Persona, nicht mit einer allgemeinen Empfehlung. |
| Jivet et al. (2018), *License to Evaluate*: Lern-Dashboards stützen sich überwiegend auf sozialen Vergleich und selten auf eine Lerntheorie | Bezugsnorm ist ausschließlich die eigene Vergangenheit (individuelle Bezugsnorm), nie eine Gruppe. Das deckt sich mit Abschnitt 2. |
| Verbert et al. (2013), Prozessmodell für Lernanalytik: Wahrnehmen, Reflektieren, Deuten, Handeln | Jeder Block endet mit einer Handlungsmöglichkeit (Detail öffnen, Ziel ändern, Training starten). Ein Block, aus dem nichts folgt, gehört nicht auf den Bildschirm. |
| Shneiderman (1996), *Overview first, zoom and filter, details on demand* | Genau drei Ebenen (Abschnitt 7). Die Übersicht passt auf einen Bildschirm, Details werden geholt, nicht vorgehalten. |
| Tufte (Sparklines, Small Multiples), Few (2006), *Information Dashboard Design* | Verläufe als kleine, gleich große Kurven nebeneinander statt als einzelne große Diagramme. Wenig Fläche pro Kennzahl, viele Kennzahlen vergleichbar. |
| Kahneman, Peak-End-Regel (bereits in ADR 0056 verwendet) | Bleibt Textgewichtung in der Einzelauswertung. Sie wird **nicht** auf mehrere Sitzungen ausgedehnt, sonst entstünde eine Gewichtung ohne Grundlage. |

Ehrlich dazu: Diese Arbeiten begründen die **Anordnung und die Bezugsnorm**. Sie
begründen keine Schwellenwerte für Sprechtempo oder Redeanteil. Genau deshalb
bleibt es bei ADR 0051.

## 4. Datenlage

Ein Dashboard ist nur so gut wie das, was tatsächlich gemessen wird. Stand heute
liefert eine abgeschlossene Sitzung neun Kennzahlen (`backend/feedback/metrics.py`,
je Sitzung, nie je Turn, ADR 0051) plus die Auswertungstexte.

### 4.1 Vorhandene Kennzahlen

| Schlüssel | Anzeige | Einheit | Für Verlauf geeignet |
|---|---|---|---|
| `talk_share` | Redeanteil | % | ja |
| `questions` | Fragen an den Gesprächspartner | Anzahl (plus je 100 Wörter) | ja, normiert je 100 Wörter |
| `pace` | Sprechtempo | Wörter/min | ja |
| `word_count` | Gesprochene Wörter | Wörter | eingeschränkt, hängt stark an der Gesprächslänge |
| `reaction_time` | Reaktionszeit | s | ja |
| `pauses` | Sprechpausen | s | ja |
| `loudness` | Lautstärke | dB (Spannweite, plus Kurve im `detail_json`) | ja, als Spannweite |
| `intonation` | Sprachmelodie | Halbtöne (Umfang, plus drei weitere Faktoren und die Kurve) | ja |
| `interruptions` | Unterbrechungen | Anzahl je Gespräch | ja |

Die letzten beiden sind nachgerüstet, nachdem `acoustics.py` um eine
Tonhöhenkurve erweitert wurde. Die Sprachmelodie ist dabei die einzige Kennzahl
mit mehr als einer Zahl dahinter: Eine Prüfung der Rechenkette ergab, dass ein
Umfangswert allein einen durchgehend lebendigen Sprecher nicht von einem
unterscheidet, der einen einzigen Satz betont hat. Sie trägt deshalb vier
Faktoren (Umfang, Bewegung, Satzenden, Verlauf über das Gespräch), von denen nur
die Satzenden gedeutet werden, weil eine Steigung einen natürlichen Nullpunkt
hat und ohne Populationsnorm auskommt. Dieselbe Prüfung deckte zwei Fehler auf,
die behoben sind: Die Tonhöhe wurde auf dem 100-ms-Raster der Lautstärkekurve
analysiert, was Intonation unterabtastet (eine Kontur mit wahren 16 Halbtönen
las sich bei 3 Hz als 14,2 und bei 8 Hz als 4,8), und ein fester Analysebereich
ließ Oktavfehler zu (eine 116-Hz-Stimme erzeugte einen Frame bei 483 Hz).
Gemessen wird jetzt bei 10 ms und in zwei Durchläufen, wobei der zweite das
Fenster aus den Quartilen des ersten bildet. Zur Einheit: Halbtöne und nicht Hertz, weil eine
Spanne von 40 Hz für eine tiefe Stimme viel und für eine hohe wenig ist. Ein
Halbton ist ein Verhältnis, also ergibt derselbe Ausdrucksumfang bei jeder
Stimme dieselbe Zahl. Unterbrechungen werden als Anzahl geführt und
ausdrücklich nicht als Rate: Wie viel es zu unterbrechen gab, hängt daran, wie
lange die synthetische Stimme geredet hat, und eine Division dadurch ließe eine
TTS-Einstellung eine Aussage über den Nutzer verschieben (ADR 0051).

**Zur Unterbrechungsrate und ihrer Ampel.** Die Klassifikation liegt in
`backend/feedback/interruptions.py` und unterscheidet vier Fälle: Hörsignal,
terminale Überlappung, harte Unterbrechung, weiche Überlappung. Die erste Regel
gewinnt, und diese Reihenfolge ist der eigentliche Schutz: Würde ein kurzes
„mhm“ mitgezählt, bestrafte die Anwendung genau das Zuhören, das sie beibringen
will. Jede harte Unterbrechung erzeugt zusätzlich einen `Finding`-Eintrag mit
Zeitstempel, womit diese Tabelle ihren ersten Schreiber und Leser hat.

Die dreistufige Ampel auf dieser Kennzahl ist ein **Versuch** und steht im
Widerspruch zu ADR 0004, ADR 0051 und ADR 0065, die alle drei ablehnen, eine
Zahl gegen eine erfundene Grenze zu stellen. Sie wurde ausdrücklich gewünscht,
die ADRs bleiben vorerst unverändert, und sie ist deshalb auf **eine Kachel in
der Auswertung eines einzelnen Gesprächs** beschränkt. Auf dem Dashboard
erscheint sie nicht, weil ADR 0065 genau diesen Bildschirm regelt.

Ein Klick auf die Kachel öffnet eine eigene Seite (`/trainings/:sessionId/kennzahl/:metricKey`), nicht ein Aufklappen an Ort und Stelle: Die Ausschnitte sind mehrere Zeilen lang, und die Seite soll verlinkbar sein. Dort steht je Unterbrechung der Transkriptausschnitt:
die abgeschnittene Zeile des Gegenübers, ein sichtbarer Bruch an der Stelle des
Einsatzes und durchgestrichen daneben, was das Gegenüber noch gesagt hätte.
Dafür hält `turn.unheard_text` seit Migration `a91c5f70d8e3` fest, was bereits
synthetisiert, aber nicht mehr abgespielt war. Bewusst neben dem Transkript und
nicht darin, denn ADR 0035 hält Transkript und Modellgedächtnis exakt auf das
Gehörte. Für ältere Gespräche ist das Feld leer, und der Block sagt das.

Hörsignale werden daneben ausgewiesen und zählen nie dagegen. Sie verrechnen
sich auch nicht gegen Unterbrechungen, denn das wäre ein Tauschkurs, den nichts
belegt. Ebenso stehen Gesprächslänge und Zahl der Redebeiträge als Kontext neben
der Zahl, nicht in ihr.

Eine Unterbrechungs**rate** je Persona-Redebeitrag war zunächst gebaut und wurde
wieder entfernt. Bei 6 bis 9 Redebeiträgen je Gespräch ergab schon eine einzelne
Unterbrechung 0,11 bis 0,17, sodass jede Unterbrechung sofort auf der obersten
Stufe landete und Grün nur bei exakt null erreichbar war. Der Nenner sagte mehr
aus als das Gespräch. Geblieben ist die Anzahl, mit der Zahl der Redebeiträge
als Kontext daneben statt darunter. Die Ampelgrenzen liegen jetzt bei 0 (grün),
bis 2 (gelb) und darüber (rot) und sind weiterhin geraten. Eingefärbt wird allein die Zahl, nicht die
ganze Kachel: Eine rote Fläche würde eine Orientierung schreien, die zwei
erfundene Grenzwerte nicht tragen.

**Nicht gebaut, mit Absicht: Füllwörter.** In 21 gespeicherten Nutzerbeiträgen
dieser Installation kommt kein einziges „äh“, „ähm“ oder vergleichbares
Füllwort vor. Whisper normalisiert sie weg, die Transkripte lesen sich wie
lektorierter Text. Eine Füllwortzählung würde daher die Nachbearbeitung des
Spracherkenners messen und nicht das Sprechen, und sie würde für jeden Nutzer
nahe null ausweisen. Sie bleibt draußen, bis entweder der Spracherkenner
angewiesen werden kann, wörtlich zu transkribieren, oder die Größe aus dem
Audiosignal selbst kommt (gefüllte Pausen sind akustisch erkennbar).

Zusätzlich aus der `session`-Tabelle ohne neue Messung ableitbar: Anzahl und
Zeitpunkte der Trainings, Dauer, Szenario, Persona, Status (abgeschlossen oder
abgebrochen), also Aktivität und Vielfalt.

### 4.2 Abdeckung der Fokusziele

Der Katalog aus F-62 hat 15 Ziele. Was davon heute mit Daten hinterlegt werden
kann:

| Fokusziel | Heute belegbar durch | Lücke |
|---|---|---|
| Ausgewogenes Sprechtempo | `pace`, `pauses` | keine |
| Souveräne Lautstärke | `loudness` samt Kurve | keine |
| Ausgewogener Redeanteil | `talk_share` | keine |
| Aktive Bedarfsermittlung | `questions`, `talk_share` | ob an Kundenaussagen angeknüpft wird, ist Text |
| Aktives Zuhören | `interruptions`, `reaction_time`, `pauses` | ob an Kundenaussagen angeknüpft wird, ist Text |
| Prägnante Sprache | `word_count` mit Wörtern je Satz | Füllwörter werden nicht gezählt |
| Regelmäßiges Training | Sitzungsdaten | keine |
| Trainingsvielfalt | Persona × Szenario | keine |
| Lebendige Sprachmelodie | `intonation` (Tonhöhenumfang in Halbtönen, plus Kurve) | keine |
| Deutliche Artikulation | nichts | eigene Messung nötig |
| Souveränität unter Druck | nichts | verlangt Werte je Gesprächsphase, gespeichert wird nur je Sitzung (ADR 0051) |
| Souveräner Gesprächseinstieg | Auswertungstext | keine Messung |
| Sichere Einwandbehandlung | Auswertungstext | keine Messung |
| Klarer Gesprächsabschluss | Auswertungstext, `phase_language` | keine Messung |
| Empathie und Kundenorientierung | Auswertungstext | keine Messung, laut Katalog auch keine geplant |

Neun Ziele sind also heute mit Zahlen unterlegbar, sechs zunächst nur mit Text.
Das ist kein Mangel des Dashboards, sondern der Umsetzungsstand. Der Entwurf
muss beides tragen können, und ein Ziel ohne Messung darf keine leere Kachel
erzeugen (Abschnitt 6).

### 4.3 Zwei methodische Vorbehalte, die in die Oberfläche gehören

* **Die Sitzungen sind nicht vergleichbar wie Messwiederholungen.** Szenario und
  Persona wechseln, und beide beeinflussen Redeanteil, Tempo und Fragenanzahl
  stärker als eine Verhaltensänderung es täte. Ein Verlauf zeigt deshalb
  Streuung, nicht Entwicklung. Umgang damit: Streuungsband statt Trendlinie
  (Abschnitt 8), optional später ein Filter auf eine Szenario-Kategorie.
* **Kleine Fallzahlen.** Nach zwei Gesprächen ist jede Kurve Rauschen. Der
  Entwurf setzt eine Mindestanzahl (Abschnitt 6) und sagt sie an, statt eine
  Linie durch zwei Punkte zu ziehen.

### 4.4 Ein Altbestand, den das Dashboard sichtbar gemacht hat

Beim Bau von Stufe 1 fiel auf, dass die Tabelle `metric_type` beide Vokabulare
gleichzeitig aktiv führte: die deutschen Schlüssel von vor ADR 0057
(`redeanteil`, `tempo`, `lautstaerke`, …) neben ihren englischen Nachfolgern,
mit identischen Anzeigenamen. ADR 0057 hält fest, dass der alte Schlüssel beim
Seeding deaktiviert wird, aber der entsprechende Aufruf fehlte in
`provision.py`, und keine Ansicht hat den Unterschied je bemerkt. Auf dem
Dashboard wären daraus zwei Karten „Redeanteil“ nebeneinander geworden.

Behoben in zwei Schritten: Das Seeding deaktiviert jetzt Metriktypen, die nicht
mehr im Inventar stehen (wie bei Persona und Szenario), und die Auflistung
`GET /api/sessions` führt je Messwert ein `active` mit, damit das Dashboard
Werte aus stillgelegten Metriken auslässt. Zusammenführen wäre die falsche
Lösung: Die Definitionen haben sich mit ADR 0051 geändert, und zwei
unterschiedliche Messungen zu einer Linie zu verbinden wäre die stille Art von
falsch. Die Detailansicht eines vergangenen Trainings filtert bewusst nicht,
dort gehört hin, was damals gemessen wurde.

## 5. Aufbau

Eigene Route `/fortschritt`, verlinkt aus dem Kopfbereich und aus dem Profil.
Nicht im Profil selbst: Dieses ist bereits lang und behandelt Konto, Daten und
Einstellungen, während das Dashboard eine Arbeitsansicht ist.

```
+-----------------------------------------------------------------------+
|  Ihr Fortschritt                     [ 30 Tage | 6 Monate | Gesamt ]   |
|  14 Trainings, 6 Szenarien, 2 Gesprächspartner                         |  A
+-----------------------------------------------------------------------+
|  IHRE FOKUSZIELE                                                       |
|  +----------------------+ +----------------------+ +-----------------+ |
|  | Sprechtempo          | | Redeanteil           | | Einwand-        | |
|  | 132 W/min            | | 46 %                 | | behandlung      | |  B
|  | ~~~~/\~~~~~ (12)     | | ~~~~~~\_~~~ (12)     | | Text, keine     | |
|  | Ihr Bereich 118-141  | | Ihr Bereich 41-58    | | Messung         | |
|  | > Details            | | > Details            | | > Details       | |
|  +----------------------+ +----------------------+ +-----------------+ |
+-----------------------------------------------------------------------+
|  KENNZAHLEN UEBER DIE ZEIT                                             |
|  Redeanteil    ~~~~~~~~   Fragen        ~~~~~~~~   Sprechtempo ~~~~~~  |  C
|  Reaktionszeit ~~~~~~~~   Sprechpausen  ~~~~~~~~   Lautstaerke  ~~~~~  |
|  (Small Multiples, gleiche Breite, je mit eigenem Streuungsband)       |
+-----------------------------------------------------------------------+
|  WAS IN IHREN AUSWERTUNGEN WIEDERKEHRT                                 |
|  Haeufig als Staerke genannt      Haeufig als Verbesserung genannt     |  D
|  - Klare Struktur (5 von 8)       - Zu frueh auf den Preis (4 von 8)   |
|  - Ruhiger Ton (4 von 8)          - Abschluss bleibt offen (3 von 8)   |
|                                                                        |
|  [ Abschluss gezielt ueben ]  Szenario "Abschluss nach Uebergabe"      |  E
|                               mit Thomas Brandt                        |
+-----------------------------------------------------------------------+
```

### A. Kopf

Zeitraumwahl und die reinen Aktivitätszahlen. Aktivität braucht keine Norm, sie
zählt, was getan wurde (ADR 0065 nennt das ausdrücklich als erlaubt). Der
Zeitraum ist auf sechs Monate begrenzt, weil ältere Trainings gelöscht werden
(ADR 0067). Die Auswahl „Gesamt“ heißt also „alles, was noch da ist“, und sagt
das auch.

### B. Fokusziele

Eine Kachel je gewähltem Ziel, höchstens fünf, in der Reihenfolge des Katalogs.
Jede Kachel zeigt:

* den Zielnamen,
* den zuletzt gemessenen Wert, wenn es eine Messung gibt,
* eine Sparkline über die Sitzungen im Zeitraum,
* den **eigenen** üblichen Bereich als Text („Ihr Bereich 118 bis 141“),
  berechnet als Median plus/minus mittlere absolute Abweichung, also dieselbe
  Konstruktion, die `metrics.py` schon für die Lautstärkekurve verwendet. Das
  ist kein Zielbereich, sondern eine Beschreibung der eigenen Streuung, und es
  ist der einzige Bezugspunkt, den ADR 0051 zulässt,
* bei Zielen ohne Messung stattdessen die letzten Aussagen aus den
  Auswertungstexten zu diesem Ziel,
* einen Verweis in die Detailebene.

**Wenn keine Fokusziele gesetzt sind**, tritt an diese Stelle ein Block
„Überblick“: die drei Kennzahlen mit der größten Streuung über den Zeitraum,
also die, bei denen sich überhaupt etwas bewegt, jeweils mit Sparkline, und
daneben eine Einladung, Fokusziele zu wählen, die ins Profil führt. Damit ist
der Bereich nie leer, und die Einladung ist ein Angebot statt einer Mahnung. Das
Setzen von Zielen bleibt freiwillig (F-62).

### C. Kennzahlen über die Zeit

Alle vorhandenen Kennzahlen als Small Multiples: gleiche Größe, gleiche
Zeitachse, untereinander vergleichbar. Bewusst ohne Auswahl und ohne
Umschalter, damit der Bereich nicht zu einem Analysewerkzeug wird. Wer mehr
will, öffnet die Detailebene.

Kennzahlen, die im Zeitraum nur einmal vorliegen, erscheinen als einzelner Punkt
mit Wert, nicht als Kurve.

### D. Stärken und Schwächen

Der einzige Bereich, der über die reine Anzeige hinausgeht, und damit der, der
am sorgfältigsten begründet werden muss.

Die Auswertung eines Gesprächs erzeugt bereits Punkte zweier Arten,
`strength` und `improvement` (`feedback_point.kind`). Das Dashboard erfindet
nichts hinzu, sondern **zählt, was die Auswertungen gesagt haben**: „In 4 von 8
Auswertungen wurde der Abschluss als Verbesserungspunkt genannt.“ Formulierung
und Bezug bleiben damit qualitativ, wie ADR 0004 es verlangt, und es entsteht
keine Note über Sitzungen hinweg, die ADR 0065 ausschließt. Der Unterschied ist
wichtig genug, um ihn im Text sichtbar zu halten: Angezeigt wird eine
Häufigkeit von Aussagen, keine Messung einer Eigenschaft.

Dafür fehlt heute eine Voraussetzung. Die Punkte sind Freitext und tragen außer
einer optionalen Turn-Referenz keine Zuordnung; `feedback_point.metric_type_id`
existiert, wird aber nie geschrieben. Vorschlag: **Der Wrap-up-Generator ordnet
jedem Punkt beim Schreiben einen Schlüssel aus dem Fokuszielkatalog zu**
(geschlossenes Vokabular, dieselben 15 Schlüssel, plus „ohne Zuordnung“). Das
ist eine Zeile mehr im JSON-Schema des Generators und eine Spalte auf
`feedback_point`, und es macht die Aggregation deterministisch, ohne einen
zweiten Modellaufruf über die Historie. Die Alternative, alle Punkte einer
Person nachträglich durch ein Modell clustern zu lassen, wäre teurer, nicht
reproduzierbar und würde bei jeder Ansicht andere Gruppen erzeugen.

Nebeneffekt, der den Aufwand rechtfertigt: Mit dieser Zuordnung bekommen auch
die sieben Fokusziele ohne Messung (Abschnitt 4.2) eine Datengrundlage, und die
Fokuszielkacheln in Bereich B können sie zeigen.

Anzeige: höchstens drei Punkte je Spalte, absteigend nach Häufigkeit, erst ab
zwei Nennungen. Ein einzelner Punkt aus einem einzelnen Gespräch ist eine
Beobachtung, kein Muster.

### E. Üben

Aus einem wiederkehrenden Verbesserungspunkt wird genau ein Vorschlag: ein
Szenario und eine Persona, mit einem Knopf, der das Training startet. Kein
Vorschlagsstapel, denn die Entscheidung, was als Nächstes geübt wird, soll in
einem Klick enden.

Drei Wege, in dieser Rangfolge:

1. **Ein vorhandenes Folgeszenario** (F-60, ADR 0069). Zu dem Gespräch, in dem
   der Punkt zuletzt genannt wurde, existiert oft bereits ein vom System
   entworfenes Folgeszenario. Es ist der beste Treffer und kostet keine neue
   Logik: Übergabe an den Trainingsablauf über den bestehenden
   `TrainingStart`-Mechanismus im Router.
2. **Feste Zuordnung Fokusziel zu Szenario-Kategorie und Persona.** Eine kleine
   Tabelle, kein Modellaufruf: Einwandbehandlung führt zu `pricing` oder
   `closing` mit der fordernden Persona, Bedarfsermittlung zu `requirements`,
   Souveränität unter Druck zu `operations` mit Eskalationscharakter. Die
   Kategorien existieren bereits (ADR 0072), die Zuordnung ist Redaktionsarbeit
   und keine Rechenlogik.
3. **Paraverbale Ziele binden nicht an ein Szenario.** Sprechtempo oder
   Lautstärke lassen sich in jedem Gespräch üben. Hier lautet der Vorschlag
   „irgendein Szenario, das Sie noch nicht gespielt haben“, was zugleich die
   Trainingsvielfalt erhöht.

Der Vorschlag nennt immer, woher er kommt („weil der Abschluss in Ihren letzten
Auswertungen dreimal genannt wurde“). Eine Empfehlung ohne Begründung ist an
dieser Stelle eine Anweisung.

## 6. Zustände

Ein Dashboard wird an seinen Randfällen beurteilt, nicht am vollen Bildschirm.

| Zustand | Anzeige |
|---|---|
| Keine Einwilligung zur Speicherung (ADR 0066) | Der Bildschirm erklärt, dass ohne Speicherung kein Verlauf entstehen kann, und verlinkt die Einstellung im Profil. Kein leeres Diagrammgerüst. |
| Einwilligung erteilt, noch kein Training | Erklärt, was hier entstehen wird, zeigt die gewählten Fokusziele als Vorschau und führt mit einem Knopf ins erste Training. |
| 1 bis 2 Trainings | Kennzahlen als Einzelwerte, ausdrücklich ohne Verlauf, mit dem Hinweis, ab wann ein Verlauf gezeigt wird. Bereich D bleibt leer, da Muster mindestens zwei Nennungen brauchen. |
| Ab 3 Trainings | Verläufe und Streuungsband. |
| Fokusziele gesetzt, aber ein Ziel ohne Messung | Die Kachel zeigt Aussagen aus den Auswertungen statt einer Kurve und sagt, dass es dazu keine Messung gibt. Keine leere Kachel und keine ersatzweise erfundene Zahl. |
| Keine Fokusziele | Bereich B wird durch den Überblick plus Einladung ersetzt (Abschnitt B). |
| Trainings vorhanden, aber ohne Auswertung (Job fehlgeschlagen) | Kennzahlen erscheinen, Bereich D erklärt, dass zu diesen Gesprächen keine Auswertung vorliegt. Die Zahlen liegen unabhängig von der Auswertung in der Datenbank. |

Die Schwelle von drei Trainings ist gesetzt, nicht gemessen. Sie ist die
kleinste Zahl, bei der eine Streuung überhaupt eine Form hat. Sie gehört als
Konstante an eine Stelle, nicht in mehrere Komponenten.

## 7. Drill-down

Drei Ebenen, mehr nicht:

1. **Übersicht** `/fortschritt`, wie oben. Passt auf einen Bildschirm.
2. **Detail einer Kennzahl oder eines Fokusziels**. Größeres Diagramm mit allen
   Punkten des Zeitraums, Werte als Tabelle darunter (das ist zugleich die
   barrierefreie Alternative), je Punkt Datum, Szenario und Persona, und was die
   Auswertungen zu diesem Ziel gesagt haben. Als eigene Route
   (`/fortschritt/:metrik`), damit der Zustand teilbar und die
   Zurück-Navigation die des Browsers ist.
3. **Ein einzelnes Training**. Führt in die bestehende Ansicht
   `PastSessionView`. Diese Ebene ist bereits gebaut und wird nicht verdoppelt.

## 8. Visuelle Sprache und Barrierefreiheit

* **Keine Bewertungsfarben.** Ein Verlauf ist blau, wie alles andere.
  Rot und Grün behaupten Ziele (ADR 0065).
* **Keine Pfeile, keine Deltas, kein „besser“.** Auch nicht als Tooltip.
* **Streuungsband statt Trendlinie.** Der eigene übliche Bereich wird als
  schwaches Band hinterlegt, die Werte als Punkte mit dünner Verbindung.
  Eine Regressionsgerade würde eine Richtung behaupten und wird nicht gezogen.
* **Sparklines ohne Achsen** in der Übersicht, mit Achsen erst im Detail.
* **Zahl neben der Kurve.** Der letzte Wert steht als Zahl daneben, damit die
  Kachel auch ohne Kurvenlesen etwas sagt.
* **Barrierefreiheit** (die Anwendung führt eine Erklärung nach BITV):
  Jedes Diagramm hat eine Textalternative mit den Werten, im Detail als
  sichtbare Tabelle. Nichts wird allein über Farbe kodiert. Der Drill-down ist
  mit der Tastatur erreichbar. Animationen respektieren
  `prefers-reduced-motion`. Kein Diagramm ist die einzige Quelle einer Aussage.
* **Kein Diagramm ohne Bezugsgröße.** Neben jeder Kurve steht, aus wie vielen
  Trainings sie besteht.

## 9. Technischer Zuschnitt

Vorschlag, damit die spätere Umsetzung nicht am Datenweg hängt:

* **Ein Endpunkt** `GET /api/progress?period=...`, der alles für die Übersicht
  liefert: Aktivitätszahlen, je Kennzahl die Reihe (Zeitpunkt, Wert,
  Sitzungs-Id), die Fokusziele mit ihrer Zuordnung, die gezählten Punkte aus den
  Auswertungen und den Übungsvorschlag. Ein Endpunkt statt vier, aus demselben
  Grund wie bei `/api/focus`: Der Bildschirm braucht alles gleichzeitig, und
  Teilzustände sehen aus wie Fehler.
* **Auf Anfrage berechnet, nicht materialisiert.** Sechs Monate Aufbewahrung
  begrenzen die Datenmenge je Konto auf eine Größenordnung, die eine Abfrage
  ohne Aggregattabelle trägt. Eine Aggregattabelle wäre eine zweite Wahrheit,
  die bei jeder Löschung nachgezogen werden müsste (ADR 0066, ADR 0067).
* **Englisch auf der Leitung**, wie überall (ADR 0057, ADR 0061). Die deutschen
  Anzeigenamen der Kennzahlen kommen wie bisher aus `metric_type.name`.
* **Eine Schemaänderung**, klein: die Zuordnung eines `feedback_point` zu einem
  Fokusziel (Abschnitt D). Nullable, geschlossenes Vokabular als CHECK, wie
  `scenario.category` (ADR 0072).
* **Keine neue Messung in dieser Stufe.** Was Abschnitt 4.2 als Lücke ausweist,
  bleibt Lücke und wird als solche angezeigt.

## 10. Was noch entschieden werden muss

Diese Punkte gehören in ADRs, bevor gebaut wird:

1. **Aggregation von Feedback-Punkten über Sitzungen** (Abschnitt D). ADR 0065
   regelt die Kennzahlen, nicht die Texte. Zu entscheiden ist, dass eine
   gezählte Häufigkeit von Aussagen keine Bewertung im Sinne von ADR 0004 ist,
   und unter welcher Formulierung sie erscheint. Ohne diese Entscheidung ist
   Bereich D nicht gedeckt.
2. **Zuordnung der Feedback-Punkte zum Fokuszielkatalog** im Generator,
   einschließlich der Frage, was passiert, wenn das Modell einen Schlüssel
   erfindet (Antwort im Sinne des Hauses: verwerfen, nicht raten).
3. **Der Übungsvorschlag** (Abschnitt E): Eine Empfehlung ist eine Aussage über
   den Nutzer. Zu klären ist, ob die feste Zuordnungstabelle ausreicht oder ob
   das als Bevormundung wirkt.

Offene Fragen an die Projektleitung, die ich nicht allein entscheiden sollte:

* ~~Soll „Trainingsvielfalt“ als Abdeckungsraster (Persona × Szenario) sichtbar
  sein?~~ Beantwortet und gebaut: Gezeigt werden nur die Kombinationen, die
  tatsächlich gespielt wurden, mit ihrer Häufigkeit. Ein Raster über die ganze
  Bibliothek mit leeren Feldern hätte aus einer Beschreibung eine Aufgabenliste
  gemacht.
* Soll der Zeitraumfilter voreingestellt 30 Tage oder alles zeigen? Bei der
  aktuellen Datenlage im Pilotbetrieb wären 30 Tage oft leer.

## 11. Umsetzung in Stufen

| Stufe | Inhalt | Voraussetzung |
|---|---|---|
| 1 (gebaut) | Kopf, Kennzahlen mit Verläufen, Fokuszielkacheln für die acht messbaren Ziele, alle Zustände aus Abschnitt 6, Detailebene | Nur vorhandene Daten. Kein Schemaeingriff. |
| 2 | Bereich D und E | Zuordnung im Generator, eine Spalte, ADR aus Abschnitt 10 |
| 3 | Fokusziele ohne Messung mit Zahlen unterlegen | Neue Messungen: Sprachmelodie (F0), Füllwörter, Unterbrechungen zählen, Werte je Gesprächsphase |

Stufe 1 ist für sich genommen brauchbar und hält jede bestehende Entscheidung
ein. Das ist der Zuschnitt, mit dem angefangen werden sollte.
