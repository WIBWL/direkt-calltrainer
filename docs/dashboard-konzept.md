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

**Überarbeitung (September 2026).** Der Bildschirm ist umgebaut worden, weil
drei Dinge nicht mehr stimmten, seit das Inventar von neun auf sechzehn
Kennzahlen gewachsen war:

* **Kennzahlen als Tabelle statt als Kachelraster.** Der Umschalter über dem
  Raster war für neun Kennzahlen gedacht und zeigte zuletzt neun und sieben
  Kacheln, also wieder die Wand, gegen die er gebaut worden war. Jetzt steht
  jede Kennzahl in einer Zeile (`ProgressMetricTable.tsx`): Name, letzter Wert,
  Verlauf als Sparkline, eigener üblicher Bereich, Zahl der Trainings, unter den
  beiden Gruppen Sprechweise und Gesprächsinhalt. Das ist Tuftes
  Sparkline-Tabelle, passt auf einen Bildschirm und ist barrierefreier als
  sechzehn verlinkte Grafiken. Der Umschalter entfällt.
* **Reihenfolge.** Zuoberst „Ihr Training“: die drei Zahlen (Trainings,
  Szenarien, Gesprächspartner) als Karten, der Kalender und das Raster
  Szenario × Gesprächspartner, alle drei über sämtliche gespeicherten Trainings.
  Darunter eine Trennlinie mit dem Zeitraumschalter, und erst unter ihr
  Fokusziele, das Wiederkehrende mit dem Übungsvorschlag als Band darunter und
  zuletzt die Kennzahlen. Die Stellung des Schalters sagt
  damit, was er erreicht: alles darüber zählt jedes Training, alles darunter
  liest die Auswahl. Vorher stand er im Kopf neben den Zahlen, sah aus, als
  gelte er für sie und den Kalender, und der Kalender brauchte eine Erklärung,
  warum er es nicht tut. Der Übungsvorschlag, der einzige Block, der zurück ins
  Training führt, bleibt weit oben (Abschnitt 3, Zimmerman). Die
  Abschnittsüberschriften sind dieselben wie auf der Feedback-Seite
  (`SectionHeading.tsx`, Oberzeile und Titel), damit die Seite über viele
  Trainings und die über eines dieselbe Sprache sprechen.
* **Kennzahlen, die keine Kurve vertragen.** Zählwerte (Fragen, Füllwörter,
  Wiederholungen, Verzögerungslaute, Unterbrechungen) stehen als ganze Zahl je
  Gespräch, ihr üblicher Bereich gerundet und nie unter null. Eine Fassung je 100
  gesprochene Wörter (Abschnitt 4.1 hatte das für die Fragen vorgesehen) war
  kurz gebaut und ist wieder entfernt, weil sie jede Anzahl zur Kommazahl machte;
  die Gesprächsdauer steht als eigene Zeile daneben. Die Wortanzahl selbst fehlt
  in der Übersicht, weil sie über mehrere Trainings nur die Gesprächsdauer
  wiederholt. **Die Lautstärke fehlt auf dem ganzen Dashboard**, auch im
  Druck-Vergleich auf der Zielseite: Ihr dB-Wert ist der Pegel der Aufnahme und
  über mehrere Gespräche vor allem Mikrofon und Abstand (derselbe Grund, aus dem
  das Fokusziel dazu zurückgezogen wurde, Abschnitt 4.2). Innerhalb eines
  Gesprächs bleibt sie in dessen Auswertung. Der
  Gesprächseinstieg („von 3“) bekommt keine Kurve und kein Band, sondern je
  Training die Zahl der erkannten Teile (`PartsStrip.tsx`) und den Satz „in X von
  N Trainings alle 3 Teile erkannt“: Eine Linie über einem Band läse sich als
  Note auf dem Weg zur Bestnote, und genau diese Lesart hat ADR 0086 schon auf
  der Kachel des einzelnen Gesprächs vermieden.

Das Raster Szenario × Gesprächspartner sortiert Zeilen und Spalten nach
Häufigkeit und zeigt fünf Szenarien, den Rest hinter „weitere Szenarien
anzeigen“; mit einem Dutzend gespielter Szenarien war es das längste Element der
Seite geworden.

