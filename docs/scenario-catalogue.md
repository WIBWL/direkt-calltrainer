# Szenario- und Persona-Katalog

## 1 Zweck und Geltungsbereich

Dieser Katalog beschreibt Trainingsfälle auf fachlicher Ebene, bevor sie als Datensätze angelegt werden. Er ist die Zwischenstufe zwischen der Anforderungsliste (`initial_requirements.md`) und dem Inhalt der Bibliothek.

Für jeden Eintrag ist ausgewiesen, **worauf er zurückgeht**: eine Anforderung (`R-xx`), eine Randbedingung (`C-xx`) oder — wenn kein Beleg vorliegt — `Systementwurf`. Das ist dieselbe Konvention wie in der Spalte *Herkunft* des Feature-Katalogs, und sie ist der Grund, warum dieser Katalog überhaupt geführt wird: Ein Trainingsfall ohne Belegkette ist eine Erfindung, und das soll man ihm ansehen.

### 1.1 Anonymisierungsregel

Der Katalog nennt **keine Unternehmen, Personen, Orte, Produkte, Partner oder Marken**. Die Pilotunternehmen erscheinen ausschließlich als **Tätigkeitsprofile** (Abschnitt 2). Drei Gründe:

- **C-05 (R-40, R-41):** Das Training soll ohne kundenspezifisches Produkt- und Fachwissen durchführbar sein. Ein Szenario, das ein konkretes Produkt voraussetzt, verletzt genau diese Randbedingung.
- **ADR 0045:** `case_facts` sind über den *Fall* zu schreiben, nie über den Anrufer und nie über ein benanntes System — sonst ist ein Szenario nicht mehr mit jeder Persona kombinierbar (ADR 0015).

Was **bleibt**, ist die *Tätigkeit*: welcher Art die Arbeit ist, in welchem Verhältnis man zum Gegenüber steht, wie lange Gespräche laufen, worüber gestritten wird. Das trägt die Realitätsnähe, ohne die Unternehmen zu identifizieren.

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

**Aufgelöst wird das über die Bibliothek selbst, nicht über eine Produktausrichtung.** F-03 führt ohnehin drei Szenario-Typen nebeneinander; das Angebots- und Preisgespräch ist einer davon, nicht der Zuschnitt des Werkzeugs. Wer verhandlungsnah trainieren will, wählt ein solches Szenario; wer nicht, wählt eines der übrigen. Es gibt keine Ausrichtung, gegen die sich ein Profil wehren müsste — und damit auch nichts zu entscheiden.

Daraus folgt die eigentliche Anforderung an diesen Katalog: **Beide Seiten müssen tatsächlich besetzt sein.** Eine Bibliothek, die nur Preisgespräche kennt, wäre für Profil A unbrauchbar, auch ohne dass das Produkt sich je auf Vertrieb festgelegt hätte. Der Katalog führt deshalb je Szenario das Attribut **Vertriebsnähe** (`neutral` / `beratungsnah` / `verhandlungsnah`) — als Orientierung beim Auffüllen der Bibliothek und als prüfbare Kennzahl der Ausgewogenheit (Abschnitt 6.3). Es ist ein Attribut dieses Dokuments, kein Datenfeld und kein Filter im Produkt.

---

## 3 Aufbau eines Eintrags

ADR 0001 und ADR 0045 trennen strikt: die **Persona** trägt die *Art und Weise*, das **Szenario** trägt die *Sache*. Jede Persona muss mit jedem Szenario laufen können (ADR 0015). Der Katalog folgt dieser Trennung — ein Szenario enthält deshalb **keine** Persona-Beschreibung, sondern höchstens eine Empfehlung, welche Persona den Fall besonders scharf stellt.

### Ein Szenario beschreibt

| Feld | Entspricht Datenfeld | Inhalt |
|---|---|---|
| Situation | `description` | die Ausgangslage — nur die Lage, kein Nutzerziel |
| Rolle Trainingsperson | Teil von `description` | in welcher Funktion der Nutzer angerufen wird. Die Rollen folgen **C-07** (R-01, R-02): Support, beratende Projektrollen, technische Rollen ohne vertriebliche Vorerfahrung |
| Fall | `case_facts` | Zahlen, Fristen, Vorgeschichte. Über den *Fall*, nie über den Anrufer |
| Anrufziel | `call_goal` | was der **Anrufer** erreichen will, ein Satz |
| Erledigt wenn | `success_condition` | die beobachtbare Bedingung, ab der der Anrufer die Sache als geklärt ansieht |
| Typ | *(Katalogattribut, kein Datenfeld)* | einer der drei Typen aus **F-03** (kurzer Support-Fall / beratendes Projektgespräch / Angebots- und Preisgespräch) — Kennzahl der Ausgewogenheit, siehe 6.1 |
| Dauer | — | kurz / mittel / lang. **Eigene Achse**, nicht mit dem Typ zu verwechseln. Spanne aus **C-06** (R-03) |
| Vertriebsnähe | *(Katalogattribut, kein Datenfeld)* | neutral / beratungsnah / verhandlungsnah — dient der Ausgewogenheit der Bibliothek, siehe 2.1 |
| Trainingsfokus | — | die Analyse-Features, die in diesem Fall greifen |
| Herkunft | — | `R-xx` / `C-xx` / `Systementwurf`, plus Tätigkeitsprofil |

