# Anforderungsliste

**Stand:** Entwurf

**Geltungsbereich:** Anforderungen aus den bisher durchgeführten Erstgesprächen mit Solox und APPOLLO Systems

| Erhebung                     | Kürzel | Datum      | Ansprechpartner |
| :--------------------------- | :----- | :--------- | :-------------- |
| Erstgespräch Solox GmbH      | `SO`   | 24.06.2026 | Nicolas Heyne   |
| Erstgespräch APPOLLO Systems | `AP`   | 22.07.2026 | Eckhard Herdt   |

## Zweck

Diese Liste bildet die oberste Ebene der Anforderungsdokumentation. Sie hält fest, *welcher Bedarf* erhoben wurde, noch bevor entschieden ist, ob daraus ein Feature, ein Qualitätsziel oder eine Randbedingung wird.

Die Formulierung erfolgt in Bedarfssprache.

Sie ist zugleich die Quelle, aus der die nachgelagerte Dokumentation hervorgeht: Features, Qualitätsziele, Randbedingungen und Nicht-Ziele werden aus dieser Liste abgeleitet und nicht unabhängig davon aufgestellt. Jeder dieser Einträge soll sich auf eine Anforderung mit R-Nummer zurückführen lassen. Umgekehrt soll jede Anforderung entweder abgeleitet oder als offener Punkt ausgewiesen sein. Was sich nicht zurückführen lässt, ist in *Nicht aus den Erhebungen belegt* zu führen und als solches kenntlich zu machen.

| Typ           | Kürzel | Ziel                                   |
| :------------ | :----- | :------------------------------------- |
| Funktion      | F      | Feature-Katalog und Anforderungsbaum   |
| Qualitätsziel | Q      | arc42, Kapitel 10 (Qualitätsszenarien) |
| Randbedingung | C      | arc42, Kapitel 2                       |
| Nicht-Ziel    | N      | arc42, Kapitel 1 (Abgrenzung)          |

## Referenzschema

Verwiesen wird nach dem Muster `SO <Kapitel>.<Frage>` beziehungsweise `AP <Kapitel>.<Frage>`. Die Fragennummer ergibt sich aus der bestehenden Reihenfolge im jeweiligen Protokoll. So bezeichnet `SO 4.5` die fünfte Frage in Kapitel 4. Eine Anpassung der Protokolle ist dafür nicht erforderlich.

Anforderungen mit zwei Quellenangaben sind unabhängig durch beide Erhebungen belegt.

Die Spalte *Bezug* verweist auf die bereits vergebenen Feature-IDs, damit die bestehende Dokumentation anschlussfähig bleibt.

## Anforderungen

### Zielgruppe und Nutzungskontext

| ID   | Anforderung                                                                                                                                                                     | Quelle         | Typ | Bezug    |
| :--- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | :------------- | :-- | :------- |
| R-01 | Zur Zielgruppe gehören Personen mit direktem Kundenkontakt in Support- sowie in beratenden Projekt- und Entwicklungsrollen.                                                     | SO 4.1         | C   | *keiner* |
| R-02 | Zur Zielgruppe gehören auch Personen mit technischem Hintergrund ohne vertriebliche Vorerfahrung.                                                                               | AP 3.1         | C   | *keiner* |
| R-03 | Die Gesprächsdauern reichen von kurzen Rückfragen bis zu Gesprächen von einer Stunde.                                                                                           | SO 4.6, AP 3.6 | C   | F-03     |
| R-04 | Die Entscheidungsbefugnis der Nutzer ist in manchen Fällen nicht ausreichend, sodass insbesondere im Support und bei technischen Fragen teilweise Rücksprache nötig ist. Das soll sich im Gesprächsverhalten widerspiegeln. | SO 4.2, AP 3.2 | F   | *offen*  |

### Trainingsgegenstand und Gesprächssimulation