Dazu drei kleinere Änderungen: Die Fokuskacheln zeigen unter der ersten
Kennzahl bis zu zwei weitere, weil etwa Sprechtempo, Pausen und Sprechlänge
zusammen erst den Rhythmus ergeben. Ziele ohne Messung zeigen ihre Nennungen als
Punktreihe wie der Block D statt als große Ziffer „3 von 8“. Erklärungen stehen
hinter einem „i“ (`InfoDetails`), wobei der eine Satz, der nicht überlesen werden
darf, sichtbar bleibt. Und der Schalter wählt jetzt **die letzten 5, die letzten
10 oder alle Trainings** statt 30 Tage, 6 Monate oder Gesamt (Abschnitt 10).

Kalender der Trainingstage (`ActivityCalendar.tsx`) und Raster Szenario ×
Persona (`VarietyGrid.tsx`) brauchen nur die Sitzungsdaten, keine Messwerte. Sie
standen zuerst oben, weil sie im Pilotbetrieb das Einzige waren, was schon etwas
zeigte, dann eine Zeitlang unten als Kontext, und stehen jetzt wieder oben,
diesmal über dem Zeitraumschalter (siehe Reihenfolge oben). Die Gesprächsdauer
läuft als abgeleitete Reihe neben den gemessenen Kennzahlen mit.

Der Kalender stand zuerst als Balkendiagramm je Tag, Woche oder Monat da. Die
Zahlen sind dieselben; was ein Kalender hinzufügt, ist die Form einer Woche:
ob die Trainings auf Werktagen liegen, ob vierzehn Tage nichts passiert ist, ob
sie sich vor einem Termin häufen. Nichts davon ist in einer Balkenreihe lesbar,
und alles davon ist das, was man eine Trainingshistorie fragt. Ein Tag mit
Trainings trägt deren Anzahl und eine Einfärbung in drei Stufen (ein, zwei,
drei und mehr), ein leerer Tag sein Datum, der heutige einen Ring. Gezählt
werden nur abgeschlossene Trainings. Ein abgebrochenes Gespräch wird weder
gezählt noch eigens markiert, denn die Frage lautet, wann jemand trainiert hat.

Gezeigt wird ein Monat, beim Aufruf der laufende; zwei Pfeile blättern zurück
bis zum Monat des ältesten Trainings und wieder vor. Sechs Monate
nebeneinander waren eine Wand aus Rastern, in der ausgerechnet der gesuchte
Monat am schwersten zu finden war, und die Karte daneben stand neben einem
halben Meter leerem Rand.

Der Zeitraumschalter lässt den Kalender bewusst unberührt und steht deshalb
unter ihm. Er sagt, über welche Trainings die Kennzahlen gelesen werden; ein
Kalender trägt seinen Zeitraum schon im Raster. Ihm Monate wegzuschneiden
hieße, dieselbe Aussage zweimal zu treffen, das zweite Mal als Loch in einer
Grafik. Der Kalender liest deshalb alle gespeicherten Trainings, und seit der
Schalter unter dem Block steht, tun das auch die drei Zahlen und das Raster
daneben: Ein Teil des Blocks über dem Schalter, der ihm trotzdem folgt, wäre
genau die Unklarheit, die die neue Stellung beseitigen soll.

Der Übungsvorschlag stand zuerst als dritte Karte in der Reihe der beiden
Listen. Inhaltlich gehört er dorthin, denn er folgt aus den
Verbesserungspunkten daneben; von der Form her nicht: Eine Karte mit Absatz,
Angebot und Knopf lief in einer 450 px breiten Spalte dreimal so hoch wie ihre
Nachbarn, die zwei Zeilen tragen. Er steht deshalb als Band über die volle
Breite unter den beiden Listen, Begründung links, Angebot rechts. Was er nicht
wieder werden darf, ist ein eigener Abschnitt am Seitenfuß — dort hat er
angefangen, und dort hat ihn niemand erreicht.

Bereich D ist inzwischen echt (`ProgressRecurring.tsx`, Rechenteil
`utils/goalMentions.ts`). Die Beispielansicht ist entfernt: Seit ADR 0080 trägt
jeder Feedback-Punkt das Fokusziel, um das es geht, sodass gezählt werden kann,
was die Auswertungen gesagt haben. Bereich E ist ebenfalls gebaut
(`ProgressPractice.tsx`, Tabelle in `utils/practiceRoutes.ts`). Eine
Abweichung von Abschnitt 5.E: Die Persona wird nicht nach Anforderungsgrad
gewählt, weil der Draht auf einer Persona keinen trägt. Vorgeschlagen wird der
Gesprächspartner aus dem Training, in dem der Punkt zuletzt genannt wurde.

