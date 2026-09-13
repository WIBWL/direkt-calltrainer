# Szenario- und Persona-Katalog

## 1 Zweck und Geltungsbereich

Dieser Katalog beschreibt Trainingsfälle auf fachlicher Ebene, bevor sie als Datensätze angelegt werden. Er ist die Zwischenstufe zwischen der Anforderungsliste (`initial_requirements.md`) und dem Inhalt der Bibliothek.

Für jeden Eintrag ist ausgewiesen, **worauf er zurückgeht**: eine Anforderung (`R-xx`), eine Randbedingung (`C-xx`) oder — wenn kein Beleg vorliegt — `Systementwurf`. Das ist dieselbe Konvention wie in der Spalte *Herkunft* des Feature-Katalogs, und sie ist der Grund, warum dieser Katalog überhaupt geführt wird: Ein Trainingsfall ohne Belegkette ist eine Erfindung, und das soll man ihm ansehen.

> **Stand der Umsetzung (September 2026).** Von 14 Personas sind **6** als Datensätze angelegt, von 14 Szenarien **12**. Dazu kommen fünf Szenarien, die vor dem Katalog entstanden sind. Die Bibliothek umfasst damit 6 Personas (vier deutsch-, zwei englischsprachig) und 17 Szenarien. Welcher Katalogeintrag welchem Datensatz entspricht, steht bei jedem Eintrag in der Zeile **Bibliothek** und gesammelt in Abschnitt 6. Quelle der Datensätze ist `backend/db/seed_data.py`.

### 1.1 Anonymisierung und Konkretheit

Diese Regel gilt **auf zwei Ebenen verschieden**, und das ist der Kern: Der Katalog beschreibt Falltypen, die Bibliothek instanziiert sie. Ein Falltyp ohne Eigennamen ist richtig; ein Trainingsfall ohne Eigennamen ist blass.

**Der Katalog** nennt keine Unternehmen, Personen, Orte, Produkte, Partner oder Marken. Die Pilotunternehmen erscheinen ausschließlich als **Tätigkeitsprofile** (Abschnitt 2). Was bleibt, ist die *Tätigkeit*: welcher Art die Arbeit ist, in welchem Verhältnis man zum Gegenüber steht, wie lange Gespräche laufen, worüber gestritten wird. Das trägt die Realitätsnähe, ohne die Pilotunternehmen zu identifizieren.

**Die Bibliothek** (`backend/db/seed_data.py`) trägt denselben Fall mit erfundenen Konkreta: ein benanntes Produkt auf der eigenen Seite (*Kontura Flow*, *Kontura Archive*, *Kontura Connect*), Beträge, Datumsangaben, Ticketnummern, Dritte auf Nutzerseite mit Namen. Die Zahlen sind innerhalb eines Szenarios und über die Bibliothek hinweg stimmig (80 Euro je Nutzer, 1.600 Euro Tagessatz), weil eine Persona, die nachbohrt, jeden Widerspruch zutage fördert. Verboten bleibt genau das, was *identifiziert* oder was den *Anrufer* beschreibt:

| erlaubt und erwünscht | bleibt verboten |
|---|---|
| erfundenes Produkt der eigenen Seite samt Version | echte Unternehmen, Produkte, Orte, Marken, Partner |
| Beträge, Stückzahlen, Fristen, Ticketnummern | Name, Arbeitgeber oder Motiv **des Anrufers** (ADR 0045) |
| Dritte auf Nutzerseite mit Namen | Fachwissen, das von außen mitgebracht werden muss (C-05) |

Zwei Begründungen, und beide sagen etwas anderes, als frühere Fassungen dieses Abschnitts behauptet haben:

- **C-05 (R-40, R-41)** verlangt, dass das Training **ohne kundenspezifisches Produkt- und Fachwissen** durchführbar ist. Ein Fall, der seine Fakten selbst mitbringt, verlangt genau das nicht — ob das Produkt darin einen Namen trägt, ändert daran nichts. Verboten ist der Fall, der auf *ungenanntes* Wissen verweist. Das **Abstrakte ist hier die größere Gefahr**: „Der Prozess hat etwa acht Schritte" zwingt die Trainingsperson, die Lücke aus ihrem eigenen Arbeitsalltag zu füllen — also mit genau dem kundenspezifischen Wissen, das C-05 heraushalten wollte. C-05 ist erfüllt, weil der Fall geschlossen ist, nicht weil er blass ist.
- **ADR 0045** sagt das Gegenteil dessen, was ihm hier früher zugeschrieben wurde. Sein Abschnitt *„The Scenario carries the case"* führt das Produkt unter dem auf, was in `case_facts` **hineingehört**: *„the facts of the case: product, figures, dates, history"*. Die Einschränkung, die er macht, betrifft ausschließlich den Anrufer — *„never about the caller: no name, no employer, no personality, no motive"* — und die gilt unverändert weiter, denn sie ist es, die jede Persona jeden Fall tragen lässt (ADR 0015).

> **Zur Korrektur.** Bis Anfang September 2026 stand hier, `case_facts` seien „nie über ein benanntes System" zu schreiben, mit ADR 0045 als Beleg. Dieser Halbsatz steht im ADR nicht; er wurde beim Schreiben dieses Katalogs hinzuinterpretiert und hat die zwölf aus S-01–S-13 abgeleiteten Bibliothekseinträge abstrakter gemacht, als der ADR es verlangt — während die fünf älteren Einträge, die vor dem Katalog entstanden, immer schon Produkte und Beträge nannten. Es wurde hier keine Regel gekippt, sondern eine Fehlzuschreibung zurückgenommen. Ein ADR dazu gibt es deshalb nicht: Er würde eine Kursänderung dokumentieren, die es nie gab. Die zwölf Einträge sind inzwischen konkret nachgeschrieben.

---

## 2 Tätigkeitsprofile

Die beiden Pilotunternehmen unterscheiden sich nicht in der Person des Ansprechpartners, sondern in der **Struktur ihres Geschäfts**. Daraus folgt ihr unterschiedlicher Trainingsbedarf — und daraus wiederum, was der Katalog abdecken muss.

### Profil A — Betrieb und Betreuung im Bestandskundengeschäft

| Merkmal | Ausprägung |
|---|---|
| Leistung | laufender Betrieb, Betreuung, Störungsbehebung, schrittweise Weiterentwicklung bereits eingeführter Abläufe |
| Fachlicher Schwerpunkt | dokumenten- und beleggetriebene Geschäftsprozesse, angrenzende Systemtechnik |
| Kundenbeziehung | Bestandskunden, wiederkehrende Ansprechpartner, langfristig |
| Anlass eines Gesprächs | eine Störung, eine Rückfrage, ein offener Punkt aus einem laufenden Vorhaben |
| Rollen der Trainingspersonen | Support sowie beratende Projekt- und Entwicklungsrollen (**C-07**, R-01) |
| Gesprächsdauer | von der kurzen Rückfrage bis zum Termin von einer Stunde (**C-06**, R-03) |
| Vertriebsanteil | gering; Preisgespräche entstehen anlassbezogen, nicht als eigene Disziplin (**R-46**) |
| Belegstelle | SO 4.1, 4.4, 4.6, 5.1 |

### Profil B — Beratung und Einführung im Projektgeschäft

| Merkmal | Ausprägung |
|---|---|
| Leistung | Beratung, Analyse und Anforderungsklärung, Einführung einer Plattform- oder Automatisierungslösung |
| Fachlicher Schwerpunkt | Prozessaufnahme und -modellierung, Konfiguration statt Individualentwicklung, Anbindung an Bestehendes |
| Kundenbeziehung | Erstkontakte und Neukunden, gemischte Runden aus Fachbereich, IT und Einkauf |
| Anlass eines Gesprächs | eine Entscheidung mit Investitionscharakter, ein Angebot, eine offene Bewertung |
| Rollen der Trainingspersonen | technische Rollen ohne vertriebliche Vorerfahrung, Beratung, Geschäftsführung (**C-07**, R-02) |
| Gesprächsdauer | überwiegend 30 bis 60 Minuten, feste Phasenfolge (**R-13**) |
| Vertriebsanteil | hoch; Verhandlung und Einwandbehandlung sind Teil des Alltags (**R-10, R-12**) |
| Belegstelle | AP 3.1–3.6, AP 6 |