| ID   | Anforderung                                                                                                                                                                                                            | Quelle                | Typ | Bezug      |
| :--- | :--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | :-------------------- | :-- | :--------- |
| R-05 | Nutzer wollen ein Gegenüber, mit dem sich realistische externe Kundengespräche üben lassen.                                                                                                                            | SO 4.4, AP 3.4        | F   | F-01       |
| R-06 | Das simulierte Gegenüber soll Gesprächsdynamik und emotionale Reaktionen abbilden, nicht nur fachliche Inhalte.                                                                                                        | SO 4.5                | F   | F-01, F-04 |
| R-07 | Kundentypen, die stark auf Kosten achten und Beratung ablehnen, sobald sie zusätzlich Geld kostet, sollen abbildbar sein.                                                                                              | SO 4.3, 4.5           | F   | F-04       |
| R-08 | Gesprächspartner vom Typ Geschäftsführer oder IT-Leiter mit Fokus auf Strategie und Budget sollen abbildbar sein.                                                                                                      | AP 3.5                | F   | F-04       |
| R-09 | Sowohl kurze, problemgetriebene Support-Fälle als auch längere beratende Projektgespräche sollen trainierbar sein.                                                                                                     | SO 4.1, 4.4, 4.6, 6.1 | F   | F-03       |
| R-10 | Angebots- und Verkaufsgespräche, Preisdiskussionen sowie die Anforderungsdefinition sollen trainierbar sein.                                                                                                           | AP 3.4                | F   | F-03       |
| R-11 | Gesprächsverläufe, die sich über mehrere Termine erstrecken, sollen abbildbar sein.                                                                                                                                    | SO 4.4, 4.6           | F   | F-23       |
| R-12 | Nutzer wollen den Umgang mit spontanen Einwänden trainieren.                                                                                                                                                           | AP 2.1, 6             | F   | F-01       |
| R-13 | Follow-up-Gespräche folgen einem festen Phasenschema von Aufwärmen über Agenda, Kundennutzen, Vertrauensaufbau und Referenzen bis zu Preisverhandlung und Einwandbehandlung. Das Training soll sich daran orientieren. | AP 6                  | F   | F-42       |

### Erkennung von Sprech- und Kommunikationsverhalten

| ID   | Anforderung                                                                                                                                        | Quelle         | Typ | Bezug                  |
| :--- | :------------------------------------------------------------------------------------------------------------------------------------------------- | :------------- | :-- | :--------------------- |
| R-14 | Nutzer wollen eigene blinde Flecken im Sprechverhalten erkennen, insbesondere bei Intonation, Sprechtempo, Lautstärke und undeutlicher Aussprache. | SO 1, 2.1, 6.1 | F   | F-35, F-36, F-37, F-38 |
| R-15 | Nutzer wollen erkennen, wenn sie einen Sachverhalt komplizierter erklären als nötig oder zu viele Informationen geben.                             | SO 3.1, 6.3    | F   | F-08                   |
| R-16 | Nutzer mit technischem Hintergrund wollen lernen, adressatengerecht statt stark technisch zu formulieren.                                          | AP 2.1         | F   | F-08, F-40             |
| R-17 | Nutzer wollen Missverständnisse erkennen, die im Gespräch entstehen, obwohl beide Seiten sich vermeintlich klar ausgedrückt haben.                 | SO 3.1, 3.2    | F   | F-08                   |
| R-18 | Nutzer wollen flüssiger und spontaner sprechen können, denn wie flüssig ein Gespräch verläuft, gilt als zentraler Erfolgsmaßstab.                       | AP 2.1, 5.2    | F   | *offen*                |
| R-19 | Nutzer wollen verstehen, wie sie beim Gegenüber ankommen.                                                                                          | SO 4.10, 6.1   | F   | F-09, F-39             |

### Feedback und Auswertung