Die zweite Ebene ist seither vollständig (Abschnitt 7). Sie besteht aus zwei
Seiten: `/fortschritt/:metrik` für eine Kennzahl (`ProgressMetricView.tsx`) und
`/fortschritt/ziel/:ziel` für ein Fokusziel (`ProgressGoalView.tsx`). Beide
zeigen unter Diagramm und Tabelle die Sätze aus den Auswertungen zu diesem Ziel,
wörtlich und je mit Link in das Gespräch, aus dem sie stammen
(`GoalStatements.tsx`). Dafür trägt ein markierter Feedback-Punkt seinen Text auf
der Liste mit, was die Ergänzung zu ADR 0064 begründet. Die Zielseite ist der
Grund, dass die Kacheln der sechs Ziele ohne Messung keine Sackgasse mehr sind:
Eine Häufigkeit, hinter die niemand schauen kann, liest sich wie eine Messung.

Aus Stufe 3 sind die Sprachmelodie und die Unterbrechungen gebaut, Füllwörter
sind bewusst verworfen (Whisper normalisiert sie weg), das Fokusziel zur
Lautstärke ist zurückgezogen (Abschnitt 4.2). Hinzugekommen ist der Vergleich
für „Souveränität unter Druck“ (ADR 0081): Dieselben Kennzahlen werden ein
zweites und drittes Mal gerechnet, über die Stellen, an denen das Gegenüber
widersprochen oder nachgehakt hat, und über den Rest. Welche Stellen das waren,
markiert die Auswertung in dem Modellaufruf, den sie ohnehin macht; damit danach
überhaupt noch etwas zu messen ist, hält jede Nutzeräußerung ihre Rohwerte fest
(die Aufnahme ist zu diesem Zeitpunkt längst gelöscht, ADR 0048). Verglichen wird
nichts: Es stehen zwei Zahlen nebeneinander, und wie groß ein Unterschied sein
darf, sagt niemand. Damit ist Stufe 3 abgeschlossen: Was dort offen aussah, ist entweder gebaut oder mit Begründung verworfen, und die Artikulation ist der letzte Fall der zweiten Art (Abschnitt 4.2).

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

Der Katalog aus F-62 hat 14 Ziele. „Souveräne Lautstärke“ stand hier bis zur
Ergänzung von ADR 0076 und ist zurückgezogen: Gemessen wird der Pegel der
Aufnahme, und der sagt genauso viel über Mikrofon und Sitzabstand wie über die
sprechende Person. Die Kennzahl `loudness` bleibt, das Ziel nicht. Was heute mit
Daten hinterlegt werden kann:

| Fokusziel | Heute belegbar durch | Lücke |
|---|---|---|
| Ausgewogenes Sprechtempo | `pace`, `pauses` | keine |
| Ausgewogener Redeanteil | `talk_share` | keine |
| Aktive Bedarfsermittlung | `questions`, `talk_share` | ob an Kundenaussagen angeknüpft wird, ist Text |
| Aktives Zuhören | `interruptions`, `reaction_time`, `pauses` | ob an Kundenaussagen angeknüpft wird, ist Text |
| Prägnante Sprache | `word_count` mit Wörtern je Satz | Füllwörter werden nicht gezählt |
| Regelmäßiges Training | Sitzungsdaten | keine |
| Trainingsvielfalt | Persona × Szenario | keine |
| Lebendige Sprachmelodie | `intonation` (Tonhöhenumfang in Halbtönen, plus Kurve) | keine |
| Deutliche Artikulation | Auswertungstext, und der dünn | keine Messung, und es ist keine geplant (siehe unten) |
| Souveränität unter Druck | `pace`, `pauses`, `run_length`, `loudness`, `talk_share`, je über die fordernden Stellen und über den Rest (ADR 0081) | welche Stellen fordernd waren, entscheidet die Auswertung und nicht eine Messung |
| Souveräner Gesprächseinstieg | `opening`: Begrüßung, eigener Name und Hilfsangebot bzw. Anliegen im ersten Beitrag, dazu dessen Tempo (ADR 0086) | ob der Einstieg *zugewandt* klang, steht nur im Auswertungstext |
| Sichere Einwandbehandlung | Auswertungstext | keine Messung |
| Klarer Gesprächsabschluss | `closing`: Zusammenfassung, konkreter nächster Schritt und Verabschiedung in den letzten zwei Beiträgen (ADR 0089), dazu Auswertungstext und `phase_language` | ob das Richtige zusammengefasst und ein tragfähiger Schritt vereinbart wurde, bleibt Text |
| Empathie und Kundenorientierung | Auswertungstext | keine Messung, laut Katalog auch keine geplant |