### 2.1 Wie der Katalog beide Profile trägt

Der Unterschied ist **strukturell, nicht personengebunden**: Profil A verkauft laufenden Betrieb an Bestehende, Profil B verkauft Veränderung an Neue. Das eine Profil fordert verhandlungsnahes Training ausdrücklich, das andere lehnt es für die eigenen Rollen ebenso ausdrücklich ab (**R-46**).

**Aufgelöst wird das über die Bibliothek selbst, nicht über eine Produktausrichtung.** F-03 führt ohnehin drei Szenario-Typen nebeneinander; das Angebots- und Preisgespräch ist einer davon, nicht der Zuschnitt des Werkzeugs. Im Produkt ist das die **Kategorie** eines Szenarios (`scenario.category`, ADR 0072) mit vier Werten — *Betrieb & Störung*, *Beratung & Anforderung*, *Preis & Kondition*, *Abschluss & Einwand* —, nach der die Szenarioauswahl filtert. Wer verhandlungsnah trainieren will, wählt eine der beiden letzten; wer nicht, eine der beiden ersten. Die Rolle, die jemand beim ersten Start angibt (F-62), wählt diese Kategorien für die Vorschläge vor — *Technischer Support* etwa nur *Betrieb & Störung* —, sperrt aber nichts. Es gibt keine Ausrichtung, gegen die sich ein Profil wehren müsste — und damit auch nichts zu entscheiden.

Daraus folgt die eigentliche Anforderung an diesen Katalog: **Beide Seiten müssen tatsächlich besetzt sein.** Eine Bibliothek, die nur Preisgespräche kennt, wäre für Profil A unbrauchbar, auch ohne dass das Produkt sich je auf Vertrieb festgelegt hätte. Der Katalog führt deshalb je Szenario das Attribut **Vertriebsnähe** (`neutral` / `beratungsnah` / `verhandlungsnah`) — als Orientierung beim Auffüllen der Bibliothek und als prüfbare Kennzahl der Ausgewogenheit (Abschnitt 6.3). Anders als die Kategorie ist es ein Attribut dieses Dokuments, kein Datenfeld und kein Filter im Produkt.

---

## 3 Aufbau eines Eintrags

ADR 0001 und ADR 0045 trennen strikt: die **Persona** trägt die *Art und Weise*, das **Szenario** trägt die *Sache*. Jede Persona muss mit jedem Szenario laufen können (ADR 0015). Der Katalog folgt dieser Trennung — ein Szenario enthält deshalb **keine** Persona-Beschreibung, sondern höchstens eine Empfehlung, welche Persona den Fall besonders scharf stellt.

Die Datenfelder haben **drei Adressaten**, und das bestimmt ihre Sprache: Was das Modell liest, ist Englisch, damit allein die Sprache der Persona entscheidet, in welcher Sprache gesprochen wird (ADR 0043). Was die Oberfläche zeigt, ist Deutsch. Und was sich an die **Trainingsperson** richtet, gelangt nie in den Prompt (ADR 0054, ADR 0062).

### Ein Szenario beschreibt

| Feld | Entspricht Datenfeld | Adressat | Inhalt |
|---|---|---|---|
| Titel | `title` (auf dem Wire `name`) | Oberfläche | Name auf der Szenariokarte |
| Kurzbeschreibung | `short_description` | Oberfläche | ein bis zwei Sätze auf der Karte |
| Situation | `description` / `description_label` | Modell / Oberfläche | die Ausgangslage — nur die Lage, kein Nutzerziel. Englisch für das Modell, deutscher Zwilling für das Infofenster hinter der Karte |
| Rolle Trainingsperson | Teil von `description` und `briefing` | Modell und Trainingsperson | in welcher Funktion der Nutzer angerufen wird. Die Rollen folgen **C-07** (R-01, R-02): Support, beratende Projektrollen, technische Rollen ohne vertriebliche Vorerfahrung |
| Fall | `case_facts` / `case_facts_label` | Modell / Oberfläche | Zahlen, Fristen, Vorgeschichte. Über den *Fall*, nie über den Anrufer. Enthält nur, was **der Anrufer** weiß |
| Anrufziel | `call_goal` | Modell | was der **Anrufer** erreichen will |
| Erledigt wenn | `call_goal` | Modell | die beobachtbare Bedingung, ab der der Anrufer die Sache als geklärt ansieht. Im Datenmodell **derselbe Absatz wie das Anrufziel** — die beiden Felder wurden zusammengelegt, weil die Trennung nur der Editor verlangte und nichts sie las. Der Katalog führt sie der Lesbarkeit halber weiter getrennt |
| Briefing | `briefing` | Trainingsperson | Rolle, Spielraum (was zugesagt, angeboten, eskaliert werden darf), was als gutes Ergebnis gilt. **Nie**, was zu sagen ist (R-43). Hier steht auch, was die Trainingsperson weiß und der Anrufer nicht (siehe S-12, S-13). Muss zur Bedingung in `call_goal` passen |
| Kategorie | `category` | Oberfläche (Filter) | `operations` / `requirements` / `pricing` / `closing` (ADR 0072), eine Verfeinerung der drei Typen aus **F-03**, siehe 6.1. Nie Prompt-Eingabe |
| Dauer | — | — | kurz / mittel / lang. **Eigene Achse**, nicht mit der Kategorie zu verwechseln. Spanne aus **C-06** (R-03) |
| Vertriebsnähe | *(Katalogattribut, kein Datenfeld)* | — | neutral / beratungsnah / verhandlungsnah — dient der Ausgewogenheit der Bibliothek, siehe 2.1 |
| Trainingsfokus | — | — | die Analyse-Features, die in diesem Fall greifen |
| Herkunft | — | — | `R-xx` / `C-xx` / `Systementwurf`, plus Tätigkeitsprofil |