| ID   | Anforderung                                                                                                                                                   | Quelle         | Typ | Bezug      |
| :--- | :------------------------------------------------------------------------------------------------------------------------------------------------------------ | :------------- | :-- | :--------- |
| R-20 | Nutzer wollen nach einem Gespräch eine zusammenfassende Rückmeldung erhalten.                                                                                 | SO 6.3, AP 5.3 | F   | F-09       |
| R-21 | Die Rückmeldung soll qualitativ und differenziert ausfallen und sich nicht auf einen einzelnen Zahlenwert reduzieren.                                         | SO 6.2, 6.3    | Q   | F-09, F-14 |
| R-22 | Nutzer wollen konkrete, anwendbare Verbesserungsvorschläge, die sich auf bestimmte Stellen im Gespräch beziehen.                                              | SO 6.3         | F   | F-10, F-47 |
| R-23 | Verbesserungsvorschläge sollen strukturiert sein und sich am internen Gesprächsleitfaden orientieren.                                                         | AP 5.3         | F   | F-10       |
| R-24 | Nutzer wollen die Auswertung visuell im Stil eines Dashboards dargestellt bekommen.                                                                           | AP 5.3         | F   | *offen*    |
| R-25 | Die Rückmeldung soll berücksichtigen, dass ein Gespräch von den Beteiligten unterschiedlich wahrgenommen wird.                                                | SO 6.3         | Q   | *offen*    |
| R-26 | Der Erfolg soll qualitativ gemessen werden: an Verständlichkeit, hilfreicher Gesprächsführung, Vertrauen, Kompetenzwirkung und der Flüssigkeit des Gesprächs. | SO 6.2, AP 5.2 | Q   | F-06       |
| R-27 | Regelmäßiges Feedback ist Voraussetzung dafür, dass das Werkzeug angenommen wird.                                                                             | AP 3.10        | Q   | F-13       |

### Reflexion und Lernprozess

| ID   | Anforderung                                                                                                                                      | Quelle         | Typ | Bezug      |
| :--- | :----------------------------------------------------------------------------------------------------------------------------------------------- | :------------- | :-- | :--------- |
| R-28 | Nutzer wollen Gespräche genauer reflektieren können, als es aus der bloßen Erinnerung möglich ist.                                               | SO 4.7         | F   | F-12       |
| R-29 | Das Training soll kontinuierlich über längere Zeiträume nutzbar sein, weil blinde Flecken sich erst mit der Zeit einschleifen.                   | SO 4.7, AP 3.7 | F   | F-13, F-48 |
| R-30 | Nutzer wollen die Entwicklung des eigenen Gesprächsverhaltens über mehrere Gespräche hinweg nachvollziehen.                                      | SO 4.7         | F   | F-13       |
| R-31 | Nutzer wollen das gemeinsame Verständnis nach einem Gespräch absichern, wie es bisher über eine zusammenfassende E-Mail an den Kunden geschieht. | SO 2.3, 3.3    | F   | *offen*    |

### Bedienung und Akzeptanz

| ID   | Anforderung                                                                        | Quelle               | Typ | Bezug            |
| :--- | :--------------------------------------------------------------------------------- | :------------------- | :-- | :--------------- |
| R-32 | Der Nutzen des Trainers soll unmittelbar erkennbar und die Bedienung einfach sein. | SO 4.8, 4.10, AP 3.9 | Q   | F-15             |
| R-33 | Eine unklare oder überladene Oberfläche soll die Nutzung nicht erschweren.         | SO 4.9, AP 3.9       | Q   | F-15             |
| R-34 | Notwendige Einstellungen sollen klar sichtbar sein, Spezialoptionen zurücktreten.  | SO 4.9, 4.10         | Q   | F-16, F-17, F-43 |

### Sprache, Geräte und Umfeld

| ID   | Anforderung                                                                                                                                                                                                   | Quelle              | Typ | Bezug      |
| :--- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | :------------------ | :-- | :--------- |
| R-35 | Das Training soll in der Sprache stattfinden, in der die Kundengespräche des jeweiligen Unternehmens geführt werden. Belegt sind Deutsch bei Solox sowie Englisch und teilweise Spanisch bei APPOLLO Systems. | SO 4.3, AP 3.3      | C   | F-18, F-25 |
| R-36 | Das Training soll am PC mit Headset durchführbar sein, analog zum Ablauf eines realen Telefonats.                                                                                                             | SO 5.1, 5.2         | C   | F-19       |
| R-37 | Das Training soll auch am Smartphone nutzbar sein, da mobile Telefonie in beiden Unternehmen im Einsatz ist.                                                                                                     | SO 5.2, AP 4.2      | C   | F-20       |
| R-38 | Eine Anbindung an die eingesetzte Telefonsoftware Starface ist denkbar.                                                                                                                                       | SO 5.1              | F   | F-29       |
| R-39 | Neben klassischen Telefonaten werden Konferenzwerkzeuge wie Teams, Zoom und GoToMeeting genutzt.                                                                                                              | SO 4.6, 5.1, AP 4.1 | F   | F-32       |