Elf Ziele sind also heute mit Zahlen unterlegbar, drei nur mit Text. Zuletzt
hinzugekommen ist der Gesprächsabschluss (ADR 0089), das Gegenstück zum
Einstieg. Eines der elf ist der Sonderfall: „Souveränität unter Druck“ wird nicht als Verlauf
gezeigt, sondern als Vergleich zweier Abschnitte innerhalb eines Gesprächs
(Abschnitt 5.B und ADR 0081). Ein Verlauf daraus wäre der Unterschied zwischen
den Abschnitten als Linie, also genau die Zahl, die es nicht geben soll.
Das ist kein Mangel des Dashboards, sondern der Umsetzungsstand. Der Entwurf
muss beides tragen können, und ein Ziel ohne Messung darf keine leere Kachel
erzeugen (Abschnitt 6).

**Die Artikulation bekommt keine Messung, und das ist eine Entscheidung und kein
Rückstand.** Sie stand als letzter offener Punkt in Stufe 3. Drei Gründe, jeder
für sich ausreichend:

* **Das Mikrofon ist nicht herauszurechnen.** Undeutlichkeit zeigt sich in der
  spektralen Schärfe des Signals, und die hängt von Mikrofon, Abstand und der
  automatischen Verstärkung des Browsers ab. Das ist genau das Argument, mit dem
  heute das Fokusziel zur Lautstärke zurückgezogen wurde, nur trifft es hier
  härter: Bei der Lautstärke bleibt innerhalb eines Gesprächs wenigstens der
  Vergleich zweier Abschnitte gültig, weil das Gerät dasselbe ist. Ein Wert für
  Deutlichkeit hat keinen solchen inneren Bezugspunkt.
* **Der Erkenner räumt auf, bevor irgendetwas messen könnte.** Whisper
  normalisiert verschluckte Endungen zu korrekten Wörtern, wie es die Füllwörter
  wegnormalisiert. Aus dem Transkript ist Undeutlichkeit deshalb nicht ablesbar,
  und die Wortfehlerrate zu messen hieße, die Erkennerqualität zu berichten.
* **Es gäbe keinen Schwellenwert.** Selbst mit einem sauberen Maß bliebe offen,
  ab wann jemand undeutlich spricht. Für diese Nutzergruppe ist nichts
  validiert, und ADR 0051 verbietet die Erfindung genau hier.

Was bleibt, ist der Auswertungstext, und der ist bei diesem Ziel **dünner als bei
den beiden anderen Textzielen**: Ob ein Abschluss klar war, steht im Gesagten und
ist aus dem Transkript lesbar. Ob jemand deutlich gesprochen hat, steht gerade
nicht darin. Das Modell kann dazu nur etwas sagen, wenn es im Transkript
Nachfragen des Gegenübers findet („Wie bitte?“), und das ist ein schwaches
Indiz. Daraus folgt eine Frage an die Projektleitung, die hier nicht allein
entschieden wird: **Soll „Deutliche Artikulation“ im Katalog bleiben?** Ein Ziel
anzubieten, zu dem die Anwendung dauerhaft fast nichts sagen kann, ist dieselbe
Art von Versprechen, wegen der die Lautstärke gegangen ist. Bis das entschieden
ist, bleibt das Ziel wählbar, und `focus_goal.evidence` steht auf
`interpretive` statt wie bisher auf `mixed` — die Spalte sagt, wie weit ein Ziel
ableitbar ist, und „gemischt“ war eine Zusage auf eine Messung, die nicht
kommt.

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