> **Zur Rolle der Trainingsperson.** Sie ist kein eigenes Datenfeld: ADR 0045 hält fest, dass das *Ziel des Nutzers* nicht in den Persona-Prompt gehört. Was der Nutzer beruflich **ist**, steht dagegen sehr wohl in `description` — die Seed-Daten schreiben genau das („the user, who works in support") — und ein zweites Mal, an die Trainingsperson gerichtet, im `briefing`. Der Katalog führt es als eigene Zeile, weil C-07 die Zielgruppe verbindlich benennt und die Abdeckung darüber geprüft wird.

> **Zu Situation und Fall doppelt.** Englischer Prompttext und deutscher Anzeigetext werden **nicht maschinell abgeglichen** — die Tests prüfen nur, dass beide existieren und sich unterscheiden. Wer das eine ändert, muss das andere im selben Zug nachziehen.

### Eine Persona beschreibt

| Feld | Entspricht Datenfeld | Inhalt |
|---|---|---|
| Name | `name` | Vor- und Nachname; der Schlüssel `key` trägt ihn mit (eine Umbenennung ist ein neuer Datensatz) |
| Rolle | `role` / `role_label` | Funktion des Gegenübers — nur die Position, nichts Beschreibendes. Englisch für das Modell, kurzes deutsches Label für die Karte |
| Haltung | `traits` / `traits_label` | Charakterzüge |
| Manier | `behavior` | wie hartnäckig, wie lange vage Antworten toleriert werden, was sie zufriedenstellt — **nur Manier, nichts Situatives** |
| Einwände | `persona_objection.text` / `text_label` | 3–4 Stück, als *Bewegung* formuliert, nicht als Zitat, szenarioneutral (**R-12**) |
| Trainingsziel | `training_goal` | deutscher Satz fürs Infofenster („Was Sie hier trainieren"); erreicht das Modell nicht |
| Schwierigkeitsgrad | `difficulty` | leicht / mittel / schwer. Wird gespeichert, aber **weiterhin nirgends gelesen** und nicht ausgeliefert; ADR 0045 lässt ihn bestehen und nennt die Auswahlkarte (ADR 0015) als naheliegenden Ort |
| Sprache und Stimme | `language_code`, `kugelaudio_voice_id`, `tts_voice` | Sprache ist seit ADR 0043 eine Eigenschaft der **Persona**, nicht der Session und nicht des Szenarios (**C-01**). Ohne KugelAudio-Stimme bleibt eine Persona inaktiv |
| Porträt | `avatar_url` | Pfad auf `frontend/public/personas/<key>.webp`; fehlt es, zeigt die Oberfläche Initialen |
| Herkunft | — | `R-xx` / `Systementwurf` |

---

## 4 Persona-Katalog

Sortiert nach Belegstärke. **Direkt belegt** = im Erstgespräch benannt. **Abgeleitet** = folgt aus einer Anforderung, die auf ein anderes Feature zielt. **Systementwurf** = kein Beleg, bewusste Erfindung.

Anders als der Szenariokatalog ist der Persona-Katalog **dünn belegt**: In beiden Erhebungen zusammen sind genau zwei Kundentypen namentlich beschrieben (R-07, R-08). Alles Weitere trägt eine schwächere Kette. Das ist kein Grund, es nicht zu bauen — aber ein Grund, es auszuweisen.

| ID | Persona | Haltung und Manier | Herkunft | Belegstärke | Bibliothek |
|---|---|---|---|---|---|
| **P-01** | Kostenkritischer Bestandskunde | Nimmt jede Leistung an, solange sie nichts extra kostet. Sobald ein Preis fällt, bricht er ab — nicht laut, sondern endgültig. Verhandelt nicht, er lehnt ab. | **R-07** (SO 4.3, 4.5) | **Direkt belegt.** Der einzige wörtlich beschriebene Kundentyp der gesamten Erhebung. | **Marcel Kropp** · de · mittel |
| **P-02** | Technisch Verantwortlicher | Will die Langfassung, bohrt nach, prüft Sicherheit und Betrieb, stellt geschlossene Kontrollfragen. Entscheidet nicht allein und sagt das auch. | **R-08** (AP 3.5), Detail AP 3.2 | **Direkt belegt.** R-08 nennt Geschäftsführung *und* technische Leitung; beide Hälften sind besetzt. | **Patrick Lohberg** · de · schwer |
| **P-03** | Fachfremder Ansprechpartner | Ohne technisches Vorwissen. Steigt bei Fachbegriffen sichtbar aus und sagt es. Braucht Bilder statt Begriffe, gibt sich mit einer Definition nicht zufrieden. | **R-16** (AP 2.1) | **Belegt, indirekt.** R-16 ist der Nutzerbedarf; die Persona ist der Hebel, der ihn trainierbar macht. Trägt F-40. | **Floyd Jenkins** · **en** · leicht |
| **P-04** | Scheinbar klar, tatsächlich mehrdeutig | Formuliert knapp und selbstsicher, bestätigt Rückfragen zu schnell, meint aber etwas anderes. Das Missverständnis fällt erst spät auf — und dann sichtbar. | **R-17** (SO 3.1, 3.2) | **Belegt, indirekt.** R-17 ist der meistgenannte inhaltliche Schmerzpunkt aus Profil A. Anspruchsvollste Persona des Katalogs. | — |
| **P-05** | Anrufer unter Zeitdruck | Akutes Problem, wenig Geduld für Vorreden, beschreibt das Problem unpräzise, drängt auf eine Aussage. Sachlich, aber gereizt. | **R-06** (SO 4.5) + **R-09** | **Abgeleitet.** R-06 fordert emotionale Reaktionen, nennt aber keinen Typ; der Support-Kontext kommt aus R-09. | — |
| **P-06** | Wortkarger Gesprächspartner | Antwortet einsilbig, liefert von sich aus nichts. Wer nicht fragt, bekommt nichts — und das Gespräch versandet. | **R-50** (SO-S 1) | **Abgeleitet.** R-50 begründet die Kennzahl *Fragenanteil* mit „die fragende Seite führt". Diese Persona macht das erlebbar statt nur messbar. | **Kerstin Kaser** · de · mittel |
| **P-07** | Drängt auf sofortige Zusage | Verlangt eine verbindliche Entscheidung im Gespräch. „Ich frage intern nach" wird nicht akzeptiert — außer mit Termin und Namen. | **R-04** (SO 4.2, AP 3.2) — *offen* | **Interpretation.** Würde eine bisher heimatlose Anforderung schließen, aber nur unter einer Lesart, die rückzufragen ist (Abschnitt 7). | — |
| **P-08** | Geschäftsführung, Strategie und Budget | Ungeduldig mit technischen oder ausweichenden Antworten, erfahren im Verhandeln, will Zahl, Datum oder Namen. Eine konkrete Antwort beendet das Thema sofort. | **R-08** (AP 3.5) | **Direkt belegt.** | **Andreas Kastner** · de · mittel |
| **P-09** | Höflich und hartnäckig | Unterbricht nie, wird nie laut, ist aber genauso schwer zufriedenzustellen: dieselbe Frage ein drittes und viertes Mal, freundlich. | *Systementwurf* | **Kein Beleg.** Entstand als Nachweis des Sprachpfads (ADR 0043). Als Kontrast zu P-08 didaktisch wertvoll — gleiche Hartnäckigkeit, andere Tonlage — und deshalb zu behalten, aber ohne nachträglich erfundene R-Nummer. | **Phoebe Johnson** · **en** · leicht |
| **P-10** | Routinierter Einkäufer | Arbeitet mit Pausen, Vergleichen und Zeitdruck. Lässt Stille stehen, um sie füllen zu lassen. Nennt ein Vergleichsangebot, ohne es zu belegen. | **R-10** (AP 3.4) | **Abgeleitet.** R-10 belegt die Preisdiskussion als Gesprächsart, nicht diesen Typ. Nur für Profil B relevant. | — |
| **P-11** | Umständlicher Prozesskenner | Kennt den eigenen Ablauf im Schlaf und erklärt ihn in voller Länge, mit internen Kürzeln und Sonderfällen. Nimmt Nachfragen nicht übel, wiederholt aber gern. | *Systementwurf* (spiegelt **R-15**, **R-16**) | **Kein direkter Beleg.** Das Gegenstück zu P-03: hier muss der Nutzer *zuhören und ordnen*, statt zu vereinfachen. | — |
| **P-12** | Formeller Ansprechpartner | Protokollarisch, notiert Zusagen mit und liest sie zurück. Fragt nach Zuständigkeit, Nachweis und Verbindlichkeit statt nach Funktion. | *Systementwurf* | **Kein Beleg.** Plausibel für reguliertes Umfeld in Profil B, aber vollständig erfunden. | — |
| **P-13** | Eskalierend nach Ausfall | Laut, unterbricht, wiederholt die Dringlichkeit, fordert einen Zeitpunkt. Beruhigt sich erst, wenn ein konkreter Termin genannt wird. | **R-06** (SO 4.5), stark erweitert | **Abgeleitet, grenzwertig.** R-06 belegt „emotionale Reaktionen"; *Eskalation* ist unsere Auslegung. Beide Erhebungen sprechen von Missverständnissen, nicht von Konflikt. Vor dem Bau rückzufragen. | — |
| **P-14** | Enttäuscht, dann fordernd | Zunächst auffällig still, gibt wenig zurück; kippt dann in eine Forderung nach Ausgleich oder Zusage. | *Systementwurf* | **Kein Beleg.** Eine eigenständige Manier, weil sie den Umgang mit *Schweigen* trainiert — sonst deckt kein Eintrag das ab. | — |

Die Spalte **Bibliothek** nennt Name, Sprache und den gespeicherten Schwierigkeitsgrad. Die Seed-Schlüssel lauten `marcel-kropp-cost-critical`, `patrick-lohberg-it-lead`, `floyd-jenkins-non-technical`, `kerstin-kaser-clerk`, `andreas-kastner-ceo` und `phoebe-johnson-marketing`.

> **Zur Sprache.** Dass P-03 und P-09 englisch sprechen, ist eine Setzung der Bibliothek, keine Eigenschaft des Katalogtyps: Jeder Typ ließe sich in jeder Sprache anlegen. Weil die Sprache an der Persona hängt, bestimmt diese Wahl allerdings, **wer** für ein Training auf Englisch zur Verfügung steht (siehe S-14).

### 4.1 Regel für die Einwände (R-12, ADR 0045)

`persona_objection` ist seit ADR 0045 das Zuhause von R-12. Beim Schreiben gilt:

- **Zweisprachig**: `text` ist Englisch und geht an das Modell, `text_label` ist der deutsche Zwilling fürs Infofenster. Beide werden im selben Zug geschrieben.
- **Als Bewegung, nicht als Zitat**: *„refuses outright as soon as an additional cost is named"*, nicht der wörtliche Satz. Das Modell übernimmt Zitate wörtlich und kollabiert dann auf eine einzige Formulierung.
- **Szenarioneutral** — sonst bricht ADR 0015.
- Drei bis vier je Persona.

Der eine wörtlich belegte Einwand aus der Erhebung (Profil A, kostenkritischer Kunde: sinngemäß *„wenn das etwas kostet, dann nicht"*) geht deshalb nicht als Zitat in die Daten, sondern als Bewegung — bei Marcel Kropp steht er genau so als erster Einwand. Der Wortlaut gehört in die Belegkette, nicht in den Prompt.

---

## 5 Szenario-Katalog

Die Zeile **Fall** beschreibt hier den *Falltyp*, nicht den ausgelieferten Trainingsfall. Der Eintrag in der Bibliothek trägt denselben Fall mit erfundenen Konkreta — benanntes Produkt, Beträge, Datumsangaben, Ticketnummern. Warum beide Ebenen sich unterscheiden müssen, steht in Abschnitt 1.1. Die Zeile **Bibliothek** nennt Seed-Schlüssel, Titel und Kategorie des Datensatzes; wo der Titel im Produkt vom Katalogtitel abweicht, gilt für die Oberfläche der Titel der Bibliothek.

### 5.1 Aus Profil A — Betrieb und Betreuung

#### S-01 Störung im laufenden Betrieb

| | |
|---|---|
| **Situation** | Ein wiederkehrender, beleggetriebener Ablauf bleibt stehen; Vorgänge werden nicht mehr zugeordnet. Ein Stichtag steht bevor. |
| **Fall** | Der Ablauf läuft seit Jahren unverändert. Seit einem Versionsupdate vor gut einer Woche bleiben alle Vorgänge liegen, rund 30 pro Tag, inzwischen knapp hundert. Der Behelf ist manuelle Einzelzuordnung. Ein Ticket ist offen, ohne Rückmeldung. Der Stichtag ist in acht Tagen; was bis dahin liegt, rutscht in die nächste Periode. |
| **Anrufziel** | Wissen, woran es liegt, und ein Datum bekommen, bis zu dem es wieder läuft. |
| **Erledigt wenn** | ein Grund und ein Termin genannt werden — oder klar gesagt wird, dass es bis zum Stichtag nicht behoben ist und was stattdessen gilt. Eine Zusage zu prüfen reicht nicht. |
| **Rolle Trainingsperson** | Support |
| **Typ / Dauer** | Kurzer Support-Fall / kurz |
| **Vertriebsnähe** | neutral |
| **Trainingsfokus** | F-08, F-24, F-36, F-41 |
| **Empfohlene Personas** | P-05, P-13 |
| **Herkunft** | **R-09** (SO 4.1, 4.4), **R-03** — Profil A |
| **Bibliothek** | `process-halted-before-deadline` · „Störung im laufenden Betrieb" · Betrieb & Störung |

#### S-02 Fachliche Erklärung an einen fachfremden Ansprechpartner

| | |
|---|---|
| **Situation** | Eine bevorstehende, verpflichtende Umstellung mit gesetzter Frist betrifft einen Ablauf des Kunden. Der Kunde will wissen, was das für ihn heißt und was er tun muss. |
| **Fall** | Eine Schnittstelle, über die ein Ablauf des Kunden läuft, wird zu einem festen Termin abgeschaltet. Betroffen ist ein Ablauf, den drei Personen bedienen, keine davon technisch; auch Dritte, die Daten zuliefern, müssten umstellen. Es gab bereits ein Rundschreiben, das niemand verstanden hat. Budget ist nicht eingeplant. |
| **Anrufziel** | In eigenen Worten erklärt bekommen, was zu tun ist und was es kostet — ohne Fachbegriffe. |
| **Erledigt wenn** | drei konkrete Schritte benannt sind, die der Anrufer nachvollziehbar wiedergeben kann. Ein Verweis auf eine Dokumentation reicht nicht. |
| **Rolle Trainingsperson** | Beratung oder Entwicklung |
| **Typ / Dauer** | Beratendes Projektgespräch / mittel |
| **Vertriebsnähe** | neutral |
| **Trainingsfokus** | F-08, F-40, F-38, F-10 |
| **Empfohlene Personas** | P-03, P-06 |
| **Herkunft** | **R-16** (AP 2.1), **R-15** (SO 3.1) — profilübergreifend |
| **Bibliothek** | `explain-mandatory-change-plainly` · „Erklärung für einen fachfremden Kontakt" · Beratung & Anforderung |

> **C-05-Hinweis:** Der Fall trägt bewusst *die Form* einer verpflichtenden Frist, nicht deren Inhalt. Er darf kein Fachwissen über eine bestimmte Regelung voraussetzen — sonst ist er nicht mehr ohne Wissensbasis spielbar. Die Bibliothek löst das, indem die Frist das Abschaltdatum des eigenen (erfundenen) Produkts ist, nicht eine gesetzliche Regelung.

#### S-03 Anforderungsklärung bei vagem Kundenwunsch

| | |
|---|---|
| **Situation** | Der Kunde möchte einen wiederkehrenden manuellen Ablauf „automatisieren", kann aber weder Auslöser noch Zielzustand benennen. |
| **Fall** | Der Ablauf wird von zwei Abteilungen unterschiedlich gehandhabt. Zwei frühere Anläufe sind ohne Ergebnis geblieben. Ein Budget ist nicht genannt, ein Wunschtermin schon: „möglichst dieses Jahr". |
| **Anrufziel** | Herausfinden, ob das machbar ist und wie es weitergeht. |
| **Erledigt wenn** | der Anrufer benennen kann, was als Nächstes passiert, wer es tut und wann. Eine allgemeine Machbarkeitsaussage reicht nicht. |
| **Rolle Trainingsperson** | Beratung oder Entwicklung |
| **Typ / Dauer** | Beratendes Projektgespräch / lang |
| **Vertriebsnähe** | beratungsnah |
| **Trainingsfokus** | F-41, F-24, F-42 |
| **Empfohlene Personas** | P-04, P-11, P-06 |
| **Herkunft** | **R-17** (SO 3.1, 3.2), **R-10** (AP 3.4, Anforderungsdefinition) — **beidseitig belegt** |
| **Bibliothek** | `vague-automation-request` · „Anforderungsklärung bei vagem Wunsch" · Beratung & Anforderung |

#### S-04 Leistung außerhalb des Vertrags

| | |
|---|---|
| **Situation** | Eine gewünschte Anpassung ist vom laufenden Vertrag nicht gedeckt und wäre als Aufwand zu berechnen. |
| **Fall** | Der Vertrag deckt Betrieb und Fehlerbehebung, nicht Erweiterungen. Der Wunsch entspricht etwa einem Tag Aufwand. Vergleichbares wurde vor zwei Jahren einmal kulanzhalber ohne Berechnung erledigt, und der Anrufer erinnert sich genau daran. |
| **Anrufziel** | Die Anpassung bekommen — ohne zusätzliche Kosten. |
| **Erledigt wenn** | entweder eine Zusage ohne Berechnung vorliegt, oder nachvollziehbar begründet ist, warum berechnet wird, **und** der Anrufer diese Begründung wiedergeben kann. |
| **Rolle Trainingsperson** | Beratung oder Kundenverantwortung |
| **Typ / Dauer** | Angebots- und Preisgespräch / mittel |
| **Vertriebsnähe** | beratungsnah — **ausdrücklich kein Abschlussgespräch** |
| **Trainingsfokus** | F-35, F-39, F-42 |
| **Empfohlene Personas** | **P-01** (der Fall, für den sie gedacht ist), P-08 |
| **Herkunft** | **R-07** (SO 4.3, 4.5) — Profil A |
| **Bibliothek** | `change-outside-contract-scope` · „Leistung außerhalb des Vertrags" · Preis & Kondition |

#### S-05 Eskalation nach einem Ausfall

| | |
|---|---|
| **Situation** | Eine zentrale Systemkomponente ist seit dem Morgen gestört. Die Geschäftsführung des Kunden ruft selbst an und ist verärgert. |
| **Fall** | Der Ausfall dauert seit fünf Stunden. Betroffen sind alle Standorte. Eine erste Meldung wurde vor drei Stunden aufgenommen, seither kam keine Rückmeldung. Ein vergleichbarer Ausfall lag zuletzt vor vier Monaten vor. |
| **Anrufziel** | Einen Zeitpunkt genannt bekommen und wissen, wer sich kümmert. |
| **Erledigt wenn** | ein Name und ein Zeitpunkt genannt sind — oder offen gesagt wird, dass beides noch nicht feststeht, samt Zusage, wann es feststeht. |
| **Rolle Trainingsperson** | Support oder Kundenverantwortung |
| **Typ / Dauer** | Kurzer Support-Fall / kurz |
| **Vertriebsnähe** | neutral |
| **Trainingsfokus** | F-37, F-35, F-41, F-42 |
| **Empfohlene Personas** | **P-13**, P-07 |
| **Herkunft** | **R-06** (SO 4.5) — Profil A. Eskalationsgrad ist Auslegung, siehe P-13 |
| **Bibliothek** | `outage-escalation-no-callback` · „Eskalation nach einem Ausfall" · Betrieb & Störung |

> **Wer anruft, steht nicht im Fall.** Die Situation nennt „die Geschäftsführung"; in der Bibliothek ist das gestrichen, weil es den Anrufer beschreibt (ADR 0045) und der Fall mit jeder Persona laufen muss. Wie laut der Ausfall vorgetragen wird, ist Sache der Persona.

#### S-06 Folgetermin in einem laufenden Vorhaben

| | |
|---|---|
| **Situation** | Dritter Abstimmungstermin zu einem laufenden Vorhaben. Offene Punkte aus der Vorwoche sind teilweise ungeklärt. |
| **Fall** | Von fünf Punkten der Vorwoche sind zwei erledigt, zwei offen, einer ist zwischenzeitlich hinfällig geworden. Für einen offenen Punkt war eine Rückmeldung zugesagt, die nicht kam. |
| **Anrufziel** | Die offenen Punkte abschließen und wissen, woran es beim zugesagten Rückruf gehakt hat. |
| **Erledigt wenn** | zu jedem offenen Punkt ein Stand und ein nächster Schritt vorliegt. |
| **Rolle Trainingsperson** | Projekt- und Entwicklungsseite |
| **Typ / Dauer** | Beratendes Projektgespräch / lang, sitzungsübergreifend |
| **Vertriebsnähe** | beratungsnah |
| **Trainingsfokus** | F-23, F-13, F-42 |
| **Empfohlene Personas** | P-04, P-08 |
| **Herkunft** | **R-11** (SO 4.4, 4.6) → **F-23** — Profil A |
| **Bibliothek** | — nicht angelegt |

> **Technisch blockiert.** F-23 setzt voraus, dass sich der Gegenpart an frühere Termine *erinnert*. Ein sitzungsübergreifendes Gedächtnis gibt es nicht, und `scenario` hat kein Feld dafür. Heute ließe sich der Fall nur als Vorgeschichte in den `case_facts` bauen — dann erinnert sich der Gegenpart nicht, er wurde informiert. Das ist ein anderes Feature.
>
> **Am nächsten kommt das Folgeszenario** (F-60, ADR 0069 mit zweiter Ergänzung): Nach einem Training lässt sich auf Wunsch der *nächste Anruf in derselben Sache* erzeugen, der den Fall des gespielten Szenarios samt dessen Ausgang fortschreibt. Das ist genau die „informierte" Variante — pro Nutzer aus dem eigenen Training erzeugt, nicht als Bibliothekseintrag. S-06 als eigener Datensatz bleibt deshalb unangelegt; F-23 ist weiterhin nicht gebaut.

#### S-07 Absicherndes Wrap-up am Gesprächsende

| | |
|---|---|
| **Situation** | Am Ende eines Klärungsgesprächs soll das gemeinsame Verständnis mündlich zusammengefasst werden, bevor die schriftliche Zusammenfassung folgt. |
| **Fall** | Vier Punkte wurden besprochen. Bei einem davon liegt ein Missverständnis vor: Der Anrufer hat etwas anderes verstanden, als gemeint war, und wird das beim Zusammenfassen bemerken — aber nur, wenn die Zusammenfassung konkret genug ist, um ihm zu widersprechen. |
| **Anrufziel** | Sicher sein, dass beide Seiten dasselbe meinen. |
| **Erledigt wenn** | die Zusammenfassung alle vier Punkte trifft **und** der abweichende Punkt aufgefallen und richtiggestellt ist. |
| **Rolle Trainingsperson** | beliebig (in der Bibliothek: Support oder Beratung) |
| **Typ / Dauer** | Kurzer Support-Fall / kurz |
| **Vertriebsnähe** | neutral |
| **Trainingsfokus** | F-08, F-40, F-41, F-54 |
| **Empfohlene Personas** | P-04, P-06 |
| **Herkunft** | **R-31** (SO 2.3, 3.3), **R-17** — Profil A, direkt aus der dokumentierten Praxis der Zusammenfassungsmail |
| **Bibliothek** | `closing-recap-mismatch` · „Absicherndes Wrap-up am Gesprächsende" · Betrieb & Störung |

### 5.2 Aus Profil B — Beratung und Einführung

Alle Szenarien dieses Abschnitts sind **Vorschläge**. Für Profil B fehlt eine dem Erstgespräch von Profil A vergleichbare Detailtiefe zu typischen Gesprächsverläufen (Abschnitt 7). S-08 bis S-13 sind trotzdem als Datensätze angelegt — mit dem ausdrücklichen Vermerk in `seed_data.py`, dass sie nicht mit den Kunden gegengeprüft sind.

#### S-08 Prozessaufnahme im Fachbereich

| | |
|---|---|
| **Situation** | Erstes Gespräch mit einem Fachbereich, um einen bestehenden manuellen Ablauf für eine spätere Modellierung zu erfassen. |
| **Fall** | Der Ablauf hat vier Schritte und drei Sonderfälle. Er ist nur auf einem veralteten Blatt beschrieben. Zwei Personen führen einen Schritt unterschiedlich aus, was messbar Nacharbeit erzeugt. Der Anrufer, einer der beiden, hält beide Varianten für dasselbe. |
| **Anrufziel** | Erklären, wie es heute läuft, und wissen, wie es weitergeht. |
| **Erledigt wenn** | die Schritte zurückgespiegelt wurden **und** die Abweichung zwischen den beiden Varianten benannt ist. |
| **Rolle Trainingsperson** | Beratung / Anforderungsanalyse |
| **Typ / Dauer** | Beratendes Projektgespräch / lang |
| **Vertriebsnähe** | beratungsnah |
| **Trainingsfokus** | F-24, F-41, F-40 |
| **Empfohlene Personas** | **P-11**, P-04 |
| **Herkunft** | **R-10** (AP 3.4, Anforderungsdefinition) — Profil B |
| **Bibliothek** | `process-capture-interview` · „Prozessaufnahme im Fachbereich" · Beratung & Anforderung |

#### S-09 Einwände gegen die Technologieentscheidung

| | |
|---|---|
| **Situation** | Der Kunde äußert Vorbehalte gegen den vorgeschlagenen Lösungsansatz: Abhängigkeit vom Anbieter, Grenzen bei komplexen Anforderungen, Zweifel an der Tragfähigkeit auf Dauer. |
| **Fall** | Ein früheres Vorhaben mit vergleichbarem Ansatz ist beim Kunden nach zwei Jahren abgelöst worden. Der Anrufer war daran beteiligt und führt es an, ohne die Gründe genau zu kennen. Eine Entscheidung steht in sechs Wochen an. |
| **Anrufziel** | Prüfen, ob der Einwand entkräftet werden kann — und zwar mit Belegen, nicht mit Zusicherungen. |
| **Erledigt wenn** | jeder der drei Vorbehalte eine konkrete Antwort erhalten hat, oder offen als Risiko benannt ist. Eine pauschale Beruhigung zählt nicht. |
| **Rolle Trainingsperson** | Beratung oder Geschäftsführung |
| **Typ / Dauer** | Angebots- und Preisgespräch / mittel |
| **Vertriebsnähe** | **verhandlungsnah** |
| **Trainingsfokus** | F-40, F-08, F-39 |
| **Empfohlene Personas** | **P-02**, P-08 |
| **Herkunft** | **R-12** (AP 2.1, 6) — Profil B |
| **Bibliothek** | `technology-choice-objections` · „Einwände gegen die Lösungswahl" · **Abschluss & Einwand** |

> Die Kategorie weicht vom F-03-Typ ab: Der Fall ist ein Angebotsgespräch, aber es wird nicht über den Preis gestritten, sondern über Vorbehalte vor einer Entscheidung. ADR 0072 trennt genau deshalb *Preis & Kondition* von *Abschluss & Einwand*.

#### S-10 Preis- und Konditionsverhandlung

| | |
|---|---|
| **Situation** | Der Einkauf des Kunden fordert einen Nachlass und verweist auf ein Vergleichsangebot. |
| **Fall** | Das vorliegende Angebot liegt bei einem laufenden Jahresbetrag im mittleren fünfstelligen Bereich. Gefordert wird ein fester Prozentsatz Nachlass. Das genannte Vergleichsangebot liegt rund 20 Prozent darunter, deckt aber nach Aktenlage einen kleineren Umfang ab — was der Anrufer nicht von sich aus sagt, sondern erst auf Nachfrage einräumt. Die Entscheidung soll in dieser Woche fallen. |
| **Anrufziel** | Den Preis senken. Der Verweis auf den Wettbewerb ist das Mittel, nicht das Ziel. |
| **Erledigt wenn** | eine Zahl mit Gültigkeitsdatum zugesagt ist, oder klar gesagt wird, dass es keinen Nachlass gibt und warum. „Ich prüfe das intern" ist kein Ergebnis. |
| **Rolle Trainingsperson** | Vertrieb oder Geschäftsführung |
| **Typ / Dauer** | Angebots- und Preisgespräch / mittel |
| **Vertriebsnähe** | **verhandlungsnah** — für Profil A nicht einschlägig (**R-46**), dort wird schlicht ein anderes Szenario gewählt |
| **Trainingsfokus** | F-35, F-36, F-41, F-42 |
| **Empfohlene Personas** | **P-10**, P-08 |
| **Herkunft** | **R-10** (AP 3.4) — Profil B. Deckt die verhandlungsnahe Seite ab, die Profil B ausdrücklich fordert |
| **Bibliothek** | `procurement-price-negotiation` · „Preis- und Konditionsverhandlung" · Preis & Kondition |

#### S-11 Gespräch mit einer skeptischen IT-Seite

| | |
|---|---|
| **Situation** | Der Fachbereich ist überzeugt, die IT-Seite sieht Steuerbarkeit, Sicherheit und Betrieb gefährdet, wenn Fachbereiche selbst konfigurieren. |
| **Fall** | Der Fachbereich hat bereits ohne Abstimmung mit einer Testumgebung begonnen und Firmendaten hineingeladen. Es gibt eine interne Richtlinie, die das untersagt. Weitere Fachbereiche wollen nachziehen. Die IT-Seite ist nicht grundsätzlich dagegen, sondern übergangen worden — was ein anderer Einwand ist als der, den sie laut vorbringt. |
| **Anrufziel** | Klären, wer künftig was entscheidet und betreibt. |
| **Erledigt wenn** | Zuständigkeit, Freigabeweg und Betriebsverantwortung benannt sind. |
| **Rolle Trainingsperson** | Beratung |
| **Typ / Dauer** | Beratendes Projektgespräch / mittel |
| **Vertriebsnähe** | beratungsnah |
| **Trainingsfokus** | F-42, F-40, F-24 |
| **Empfohlene Personas** | **P-02**, P-12 |
| **Herkunft** | **R-08** (AP 3.5), **R-04** (AP 3.2, in Lesart 2, siehe Abschnitt 7) — Profil B |
| **Bibliothek** | `sceptical-it-governance` · „Gespräch mit einer skeptischen IT-Seite" · Beratung & Anforderung |

#### S-12 Gespräch im regulierten Umfeld

| | |
|---|---|
| **Situation** | Ein Ansprechpartner aus einem stark regulierten Bereich fragt nach Datenhaltung, Zugriffsrechten und Nachweispflichten. |
| **Fall** | Eine interne Prüfung steht in drei Monaten an. Was gesagt wird, wird dort zitiert. Dieselben Fragen blieben vor der letzten Prüfung teilweise unbeantwortet. Der Anrufer notiert mit und liest Zusagen zurück. |
| **Briefing** | Für zwei der drei Fragen hat die Trainingsperson eine belastbare Antwort, für die dritte nicht. |
| **Anrufziel** | Für jede Frage eine belastbare, zitierfähige Aussage bekommen. |
| **Erledigt wenn** | jede Frage entweder beantwortet oder ausdrücklich als offen markiert ist — mit Zusage, wer bis wann nachliefert. Eine unsichere Antwort, die sicher klingt, gilt als **nicht** erledigt. |
| **Rolle Trainingsperson** | Beratung |
| **Typ / Dauer** | Beratendes Projektgespräch / mittel |
| **Vertriebsnähe** | beratungsnah |
| **Trainingsfokus** | F-42, F-40, F-38, F-39 |
| **Empfohlene Personas** | **P-12**, P-02 |
| **Herkunft** | *Systementwurf* — plausibel für Profil B, nicht belegt |
| **Bibliothek** | `regulated-environment-questions` · „Gespräch im regulierten Umfeld" · Beratung & Anforderung |

> **Wissen der Trainingsperson gehört ins Briefing, nicht in den Fall.** Welche Frage keine belastbare Antwort hat, weiß die Anbieterseite, nicht der Anrufer. Stünde es in `case_facts`, spielte das Modell den Anrufer allwissend. Frühere Fassungen dieses Eintrags führten es unter *Fall*.

#### S-13 Termin- und Erwartungskorrektur

| | |
|---|---|
| **Situation** | Ein zugesagter Termin ist nicht haltbar. Der Kunde hat intern bereits darauf geplant. |
| **Fall** | Der Termin war vor sechs Wochen zugesagt und liegt in wenigen Tagen. Der Kunde hat nachgelagerte Termine daran gehängt, davon einen mit Dritten, der nur bis zu einer Frist kostenfrei abgesagt werden kann. Der Anrufer ruft an, um den Termin bestätigt zu bekommen, und ahnt nichts von einer Verschiebung. |
| **Briefing** | Die Trainingsperson weiß, dass der Termin nicht zu halten ist, warum, und welcher neue Termin realistisch ist. |
| **Anrufziel** | Den Termin bestätigt bekommen — und falls er nicht hält, wissen, was jetzt gilt und ob der Termin mit Dritten zu retten ist. |
| **Erledigt wenn** | ein neuer Termin genannt ist **und** gesagt wurde, was mit dem nachgelagerten Termin passiert. |
| **Rolle Trainingsperson** | Projektleitung |
| **Typ / Dauer** | Kurzer Support-Fall / kurz |
| **Vertriebsnähe** | neutral |
| **Trainingsfokus** | F-35, F-39, F-41, F-37 |
| **Empfohlene Personas** | **P-14**, P-07 |
| **Herkunft** | *Systementwurf*, gestützt auf **R-06** — profilübergreifend |
| **Bibliothek** | `deadline-correction` · „Termin- und Erwartungskorrektur" · Betrieb & Störung |

#### S-14 Abstimmung in englischer Sprache

| | |
|---|---|
| **Situation** | Abstimmung mit einem internationalen Projektpartner zu einem laufenden Vorhaben. |
| **Fall** | Wie S-06 oder S-08, nur in englischer Sprache geführt. |
| **Anrufziel** | Wie im zugrunde liegenden Szenario. |
| **Erledigt wenn** | Wie im zugrunde liegenden Szenario. |
| **Rolle Trainingsperson** | Beratung oder Projektleitung |
| **Typ / Dauer** | Beratendes Projektgespräch / mittel |
| **Vertriebsnähe** | beratungsnah |
| **Trainingsfokus** | F-36, F-38, F-51 |
| **Empfohlene Personas** | eine Persona mit `language_code = en` (heute P-03 Floyd Jenkins oder P-09 Phoebe Johnson) |
| **Herkunft** | **R-35** (SO 4.3, AP 3.3) — Profil B |
| **Bibliothek** | — kein eigener Datensatz, siehe unten |

> **Kein eigenes Szenario.** Die Sprache hängt seit ADR 0043 an der **Persona**, nicht am Szenario — Szenarien sind sprachneutral. „Englisches Szenario" ist damit keine Kategorie: Man wählt eine englischsprachige Persona zu einem beliebigen Szenario. S-14 bleibt als *Hinweis* im Katalog stehen, wird aber **nicht** als eigener Datensatz angelegt. Nach einem Training bietet der Nachgesprächsbildschirm dasselbe Szenario mit einer Persona der anderen Sprache ausdrücklich an (F-64, ADR 0087).
>
> **C-01 verbietet Englisch nicht — im Gegenteil.** Die Randbedingung heißt „Sprache konfigurierbar" und führt Englisch ausdrücklich als belegt (R-35). Die frühere Beschränkung auf Deutsch stand in **ADR 0006, und die ist abgelöst** (0006 → 0022 → 0043). Es gibt zwei englischsprachige Personas und ein englisches Language Pack. Die verbleibende Einschränkung ist rein technisch: Der DiReKT-Fallback hält nur deutsche Stimmen vor, eine englische Persona hängt damit an der Verfügbarkeit von KugelAudio.
>
> Ein Feature „Training auf Englisch" existiert nicht; die in einer früheren Fassung genannte ID **F-25 gibt es im Feature-Katalog nicht**. Die Sprache wird über C-01 und R-35 geführt, die Umschaltung der *Oberfläche* getrennt davon über F-56.

### 5.3 Bibliothekseinträge ohne Katalogeintrag

Fünf Szenarien sind **vor** diesem Katalog entstanden und haben keine S-Nummer. Sie werden hier nur geführt, damit die Abdeckung in Abschnitt 6 die ganze Bibliothek zählt. Typ, Dauer und Vertriebsnähe sind nachträglich eingeordnet; eine Belegkette haben sie nicht (*Systementwurf*).

| Seed-Schlüssel | Titel | Kategorie | Rolle Trainingsperson | Typ / Dauer | Vertriebsnähe |
|---|---|---|---|---|---|
| `cold-call-followup` | Offenes Anliegen zu bestehendem Vertrag | Betrieb & Störung | Support | Kurzer Support-Fall / kurz | neutral |
| `escalation-repeated-outage` | Wiederholter Ausfall trotz Zusage | Betrieb & Störung | Support | Kurzer Support-Fall / kurz | neutral |
| `price-cancellation-risk` | Kündigungsabsicht wegen Preis | Preis & Kondition | Vertrieb | Angebots- und Preisgespräch / mittel | verhandlungsnah |
| `upsell-seat-expansion` | Ausbau auf eine zweite Abteilung | Abschluss & Einwand | Vertrieb | Angebots- und Preisgespräch / kurz | verhandlungsnah |
| `closing-after-handover` | Abschluss nach Erstgespräch mit Kollegin | Abschluss & Einwand | Vertrieb | Angebots- und Preisgespräch / mittel | verhandlungsnah |

### 5.4 Was außerhalb dieses Katalogs in die Bibliothek kommt

Der Katalog beschreibt nur die **ausgelieferten** Szenarien. Neben ihnen enthält die Bibliothek eines Nutzers Einträge, die hier bewusst nicht geführt werden, weil sie keinen fachlichen Vorlauf haben:

| Art | Entsteht durch | Beleg |
|---|---|---|
| Eigene Szenarien („Individuell") | Nutzer schreibt sie im Editor, optional aus PDF-Fakten; im eigenen Unternehmen teilbar | ADR 0058, ADR 0060, F-58 |
| Folgeszenario | auf Wunsch nach einem Training aus dessen Verbesserungspunkten, als nächster Anruf in derselben Sache | ADR 0069, F-60 |
| Rollentausch | auf Wunsch nach einem Training: derselbe Fall, der Nutzer ruft an | ADR 0070, F-61 |
| Zufallsszenario | kein Datensatz — zieht beim Start aus den ausgelieferten und eigenen Szenarien der aktuellen Filter | F-62 |

Für alle vier gilt die Regel aus Abschnitt 1.1 unverändert; für eigene Szenarien setzt sie `backend/authored_text.py` an der Schreibgrenze durch (ADR 0059).

---

## 6 Abdeckung

### 6.1 Nach Kategorie (ADR 0072) und Szenario-Typ (F-03)

Die vier Kategorien verfeinern die drei Typen aus F-03: Das Angebots- und Preisgespräch ist geteilt, weil einen Preis herunterzuhandeln und zu einer Unterschrift zu kommen verschiedene Übungen sind.

| Kategorie | Anzeige | F-03-Typ | aus dem Katalog | ohne Katalogeintrag | Bibliothek |
|---|---|---|---|---|---|
| `operations` | Betrieb & Störung | Kurze Support-Fälle | S-01, S-05, S-07, S-13 | 2 | **6** |
| `requirements` | Beratung & Anforderung | Längere beratende Projektgespräche | S-02, S-03, S-08, S-11, S-12 *(S-06 nicht angelegt)* | — | **5** |
| `pricing` | Preis & Kondition | Angebots- und Preisgespräche | S-04, S-10 | 1 | **3** |
| `closing` | Abschluss & Einwand | Angebots- und Preisgespräche | S-09 | 2 | **3** |

Alle drei Typen aus F-03 und alle vier Kategorien sind in der Bibliothek besetzt. Der beratende Typ, der vor dem Katalog vollständig fehlte, ist mit fünf Einträgen jetzt der zweitgrößte.

### 6.2 Nach Dauer (C-06, R-03)

| Dauer | Katalog | ohne Katalogeintrag |
|---|---|---|
| kurz | S-01, S-05, S-07, S-13 | `cold-call-followup`, `escalation-repeated-outage`, `upsell-seat-expansion` |
| mittel | S-02, S-04, S-09, S-10, S-11, S-12, S-14 | `price-cancellation-risk`, `closing-after-handover` |
| lang | S-03, S-06, S-08 | — |

C-06 spannt „kurze Rückfrage bis eine Stunde" auf; alle drei Längen sind im Katalog vertreten, in der Bibliothek *lang* nur mit S-03 und S-08.

> **Dauer ist die Anlage des Falls, nicht die gespielte Gesprächslänge.** Weder Szenario noch Persona begrenzen die Dauer, und die tatsächlich geführten Trainings laufen erheblich kürzer als eine Stunde — typisch sechs bis neun Äußerungen der Persona. Ein „langer" Fall ist einer, der ein langes Gespräch *tragen würde*.

> **6.1 und 6.2 zusammen belegen Q-06.** Das Qualitätsziel *Flexibilität der Trainingssituation* (arc42 Kap. 10, Herkunft R-03/R-09) verlangt wörtlich, dass das System „unterschiedliche Szenario-Typen und Gesprächslängen von kurzen Support-Fällen bis zu einstündigen Gesprächen" unterstützt. Dieser Katalog ist der inhaltliche Nachweis für die Typen und die *angelegten* Längen; ob einstündige Gespräche im Training auch tatsächlich entstehen, belegt er nicht.

### 6.2a Nach Rolle der Trainingsperson (C-07)

| Rolle | Katalog | ohne Katalogeintrag |
|---|---|---|
| Support | S-01, S-05, S-07 | `cold-call-followup`, `escalation-repeated-outage` |
| Beratung / Entwicklung / Anforderungsanalyse | S-02, S-03, S-04, S-07, S-08, S-09, S-11, S-12, S-14 | — |
| Projekt- und Entwicklungsseite, Projektleitung | S-06, S-13 | — |
| Vertrieb / Geschäftsführung | S-09, S-10 | `price-cancellation-risk`, `upsell-seat-expansion`, `closing-after-handover` |

C-07 nennt drei Gruppen: Support, beratende Projektrollen und technische Rollen ohne vertriebliche Vorerfahrung. Alle drei sind abgedeckt. Mit den älteren Einträgen hat die Support-Seite in der Bibliothek fünf Szenarien, die Vertriebsseite ebenfalls fünf.

Im Produkt fragt der erste Start nach einer **Rolle** (F-62), die bestimmte Kategorien für die Szenario-Vorschläge vorwählt (`TRAINING_ROLE_CATALOGUE`): *Vertrieb* → Preis, Abschluss, Beratung; *Kundenservice* → Betrieb, Beratung; *Technischer Support* → Betrieb; *Beratung / Key Account* → Beratung, Preis. Diese Zuordnung läuft über die Kategorie, nicht über die Rollenzeile dieses Katalogs.

### 6.3 Nach Vertriebsnähe

| Vertriebsnähe | Katalog | ohne Katalogeintrag | Für Profil A einschlägig |
|---|---|---|---|
| neutral | S-01, S-02, S-05, S-07, S-13 | `cold-call-followup`, `escalation-repeated-outage` | ja |
| beratungsnah | S-03, S-04, S-06, S-08, S-11, S-12, S-14 | — | ja |
| verhandlungsnah | S-09, S-10 | `price-cancellation-risk`, `upsell-seat-expansion`, `closing-after-handover` | nein |

Im Katalog stehen zwölf von vierzehn Szenarien Profil A offen. In der Bibliothek sind es **12 von 17** (neutral 7, beratungsnah 5), verhandlungsnah 5. Damit ist belegt, was Abschnitt 2.1 behauptet: Die Bibliothek trägt beide Bedürfnisse nebeneinander, ohne sich auf eines festzulegen. **R-46** ist erfüllt, weil niemand ein verhandlungsnahes Szenario wählen muss — nicht, weil es unterdrückt würde.

### 6.4 Belegstärke

| Belegstärke | Personas | Szenarien |
|---|---|---|
| Direkt belegt | **P-01**, **P-02**, **P-08** | **S-01**, **S-03**, **S-04**, **S-05**, **S-07**, **S-08**, **S-09**, **S-10**, **S-11**, S-14 |
| Abgeleitet | **P-03**, P-04, P-05, **P-06**, P-10, P-13 | **S-02**, S-06 |
| Systementwurf | **P-09**, P-11, P-12, P-14 | **S-12**, **S-13** |
| Interpretation offen | P-07 | — |

**Fett** = als Datensatz angelegt. Das Verhältnis ist bei den **Szenarien gut und bei den Personas schlecht**. Angelegt sind alle direkt belegten Personas, aber nur zwei der sechs abgeleiteten. Genau dort setzen die Rückfragen an.

### 6.5 Voraussetzungen, die noch fehlen

| Eintrag | Blockiert durch |
|---|---|
| S-06 | sitzungsübergreifendes Gedächtnis (F-23, COULD, nicht gebaut). Das Folgeszenario deckt die „informierte" Variante ab, siehe 5.1 |
| S-14 | nichts — bewusst kein Datensatz. Englisch ist über zwei Personas spielbar; einzige technische Hürde: der DiReKT-Fallback hält keine englischen Stimmen vor |
| P-07 | Auslegung von R-04 (siehe 7) |
| P-13 | Rückfrage zum tatsächlichen Eskalationsgrad (siehe 7) |
| jede neue Persona | eine ausgewählte KugelAudio-Stimme und ein Porträt; ohne Stimme bleibt sie inaktiv, `tests/test_persona_scenario_library.py` prüft beides |

---

## 7 Offene Punkte

**1 — R-04 ist zweideutig.**
> *„Die Entscheidungsbefugnis der Nutzer ist in manchen Fällen nicht ausreichend […]. Das soll sich im Gesprächsverhalten widerspiegeln."*

Lesart 1: Der **Nutzer** hat keine Befugnis — nicht umsetzbar, das System kann dem Nutzer nichts verbieten. Lesart 2: Der **Gegenpart** verlangt eine Entscheidung, die der Nutzer nicht treffen darf — trainierbar über P-07 und über ein Erledigt-Kriterium, das Rücksprache mit Termin ausdrücklich zulässt. Die Bibliothek nutzt Lesart 2 inzwischen stillschweigend: S-11 ist in `seed_data.py` so begründet, und mehrere Szenarien lassen „Rücksprache mit Termin" als Ergebnis zu (`price-cancellation-risk`, `closing-after-handover`). P-07 selbst ist nicht angelegt. **Rückzufragen**, bevor weitere Einträge darauf gebaut werden.

**2 — Der Persona-Katalog braucht Material.** Zwei namentlich belegte Kundentypen tragen keine Bibliothek, die F-04 „erweiterbar" nennt. Belegt ist außerdem genau **ein** wörtlicher Einwand für die gesamte `persona_objection`-Tabelle. Konkret fehlen:

- vier bis fünf typische Gegenübertypen je Profil, mit je zwei Sätzen zum Auftreten
- die wiederkehrenden Bremssätze im Wortlaut (Rohmaterial für R-12)
- der tatsächliche Eskalationsgrad in Profil A — entscheidet über P-05 gegen P-13
- ein konkretes Beispiel für ein Missverständnis trotz vermeintlich klarer Formulierung (trägt P-04, S-03, S-07)

Die Lücke ist in der Bibliothek spürbar: Für S-05, S-08, S-10, S-12 und S-13 ist die erstempfohlene Persona (P-13, P-11, P-10, P-12, P-14) nicht angelegt; diese Fälle laufen heute mit einer der sechs vorhandenen.

**3 — Für Profil B fehlen echte Gesprächsverläufe.** S-08 bis S-13 sind aus dem Tätigkeitsprofil erschlossen, nicht aus einer Erhebung. Sie sind inzwischen als Datensätze angelegt, **ohne** gegengeprüft zu sein. Am ergiebigsten wäre der bereits angebotene Gesprächsleitfaden samt einem anonymisierten realen Gesprächsverlauf — wobei **R-43** gilt: Der Leitfaden darf das Szenario *strukturieren*, aber nicht als Bewertungsmaßstab hinterlegt werden.

**4 — Fallfakten sind erfunden.** Sämtliche Zahlen, Fristen und Mengen in Abschnitt 5 und in der Bibliothek sind plausibel gesetzt, nicht erhoben. Sie erfüllen ihren Zweck (ADR 0045: ein Fall, der über die Sitzung stabil bleibt und gegen den sich Feedback messen lässt), sind aber jederzeit gegen erhobene Werte auszutauschen — dann im englischen Prompttext **und** im deutschen Anzeigetext.

**5 — Die Zuordnung Persona × Szenario ist eine Empfehlung, keine Einschränkung.** ADR 0015 verlangt, dass **jede** Persona mit **jedem** Szenario läuft. „Empfohlene Personas" bedeutet: Dieser Fall wird mit dieser Manier am schärfsten. Es bedeutet nicht, dass die übrigen Kombinationen gesperrt wären — und der Katalog darf auch nicht so gelesen werden, dass daraus eine Kompatibilitätsmatrix im Datenmodell würde. Das Produkt hält sich daran: Die Empfehlungen dieses Katalogs erreichen die Oberfläche nicht.

---

## 8 Stand und nächste Schritte

**Umgesetzt** sind alle Einträge, die ohne Rückfrage baubar waren, und darüber hinaus die Vorschläge aus Profil B:

- Personas P-01, P-02, P-03, P-06, P-08, P-09
- Szenarien S-01 bis S-05 und S-07 bis S-13

**Als Nächstes**, nach den Rückfragen aus Abschnitt 7:

1. **P-04** — belegt (R-17) und für drei Szenarien erstempfohlen oder mitempfohlen (S-03, S-07, S-08); braucht das Missverständnis-Beispiel aus Punkt 7.2.
2. **P-05 oder P-13** — je nach Eskalationsgrad; schließt die Empfehlung für S-01 und S-05.
3. **P-10** — die erstempfohlene Persona des einzigen rein verhandlungsnahen Katalogfalls S-10.
4. **P-07** — erst nach Klärung von R-04.
5. P-11, P-12, P-14 — Systementwürfe; nur bauen, wenn die zugehörigen Fälle (S-08, S-12, S-13) im Pilot tatsächlich gespielt werden.

Jede neue Persona braucht eine KugelAudio-Stimme, ein Porträt, deutsche Zwillinge für Rolle, Haltung und Einwände und ein `training_goal` (Abschnitt 3).

**Nicht** anzulegen: S-14 (kein eigener Datensatz, siehe 5.2) und S-06 (blockiert, siehe 5.1).

Diese Seite ist in die Doku-Site eingebunden (`mkdocs.yml`, Eintrag *Szenario- und Persona-Katalog*).