### Wissensbasis und Fachlichkeit

| ID   | Anforderung                                                                                                                                      | Quelle      | Typ | Bezug      |
| :--- | :----------------------------------------------------------------------------------------------------------------------------------------------- | :---------- | :-- | :--------- |
| R-40 | Das Training soll ohne kundenspezifisches Produkt- und Fachwissen durchführbar sein, da sich die Fachlichkeit je Kundenlandschaft unterscheidet. | SO 5.3, 5.4 | C   | F-06       |
| R-41 | Für einen ersten Prototyp soll keine vollständige Wissensbasis vorausgesetzt werden.                                                             | SO 5.4      | C   | F-26       |
| R-42 | Nutzer sollen bei Bedarf eigene Dokumente bereitstellen können, um den fachlichen Rahmen zu prägen.                                              | SO 5.3      | F   | F-26, F-45 |
| R-43 | Bestehende Gesprächsleitfäden, die als Präsentationsdokumente vorliegen, sollen als Bewertungsgrundlage einbringbar sein.                        | AP 4.3, 4.4 | F   | F-26, F-45 |

### Erweiterung über die Simulation hinaus

| ID   | Anforderung                                                                                                                                                                                                                         | Quelle | Typ | Bezug   |
| :--- | :---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | :----- | :-- | :------ |
| R-44 | Nutzer wollen echte Kundentelefonate mitlaufen lassen und auswerten, nicht nur simulierte Gespräche. Vom Gesprächspartner wird dafür Offenheit erwartet, auch weil Skripte und Protokolle für den Kunden einen Mehrwert darstellen. | AP 6   | F   | *offen* |

### Abgrenzungen

| ID   | Anforderung                                                                                                                                                   | Quelle         | Typ | Bezug      |
| :--- | :------------------------------------------------------------------------------------------------------------------------------------------------------------ | :------------- | :-- | :--------- |
| R-45 | Klassische vertriebliche Kennzahlen wie Abschlussquote oder Umsatz sollen nicht als Erfolgsmaßstab dienen.                                                    | SO 6.2, AP 5.2 | N   | F-28       |
| R-46 | Ein stark vertriebslastiger Fokus passt nicht zu den Rollen bei Solox. Die Abgrenzung gilt unternehmensspezifisch und nicht produktweit, siehe Konflikt K-01. | SO 4.9         | N   | F-06, F-28 |
| R-47 | Fernwartung und Bildschirmfreigabe sind Teil realer Support-Gespräche, aber nicht Gegenstand des Trainings.                                                   | SO 4.4, 5.1    | N   | *offen*    |

### Zusammenarbeit

| ID   | Anforderung                                                                                                                            | Quelle       | Typ | Bezug    |
| :--- | :------------------------------------------------------------------------------------------------------------------------------------- | :----------- | :-- | :------- |
| R-48 | Rückfragen an die fachlichen Ansprechpartner sollen gebündelt gestellt werden. Der bevorzugte Kanal unterscheidet sich je Unternehmen. | SO 7.1, AP 6 | C   | *keiner* |

## Verteilung

| Typ               | Anzahl |
| :---------------- | :----- |
| Funktion (F)      | 26     |
| Qualitätsziel (Q) | 8      |
| Randbedingung (C) | 11     |
| Nicht-Ziel (N)    | 3      |
| **Gesamt**        | **48** |

Zehn Anforderungen sind durch beide Erhebungen unabhängig belegt.

## Konflikte zwischen den Erhebungen

Die folgenden Punkte sind keine Anforderungen, sondern offene Entscheidungen. Sie entstehen dort, wo die beiden Pilotunternehmen Unterschiedliches erwarten.

### K-01: Vertrieblicher Fokus