Stand nach der Überarbeitung (September 2026). Die Buchstaben der Abschnitte
unten sind die ursprünglichen, die Reihenfolge auf dem Bildschirm ist A mit dem
Aktivitätsteil, dann der Zeitraumschalter, dann B, D mit E und C.

```
+-----------------------------------------------------------------------+
|  Ihr Fortschritt                                                       |
|  WAS SIE GETAN HABEN · Ihr Training                                    |
|  +----------+ +----------------+ +---------------------------------+  |  A
|  | 14       | | Kalender des   | | Szenario × Gesprächspartner     |  |
|  | Trainings| | Monats         | |                                 |  |
|  | 6 Szen.  | |                | |                                 |  |
|  | 2 Partner| |                | |                                 |  |
|  +----------+ +----------------+ +---------------------------------+  |
|  ---- Ausgewertet werden [ Letzte 5 | Letzte 10 | Alle ] ----------   |
+-----------------------------------------------------------------------+
|  IHRE FOKUSZIELE                                                       |
|  +----------------------+ +----------------------+ +-----------------+ |
|  | Sprechtempo          | | Redeanteil           | | Einwand-        | |
|  | 132 W/min            | | 46 %                 | | behandlung      | |  B
|  | ~~~~/\~~~~~ (12)     | | ~~~~~~\_~~~ (12)     | | Verbesserung    | |
|  | Ihr Bereich 118-141  | | Ihr Bereich 41-58    | | ●●●○○○○○ 3/8    | |
|  | Pausen   0,6 s  ~~~  | |                      | | keine Messung   | |
|  | am Stück 1,2 s  ~~~  | |                      | |                 | |
|  +----------------------+ +----------------------+ +-----------------+ |
+-----------------------------------------------------------------------+
|  WAS IN IHREN AUSWERTUNGEN WIEDERKEHRT                                 |
|  +---------------------------+ +---------------------------------+   |  D
|  | Als Stärke                | | Als Verbesserung                |   |
|  | 1 Klare Struktur       5  | | 1 Abschluss                 4   |   |
|  | 2 Ruhiger Ton          4  | | 2 Einwände                  3   |   |
|  +---------------------------+ +---------------------------------+   |
|  +-------------------------------------------------------------+     |
|  | ALS NÄCHSTES ÜBEN                                           |     |  E
|  | VORSCHLAG Abschluss    | Abschluss nach Übergabe            |     |
|  | in 4 von 8 genannt     | mit Thomas Brandt  [ Starten ]     |     |
|  +-------------------------------------------------------------+     |
+-----------------------------------------------------------------------+
|  KENNZAHLEN ÜBER DIE ZEIT                                              |
|  Kennzahl         Zuletzt   Verlauf        Ihr Bereich       Trainings |  C
|  ● Sprechweise                                                         |
|  Sprechtempo      132 W/min ~~~/\~~~~      118 bis 141 W/min       12  |
|  Sprechpausen     0,6 s     ~~~~\_~~~      0,4 bis 0,8 s           12  |
|  ● Gesprächsinhalt                                                     |
|  Fragen           4         ~~~~\/~~~      3 bis 6                 12  |
|  Gesprächseinstieg 3 Teile  [3][2][3][3]   in 9 von 12 alle 3      12  |
+-----------------------------------------------------------------------+
```

### A. Kopf

Die reinen Aktivitätszahlen mit Kalender und Vielfalt, darunter die Auswahl der
Trainings. Aktivität braucht keine Norm, sie zählt, was getan wurde (ADR 0065
nennt das ausdrücklich als erlaubt), und sie zählt immer alle gespeicherten
Trainings. Die Auswahl gilt für alles unter ihr. Gewählt wird nach Anzahl, nicht
nach Tagen: die letzten 5, die letzten 10 oder alle. Nach Tagen war die Auswahl bei jemandem, der in Schüben trainiert,
oft leer, und „6 Monate“ und „Gesamt“ waren wegen der Löschfrist (ADR 0067) fast
immer dasselbe. „Alle“ heißt also „alles, was noch da ist“.

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
* bei Zielen ohne Messung stattdessen, wie oft das Ziel in den Auswertungen
  genannt wurde, und auf der Detailebene die Sätze selbst,
* einen Verweis in die Detailebene.