> **Zur Rolle der Trainingsperson.** Sie ist kein eigenes Datenfeld: ADR 0045 hält fest, dass das *Ziel des Nutzers* nicht in den Persona-Prompt gehört. Was der Nutzer beruflich **ist**, steht dagegen sehr wohl in `description` — die bestehenden Seed-Daten schreiben genau das („the user, who works in support"). Der Katalog führt es als eigene Zeile, weil C-07 die Zielgruppe verbindlich benennt und die Abdeckung darüber geprüft wird.

### Eine Persona beschreibt

| Feld | Entspricht Datenfeld | Inhalt |
|---|---|---|
| Rolle | `role` / `role_label` | Funktion des Gegenübers |
| Haltung | `traits` | Charakterzüge |
| Manier | `behavior` | wie hartnäckig, wie lange vage Antworten toleriert werden, was sie zufriedenstellt — **nur Manier, nichts Situatives** |
| Einwände | `objections` | 3–4 Stück, als *Bewegung* formuliert, nicht als Zitat, szenarioneutral (**R-12**) |
| Schwierigkeitsgrad | `difficulty` | leicht / mittel / schwer. Das arc42-Glossar zählt ihn ausdrücklich zur Persona; ADR 0045 lässt ihn bestehen, obwohl er heute nirgends gelesen wird, und nennt die Auswahlkarte (ADR 0015) als naheliegenden Ort |
| Sprache | `language_code` | seit ADR 0043 eine Eigenschaft der **Persona**, nicht der Session und nicht des Szenarios (**C-01**) |
| Herkunft | — | `R-xx` / `Systementwurf` |

---

## 4 Persona-Katalog

Sortiert nach Belegstärke. **Direkt belegt** = im Erstgespräch benannt. **Abgeleitet** = folgt aus einer Anforderung, die auf ein anderes Feature zielt. **Systementwurf** = kein Beleg, bewusste Erfindung.

Anders als der Szenariokatalog ist der Persona-Katalog **dünn belegt**: In beiden Erhebungen zusammen sind genau zwei Kundentypen namentlich beschrieben (R-07, R-08). Alles Weitere trägt eine schwächere Kette. Das ist kein Grund, es nicht zu bauen — aber ein Grund, es auszuweisen.

| ID | Persona | Haltung und Manier | Herkunft | Belegstärke |
|---|---|---|---|---|
| **P-01** | Kostenkritischer Bestandskunde | Nimmt jede Leistung an, solange sie nichts extra kostet. Sobald ein Preis fällt, bricht er ab — nicht laut, sondern endgültig. Verhandelt nicht, er lehnt ab. | **R-07** (SO 4.3, 4.5) | **Direkt belegt.** Der einzige wörtlich beschriebene Kundentyp der gesamten Erhebung. Bisher nicht in der Bibliothek. |
| **P-02** | Technisch Verantwortlicher | Will die Langfassung, bohrt nach, prüft Sicherheit und Betrieb, stellt geschlossene Kontrollfragen. Entscheidet nicht allein und sagt das auch. | **R-08** (AP 3.5), Detail AP 3.2 | **Direkt belegt.** R-08 nennt Geschäftsführung *und* technische Leitung; nur die erste Hälfte ist umgesetzt. |
| **P-03** | Fachfremder Ansprechpartner | Ohne technisches Vorwissen. Steigt bei Fachbegriffen sichtbar aus und sagt es. Braucht Bilder statt Begriffe, gibt sich mit einer Definition nicht zufrieden. | **R-16** (AP 2.1) | **Belegt, indirekt.** R-16 ist der Nutzerbedarf; die Persona ist der Hebel, der ihn trainierbar macht. Trägt F-40. |
| **P-04** | Scheinbar klar, tatsächlich mehrdeutig | Formuliert knapp und selbstsicher, bestätigt Rückfragen zu schnell, meint aber etwas anderes. Das Missverständnis fällt erst spät auf — und dann sichtbar. | **R-17** (SO 3.1, 3.2) | **Belegt, indirekt.** R-17 ist der meistgenannte inhaltliche Schmerzpunkt aus Profil A. Anspruchsvollste Persona des Katalogs. |
| **P-05** | Anrufer unter Zeitdruck | Akutes Problem, wenig Geduld für Vorreden, beschreibt das Problem unpräzise, drängt auf eine Aussage. Sachlich, aber gereizt. | **R-06** (SO 4.5) + **R-09** | **Abgeleitet.** R-06 fordert emotionale Reaktionen, nennt aber keinen Typ; der Support-Kontext kommt aus R-09. |
| **P-06** | Wortkarger Gesprächspartner | Antwortet einsilbig, liefert von sich aus nichts. Wer nicht fragt, bekommt nichts — und das Gespräch versandet. | **R-50** (SO-S 1) | **Abgeleitet.** R-50 begründet die Kennzahl *Fragenanteil* mit „die fragende Seite führt". Diese Persona macht das erlebbar statt nur messbar. |
| **P-07** | Drängt auf sofortige Zusage | Verlangt eine verbindliche Entscheidung im Gespräch. „Ich frage intern nach" wird nicht akzeptiert — außer mit Termin und Namen. | **R-04** (SO 4.2, AP 3.2) — *offen* | **Interpretation.** Würde eine bisher heimatlose Anforderung schließen, aber nur unter einer Lesart, die rückzufragen ist (Abschnitt 7). |
| **P-08** | Geschäftsführung, Strategie und Budget | Ungeduldig mit technischen oder ausweichenden Antworten, erfahren im Verhandeln, will Zahl, Datum oder Namen. Eine konkrete Antwort beendet das Thema sofort. | **R-08** (AP 3.5) | **Direkt belegt. Vorhanden.** |
| **P-09** | Höflich und hartnäckig | Unterbricht nie, wird nie laut, ist aber genauso schwer zufriedenzustellen: dieselbe Frage ein drittes und viertes Mal, freundlich. | *Systementwurf* | **Kein Beleg.** Entstand als Nachweis des Sprachpfads (ADR 0043). Als Kontrast zu P-08 didaktisch wertvoll — gleiche Hartnäckigkeit, andere Tonlage — und deshalb zu behalten, aber ohne nachträglich erfundene R-Nummer. **Vorhanden.** |
| **P-10** | Routinierter Einkäufer | Arbeitet mit Pausen, Vergleichen und Zeitdruck. Lässt Stille stehen, um sie füllen zu lassen. Nennt ein Vergleichsangebot, ohne es zu belegen. | **R-10** (AP 3.4) | **Abgeleitet.** R-10 belegt die Preisdiskussion als Gesprächsart, nicht diesen Typ. Nur für Profil B relevant. |
| **P-11** | Umständlicher Prozesskenner | Kennt den eigenen Ablauf im Schlaf und erklärt ihn in voller Länge, mit internen Kürzeln und Sonderfällen. Nimmt Nachfragen nicht übel, wiederholt aber gern. | *Systementwurf* (spiegelt **R-15**, **R-16**) | **Kein direkter Beleg.** Das Gegenstück zu P-03: hier muss der Nutzer *zuhören und ordnen*, statt zu vereinfachen. |
| **P-12** | Formeller Ansprechpartner | Protokollarisch, notiert Zusagen mit und liest sie zurück. Fragt nach Zuständigkeit, Nachweis und Verbindlichkeit statt nach Funktion. | *Systementwurf* | **Kein Beleg.** Plausibel für reguliertes Umfeld in Profil B, aber vollständig erfunden. |
| **P-13** | Eskalierend nach Ausfall | Laut, unterbricht, wiederholt die Dringlichkeit, fordert einen Zeitpunkt. Beruhigt sich erst, wenn ein konkreter Termin genannt wird. | **R-06** (SO 4.5), stark erweitert | **Abgeleitet, grenzwertig.** R-06 belegt „emotionale Reaktionen"; *Eskalation* ist unsere Auslegung. Beide Erhebungen sprechen von Missverständnissen, nicht von Konflikt. Vor dem Bau rückzufragen. |
| **P-14** | Enttäuscht, dann fordernd | Zunächst auffällig still, gibt wenig zurück; kippt dann in eine Forderung nach Ausgleich oder Zusage. | *Systementwurf* | **Kein Beleg.** Eine eigenständige Manier, weil sie den Umgang mit *Schweigen* trainiert — sonst deckt kein Eintrag das ab. |

### 4.1 Regel für die Einwände (R-12, ADR 0045)

`persona_objection` ist seit ADR 0045 das Zuhause von R-12. Beim Schreiben gilt:

- **Englisch** — die Tabelle hat keine Sprachspalte.
- **Als Bewegung, nicht als Zitat**: *„refuses outright as soon as an additional cost is named"*, nicht der wörtliche Satz. Das Modell übernimmt Zitate wörtlich und kollabiert dann auf eine einzige Formulierung.
- **Szenarioneutral** — sonst bricht ADR 0015.
- Drei bis vier je Persona.

Der eine wörtlich belegte Einwand aus der Erhebung (Profil A, kostenkritischer Kunde: sinngemäß *„wenn das etwas kostet, dann nicht"*) geht deshalb nicht als Zitat in die Daten, sondern als Bewegung. Der Wortlaut gehört in die Belegkette, nicht in den Prompt.

---

## 5 Szenario-Katalog

### 5.1 Aus Profil A — Betrieb und Betreuung

#### S-01 Störung im laufenden Betrieb

| | |
|---|---|
| **Situation** | Ein wiederkehrender, beleggetriebener Ablauf bleibt stehen; Vorgänge werden nicht mehr zugeordnet. Ein Stichtag steht bevor. |
| **Fall** | Der Ablauf läuft seit über einem Jahr unverändert. Seit drei Tagen bleiben Vorgänge liegen, rund 30 pro Tag. Der Behelf ist manuelle Einzelzuordnung. Der Stichtag ist in acht Tagen. |
| **Anrufziel** | Wissen, woran es liegt, und ein Datum bekommen, bis zu dem es wieder läuft. |
| **Erledigt wenn** | ein Grund und ein Termin genannt werden — oder klar gesagt wird, dass es bis zum Stichtag nicht behoben ist und was stattdessen gilt. Eine Zusage zu prüfen reicht nicht. |
| **Rolle Trainingsperson** | Support |
| **Typ / Dauer** | Kurzer Support-Fall / kurz |
| **Vertriebsnähe** | neutral |
| **Trainingsfokus** | F-08, F-24, F-36, F-41 |
| **Empfohlene Personas** | P-05, P-13 |
| **Herkunft** | **R-09** (SO 4.1, 4.4), **R-03** — Profil A |

#### S-02 Fachliche Erklärung an einen fachfremden Ansprechpartner

| | |
|---|---|
| **Situation** | Eine bevorstehende, verpflichtende Umstellung mit gesetzter Frist betrifft einen Ablauf des Kunden. Der Kunde will wissen, was das für ihn heißt und was er tun muss. |
| **Fall** | Die Frist läuft in knapp fünf Monaten ab. Betroffen ist ein Ablauf, den drei Personen bedienen. Es gab bereits ein Rundschreiben, das niemand verstanden hat. Ob Anpassungen nötig sind, ist offen. |
| **Anrufziel** | In eigenen Worten erklärt bekommen, was zu tun ist und was es kostet — ohne Fachbegriffe. |
| **Erledigt wenn** | drei konkrete Schritte benannt sind, die der Anrufer nachvollziehbar wiedergeben kann. Ein Verweis auf eine Dokumentation reicht nicht. |
| **Rolle Trainingsperson** | Beratung oder Entwicklung |
| **Typ / Dauer** | Beratendes Projektgespräch / mittel |
| **Vertriebsnähe** | neutral |
| **Trainingsfokus** | F-08, F-40, F-38, F-10 |
| **Empfohlene Personas** | P-03, P-06 |
| **Herkunft** | **R-16** (AP 2.1), **R-15** (SO 3.1) — profilübergreifend |

> **C-05-Hinweis:** Der Fall trägt bewusst *die Form* einer regulatorischen Frist, nicht deren Inhalt. Er darf kein Fachwissen über eine bestimmte Regelung voraussetzen — sonst ist er nicht mehr ohne Wissensbasis spielbar.

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

#### S-04 Leistung außerhalb des Vertrags

| | |
|---|---|
| **Situation** | Eine gewünschte Anpassung ist vom laufenden Vertrag nicht gedeckt und wäre als Aufwand zu berechnen. |
| **Fall** | Der Vertrag deckt Betrieb und Fehlerbehebung, nicht Erweiterungen. Der Wunsch entspricht etwa einem halben Tag Aufwand. Vergleichbares wurde vor zwei Jahren einmal kulanzhalber ohne Berechnung erledigt. |
| **Anrufziel** | Die Anpassung bekommen — ohne zusätzliche Kosten. |
| **Erledigt wenn** | entweder eine Zusage ohne Berechnung vorliegt, oder nachvollziehbar begründet ist, warum berechnet wird, **und** der Anrufer diese Begründung wiedergeben kann. |
| **Rolle Trainingsperson** | Beratung oder Kundenverantwortung |
| **Typ / Dauer** | Angebots- und Preisgespräch / mittel |
| **Vertriebsnähe** | beratungsnah — **ausdrücklich kein Abschlussgespräch** |
| **Trainingsfokus** | F-35, F-39, F-42 |
| **Empfohlene Personas** | **P-01** (der Fall, für den sie gedacht ist), P-08 |
| **Herkunft** | **R-07** (SO 4.3, 4.5) — Profil A |

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

> **Technisch blockiert.** F-23 setzt voraus, dass sich der Gegenpart an frühere Termine *erinnert*. Ein sitzungsübergreifendes Gedächtnis gibt es nicht, und `scenario` hat kein Feld dafür. Heute ließe sich der Fall nur als Vorgeschichte in den `case_facts` bauen — dann erinnert sich der Gegenpart nicht, er wurde informiert. Das ist ein anderes Feature. Vor dem Bau als ADR oder Issue klären.

#### S-07 Absicherndes Wrap-up am Gesprächsende

| | |
|---|---|
| **Situation** | Am Ende eines Klärungsgesprächs soll das gemeinsame Verständnis mündlich zusammengefasst werden, bevor die schriftliche Zusammenfassung folgt. |
| **Fall** | Vier Punkte wurden besprochen. Bei einem davon liegt ein Missverständnis vor: Der Anrufer hat etwas anderes verstanden, als gemeint war, und wird das beim Zusammenfassen bemerken. |
| **Anrufziel** | Sicher sein, dass beide Seiten dasselbe meinen. |
| **Erledigt wenn** | die Zusammenfassung alle vier Punkte trifft **und** der abweichende Punkt aufgefallen und richtiggestellt ist. |
| **Rolle Trainingsperson** | beliebig |
| **Typ / Dauer** | Kurzer Support-Fall / kurz |
| **Vertriebsnähe** | neutral |
| **Trainingsfokus** | F-08, F-40, F-41, F-54 |
| **Empfohlene Personas** | P-04, P-06 |
| **Herkunft** | **R-31** (SO 2.3, 3.3), **R-17** — Profil A, direkt aus der dokumentierten Praxis der Zusammenfassungsmail |

### 5.2 Aus Profil B — Beratung und Einführung

Alle Szenarien dieses Abschnitts sind **Vorschläge**. Für Profil B fehlt eine dem Erstgespräch von Profil A vergleichbare Detailtiefe zu typischen Gesprächsverläufen (Abschnitt 7).

#### S-08 Prozessaufnahme im Fachbereich

| | |
|---|---|
| **Situation** | Erstes Gespräch mit einem Fachbereich, um einen bestehenden manuellen Ablauf für eine spätere Modellierung zu erfassen. |
| **Fall** | Der Ablauf umfasst grob acht Schritte, drei davon mit Sonderfällen. Er ist nirgends dokumentiert. Zwei Personen führen ihn unterschiedlich aus. Der Anrufer hält beide Varianten für dasselbe. |
| **Anrufziel** | Erklären, wie es heute läuft, und wissen, wie es weitergeht. |
| **Erledigt wenn** | die Schritte zurückgespiegelt wurden **und** die Abweichung zwischen den beiden Varianten benannt ist. |
| **Rolle Trainingsperson** | Beratung / Anforderungsanalyse |
| **Typ / Dauer** | Beratendes Projektgespräch / lang |
| **Vertriebsnähe** | beratungsnah |
| **Trainingsfokus** | F-24, F-41, F-40 |
| **Empfohlene Personas** | **P-11**, P-04 |
| **Herkunft** | **R-10** (AP 3.4, Anforderungsdefinition) — Profil B |

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

#### S-10 Preis- und Konditionsverhandlung

| | |
|---|---|
| **Situation** | Der Einkauf des Kunden fordert einen Nachlass und verweist auf ein Vergleichsangebot. |
| **Fall** | Das vorliegende Angebot liegt bei einem laufenden Jahresbetrag im mittleren fünfstelligen Bereich. Das genannte Vergleichsangebot liegt rund 20 Prozent darunter, deckt aber nach Aktenlage einen kleineren Umfang ab — was der Anrufer nicht von sich aus sagt. Die Entscheidung soll in dieser Woche fallen. |
| **Anrufziel** | Den Preis senken. Der Verweis auf den Wettbewerb ist das Mittel, nicht das Ziel. |
| **Erledigt wenn** | eine Zahl mit Gültigkeitsdatum zugesagt ist, oder klar gesagt wird, dass es keinen Nachlass gibt und warum. „Ich prüfe das intern" ist kein Ergebnis. |
| **Rolle Trainingsperson** | Vertrieb oder Geschäftsführung |
| **Typ / Dauer** | Angebots- und Preisgespräch / mittel |
| **Vertriebsnähe** | **verhandlungsnah** — für Profil A nicht einschlägig (**R-46**), dort wird schlicht ein anderes Szenario gewählt |
| **Trainingsfokus** | F-35, F-36, F-41, F-42 |
| **Empfohlene Personas** | **P-10**, P-08 |
| **Herkunft** | **R-10** (AP 3.4) — Profil B. Deckt die verhandlungsnahe Seite ab, die Profil B ausdrücklich fordert |

#### S-11 Gespräch mit einer skeptischen IT-Seite

| | |
|---|---|
| **Situation** | Der Fachbereich ist überzeugt, die IT-Seite sieht Steuerbarkeit, Sicherheit und Betrieb gefährdet, wenn Fachbereiche selbst konfigurieren. |
| **Fall** | Der Fachbereich hat bereits ohne Abstimmung mit einer Testumgebung begonnen. Es gibt eine interne Richtlinie, die das untersagt. Die IT-Seite ist nicht grundsätzlich dagegen, sondern übergangen worden. |
| **Anrufziel** | Klären, wer künftig was entscheidet und betreibt. |
| **Erledigt wenn** | Zuständigkeit, Freigabeweg und Betriebsverantwortung benannt sind. |
| **Rolle Trainingsperson** | Beratung |
| **Typ / Dauer** | Beratendes Projektgespräch / mittel |
| **Vertriebsnähe** | beratungsnah |
| **Trainingsfokus** | F-42, F-40, F-24 |
| **Empfohlene Personas** | **P-02**, P-12 |
| **Herkunft** | **R-08** (AP 3.5), **R-04** (AP 3.2) — Profil B |

#### S-12 Gespräch im regulierten Umfeld

| | |
|---|---|
| **Situation** | Ein Ansprechpartner aus einem stark regulierten Bereich fragt nach Datenhaltung, Zugriffsrechten und Nachweispflichten. |
| **Fall** | Eine interne Prüfung steht in drei Monaten an. Für zwei der gestellten Fragen gibt es eine belastbare Antwort, für eine dritte nicht. Der Anrufer notiert mit und liest Zusagen zurück. |
| **Anrufziel** | Für jede Frage eine belastbare, zitierfähige Aussage bekommen. |
| **Erledigt wenn** | jede Frage entweder beantwortet oder ausdrücklich als offen markiert ist — mit Zusage, wer bis wann nachliefert. Eine unsichere Antwort, die sicher klingt, gilt als **nicht** erledigt. |
| **Rolle Trainingsperson** | Beratung |
| **Typ / Dauer** | Beratendes Projektgespräch / mittel |
| **Vertriebsnähe** | beratungsnah |
| **Trainingsfokus** | F-42, F-40, F-38, F-39 |
| **Empfohlene Personas** | **P-12**, P-02 |
| **Herkunft** | *Systementwurf* — plausibel für Profil B, nicht belegt |

#### S-13 Termin- und Erwartungskorrektur

| | |
|---|---|
| **Situation** | Ein zugesagter Termin ist nicht haltbar. Der Kunde hat intern bereits darauf geplant. |
| **Fall** | Der Termin war vor sechs Wochen zugesagt und liegt in zehn Tagen. Realistisch sind drei Wochen mehr. Der Kunde hat zwei nachgelagerte Termine daran gehängt, davon einen mit Dritten. |
| **Anrufziel** | Wissen, was jetzt gilt — und ob es einen Weg gibt, wenigstens den Termin mit Dritten zu halten. |
| **Erledigt wenn** | ein neuer Termin genannt ist **und** gesagt wurde, was mit dem nachgelagerten Termin passiert. |
| **Rolle Trainingsperson** | Projektleitung |
| **Typ / Dauer** | Kurzer Support-Fall / kurz |
| **Vertriebsnähe** | neutral |
| **Trainingsfokus** | F-35, F-39, F-41, F-37 |
| **Empfohlene Personas** | **P-14**, P-07 |
| **Herkunft** | *Systementwurf*, gestützt auf **R-06** — profilübergreifend |

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
| **Empfohlene Personas** | eine Persona mit `sprache_code = en` |
| **Herkunft** | **R-35** (SO 4.3, AP 3.3) — Profil B |

> **Kein eigenes Szenario.** Die Sprache hängt seit ADR 0043 an der **Persona**, nicht am Szenario — Szenarien sind sprachneutral. „Englisches Szenario" ist damit keine Kategorie: Man wählt eine englischsprachige Persona zu einem beliebigen Szenario. S-14 bleibt als *Hinweis* im Katalog stehen, wird aber **nicht** als eigener Datensatz angelegt.
>
> **C-01 verbietet Englisch nicht — im Gegenteil.** Die Randbedingung heißt „Sprache konfigurierbar" und führt Englisch ausdrücklich als belegt (R-35). Die frühere Beschränkung auf Deutsch stand in **ADR 0006, und die ist abgelöst** (0006 → 0022 → 0043). Es gibt bereits eine englischsprachige Persona und ein englisches Language Pack. Die verbleibende Einschränkung ist rein technisch: Der DiReKT-Fallback hält nur deutsche Stimmen vor, eine englische Persona hängt damit an der Verfügbarkeit des primären TTS-Backends.
>
> Ein Feature „Training auf Englisch" existiert nicht; die in einer früheren Fassung genannte ID **F-25 gibt es im Feature-Katalog nicht**. Die Sprache wird über C-01 und R-35 geführt, die Umschaltung der *Oberfläche* getrennt davon über F-56.

---

## 6 Abdeckung

### 6.1 Nach Szenario-Typ (F-03)

| Typ | Szenarien | Anzahl |
|---|---|---|
| Kurze Support-Fälle | S-01, S-05, S-07, S-13 | 4 |
| Längere beratende Projektgespräche | S-02, S-03, S-06, S-08, S-11, S-12 | 6 |
| Angebots- und Preisgespräche | S-04, S-09, S-10 | 3 |

Alle drei Typen aus F-03 sind besetzt. In der heutigen Bibliothek sind es zwei von dreien — der beratende Typ fehlt dort vollständig, obwohl er in Profil A der Regelfall ist.

### 6.2 Nach Dauer (C-06, R-03)

| Dauer | Szenarien |
|---|---|
| kurz | S-01, S-05, S-07, S-13 |
| mittel | S-02, S-04, S-09, S-10, S-11, S-12, S-14 |
| lang | S-03, S-06, S-08 |

C-06 spannt „kurze Rückfrage bis eine Stunde" auf; alle drei Längen sind vertreten.

> **6.1 und 6.2 zusammen belegen Q-06.** Das Qualitätsziel *Flexibilität der Trainingssituation* (arc42 Kap. 10, Herkunft R-03/R-09) verlangt wörtlich, dass das System „unterschiedliche Szenario-Typen und Gesprächslängen von kurzen Support-Fällen bis zu einstündigen Gesprächen" unterstützt. Dieser Katalog ist der inhaltliche Nachweis dafür: Ohne besetzte Typen und Längen bleibt Q-06 eine Aussage über den Code, nicht über das Training.

### 6.2a Nach Rolle der Trainingsperson (C-07)

| Rolle | Szenarien |
|---|---|
| Support | S-01, S-05 |
| Beratung / Entwicklung / Anforderungsanalyse | S-02, S-03, S-04, S-08, S-09, S-11, S-12, S-14 |
| Projekt- und Entwicklungsseite, Projektleitung | S-06, S-13 |
| Vertrieb / Geschäftsführung | S-09, S-10 |
| beliebig | S-07 |

C-07 nennt drei Gruppen: Support, beratende Projektrollen und technische Rollen ohne vertriebliche Vorerfahrung. Alle drei sind abgedeckt. Die Support-Seite ist mit zwei Szenarien am dünnsten — passend zum Befund aus 6.1, dass die kurzen Fälle in der heutigen Bibliothek fehlen.

### 6.3 Nach Vertriebsnähe

| Vertriebsnähe | Szenarien | Für Profil A einschlägig |
|---|---|---|
| neutral | S-01, S-02, S-05, S-07, S-13 | ja |
| beratungsnah | S-03, S-04, S-06, S-08, S-11, S-12, S-14 | ja |
| verhandlungsnah | S-09, S-10 | nein |

Zwölf von vierzehn Szenarien stehen Profil A offen, zwei sind verhandlungsnah. Damit ist belegt, was Abschnitt 2.1 behauptet: Die Bibliothek trägt beide Bedürfnisse nebeneinander, ohne sich auf eines festzulegen. **R-46** ist erfüllt, weil niemand ein verhandlungsnahes Szenario wählen muss — nicht, weil es unterdrückt würde.

### 6.4 Belegstärke

| Belegstärke | Personas | Szenarien |
|---|---|---|
| Direkt belegt | P-01, P-02, P-08 | S-01, S-03, S-04, S-05, S-07, S-08, S-09, S-10, S-11, S-14 |
| Abgeleitet | P-03, P-04, P-05, P-06, P-10, P-13 | S-02, S-06 |
| Systementwurf | P-09, P-11, P-12, P-14 | S-12, S-13 |
| Interpretation offen | P-07 | — |

Das Verhältnis ist bei den **Szenarien gut und bei den Personas schlecht**. Genau dort setzen die Rückfragen an.

### 6.5 Voraussetzungen, die noch fehlen

| Eintrag | Blockiert durch |
|---|---|
| S-06 | sitzungsübergreifendes Gedächtnis (F-23, COULD, nicht gebaut) |
| S-14 | **nicht** durch C-01 — dort ist Englisch belegt (R-35). Einzige echte Hürde: der DiReKT-Fallback hält keine englischen Stimmen vor |
| P-07 | Auslegung von R-04 (siehe 7) |

---

## 7 Offene Punkte

**1 — R-04 ist zweideutig und deshalb bis heute ohne Bezug.**
> *„Die Entscheidungsbefugnis der Nutzer ist in manchen Fällen nicht ausreichend […]. Das soll sich im Gesprächsverhalten widerspiegeln."*

Lesart 1: Der **Nutzer** hat keine Befugnis — nicht umsetzbar, das System kann dem Nutzer nichts verbieten. Lesart 2: Der **Gegenpart** verlangt eine Entscheidung, die der Nutzer nicht treffen darf — trainierbar über P-07 und über eine `success_condition`, die Rücksprache mit Termin ausdrücklich zulässt. Lesart 2 würde einen der letzten *offen*-Einträge schließen, ist aber Interpretation. **Rückzufragen.**

**2 — Der Persona-Katalog braucht Material.** Zwei namentlich belegte Kundentypen tragen keine Bibliothek, die F-04 „erweiterbar" nennt. Belegt ist außerdem genau **ein** wörtlicher Einwand für die gesamte `persona_objection`-Tabelle. Konkret fehlen:

- vier bis fünf typische Gegenübertypen je Profil, mit je zwei Sätzen zum Auftreten
- die wiederkehrenden Bremssätze im Wortlaut (Rohmaterial für R-12)
- der tatsächliche Eskalationsgrad in Profil A — entscheidet über P-05 gegen P-13
- ein konkretes Beispiel für ein Missverständnis trotz vermeintlich klarer Formulierung (trägt P-04, S-03, S-07)

**3 — Für Profil B fehlen echte Gesprächsverläufe.** S-08 bis S-13 sind aus dem Tätigkeitsprofil erschlossen, nicht aus einer Erhebung. Sie sollten gegengeprüft werden, bevor daraus Datensätze werden. Am ergiebigsten wäre der bereits angebotene Gesprächsleitfaden samt einem anonymisierten realen Gesprächsverlauf — wobei **R-43** gilt: Der Leitfaden darf das Szenario *strukturieren*, aber nicht als Bewertungsmaßstab hinterlegt werden.

**4 — Fallfakten sind erfunden.** Sämtliche Zahlen, Fristen und Mengen in Abschnitt 5 sind plausibel gesetzt, nicht erhoben. Sie erfüllen ihren Zweck (ADR 0045: ein Fall, der über die Sitzung stabil bleibt und gegen den sich Feedback messen lässt), sind aber jederzeit gegen erhobene Werte auszutauschen.

**5 — Die Zuordnung Persona × Szenario ist eine Empfehlung, keine Einschränkung.** ADR 0015 verlangt, dass **jede** Persona mit **jedem** Szenario läuft. „Empfohlene Personas" bedeutet: Dieser Fall wird mit dieser Manier am schärfsten. Es bedeutet nicht, dass die übrigen Kombinationen gesperrt wären — und der Katalog darf auch nicht so gelesen werden, dass daraus eine Kompatibilitätsmatrix im Datenmodell würde.

---

## 8 Nächste Schritte

Ohne weitere Rückfragen umsetzbar, weil direkt belegt und technisch frei:

1. **P-01 + S-04** als Paar — der einzige wörtlich belegte Kundentyp samt dem Fall, in dem seine Haltung greift.
2. **S-03** — beidseitig belegt und schließt den fehlenden F-03-Typ.
3. **S-01** — deckt die kurze Seite der Dauerspanne aus R-03 ab, die heute fehlt.
4. **P-02** — zweite Hälfte einer nur halb umgesetzten Anforderung (R-08).
5. **S-07** — kleiner Zuschnitt, direkt aus dokumentierter Praxis, trägt zugleich F-54.

Danach, nach den Rückfragen aus Abschnitt 7: P-04, P-05/P-13, P-07, S-08 bis S-11.

**Nicht** anzulegen: S-14 (kein eigener Datensatz, siehe 5.2) und S-06 (blockiert, siehe 5.1).

Diese Seite ist in die Doku-Site eingebunden (`mkdocs.yml`, Eintrag *Szenario- und Persona-Katalog*).