Solox lehnt einen vertriebslastigen Zuschnitt ausdrücklich ab (R-46), APPOLLO Systems will genau Preisverhandlung und Einwandbehandlung trainieren (R-10, R-12). Beide sind Pilotnutzer.

Zu entscheiden ist, ob das Produkt beide Ausrichtungen über Szenarien und Personas bedient oder ob eine Zielgruppe Vorrang erhält. Die Entscheidung wirkt auf F-03, F-06 und F-28 und gehört in einen ADR.

### K-02: Form der Rückmeldung

Solox lehnt eine Verdichtung auf Zahlen ab (R-21), APPOLLO wünscht eine Dashboard-Darstellung (R-24).

Auflösbar, wenn die visuelle Darstellung qualitative Aussagen strukturiert zeigt, statt sie zu Kennzahlen zu verdichten. Das sollte bewusst entschieden und formuliert werden.

### K-03: Wissensbasis

R-40 und R-41 grenzen kundenspezifisches Fachwissen aus, R-43 fordert das Einbringen von Gesprächsleitfäden.

Kein echter Widerspruch: Ein Gesprächsleitfaden ist kein Fachwissen, sondern eine Bewertungsgrundlage für die Gesprächsführung. Der Unterschied sollte in der Abgrenzung ausdrücklich festgehalten werden.

### K-04: Sprache

Die ursprüngliche Festlegung auf Deutsch ist durch die zweite Erhebung nicht mehr haltbar und wurde zu R-35 verallgemeinert. Der frühere negative Beleg, wonach Englisch nicht benötigt werde, ist aufgehoben, da er nur für Solox galt.

Deckt sich mit ADR 0023. Die Änderung muss in den Feature-Katalog zurückfließen, wo F-18 derzeit Deutsch als MUST und F-25 Englisch als COULD führt.

## Nicht aus den Erhebungen belegt

Die folgenden Themen sind in der bestehenden Dokumentation als Anforderungen geführt, wurden aber in keiner der beiden Erhebungen angesprochen.

| Thema                                       | bestehender Bezug | vermutliche Herkunft                                        |
| :------------------------------------------ | :---------------- | :---------------------------------------------------------- |
| Geringe Latenz der Antwortkette             | F-21              | Systementwurf, Voraussetzung für R-05                       |
| Datenschutzkonformität nach DSGVO           | F-22              | rechtliche Randbedingung                                    |
| Nutzerkonten und Zugriffsschutz             | F-31, F-49, F-50  | Systementwurf, folgt aus dem Datenschutz                    |
| Analyse der Redeanteile                     | F-24              | bisher unbelegt                                             |
| Erkennung aktiven Zuhörens                  | F-41              | bisher unbelegt                                             |
| Analyse visueller nonverbaler Kommunikation | F-33              | bisher unbelegt                                             |
| Sprachliche Konkretheit                     | F-40              | Literatur (Packard & Berger 2021), Bedarf aus R-15 und R-16 |

## Offene Punkte

- **Sechs Anforderungen haben keinen Bezug im Feature-Katalog:** R-04, R-18, R-24, R-25, R-31 und R-44. Zu entscheiden ist, ob daraus Features abgeleitet oder die Abgrenzungen dokumentiert werden.
- **R-18 und R-24** betreffen beide APPOLLO Systems und sind fachlich substanziell: Sprechflüssigkeit ist bislang keine Analysedimension, eine visuelle Auswertungsdarstellung kein Feature.
- **R-31** berührt den Kern des Wrap-ups. Die zusammenfassende E-Mail dient heute genau dem Zweck, das gemeinsame Verständnis abzusichern.
- **R-44 erweitert den Systemzweck.** Die Auswertung echter Telefonate ist etwas anderes als eine Simulation und wirft eigene Fragen zu Datenschutz und Einwilligung Dritter auf. Herdt hat sie selbst als nachrangig eingeordnet.
- **R-37** wurde gegenüber der ersten Fassung aufgewertet. Bei Solox war mobile Nutzung nur denkbar, bei APPOLLO ist das Smartphone ein genanntes Zielgerät.
- Diese Liste bildet die bisher durchgeführten Erhebungen ab. Weitere Gespräche sind hier fortzuschreiben.