Eine Kachel fällt aus diesem Schema, und zwar begründet: **„Souveränität unter
Druck“ hat keine Sparkline.** Dahinter steht kein Verlauf, sondern ein Vergleich
zweier Abschnitte innerhalb eines Gesprächs (ADR 0081). Die Kachel zählt daher
nur, in wie vielen Trainings es überhaupt eine fordernde Passage gab; die beiden
Zahlenreihen stehen eine Ebene tiefer als Tabelle je Training. Eine Linie
daraus wäre der Unterschied zwischen den Abschnitten über die Zeit, also die
eine Zahl, die es zu diesem Ziel nicht geben darf, und aggregiert über mehrere
Gespräche wäre sie zusätzlich falsch: Der Druck war in jedem Gespräch ein
anderer.

**Wenn keine Fokusziele gesetzt sind**, tritt an diese Stelle ein Block
„Überblick“: die drei Kennzahlen mit der größten Streuung über den Zeitraum,
also die, bei denen sich überhaupt etwas bewegt, jeweils mit Sparkline, und
daneben eine Einladung, Fokusziele zu wählen, die ins Profil führt. Damit ist
der Bereich nie leer, und die Einladung ist ein Angebot statt einer Mahnung. Das
Setzen von Zielen bleibt freiwillig (F-62).

### C. Kennzahlen über die Zeit

Alle vorhandenen Kennzahlen als Sparkline-Tabelle, eine Zeile je Kennzahl:
gleiche Höhe, gleiche Breite des Verlaufs, untereinander vergleichbar. Bewusst
ohne Auswahl und ohne Umschalter, damit der Bereich nicht zu einem
Analysewerkzeug wird. Wer mehr will, öffnet die Detailebene über den Namen oder
die Zeile.

Kennzahlen, die unter den gewählten Trainings seltener als dreimal vorliegen,
zeigen den letzten Wert und statt der Kurve den Hinweis, ab wann eine gezeigt
wird. Zählwerte stehen als ganze Zahl je Gespräch; der Gesprächseinstieg steht
als Zahl erkannter Teile je Training, ohne Kurve und ohne Band; die Lautstärke
fehlt (siehe Überarbeitung oben).

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
   Auswertungen zu diesem Ziel gesagt haben. Zwei eigene Routen,
   `/fortschritt/:metrik` und `/fortschritt/ziel/:ziel`, damit der Zustand
   teilbar und die Zurück-Navigation die des Browsers ist.

   Die Zitate stehen unter der Tabelle und nicht als Spalte darin: Ein Satz in
   einer Tabellenzelle ist bei keiner Breite lesbar. Stärken und
   Verbesserungspunkte stehen beide da und sind benannt. Nur die
   Verbesserungspunkte zu zeigen würde aus einem Protokoll dessen, was gesagt
   wurde, eine Mängelliste machen, und genau diese Lesart schließen ADR 0004 und
   ADR 0065 aus. Zusammengefasst wird nichts: Die Seite zitiert, sie urteilt
   nicht ein zweites Mal.

   Eine Kennzahl zeigt die Sätze zu den Zielen, für die sie die *erste*
   Kennzahl ist (`focusMetrics.goalsForMetric`). Sonst sammelte die
   Reaktionszeit Aussagen aus drei Zielen ein, für die sie nur eine Nebengröße
   ist.
3. **Ein einzelnes Training**. Führt in die bestehende Ansicht
   `PastSessionView`. Diese Ebene ist bereits gebaut und wird nicht verdoppelt.

## 8. Visuelle Sprache und Barrierefreiheit

* **Keine Bewertungsfarben, aber Farbe.** Die erste Fassung war durchgehend
  blau, und das war zu viel des Guten: Zehn gleich große, gleich blaue Kacheln
  lesen sich als ein Block, in dem nichts führt. Farbe ist jetzt zugelassen,
  aber ausschließlich als **Identität**: Ein Farbton gehört einer Gruppe von
  Kennzahlen, nie einem Wert. Zwei Regeln tragen das, und beide sind baulich
  und nicht eine Frage der Sorgfalt (`frontend/src/utils/metricGroups.ts`):

  1. Der Farbton hängt an der Kennzahl, nicht an ihrer Zahl. Das Modul, das ihn
     vergibt, bekommt nie einen Messwert zu sehen, also kann ein Wert keine
     Farbe verändern. Genau das ist der Unterschied zu einer Ampel.
  2. Rot, Gelb und Grün kommen nicht vor. Nicht weil sie hässlich wären,
     sondern weil diese Anwendung sie bereits ausgegeben hat: ADR 0078 benutzt
     genau diese drei für die Ampel in der Einzelauswertung. Ein Farbton, der
     dort etwas bedeutet, darf hier nicht Identität tragen.

  Drei Töne, nicht zehn: Sprechweise, Gesprächsinhalt, Aktivität. Es sind die
  Slots 1, 5 und 7 der dokumentierten Palette, geprüft als Menge gegen weißen
  Kartengrund (Farbsehschwäche ΔE 13,0 bei einem Zielwert von 8, Normalsicht
  16,3 bei einer Untergrenze von 15). Ein Ton je Kennzahl wären acht, und ab
  acht sind benachbarte Paare nicht mehr sicher unterscheidbar.

  Was ADR 0065 verbietet, bleibt verboten: Zielbänder, Ampelfarben, Pfeile,
  Deltas mit „besser“, Rangfolgen, jede Gesamtnote.
* **Keine Pfeile, keine Deltas, kein „besser“.** Auch nicht als Tooltip.
* **Streuungsband statt Trendlinie.** Der eigene übliche Bereich wird als
  schwaches Band hinterlegt, die Werte als Punkte mit dünner Verbindung.
  Eine Regressionsgerade würde eine Richtung behaupten und wird nicht gezogen.
* **Sparklines ohne Achsen** in der Übersicht, mit Achsen erst im Detail.
  Unter der Linie liegt eine schwache Fläche in der Gruppenfarbe, damit ein
  flacher Verlauf überhaupt als Form lesbar ist, und auf dem zuletzt gemessenen
  Punkt sitzt eine Marke, weil das der Wert ist, den die Kachel daneben als Zahl
  nennt.
* **Sechzehn Kennzahlen als Kacheln sind eine Wand**, auch in zwei Hälften.
  Eine Zeitlang zeigte die Übersicht deshalb eine Hälfte hinter einem
  Umschalter (`FilterSlider`, Einteilung nach `metric_type.aspect`); mit
  wachsendem Inventar waren das neun und sieben Kacheln. Seit der Überarbeitung
  steht jede Kennzahl als Zeile in einer Tabelle, die beiden Gruppen als
  Zeilengruppen mit einer Überschrift in ihrer Farbe. Eine Zeile ist klein genug,
  dass alle auf einen Bildschirm passen, und gleich groß genug, dass sie
  vergleichbar bleiben.
* **Zeigen, was unter dem Zeiger liegt.** Die Verläufe und die Aktivitätsbalken
  haben eine Hover-Ebene: Auf einem Verlauf erscheint unter dem Diagramm, aus
  welchem Training der Punkt stammt, bei den Balken die Anzahl je Zeitraum. Sie
  ergänzt die Textalternative und ersetzt sie nicht — die Zahlen stehen
  weiterhin im `aria-label` und auf der Detailebene als Tabelle, sonst hinge
  eine Aussage an einer Zeigergeste.
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

* **Kein eigener Endpunkt.** Vorgeschlagen war `GET /api/progress?period=...`,
  gebaut wurde er nicht, und das hat sich gehalten. `GET /api/sessions` liefert
  je Sitzung bereits die Messwerte (ADR 0064) und seit ADR 0080 die Fokusziele
  der Feedback-Punkte; alles Weitere ist Gruppieren im Browser
  (`utils/progressStats.ts`, `utils/goalMentions.ts`). Ein zweiter Weg zu
  denselben Zahlen wäre die erste Stelle, an der sie auseinanderlaufen. Der
  Zeitraum ist aus demselben Grund ein Filter im Browser und kein Parameter:
  Eine Seite lädt, danach kostet ein Wechsel des Zeitraums keine Anfrage.
  Gedeckelt ist das durch die Aufbewahrung von sechs Monaten (ADR 0067) und
  durch eine Seite von 100 Sitzungen, worüber die Ansicht Auskunft gibt.
* **Ein markierter Feedback-Punkt trägt seinen Text mit** (Ergänzung zu ADR
  0064). Was die Liste weiterhin nicht trägt, ist die Auswertung als Text:
  Zusammenfassung, Phasenabsatz, `tone_fit` und jeder nicht markierte Punkt
  bleiben auf der Detailroute.
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

## 10. Was entschieden werden musste

Alle drei Punkte sind entschieden, alle drei durch ADR 0080:

1. ~~**Aggregation von Feedback-Punkten über Sitzungen**~~ (Bereich D).
   Entschieden: Eine gezählte Häufigkeit von Aussagen ist keine Bewertung im
   Sinne von ADR 0004, solange sie als Häufigkeit auftritt. Die Formulierung
   steht in der ADR und in `ProgressRecurring.tsx`: „genannt“ durchgehend, eine
   Anzahl über einem benannten Nenner, nie ein Prozentsatz, nie eine Richtung.
2. ~~**Zuordnung der Feedback-Punkte zum Fokuszielkatalog**~~. Gebaut als
   `feedback_point.focus_goal_id`, vergeben von der Auswertung im ohnehin
   stattfindenden Modellaufruf. Ein erfundener Schlüssel wird an der
   Schreibgrenze zu NULL (`generator._goal_ids`): verworfen, nicht geraten, und
   keine Ausnahme, die eine ganze Auswertung kostet.
3. ~~**Der Übungsvorschlag**~~ (Bereich E). Die redaktionelle Tabelle bleibt,
   aber der Vorschlag nennt immer zuerst seinen Grund, und ein Ziel ohne Eintrag
   in der Tabelle erzeugt keinen Vorschlag statt eines beliebigen.

Offene Fragen an die Projektleitung, die ich nicht allein entscheiden sollte:

* ~~Soll „Trainingsvielfalt“ als Abdeckungsraster (Persona × Szenario) sichtbar
  sein?~~ Beantwortet und gebaut: Gezeigt werden nur die Kombinationen, die
  tatsächlich gespielt wurden, mit ihrer Häufigkeit. Ein Raster über die ganze
  Bibliothek mit leeren Feldern hätte aus einer Beschreibung eine Aufgabenliste
  gemacht.
* ~~Soll der Zeitraumfilter voreingestellt 30 Tage oder alles zeigen?~~
  Beantwortet und gebaut: „Gesamt“ (`ProgressView.tsx`). Im Pilotbetrieb wären
  30 Tage oft leer, und ein leerer Bildschirm beim Ankommen bringt der
  Nutzerin bei, dass hier nichts ist. Seit der Überarbeitung wird nach Anzahl
  gewählt (letzte 5, letzte 10, alle), voreingestellt bleibt „Alle“. Aus
  demselben Grund: Eine Auswahl nach Anzahl ist nie leer, solange überhaupt
  etwas gespeichert ist.

## 11. Umsetzung in Stufen

| Stufe | Inhalt | Voraussetzung |
|---|---|---|
| 1 (gebaut) | Kopf, Kennzahlen mit Verläufen, Fokuszielkacheln für die acht messbaren Ziele, alle Zustände aus Abschnitt 6, Detailebene | Nur vorhandene Daten. Kein Schemaeingriff. |
| 2 (gebaut) | Bereich D und E, dazu die zweite Ebene für Kennzahl und Fokusziel mit den zitierten Aussagen | Zuordnung im Generator, eine Spalte, ADR aus Abschnitt 10. Erledigt durch ADR 0080 (`feedback_point.focus_goal_id`, Migration `d4c81b70e2a5`) samt der redaktionellen Tabelle in `utils/practiceRoutes.ts` und der Ergänzung zu ADR 0064 für den Text auf der Liste. |
| 3 (abgeschlossen) | Fokusziele ohne Messung mit Zahlen unterlegen | Gebaut: Sprachmelodie (F-35), Unterbrechungen (F-51), Abschnittswerte für „Souveränität unter Druck“ (ADR 0081). Verworfen mit Begründung: Füllwörter (Whisper normalisiert sie weg), das Fokusziel zur Lautstärke (misst das Mikrofon mit), die Artikulation (Abschnitt 4.2). Keine offenen Punkte mehr. |

Stufe 1 ist für sich genommen brauchbar und hält jede bestehende Entscheidung
ein. Das ist der Zuschnitt, mit dem angefangen werden sollte.
